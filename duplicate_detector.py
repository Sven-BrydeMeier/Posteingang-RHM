"""
Duplikate-Erkennung für PDF-Dokumente

Erkennt doppelt eingescannte Dokumente durch:
- PDF-Hash-Vergleich (SHA-256)
- Text-Fingerprint-Ähnlichkeit
- Persistente Speicherung verarbeiteter Dokumente
"""

import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re


class DuplicateDetector:
    """Erkennt und verhindert doppelte Verarbeitung von Dokumenten"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Duplikate-Detektor

        Args:
            storage_dir: Verzeichnis für persistente Speicherung
        """
        self.storage_dir = Path(storage_dir)
        self.processed_file = self.storage_dir / "processed_documents.json"
        self.processed_docs = self._load_processed_docs()

    def _load_processed_docs(self) -> Dict:
        """Lädt bereits verarbeitete Dokumente"""
        if self.processed_file.exists():
            try:
                with open(self.processed_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Fehler beim Laden: {e}")
                return {}
        return {}

    def _save_processed_docs(self):
        """Speichert verarbeitete Dokumente"""
        try:
            with open(self.processed_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_docs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")

    def calculate_pdf_hash(self, pdf_bytes: bytes) -> str:
        """
        Berechnet SHA-256 Hash einer PDF-Datei

        Args:
            pdf_bytes: PDF als Bytes

        Returns:
            SHA-256 Hash als Hex-String
        """
        return hashlib.sha256(pdf_bytes).hexdigest()

    def calculate_text_fingerprint(self, text: str) -> str:
        """
        Erstellt Text-Fingerprint für Ähnlichkeits-Vergleich

        Args:
            text: Dokument-Text

        Returns:
            Normalisierter Fingerprint
        """
        # Normalisiere Text
        text = text.lower()
        text = re.sub(r'\s+', ' ', text)  # Whitespace normalisieren
        text = re.sub(r'[^\w\s]', '', text)  # Sonderzeichen entfernen

        # Nimm erste 500 Zeichen als Fingerprint
        fingerprint = text[:500]
        return hashlib.md5(fingerprint.encode()).hexdigest()

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Berechnet Jaccard-Ähnlichkeit zwischen zwei Texten

        Args:
            text1: Erster Text
            text2: Zweiter Text

        Returns:
            Ähnlichkeit zwischen 0 und 1
        """
        # Normalisiere und tokenisiere
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        # Jaccard-Index
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def check_duplicate(self, pdf_bytes: bytes, text: str) -> Tuple[bool, Optional[Dict]]:
        """
        Prüft ob Dokument bereits verarbeitet wurde

        Args:
            pdf_bytes: PDF als Bytes
            text: Extrahierter Text

        Returns:
            (is_duplicate, duplicate_info)
        """
        pdf_hash = self.calculate_pdf_hash(pdf_bytes)
        text_fingerprint = self.calculate_text_fingerprint(text)

        # 1. Exakter Hash-Match (100% Duplikat)
        if pdf_hash in self.processed_docs:
            return True, self.processed_docs[pdf_hash]

        # 2. Text-Fingerprint-Match (sehr wahrscheinlich Duplikat)
        for stored_hash, doc_info in self.processed_docs.items():
            if doc_info.get('text_fingerprint') == text_fingerprint:
                return True, doc_info

        # 3. Ähnlichkeits-Check (möglicherweise Duplikat - z.B. neu gescannt)
        for stored_hash, doc_info in self.processed_docs.items():
            stored_text = doc_info.get('text_preview', '')
            similarity = self.calculate_similarity(text[:500], stored_text)

            # Wenn 90% ähnlich, wahrscheinlich Duplikat
            if similarity > 0.90:
                doc_info['similarity'] = similarity
                return True, doc_info

        return False, None

    def mark_as_processed(self, pdf_bytes: bytes, text: str, metadata: Optional[Dict] = None):
        """
        Markiert Dokument als verarbeitet

        Args:
            pdf_bytes: PDF als Bytes
            text: Extrahierter Text
            metadata: Zusätzliche Metadaten
        """
        pdf_hash = self.calculate_pdf_hash(pdf_bytes)
        text_fingerprint = self.calculate_text_fingerprint(text)

        doc_info = {
            'hash': pdf_hash,
            'text_fingerprint': text_fingerprint,
            'text_preview': text[:500],  # Erste 500 Zeichen
            'timestamp': datetime.now().isoformat(),
            'size_bytes': len(pdf_bytes)
        }

        # Füge optionale Metadaten hinzu
        if metadata:
            doc_info.update(metadata)

        self.processed_docs[pdf_hash] = doc_info
        self._save_processed_docs()

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken über verarbeitete Dokumente

        Returns:
            Dict mit Statistiken
        """
        if not self.processed_docs:
            return {
                'total_documents': 0,
                'oldest_document': None,
                'newest_document': None,
                'total_size_mb': 0
            }

        timestamps = [doc.get('timestamp') for doc in self.processed_docs.values() if doc.get('timestamp')]
        sizes = [doc.get('size_bytes', 0) for doc in self.processed_docs.values()]

        return {
            'total_documents': len(self.processed_docs),
            'oldest_document': min(timestamps) if timestamps else None,
            'newest_document': max(timestamps) if timestamps else None,
            'total_size_mb': sum(sizes) / (1024 * 1024)
        }

    def clear_old_entries(self, days: int = 90):
        """
        Löscht Einträge älter als X Tage

        Args:
            days: Anzahl Tage
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        to_delete = []

        for doc_hash, doc_info in self.processed_docs.items():
            timestamp_str = doc_info.get('timestamp')
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timestamp < cutoff:
                        to_delete.append(doc_hash)
                except:
                    pass

        for doc_hash in to_delete:
            del self.processed_docs[doc_hash]

        if to_delete:
            self._save_processed_docs()

        return len(to_delete)

    def export_to_excel(self, output_path: Path):
        """
        Exportiert verarbeitete Dokumente nach Excel

        Args:
            output_path: Pfad zur Excel-Datei
        """
        import pandas as pd

        if not self.processed_docs:
            return

        rows = []
        for doc_hash, doc_info in self.processed_docs.items():
            rows.append({
                'Hash': doc_hash[:16] + '...',
                'Timestamp': doc_info.get('timestamp', ''),
                'Größe (KB)': doc_info.get('size_bytes', 0) / 1024,
                'Text-Vorschau': doc_info.get('text_preview', '')[:100],
                'Aktenzeichen': doc_info.get('aktenzeichen', ''),
                'Sachbearbeiter': doc_info.get('sachbearbeiter', '')
            })

        df = pd.DataFrame(rows)
        df.to_excel(output_path, index=False)
