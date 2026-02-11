"""
Aktendigitalisierung - Intelligente Dokumententrennung und -benennung

Dieses Modul ermöglicht die Digitalisierung kompletter Akten mit:
- Automatischer Dokumententrennung ohne Trennblätter
- Erkennung von Briefköpfen und ersten Seiten
- Intelligente Dateibenennung (Datum-Partei-Inhalt)
- ZIP-Export mit logischer Ordnerstruktur

Verwendet:
- PyMuPDF für PDF-Verarbeitung
- Pillow für Bildanalyse
- OpenAI/Anthropic für KI-gestützte Analyse
"""

import fitz  # PyMuPDF
import io
import os
import re
import json
import zipfile
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from PIL import Image
import numpy as np


@dataclass
class DetectedDocument:
    """Repräsentiert ein erkanntes Dokument innerhalb einer Akte"""
    start_page: int
    end_page: int
    pages: List[int] = field(default_factory=list)
    confidence: float = 0.0

    # Extrahierte Metadaten
    datum: Optional[str] = None
    absender: Optional[str] = None
    empfaenger: Optional[str] = None
    betreff: Optional[str] = None
    dokumenttyp: Optional[str] = None

    # Generierter Dateiname
    filename: Optional[str] = None
    folder: Optional[str] = None

    # Rohtext für Analyse
    raw_text: str = ""

    def __post_init__(self):
        if not self.pages:
            self.pages = list(range(self.start_page, self.end_page + 1))


class FirstPageDetector:
    """
    Erkennt erste Seiten von Dokumenten basierend auf visuellen und textuellen Merkmalen.

    Erkennungsmerkmale für erste Seiten:
    - Briefkopf im oberen Bereich (Logo, Adresse)
    - Anrede ("Sehr geehrte...")
    - Datum im typischen Format
    - "Betreff:" oder "Ihr Zeichen"
    - Aktenzeichen-Muster
    """

    # Typische Muster für erste Seiten (mit Gewichtung)
    FIRST_PAGE_PATTERNS = [
        # Anreden (stark)
        (r'(?i)sehr geehrte[r]?\s+(frau|herr|damen|herren)', 0.25),
        (r'(?i)^.*?dear\s+(mr|mrs|ms|sir|madam)', 0.20),
        (r'(?i)guten\s+tag', 0.15),

        # Betreff/Zeichen-Felder (sehr stark)
        (r'(?i)betreff\s*:', 0.30),
        (r'(?i)ihr\s+zeichen\s*:', 0.25),
        (r'(?i)unser\s+zeichen\s*:', 0.25),
        (r'(?i)geschäftszeichen\s*:', 0.25),
        (r'(?i)aktenzeichen\s*:', 0.25),
        (r'(?i)az\.?\s*:', 0.20),

        # Datum im Header-Bereich (mittel)
        (r'(?i)datum\s*:\s*\d{1,2}[\./]\d{1,2}[\./]\d{2,4}', 0.15),

        # Firmierung/Briefkopf (mittel)
        (r'(?i)^.{0,300}(gmbh|ag\b|e\.?\s*v\.?|rechtsanw|kanzlei|anwalt|notar)', 0.15),
        (r'(?i)^.{0,300}(amtsgericht|landgericht|oberlandesgericht|verwaltungsgericht)', 0.20),
        (r'(?i)^.{0,300}(versicherung|allianz|huk|axa|ergo)', 0.15),

        # Typische Briefelemente
        (r'(?i)per\s+(fax|email|e-mail|einschreiben)', 0.15),
        (r'(?i)in\s+sachen\s*:', 0.25),  # Gerichtsdokumente
        (r'(?i)wegen\s*:', 0.15),

        # Postanschrift (Name + Straße + PLZ)
        (r'(?i)straße|str\.\s*\d|weg\s+\d|platz\s+\d', 0.10),
        (r'\b\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+', 0.10),  # PLZ Stadt

        # Referenznummern
        (r'(?i)kunden.?nr\.?\s*:', 0.10),
        (r'(?i)vertrags.?nr\.?\s*:', 0.10),
        (r'(?i)schaden.?nr\.?\s*:', 0.15),
    ]

    # Muster die GEGEN eine erste Seite sprechen
    CONTINUATION_PATTERNS = [
        (r'(?i)^[\s]*-\s*\d+\s*-', 0.40),  # Seitennummer "-2-"
        (r'(?i)seite\s+(\d+)\s+(von|/)\s+\d+', 0.35),  # "Seite 2 von 3" (nur wenn >1)
        (r'(?i)^\s*-?\s*\d{1,2}\s*-?\s*$', 0.25),  # Nur Seitenzahl
        (r'(?i)^.*?fortsetzung', 0.30),  # "Fortsetzung"
        (r'(?i)^.*?blatt\s+\d+', 0.25),  # "Blatt 2"
        (r'(?i)^\s*\.\.\.\s*$', 0.30),  # Fortsetzungspunkte
    ]

    def __init__(self):
        self.header_templates = []  # Für Template-Matching
        self.previous_page_hash = None  # Für Ähnlichkeitsvergleich

    def analyze_page(self, page_text: str, page_image: Optional[Image.Image] = None,
                     page_num: int = 0) -> Tuple[float, Dict[str, Any]]:
        """
        Analysiert eine Seite und gibt Wahrscheinlichkeit zurück, dass es eine erste Seite ist.

        Returns:
            Tuple[float, Dict]: (Konfidenz 0-1, Details der Erkennung)
        """
        score = 0.0
        details = {
            'first_page_indicators': [],
            'continuation_indicators': [],
            'visual_features': {}
        }

        # Textuelle Analyse - fokussiere auf oberen Bereich (Header)
        text_upper = page_text[:2500] if len(page_text) > 2500 else page_text

        # Prüfe auf First-Page-Muster (mit individueller Gewichtung)
        for pattern, weight in self.FIRST_PAGE_PATTERNS:
            if re.search(pattern, text_upper, re.MULTILINE):
                score += weight
                details['first_page_indicators'].append(pattern)

        # Prüfe auf Continuation-Muster (negative Indikatoren)
        first_500_chars = page_text[:500]
        for pattern, weight in self.CONTINUATION_PATTERNS:
            match = re.search(pattern, first_500_chars, re.MULTILINE)
            if match:
                # Spezialfall: "Seite X von Y" - nur negativ wenn X > 1
                if 'seite' in pattern.lower():
                    try:
                        page_num_match = re.search(r'(\d+)', match.group())
                        if page_num_match and int(page_num_match.group(1)) > 1:
                            score -= weight
                            details['continuation_indicators'].append(pattern)
                    except:
                        score -= weight
                        details['continuation_indicators'].append(pattern)
                else:
                    score -= weight
                    details['continuation_indicators'].append(pattern)

        # Visuelle Analyse (wenn Bild verfügbar)
        if page_image:
            visual_score, visual_details = self._analyze_visual_features(page_image)
            score += visual_score * 0.3
            details['visual_features'] = visual_details

        # Datum-Erkennung im oberen Drittel
        if self._has_date_in_header(text_upper):
            score += 0.1
            details['first_page_indicators'].append('date_in_header')

        # Anrede-Erkennung
        if self._has_salutation(page_text):
            score += 0.15
            details['first_page_indicators'].append('salutation')

        # Normalisiere Score auf 0-1
        confidence = max(0.0, min(1.0, score))

        return confidence, details

    def _analyze_visual_features(self, image: Image.Image) -> Tuple[float, Dict]:
        """Analysiert visuelle Merkmale einer Seite"""
        score = 0.0
        details = {}

        # Konvertiere zu Grayscale für Analyse
        if image.mode != 'L':
            gray = image.convert('L')
        else:
            gray = image

        # Analysiere oberen Bereich (Briefkopf-Region)
        width, height = gray.size
        header_region = gray.crop((0, 0, width, int(height * 0.2)))

        # Prüfe auf dunkle Bereiche im Header (Logo/Briefkopf)
        header_array = np.array(header_region)
        dark_pixels = np.sum(header_array < 128)
        total_pixels = header_array.size
        dark_ratio = dark_pixels / total_pixels if total_pixels > 0 else 0

        details['header_dark_ratio'] = dark_ratio

        # Briefköpfe haben typischerweise mehr dunkle Pixel (Logo, Text)
        if 0.05 < dark_ratio < 0.4:
            score += 0.3
            details['has_letterhead'] = True
        else:
            details['has_letterhead'] = False

        # Prüfe auf horizontale Linien (Trennlinien im Briefkopf)
        if self._detect_horizontal_lines(header_array):
            score += 0.1
            details['has_header_lines'] = True

        return score, details

    def _detect_horizontal_lines(self, image_array: np.ndarray) -> bool:
        """Erkennt horizontale Linien im Bild"""
        # Einfache Heuristik: Suche nach Zeilen mit vielen dunklen Pixeln
        rows_dark = np.sum(image_array < 100, axis=1)
        width = image_array.shape[1]

        # Eine Linie hat mindestens 30% der Breite dunkle Pixel
        line_threshold = width * 0.3
        lines_found = np.sum(rows_dark > line_threshold)

        return lines_found >= 1

    def _has_date_in_header(self, text: str) -> bool:
        """Prüft ob im oberen Textbereich ein Datum vorkommt"""
        date_patterns = [
            r'\d{1,2}\.\d{1,2}\.\d{2,4}',  # 01.01.2024
            r'\d{1,2}\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*\d{2,4}',
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # 01/01/2024
        ]

        for pattern in date_patterns:
            if re.search(pattern, text[:1000], re.IGNORECASE):
                return True
        return False

    def _has_salutation(self, text: str) -> bool:
        """Prüft auf typische Anreden"""
        salutations = [
            r'(?i)sehr geehrte(r|s)?\s+(frau|herr|damen|herren)',
            r'(?i)liebe(r|s)?\s+(frau|herr)',
            r'(?i)guten tag',
            r'(?i)dear\s+(mr|mrs|ms|sir|madam)',
        ]

        for pattern in salutations:
            if re.search(pattern, text):
                return True
        return False


class DocumentAnalyzer:
    """
    Analysiert Dokumente mittels KI für intelligente Benennung.

    Extrahiert:
    - Datum des Dokuments
    - Absender/Empfänger (Mandant, Gegner, Gericht, etc.)
    - Dokumenttyp und Inhalt (4 Worte)
    """

    DOCUMENT_TYPES = {
        'schreiben': ['schreiben', 'brief', 'mitteilung', 'nachricht'],
        'bescheid': ['bescheid', 'beschluss', 'verfügung', 'anordnung'],
        'rechnung': ['rechnung', 'faktura', 'honorar', 'kostennote'],
        'klage': ['klage', 'klageschrift', 'klageerwiderung'],
        'antrag': ['antrag', 'gesuch', 'ersuchen'],
        'vertrag': ['vertrag', 'vereinbarung', 'abkommen'],
        'vollmacht': ['vollmacht', 'bevollmächtigung'],
        'urteil': ['urteil', 'entscheidung'],
        'gutachten': ['gutachten', 'expertise', 'stellungnahme'],
        'mahnung': ['mahnung', 'zahlungserinnerung', 'mahnbescheid'],
    }

    def __init__(self, api_client=None, api_type: str = "openai"):
        """
        Args:
            api_client: OpenAI oder Anthropic Client
            api_type: "openai" oder "anthropic"
        """
        self.api_client = api_client
        self.api_type = api_type

    def analyze_document(self, text: str) -> Dict[str, Any]:
        """
        Analysiert Dokumenttext und extrahiert Metadaten.

        Returns:
            Dict mit datum, absender, empfaenger, dokumenttyp, betreff, kurzbeschreibung
        """
        if self.api_client:
            return self._analyze_with_ai(text)
        else:
            return self._analyze_with_rules(text)

    def _analyze_with_ai(self, text: str) -> Dict[str, Any]:
        """Verwendet KI für Dokumentanalyse"""

        # Kürze Text wenn nötig
        analysis_text = text[:4000] if len(text) > 4000 else text

        prompt = f"""Analysiere dieses Dokument und extrahiere folgende Informationen im JSON-Format:

{{
    "datum": "TT.MM.JJJJ oder null wenn nicht erkennbar",
    "absender": "Name des Absenders (Firma/Person/Behörde)",
    "empfaenger": "Name des Empfängers",
    "dokumenttyp": "Art des Dokuments (z.B. Schreiben, Bescheid, Rechnung, Klage, etc.)",
    "betreff": "Betreff wenn vorhanden",
    "kurzbeschreibung": "Beschreibung in genau 4 Worten",
    "partei_rolle": "mandant/gegner/gericht/behoerde/versicherung/sonstige"
}}

DOKUMENT:
{analysis_text}

Antworte NUR mit dem JSON, ohne zusätzlichen Text."""

        try:
            if self.api_type == "openai":
                response = self.api_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=500
                )
                result_text = response.choices[0].message.content.strip()

            elif self.api_type == "anthropic":
                response = self.api_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                result_text = response.content[0].text.strip()

            # Parse JSON
            # Entferne mögliche Markdown-Formatierung
            result_text = re.sub(r'^```json\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)

            return json.loads(result_text)

        except Exception as e:
            print(f"KI-Analyse fehlgeschlagen: {e}")
            return self._analyze_with_rules(text)

    def _analyze_with_rules(self, text: str) -> Dict[str, Any]:
        """Regelbasierte Dokumentanalyse als Fallback"""
        result = {
            'datum': None,
            'absender': None,
            'empfaenger': None,
            'dokumenttyp': 'Dokument',
            'betreff': None,
            'kurzbeschreibung': 'Allgemeines Dokument',
            'partei_rolle': 'sonstige'
        }

        # Datum extrahieren
        date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{2,4})', text[:1000])
        if date_match:
            result['datum'] = date_match.group(1)

        # Betreff extrahieren
        betreff_match = re.search(r'(?i)betreff\s*:\s*(.+?)(?:\n|$)', text)
        if betreff_match:
            result['betreff'] = betreff_match.group(1).strip()[:100]

        # Dokumenttyp erkennen
        text_lower = text.lower()
        for doc_type, keywords in self.DOCUMENT_TYPES.items():
            if any(kw in text_lower for kw in keywords):
                result['dokumenttyp'] = doc_type.capitalize()
                break

        # Kurzbeschreibung aus Betreff oder ersten Worten
        if result['betreff']:
            words = result['betreff'].split()[:4]
            result['kurzbeschreibung'] = ' '.join(words)
        else:
            # Erste sinnvolle Worte aus dem Text
            words = re.findall(r'\b[A-ZÄÖÜ][a-zäöüß]+\b', text[:500])[:4]
            if words:
                result['kurzbeschreibung'] = ' '.join(words)

        return result


class AktenDigitalisierer:
    """
    Hauptklasse für die Aktendigitalisierung.

    Workflow:
    1. PDF laden und in Seiten aufteilen
    2. Jede Seite auf "erste Seite"-Merkmale prüfen
    3. Dokumente trennen
    4. Jedes Dokument analysieren und benennen
    5. ZIP-Archiv mit Ordnerstruktur erstellen
    """

    def __init__(self, api_client=None, api_type: str = "openai", confidence_threshold: float = 0.5):
        """
        Args:
            api_client: OpenAI oder Anthropic Client für KI-Analyse
            api_type: "openai" oder "anthropic"
            confidence_threshold: Mindestkonfidenz für Dokumenttrennung (0-1)
        """
        self.first_page_detector = FirstPageDetector()
        self.document_analyzer = DocumentAnalyzer(api_client, api_type)
        self.confidence_threshold = confidence_threshold
        self.api_client = api_client

    def process_pdf(self, pdf_path: str, aktenzeichen: str = "",
                    mandant: str = "") -> Tuple[List[DetectedDocument], bytes]:
        """
        Verarbeitet eine PDF-Datei und erstellt ZIP-Export.

        Args:
            pdf_path: Pfad zur PDF-Datei
            aktenzeichen: Optionales Aktenzeichen für Ordnerstruktur
            mandant: Optionaler Mandantenname

        Returns:
            Tuple[List[DetectedDocument], bytes]: (Liste erkannter Dokumente, ZIP-Daten)
        """
        # PDF öffnen
        doc = fitz.open(pdf_path)

        # Schritt 1: Seiten analysieren
        page_analyses = self._analyze_all_pages(doc)

        # Schritt 2: Dokumente trennen
        documents = self._split_into_documents(doc, page_analyses)

        # Schritt 3: Dokumente analysieren und benennen
        for document in documents:
            self._analyze_and_name_document(document, aktenzeichen, mandant)

        # Schritt 4: ZIP erstellen
        zip_data = self._create_zip(doc, documents, aktenzeichen)

        doc.close()

        return documents, zip_data

    def process_pdf_bytes(self, pdf_bytes: bytes, aktenzeichen: str = "",
                          mandant: str = "") -> Tuple[List[DetectedDocument], bytes]:
        """
        Verarbeitet PDF aus Bytes (z.B. von Streamlit Upload).
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        page_analyses = self._analyze_all_pages(doc)
        documents = self._split_into_documents(doc, page_analyses)

        for document in documents:
            self._analyze_and_name_document(document, aktenzeichen, mandant)

        zip_data = self._create_zip(doc, documents, aktenzeichen)

        doc.close()

        return documents, zip_data

    def _analyze_all_pages(self, doc: fitz.Document) -> List[Dict]:
        """Analysiert alle Seiten auf First-Page-Merkmale"""
        analyses = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Text extrahieren
            text = page.get_text()

            # Bild für visuelle Analyse erstellen
            pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))  # Reduzierte Auflösung
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))

            # Analyse durchführen
            confidence, details = self.first_page_detector.analyze_page(
                text, image, page_num
            )

            analyses.append({
                'page_num': page_num,
                'confidence': confidence,
                'details': details,
                'text': text
            })

        return analyses

    def _split_into_documents(self, doc: fitz.Document,
                              page_analyses: List[Dict]) -> List[DetectedDocument]:
        """Trennt PDF in einzelne Dokumente basierend auf Analyse"""
        documents = []
        current_doc_start = 0

        for i, analysis in enumerate(page_analyses):
            # Erste Seite ist immer Dokumentanfang
            if i == 0:
                continue

            # Prüfe ob dies eine neue erste Seite ist
            if analysis['confidence'] >= self.confidence_threshold:
                # Vorheriges Dokument abschließen
                doc_text = ""
                for page_num in range(current_doc_start, i):
                    doc_text += page_analyses[page_num]['text'] + "\n"

                documents.append(DetectedDocument(
                    start_page=current_doc_start,
                    end_page=i - 1,
                    confidence=page_analyses[current_doc_start]['confidence'],
                    raw_text=doc_text
                ))

                current_doc_start = i

        # Letztes Dokument hinzufügen
        doc_text = ""
        for page_num in range(current_doc_start, len(doc)):
            doc_text += page_analyses[page_num]['text'] + "\n"

        documents.append(DetectedDocument(
            start_page=current_doc_start,
            end_page=len(doc) - 1,
            confidence=page_analyses[current_doc_start]['confidence'] if page_analyses else 0,
            raw_text=doc_text
        ))

        return documents

    def _analyze_and_name_document(self, document: DetectedDocument,
                                   aktenzeichen: str, mandant: str) -> None:
        """Analysiert Dokument und generiert Dateinamen"""

        # KI-Analyse
        analysis = self.document_analyzer.analyze_document(document.raw_text)

        # Metadaten setzen
        document.datum = analysis.get('datum')
        document.absender = analysis.get('absender')
        document.empfaenger = analysis.get('empfaenger')
        document.dokumenttyp = analysis.get('dokumenttyp', 'Dokument')
        document.betreff = analysis.get('betreff')

        # Ordner bestimmen
        partei_rolle = analysis.get('partei_rolle', 'sonstige')
        folder_mapping = {
            'mandant': '01_Mandant',
            'gegner': '02_Gegner',
            'gericht': '03_Gericht',
            'behoerde': '04_Behoerden',
            'versicherung': '05_Versicherung',
            'sonstige': '06_Sonstige'
        }
        document.folder = folder_mapping.get(partei_rolle, '06_Sonstige')

        # Dateiname generieren: Aktenzeichen_Datum_Partei_Inhalt(4Worte)

        # 1. Aktenzeichen (vom Benutzer eingegeben)
        az_str = ""
        if aktenzeichen:
            az_str = aktenzeichen.replace('/', '-').replace(' ', '_')

        # 2. Datum
        datum_str = document.datum or datetime.now().strftime('%d.%m.%Y')
        datum_str = datum_str.replace('.', '-')

        # 3. Partei - Priorität: Mandant (wenn eingegeben) > Absender aus Analyse
        if mandant:
            partei = mandant
        else:
            partei = analysis.get('absender') or analysis.get('empfaenger') or 'Unbekannt'

        if partei:
            # Bereinige Parteinamen
            partei = re.sub(r'[^\w\säöüÄÖÜß-]', '', str(partei))[:30]
            partei = partei.strip().replace(' ', '_')
        else:
            partei = 'Unbekannt'

        # 4. Kurzbeschreibung (4 Worte)
        kurz = analysis.get('kurzbeschreibung', 'Dokument')
        if kurz:
            kurz = re.sub(r'[^\w\säöüÄÖÜß-]', '', str(kurz))
            kurz = '_'.join(kurz.split()[:4])
        else:
            kurz = 'Dokument'

        # Finale Dateiname: Aktenzeichen_Datum_Partei_Inhalt.pdf
        if az_str:
            filename = f"{az_str}_{datum_str}_{partei}_{kurz}.pdf"
        else:
            filename = f"{datum_str}_{partei}_{kurz}.pdf"

        # Bereinige ungültige Zeichen
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'_+', '_', filename)  # Mehrfache Unterstriche entfernen
        filename = filename.strip('_')  # Führende/nachfolgende Unterstriche entfernen

        document.filename = filename

    def _create_zip(self, doc: fitz.Document, documents: List[DetectedDocument],
                    aktenzeichen: str) -> bytes:
        """Erstellt ZIP-Archiv mit Ordnerstruktur"""

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Basis-Ordnername
            if aktenzeichen:
                base_folder = f"Akte_{aktenzeichen.replace('/', '-')}"
            else:
                base_folder = f"Akte_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Zähler für Duplikate
            filename_counter = {}

            for document in documents:
                # PDF für dieses Dokument erstellen
                sub_doc = fitz.open()

                for page_num in document.pages:
                    sub_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)

                # PDF in Bytes
                pdf_bytes = sub_doc.tobytes()
                sub_doc.close()

                # Pfad im ZIP
                folder = document.folder or '06_Sonstige'
                filename = document.filename or f"Dokument_{document.start_page+1}.pdf"

                # Duplikate behandeln
                full_path = f"{base_folder}/{folder}/{filename}"
                if full_path in filename_counter:
                    filename_counter[full_path] += 1
                    name, ext = os.path.splitext(filename)
                    filename = f"{name}_{filename_counter[full_path]}{ext}"
                    full_path = f"{base_folder}/{folder}/{filename}"
                else:
                    filename_counter[full_path] = 1

                # Zur ZIP hinzufügen
                zf.writestr(full_path, pdf_bytes)

            # Übersichts-JSON hinzufügen
            overview = {
                'aktenzeichen': aktenzeichen,
                'erstellt_am': datetime.now().isoformat(),
                'anzahl_dokumente': len(documents),
                'dokumente': [
                    {
                        'dateiname': d.filename,
                        'ordner': d.folder,
                        'seiten': f"{d.start_page+1}-{d.end_page+1}",
                        'datum': d.datum,
                        'absender': d.absender,
                        'dokumenttyp': d.dokumenttyp,
                        'konfidenz': round(d.confidence, 2)
                    }
                    for d in documents
                ]
            }

            zf.writestr(
                f"{base_folder}/00_Uebersicht.json",
                json.dumps(overview, ensure_ascii=False, indent=2)
            )

        return zip_buffer.getvalue()

    def preview_split(self, pdf_bytes: bytes) -> List[Dict]:
        """
        Zeigt Vorschau der Dokumenttrennung ohne vollständige Analyse.
        Nützlich für UI-Feedback.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_analyses = self._analyze_all_pages(doc)

        preview = []
        current_start = 0

        for i, analysis in enumerate(page_analyses):
            is_first_page = i == 0 or analysis['confidence'] >= self.confidence_threshold

            if is_first_page and i > 0:
                preview.append({
                    'dokument_nr': len(preview) + 1,
                    'seiten': f"{current_start + 1}-{i}",
                    'seitenanzahl': i - current_start,
                    'erste_seite_konfidenz': page_analyses[current_start]['confidence']
                })
                current_start = i

            # Letzte Seite
            if i == len(page_analyses) - 1:
                preview.append({
                    'dokument_nr': len(preview) + 1,
                    'seiten': f"{current_start + 1}-{i + 1}",
                    'seitenanzahl': i - current_start + 1,
                    'erste_seite_konfidenz': page_analyses[current_start]['confidence']
                })

        doc.close()
        return preview


# Convenience-Funktion für direkten Zugriff
def digitalisiere_akte(pdf_path: str, api_client=None, api_type: str = "openai",
                       aktenzeichen: str = "", mandant: str = "",
                       confidence: float = 0.5) -> Tuple[List[DetectedDocument], bytes]:
    """
    Convenience-Funktion für Aktendigitalisierung.

    Args:
        pdf_path: Pfad zur PDF
        api_client: OpenAI/Anthropic Client
        api_type: "openai" oder "anthropic"
        aktenzeichen: Aktenzeichen für Ordner
        mandant: Mandantenname
        confidence: Trennungs-Schwellwert (0-1)

    Returns:
        Tuple[List[DetectedDocument], bytes]: (Dokumente, ZIP-Daten)
    """
    digitalisierer = AktenDigitalisierer(
        api_client=api_client,
        api_type=api_type,
        confidence_threshold=confidence
    )

    return digitalisierer.process_pdf(pdf_path, aktenzeichen, mandant)
