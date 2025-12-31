"""
Aktenzeichen-Erkennungsmodul für RHM Posteingang
Implementiert alle Regeln aus dem Masterprompt
"""

import re
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class AktenzeichenErkenner:
    # Kanzlei-Kürzel (MQ vor M, da MQ spezifischer; TS vor ST wegen höherer Priorität)
    KUERZEL = ['MQ', 'SQ', 'TS', 'CV', 'FÜ', 'FU', 'M', 'GO', 'HE', 'RÜ', 'AK', 'TÖ', 'LI', 'AD', 'HI', 'FK', 'ST']
    KUERZEL_NORMALISIERT = {
        'MQ': 'M',  # MQ = M (RAin Marquardsen)
        'FU': 'FÜ',  # FU = FÜ
        'FÜ': 'FÜ',
        'SQ': 'SQ',
        'TS': 'TS',  # Tamara Meyer
        'CV': 'CV',
        'M': 'M',
        'GO': 'GO',  # Goeser
        'HE': 'HE',  # Herberg
        'RÜ': 'RÜ',  # Korinna Rückborn
        'AK': 'AK',  # Akkoc
        'TÖ': 'TÖ',  # Tönjes
        'LI': 'LI',  # Litzenroth
        'AD': 'AD',  # Abdul Al
        'HI': 'HI',  # Hingst
        'FK': 'FK',  # Kaya
        'ST': 'ST'   # Stöcken
    }

    # Sachbearbeiter-Namen zu Kürzel Mapping (alle Variationen inkl. OCR-Fehler)
    SACHBEARBEITER_NAMEN = {
        # SQ = Sven-Bryde Meier (Rechtsanwalt und Notar)
        # Alle OCR-Variationen: Bindestriche, Unterstriche, Leerzeichen
        'meier': 'SQ',
        'sven-bryde': 'SQ',
        'sven_bryde': 'SQ',  # OCR: Unterstrich statt Bindestrich
        'sven bryde': 'SQ',  # OCR: Leerzeichen statt Bindestrich
        'sven': 'SQ',
        'sven-bryde meier': 'SQ',
        'sven-bryde_meier': 'SQ',  # OCR: Unterstrich statt Leerzeichen
        'sven_bryde meier': 'SQ',  # OCR: Unterstrich im Namen
        'sven_bryde_meier': 'SQ',  # OCR: Nur Unterstriche
        'sven bryde-meier': 'SQ',  # OCR: Andere Bindestrich-Position
        'sven bryde meier': 'SQ',  # OCR: Nur Leerzeichen
        'sven meier': 'SQ',

        # TS = Tamara Meyer (Rechtsanwältin)
        'meyer': 'TS',
        'tamara': 'TS',
        'tamara meyer': 'TS',
        'tamara_meyer': 'TS',  # OCR: Unterstrich

        # M/MQ = Ann-Kathrin Marquardsen (Rechtsanwältin)
        'marquardsen': 'M',
        'ann-kathrin': 'M',
        'ann_kathrin': 'M',  # OCR: Unterstrich statt Bindestrich
        'ann kathrin': 'M',  # OCR: Leerzeichen statt Bindestrich
        'ann-kathrin marquardsen': 'M',
        'ann-kathrin_marquardsen': 'M',  # OCR: Unterstrich
        'ann_kathrin marquardsen': 'M',  # OCR: Unterstrich im Namen
        'ann_kathrin_marquardsen': 'M',  # OCR: Nur Unterstriche
        'ann kathrin marquardsen': 'M',  # OCR: Nur Leerzeichen

        # FÜ = Dr. Ernst Joachim Fürsen (Rechtsanwalt, Notar a.D.)
        'fürsen': 'FÜ',
        'fuersen': 'FÜ',
        'ernst joachim': 'FÜ',
        'ernst-joachim': 'FÜ',
        'ernst_joachim': 'FÜ',  # OCR: Unterstrich
        'ernst joachim fürsen': 'FÜ',
        'ernst-joachim fürsen': 'FÜ',
        'ernst_joachim fürsen': 'FÜ',  # OCR: Unterstrich
        'ernst joachim_fürsen': 'FÜ',  # OCR: Unterstrich
        'ernst-joachim_fürsen': 'FÜ',  # OCR: Unterstrich
        'ernst_joachim_fürsen': 'FÜ',  # OCR: Nur Unterstriche
        'ernst joachim fuersen': 'FÜ',
        'ernst-joachim fuersen': 'FÜ',
        'ernst_joachim fuersen': 'FÜ',  # OCR: Unterstrich
        'ernst joachim_fuersen': 'FÜ',  # OCR: Unterstrich
        'ernst-joachim_fuersen': 'FÜ',  # OCR: Unterstrich
        'ernst_joachim_fuersen': 'FÜ',  # OCR: Nur Unterstriche

        # CV = Christian Ostertun (Rechtsanwalt)
        'ostertun': 'CV',
        'christian': 'CV',
        'christian ostertun': 'CV',
        'christian_ostertun': 'CV',  # OCR: Unterstrich
        'vollbrecht': 'CV',  # Alternative Name

        # GO = Goeser
        'goeser': 'GO',
        'göser': 'GO',  # Umlaute-Alternative

        # HE = Herberg
        'herberg': 'HE',

        # RÜ = Korinna Rückborn
        'rückborn': 'RÜ',
        'rueckborn': 'RÜ',  # Umlaute-Alternative
        'korinna': 'RÜ',
        'korinna rückborn': 'RÜ',
        'korinna rueckborn': 'RÜ',
        'korinna_rückborn': 'RÜ',  # OCR: Unterstrich
        'korinna_rueckborn': 'RÜ',

        # AK = Akkoc
        'akkoc': 'AK',

        # TÖ = Tönjes
        'tönjes': 'TÖ',
        'toenjes': 'TÖ',  # Umlaute-Alternative

        # LI = Litzenroth
        'litzenroth': 'LI',

        # AD = Abdul Al
        'abdul': 'AD',
        'abdul al': 'AD',
        'abdul_al': 'AD',  # OCR: Unterstrich

        # HI = Hingst
        'hingst': 'HI',

        # FK = Kaya
        'kaya': 'FK',

        # ST = Stöcken
        'stöcken': 'ST',
        'stoecken': 'ST'  # Umlaute-Alternative
    }

    # Titel-Variationen (für erweiterte Suche)
    TITEL_VARIATIONEN = [
        'rechtsanwalt', 'rechtsanwältin', 'ra', 'rae', 'r.a.',
        'notar', 'notar a.d.', 'notar a. d.',
        'fachanwalt', 'fachanwältin', 'fa', 'fain',
        'dr.', 'dr', 'doktor'
    ]

    # Schlagwörter für "Ihr Zeichen" etc. (erweitert für bessere Erkennung + OCR-Varianten)
    ZEICHEN_KEYWORDS = [
        # Original-Keywords
        'ihr zeichen', 'ihr zeichen:', 'ihr-zeichen', 'ihr-zeichen:',
        'unser zeichen', 'unser zeichen:', 'unser-zeichen', 'unser-zeichen:',
        'ihr az', 'ihr az.', 'ihr az:', 'ihr az.:',
        'ihr aktenzeichen', 'ihr aktenzeichen:', 'ihr-aktenzeichen',
        'dortiges aktenzeichen', 'dortiges aktenzeichen:',
        'verwendungszweck', 'verwendungszweck:',
        'aktenzeichen:', 'az:', 'az.:',
        'iz', 'iz:', 'iz.',  # Kurzform für "Ihr Zeichen"

        # OCR-Varianten (häufige Verwechslungen)
        'lhr zeichen', 'lhr zeichen:',  # I statt h
        'lz', 'lz:', 'lz.',              # I statt h in iZ
        'ihr ze ichen', 'ihr ze ichen:',  # Leerzeichen im Wort
        'ihrz eichen', 'ihrz eichen:',    # Leerzeichen falsch
        'lhrz eichen',                    # Kombination
    ]

    # Externe Aktenzeichen-Schlagwörter
    EXTERNE_KEYWORDS = [
        'aktenzeichen beim', 'az.', 'schadennummer', 'schaden-nr',
        'versicherungsnummer', 'kundennummer'
    ]

    def __init__(self, excel_path: Path, storage=None):
        """
        Lädt das Aktenregister und benutzerdefinierte Kürzel.

        Args:
            excel_path: Pfad zum Aktenregister
            storage: PersistentStorage-Instanz für benutzerdefinierte Kürzel (optional)
        """
        self.akten_register = self._lade_aktenregister(excel_path)
        self.storage = storage

        # Lade benutzerdefinierte Kürzel und erweitere die Kürzel-Listen
        self._load_custom_kuerzel()

    def _lade_aktenregister(self, excel_path: Path) -> pd.DataFrame:
        """Lädt aktenregister.xlsx, Blatt 'akten' mit automatischer Header-Erkennung"""

        # Versuche verschiedene Header-Zeilen (0, 1, 2)
        for header_row in [1, 0, 2]:
            try:
                df = pd.read_excel(
                    excel_path,
                    sheet_name='akten',
                    header=header_row,
                    engine='openpyxl'
                )

                # Prüfe ob Spalten sinnvoll sind (nicht nur "Unnamed")
                unnamed_count = sum(1 for col in df.columns if str(col).startswith('Unnamed'))
                total_cols = len(df.columns)

                # Wenn weniger als 50% "Unnamed" Spalten, ist es wahrscheinlich der richtige Header
                if unnamed_count < total_cols * 0.5:
                    print(f"✓ Header in Zeile {header_row} gefunden")
                    break
            except Exception as e:
                continue
        else:
            # Fallback: Verwende header=1
            df = pd.read_excel(
                excel_path,
                sheet_name='akten',
                header=1,
                engine='openpyxl'
            )

        # Prüfe ob erforderliche Spalten vorhanden sind
        if 'Akte' not in df.columns or 'SB' not in df.columns:
            # Zeige verfügbare Spalten für Debugging
            print(f"⚠️ Warnung: Erforderliche Spalten nicht gefunden!")
            print(f"Verfügbare Spalten: {list(df.columns)}")

            # Versuche alternative Spaltennamen
            column_mapping = {}
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if 'akt' in col_lower and 'Akte' not in df.columns:
                    column_mapping[col] = 'Akte'
                elif col_lower in ['sb', 'sachbearbeiter', 'bearbeiter'] and 'SB' not in df.columns:
                    column_mapping[col] = 'SB'

            if column_mapping:
                df = df.rename(columns=column_mapping)
                print(f"✓ Spalten umbenannt: {column_mapping}")

        # Spalten bereinigen (nur wenn vorhanden)
        if 'Akte' in df.columns:
            df['Akte'] = df['Akte'].astype(str).str.strip()

        if 'SB' in df.columns:
            df['SB'] = df['SB'].astype(str).str.strip().str.upper()
            # FU zu FÜ normalisieren
            df['SB'] = df['SB'].replace('FU', 'FÜ')

        return df

    def _load_custom_kuerzel(self) -> None:
        """
        Lädt benutzerdefinierte Kürzel aus dem Storage und erweitert die Kürzel-Listen.
        """
        if not self.storage:
            return

        try:
            custom_kuerzel = self.storage.get_custom_kuerzel()

            for kuerzel, data in custom_kuerzel.items():
                kuerzel_upper = kuerzel.upper()

                # Füge zur KUERZEL Liste hinzu (wenn nicht schon vorhanden)
                if kuerzel_upper not in self.KUERZEL:
                    self.KUERZEL.append(kuerzel_upper)

                # Füge zur KUERZEL_NORMALISIERT hinzu
                if kuerzel_upper not in self.KUERZEL_NORMALISIERT:
                    self.KUERZEL_NORMALISIERT[kuerzel_upper] = kuerzel_upper

                # Füge Namen-Mapping hinzu
                name_lower = data['name'].lower()
                if name_lower not in self.SACHBEARBEITER_NAMEN:
                    self.SACHBEARBEITER_NAMEN[name_lower] = kuerzel_upper

                # Füge auch Varianten ohne Umlaute hinzu
                name_without_umlauts = (name_lower
                    .replace('ä', 'ae')
                    .replace('ö', 'oe')
                    .replace('ü', 'ue')
                    .replace('ß', 'ss'))

                if name_without_umlauts != name_lower and name_without_umlauts not in self.SACHBEARBEITER_NAMEN:
                    self.SACHBEARBEITER_NAMEN[name_without_umlauts] = kuerzel_upper

        except Exception as e:
            print(f"⚠️ Fehler beim Laden benutzerdefinierter Kürzel: {e}")

    def get_all_kuerzel_regex(self) -> str:
        """
        Generiert einen Regex-String mit allen Kürzeln (statisch + dynamisch).

        Returns:
            String wie "MQ|SQ|TS|CV|..." für Verwendung in Regex
        """
        return '|'.join(self.KUERZEL)

    def _normalisiere_ocr_text(self, text: str) -> str:
        """
        Normalisiert OCR-Text für bessere Aktenzeichen-Erkennung.

        Behebt häufige OCR-Fehler:
        - Leerzeichen um Schrägstrich: "111 / 24" → "111/24"
        - Leerzeichen in Zahlen-Folgen: "1 23/24" → "123/24"
        - Schrägstrich-Verwechslungen: "111I24", "111l24" → "111/24"
        - Leerzeichen vor Kürzeln: "111/24 SQ" → "111/24SQ"
        - Zusammengeklebte Zahlen: "1342/2450089" → "1342/24 50089"
        - Umlaut-Verwechslungen: "T6" → "Tö", "B0" → "Bö"
        """
        if not text:
            return text

        # VORVERARBEITUNG 1: Korrigiere häufige Umlaut-OCR-Fehler in Reno-Kürzeln
        # Pattern: Nach einem Aktenzeichen-Format kommt oft ein 2-3 stelliges Reno-Kürzel
        # OCR liest häufig: ö→6, ü→ii, ä→a
        # z.B. "132/25TS04T6" → "132/25TS04Tö"
        def fix_umlaut_ocr_in_reno(match):
            """Korrigiert Umlaut-OCR-Fehler in Reno-Kürzeln"""
            full_match = match.group(0)
            reno = match.group(5)  # Das Reno-Kürzel (z.B. "T6", "B0")

            # Ersetze häufige OCR-Fehler bei Umlauten
            reno_fixed = reno
            reno_fixed = re.sub(r'([A-Z])6\b', r'\1ö', reno_fixed)  # T6 → Tö, B6 → Bö
            reno_fixed = re.sub(r'([A-Z])0\b', r'\1ö', reno_fixed)  # T0 → Tö (alternative)
            reno_fixed = re.sub(r'([A-Z])ii\b', r'\1ü', reno_fixed, flags=re.IGNORECASE)  # Tii → Tü
            reno_fixed = re.sub(r'([A-Z])u([A-Z])\b', r'\1ü\2', reno_fixed)  # TuE → TüE

            if reno != reno_fixed:
                # Ersetze nur das Reno-Kürzel im Match
                return full_match.replace(reno, reno_fixed)
            return full_match

        # Finde erweiterte Aktenzeichen-Formate mit potentiell fehlerhaften Reno-Kürzeln
        # Format: 132/25TS04T6 (mit Ziffer im Reno)
        text = re.sub(
            r'\b(\d{1,4})/(\d{1,2})([A-Z]{2,3})(\d{2})([A-Z0-9]{2,3})\b',
            fix_umlaut_ocr_in_reno,
            text,
            flags=re.IGNORECASE
        )

        # VORVERARBEITUNG 2: Trenne zusammengeklebte Jahr+Nummer Kombinationen
        # z.B. "1342/2450089 / Li" → "1342/24 50089 / Li"
        # Pattern: 1-4 Ziffern / 2-stelliges Jahr + weitere Ziffern
        def split_concatenated_numbers(match):
            """Trennt Jahr von nachfolgenden Ziffern: 2450089 → 24 50089"""
            laufnr = match.group(1)
            jahr_plus = match.group(2)
            rest = match.group(3) if match.lastindex >= 3 else ""

            # Extrahiere ersten 2 Ziffern als Jahr
            if len(jahr_plus) > 2:
                jahr = jahr_plus[:2]
                extra_nummern = jahr_plus[2:]
                return f"{laufnr}/{jahr} {extra_nummern}{rest}"
            else:
                return match.group(0)  # Keine Änderung

        # Finde: Laufnr(1-4) / Jahr+ExtraZiffern (3+ Ziffern)
        text = re.sub(
            r'\b(\d{1,4})\s*[/IlL\\]\s*(\d{3,})(\s|[/IlL\\]|$)',
            split_concatenated_numbers,
            text
        )

        def clean_aktenzeichen_erweitert(match):
            """Bereinigt erweiterte Aktenzeichen: 111/24SQ09/BO"""
            g1, g2, g3, g4, g5 = match.groups()
            # Entferne Leerzeichen aus Zahlengruppen
            num1 = re.sub(r'\s+', '', g1)
            num2 = re.sub(r'\s+', '', g2)
            kuerzel = g3
            bereich = g4
            reno = g5
            return f"{num1}/{num2}{kuerzel}{bereich}/{reno}"

        def clean_aktenzeichen_mit_kuerzel(match):
            """Bereinigt Aktenzeichen mit Kürzel: 111/24SQ"""
            full_match = match.group(0)
            g1, g2, g3 = match.groups()

            # Entferne Leerzeichen aus Zahlengruppen
            num1 = re.sub(r'\s+', '', g1)
            num2 = re.sub(r'\s+', '', g2)

            # Validierung: num2 muss 1-2 Ziffern sein (nicht nur Leerzeichen)
            if not num2 or len(num2) > 2:
                return full_match  # Keine Änderung

            kuerzel = g3

            # Prüfe ob nach dem Match ein Leerzeichen folgt (um es zu erhalten)
            trailing_space = " " if full_match.endswith(" ") else ""

            return f"{num1}/{num2}{kuerzel}{trailing_space}"

        def clean_aktenzeichen_stamm(match):
            """Bereinigt Aktenzeichen-Stamm: 111/24"""
            full_match = match.group(0)
            g1, g2 = match.groups()

            # Entferne Leerzeichen aus Zahlengruppen
            num1 = re.sub(r'\s+', '', g1)
            num2 = re.sub(r'\s+', '', g2)

            # Validierung: Beide müssen Ziffern enthalten
            # num1: 1-4 Ziffern, num2: 1-2 Ziffern
            if not num1 or not num2 or len(num1) > 4 or len(num2) > 2:
                return full_match  # Keine Änderung

            # Prüfe ob nach dem Match ein Leerzeichen folgt (um es zu erhalten)
            trailing_space = " " if full_match.endswith(" ") else ""

            return f"{num1}/{num2}{trailing_space}"

        # STRATEGIE: Finde komplette Aktenzeichen-Muster (inkl. Leerzeichen) und bereinige sie
        # WICHTIG: Separatoren [/IlL\\] - aber NICHT "1" (Ziffer)

        # Pattern 1: Erweiterte Format mit Bereich und Reno
        # z.B. "1 11/24 SQ 09 / BO" → "111/24SQ09/BO"
        text = re.sub(
            r'\b([\d\s]{1,7})\s*[/IlL\\]\s*([\d\s]{1,3})\s*([A-ZÄÖÜ]{1,3})\s*(\d{2})\s*[/IlL\\]\s*([A-Z]{2,3})\b',
            clean_aktenzeichen_erweitert,
            text
        )

        # Pattern 2: Standard mit Kürzel
        # z.B. "1 11 / 24 SQ" → "111/24SQ"
        text = re.sub(
            r'\b([\d\s]{1,7})\s*[/IlL\\]\s*([\d\s]{1,3})\s*([A-ZÄÖÜ]{1,3})\b',
            clean_aktenzeichen_mit_kuerzel,
            text
        )

        # Pattern 3: Nur Stamm (ohne Kürzel)
        # z.B. "1 11 / 24" → "111/24"
        # WICHTIG: Nur wenn BEIDE Gruppen tatsächlich Ziffern enthalten
        text = re.sub(
            r'\b([\d\s]{1,7})\s*[/IlL\\]\s*([\d\s]{1,3})\b',
            clean_aktenzeichen_stamm,
            text
        )

        return text

    def _get_patterns_erweitert(self):
        """Generiert erweiterte Patterns dynamisch mit allen Kürzeln. Unterstützt 1-4 Stellen."""
        kuerzel_regex = self.get_all_kuerzel_regex()
        return [
            # Standard-Format: nur Buchstaben im Reno (z.B. BO, Li)
            rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})/([A-ZÄÖÜß]{{2,3}})\b',  # 111/24SQ09/BO
            rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})([A-ZÄÖÜß]{{2,3}})\b',   # 111/24SQ08BO
            # OCR-tolerant: akzeptiert Ziffern im Reno (z.B. T6 statt Tö)
            rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})/([A-Z0-9]{{2,3}})\b',  # 111/24SQ09/T6
            rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})([A-Z0-9]{{2,3}})\b',   # 111/24SQ08T6
        ]

    def _get_patterns_standard(self):
        """Generiert Standard-Patterns dynamisch mit allen Kürzeln. Unterstützt 1-4 Stellen."""
        kuerzel_regex = self.get_all_kuerzel_regex()
        return [
            rf'\b(\d{{1,4}})[/](\d{{1,2}})({kuerzel_regex})\b',  # 1234/01SQ
        ]

    def erkenne_sachbearbeiter_aus_text(self, text: str) -> Optional[str]:
        """
        Extrahiert den Sachbearbeiter aus Anreden und Anschriften im Text.

        Regeln:
        1. Suche in Anreden wie "Sehr geehrter Herr Kollege Meier"
        2. Suche mit Titeln wie "Rechtsanwalt Meier", "Notar Meier", "Fachanwältin Meyer"
        3. Suche in Anschriften, ABER NICHT wenn der Name nur in Kanzleinamen erscheint
        4. Erkennt alle Namens-Variationen (Vorname + Nachname, nur Vorname, nur Nachname)

        Returns:
            Kürzel des Sachbearbeiters (SQ, TS, M, FÜ, CV) oder None
        """
        text_lower = text.lower()
        lines = text.split('\n')

        # Sortiere Namen nach Länge (längste zuerst) für spezifischere Matches
        sorted_names = sorted(self.SACHBEARBEITER_NAMEN.items(), key=lambda x: len(x[0]), reverse=True)

        # Definiere "kurze" Namen, die strengere Kontext-Prüfung brauchen
        # (nur Vornamen ohne Nachname)
        short_names = {'sven', 'tamara', 'christian', 'ann-kathrin', 'ernst joachim', 'ernst-joachim'}

        # PRIORITÄT 1: Anrede-Suche (höchste Priorität)
        # Erweiterte Patterns für Anreden mit Namen
        for name, kuerzel in sorted_names:
            # Escape Sonderzeichen für regex
            name_escaped = re.escape(name)

            # Pattern: "Sehr geehrter Herr/Frau [Titel] [Name]"
            anrede_patterns = [
                rf'sehr\s+geehrte?[rn]?\s+(herr|frau|herrn)\s+(kollege?|kollegin)\s+({name_escaped})',
                rf'sehr\s+geehrte?[rn]?\s+(herr|frau|herrn)\s+({name_escaped})',
                rf'liebe?[rn]?\s+(herr|frau|kollege?|kollegin)\s+({name_escaped})',
                rf'guten\s+tag\s+(herr|frau)\s+({name_escaped})',
                rf'hallo\s+(herr|frau)\s+({name_escaped})'
            ]

            for pattern in anrede_patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return kuerzel

        # PRIORITÄT 2: Titel + Name Kombinationen (z.B. "Rechtsanwalt Meier", "Notar Meier")
        for name, kuerzel in sorted_names:
            name_escaped = re.escape(name)

            # Suche nach Titel + Name Kombinationen
            for titel in self.TITEL_VARIATIONEN:
                titel_escaped = re.escape(titel)
                # Pattern: "[Titel] [und] [Titel] [Name]" oder einfach "[Titel] [Name]"
                patterns = [
                    rf'{titel_escaped}\s+und\s+\w+\s+{name_escaped}',  # "Rechtsanwalt und Notar Meier"
                    rf'{titel_escaped}\s+{name_escaped}',               # "Rechtsanwalt Meier"
                ]

                for pattern in patterns:
                    if re.search(pattern, text_lower, re.IGNORECASE):
                        return kuerzel

        # PRIORITÄT 3: Anschrift-Suche (mit Ausschluss von Kanzleinamen)
        # Suche in den ersten 30 Zeilen (typischer Anschriftenbereich)
        for i, line in enumerate(lines[:30]):
            line_lower = line.lower().strip()

            # Überspringe Zeilen mit Kanzleinamen
            # z.B. "Radtke, Heigener und Meier" (enthält Komma oder mehrere Namen)
            if ',' in line:
                # Prüfe ob es wie ein Kanzleiname aussieht (mehrere Namen getrennt durch Komma)
                continue

            # Überspringe Zeilen mit mehreren großgeschriebenen Namen (außer wenn Titel dabei)
            if ' und ' in line_lower or ' & ' in line:
                words = re.findall(r'\b[A-ZÄÖÜ][a-zäöüß]+\b', line)
                if len(words) >= 3:  # Mehrere Namen = wahrscheinlich Kanzleiname
                    continue

            # Suche nach Sachbearbeiter-Namen (längste Namen zuerst)
            for name, kuerzel in sorted_names:
                name_escaped = re.escape(name)

                # Suche nach dem Namen als ganzes Wort/Phrase
                if re.search(rf'\b{name_escaped}\b', line_lower):
                    # Hat die Zeile Rechtsanwalts-Kontext?
                    has_title = any(titel in line_lower for titel in self.TITEL_VARIATIONEN)

                    # Für kurze Namen (nur Vornamen): IMMER Titel erforderlich
                    if name in short_names:
                        if has_title:
                            return kuerzel
                        # Kurze Namen ohne Titel ignorieren (zu unsicher)
                        continue

                    # Für längere Namen (mit Nachnamen):
                    # Akzeptiere wenn:
                    # 1. Titel vorhanden (z.B. "Rechtsanwalt Meier")
                    # 2. In Zeilen 5-15 (typischer Empfängerbereich)
                    if has_title or (5 <= i <= 15):
                        return kuerzel

        return None

    def erkenne_aktenzeichen(self, text: str) -> Dict:
        """
        Hauptfunktion: Erkennt internes und externe Aktenzeichen im Text

        Returns:
            Dict mit:
            - internes_az: Internes Kanzlei-Aktenzeichen (z.B. "151/25M")
            - stamm: Nur der Stamm (z.B. "151/25")
            - kuerzel: Sachbearbeiter-Kürzel (z.B. "M")
            - externe_az: Liste externer Aktenzeichen
            - quelle: Woher das interne AZ stammt (zeichen_feld, vollmuster, register, etc.)
        """
        result = {
            'internes_az': None,
            'stamm': None,
            'kuerzel': None,
            'externe_az': [],
            'quelle': None
        }

        # Priorität 1: "Ihr Zeichen / Unser Zeichen" etc. (erweitert auf gesamten Text)
        zeichen_az = self._suche_in_zeichen_feldern(text)
        if zeichen_az:
            result.update(zeichen_az)
            result['quelle'] = 'zeichen_feld'
            return result

        # Priorität 2: Vollmuster im gesamten Text (ohne Keyword-Kontext)
        vollmuster = self._suche_vollmuster(text)
        if vollmuster:
            result.update(vollmuster)
            result['quelle'] = 'vollmuster'
            return result

        # Priorität 3: Stämme im gesamten Text mit Registertreffer
        register_az = self._suche_stamm_mit_register(text)
        if register_az:
            result.update(register_az)
            result['quelle'] = 'register'
            return result

        # Priorität 4: Aktenkurzbezeichnung im Text → Aktenzeichen aus Register
        # (Bidirektionale Verknüpfung)
        kurzbez_az = self._suche_nach_kurzbezeichnung_im_text(text)
        if kurzbez_az:
            result.update(kurzbez_az)
            result['quelle'] = 'kurzbezeichnung_im_text'
            return result

        # Priorität 5: Parteibezeichnungen im Text → Aktenzeichen aus Register
        # (z.B. "Sache Stadtwerke / Müller" findet "Stadtwerke Müller" im Register)
        parteien_az = self._suche_nach_parteien_im_text(text)
        if parteien_az:
            result.update(parteien_az)
            # quelle wird bereits in der Funktion gesetzt (parteien_im_text oder parteien_fuzzy_match)
            return result

        # Priorität 6: Globale Suche nach häufigsten Aktenzeichen-Mustern
        # (für Fälle wo OCR-Reihenfolge stark abweicht)
        global_az = self._suche_globale_muster(text)
        if global_az:
            result.update(global_az)
            result['quelle'] = 'global_pattern'
            return result

        # Priorität 7: Beteiligten-basierter Abgleich (Fallback wenn kein AZ erkannt)
        # Extrahiere Beteiligte aus dem Text
        beteiligte = self._erkenne_beteiligte_im_text(text)
        if beteiligte:
            # Finde passende Akten im Register
            treffer = self._finde_akten_nach_beteiligten(beteiligte)

            if len(treffer) == 1:
                # EINDEUTIGE Zuordnung → Verwende AZ automatisch
                result.update(treffer[0])
                result['quelle'] = 'beteiligte_eindeutig'
                result.pop('score', None)  # Entferne Score aus Ergebnis
                return result
            elif len(treffer) > 1:
                # MEHRERE Treffer → Gib Vorschläge zurück
                result['az_vorschlaege'] = treffer  # Liste von Vorschlägen mit Score
                result['quelle'] = 'beteiligte_mehrfach'
                # Kein internes_az gesetzt, da nicht eindeutig

        # Externe Aktenzeichen sammeln (immer)
        result['externe_az'] = self._suche_externe_aktenzeichen(text)

        return result

    def _suche_in_zeichen_feldern(self, text: str) -> Optional[Dict]:
        """
        Sucht nach Aktenzeichen in "Ihr Zeichen / Unser Zeichen" etc. Zeilen
        Höchste Priorität!

        OCR-robust: Durchsucht den GESAMTEN Text ab dem Keyword
        (nicht nur ±2 Zeilen), da OCR-Textextraktion oft nicht der
        visuellen Position folgt.

        OCR-tolerant: Normalisiert Text vor der Suche
        """
        # OCR-Normalisierung für bessere Erkennung
        text = self._normalisiere_ocr_text(text)
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Prüfe, ob Zeile ein Zeichen-Keyword enthält
            if any(kw in line_lower for kw in self.ZEICHEN_KEYWORDS):
                # ERWEITERT: Suche im gesamten Text ab Keyword (wegen OCR-Reihenfolge-Problemen)
                # Erstelle Suchtext: 5 Zeilen VOR bis ALLE Zeilen NACH dem Keyword
                such_text = ""

                # 5 Zeilen vorher (für Kontext)
                for offset in range(5, 0, -1):
                    if i - offset >= 0:
                        such_text += lines[i - offset] + " "

                # Aktuelle Zeile
                such_text += line + " "

                # ALLE Zeilen nach dem Keyword bis zum Ende des Dokuments
                # (wichtig bei OCR-Reihenfolge-Problemen)
                for offset in range(1, len(lines) - i):
                    such_text += lines[i + offset] + " "

                # Erweiterte Regex: Unterstützt verschiedene Formate
                # Prüfe ZUERST auf erweiterte Formate (mit Bereich + Reno)
                erweitert_patterns = self._get_patterns_erweitert()

                for pattern in erweitert_patterns:
                    erweitert_match = re.search(pattern, such_text, re.IGNORECASE)
                    if erweitert_match:
                        zahl1, zahl2, kuerzel, bereich, reno = erweitert_match.groups()
                        stamm = f"{zahl1}/{zahl2.zfill(2)}"
                        kuerzel = kuerzel.upper()
                        kuerzel_norm = self.KUERZEL_NORMALISIERT.get(kuerzel, kuerzel)

                        result = {
                            'internes_az': f"{stamm}{kuerzel_norm}",
                            'stamm': stamm,
                            'kuerzel': kuerzel_norm,
                            'bereich': bereich,
                            'reno': reno.upper(),
                            'quelle': 'zeichen_feld_erweitert'
                        }
                        # Reichere mit Register-Daten an (z.B. Aktenkurzbezeichnung)
                        return self._anreichern_mit_register_daten(result)

                # Falls keine erweiterten Formate gefunden, suche Standard-Formate
                # Format: 1234/01 oder 1234/1 (Standard, 1-4 Stellen, nur Schrägstrich)
                stamm_patterns = [
                    r'\b(\d{1,4})[/](\d{1,2})\b',  # 1234/01
                ]

                for pattern in stamm_patterns:
                    stamm_match = re.search(pattern, such_text)
                    if stamm_match:
                        # Normalisiere zu Slash-Format
                        zahl1, zahl2 = stamm_match.groups()
                        # Fülle Jahr mit führender Null auf (1 → 01)
                        zahl2_padded = zahl2.zfill(2)
                        stamm = f"{zahl1}/{zahl2_padded}"

                        # Hole Text nach dem Stamm (Suffix)
                        start_pos = stamm_match.end()
                        suffix = such_text[start_pos:start_pos + 50]  # max 50 Zeichen

                        # Suche Kürzel im Suffix
                        # 1. Direkt nach Stamm (ohne Leerzeichen): "1342/24SQ"
                        kuerzel = self._finde_kuerzel_im_text(suffix, position_sensitive=True)

                        # 2. Falls nicht gefunden, suche nach "/ KÜRZEL" Pattern
                        # z.B. "1342/24 50089 / Li" → extrahiere "Li"
                        if not kuerzel:
                            slash_kuerzel_match = re.search(r'[/IlL\\]\s*([A-ZÄÖÜ]{1,3})\b', suffix, re.IGNORECASE)
                            if slash_kuerzel_match:
                                kuerzel_text = slash_kuerzel_match.group(1).upper()
                                # Prüfe ob es ein gültiges Kürzel ist
                                if kuerzel_text in self.KUERZEL or kuerzel_text in self.KUERZEL_NORMALISIERT:
                                    kuerzel = kuerzel_text

                        if kuerzel:
                            # Kürzel gefunden!
                            kuerzel_norm = self.KUERZEL_NORMALISIERT.get(kuerzel, kuerzel)
                            result = {
                                'internes_az': f"{stamm}{kuerzel_norm}",
                                'stamm': stamm,
                                'kuerzel': kuerzel_norm,
                                'quelle': 'zeichen_feld_mit_kuerzel'
                            }
                            # Reichere mit Register-Daten an (z.B. Aktenkurzbezeichnung)
                            return self._anreichern_mit_register_daten(result)
                        else:
                            # Kein Kürzel im Suffix → Register prüfen
                            register_info = self._pruefe_register(stamm)
                            if register_info:
                                return register_info

        return None

    def _suche_vollmuster(self, text: str) -> Optional[Dict]:
        r"""
        Sucht nach Vollmustern: \d{1,4}/\d{2}(SQ|M|MQ|TS|FÜ|CV)...
        Unterstützt nur Schrägstrich (/) als Trennzeichen
        Erkennt auch erweiterte Formate mit Bereich und Reno-Kürzel:
        - 111/24SQ09/BO (mit Schrägstrich vor Reno)
        - 111/24SQ08BO (ohne Schrägstrich vor Reno)

        OCR-tolerant: Normalisiert Text vor der Suche
        """
        # OCR-Normalisierung für bessere Erkennung
        text = self._normalisiere_ocr_text(text)

        # Patterns für verschiedene Formate (dynamisch generiert)
        patterns = self._get_patterns_erweitert() + self._get_patterns_standard()

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Nehme ersten Match
                match_data = matches[0]

                # Erweiterte Formate mit Bereich + Reno (5 Gruppen)
                if len(match_data) == 5:
                    zahl1, zahl2, kuerzel, bereich, reno = match_data
                    # Normalisiere zu Slash-Format mit gepaddetem Jahr
                    stamm = f"{zahl1}/{zahl2.zfill(2)}"
                    kuerzel = kuerzel.upper()
                    kuerzel_norm = self.KUERZEL_NORMALISIERT.get(kuerzel, kuerzel)

                    result = {
                        'internes_az': f"{stamm}{kuerzel_norm}",
                        'stamm': stamm,
                        'kuerzel': kuerzel_norm,
                        'bereich': bereich,
                        'reno': reno.upper(),
                        'quelle': 'vollmuster_erweitert'
                    }
                    # Reichere mit Register-Daten an
                    return self._anreichern_mit_register_daten(result)

                # Standard-Formate (3 Gruppen)
                else:
                    zahl1, zahl2, kuerzel = match_data
                    # Normalisiere zu Slash-Format mit gepaddetem Jahr
                    stamm = f"{zahl1}/{zahl2.zfill(2)}"
                    kuerzel = kuerzel.upper()
                    kuerzel_norm = self.KUERZEL_NORMALISIERT.get(kuerzel, kuerzel)

                    result = {
                        'internes_az': f"{stamm}{kuerzel_norm}",
                        'stamm': stamm,
                        'kuerzel': kuerzel_norm,
                        'quelle': 'vollmuster'
                    }
                    # Reichere mit Register-Daten an
                    return self._anreichern_mit_register_daten(result)

        return None

    def _suche_stamm_mit_register(self, text: str) -> Optional[Dict]:
        """
        Sucht nach Stämmen und prüft gegen Aktenregister
        Unterstützt 1-4 Stellen vor dem Jahr (z.B. 1234/25)
        Nur Schrägstrich als Trennzeichen

        OCR-tolerant: Normalisiert Text vor der Suche
        """
        # OCR-Normalisierung für bessere Erkennung
        text = self._normalisiere_ocr_text(text)

        # Pattern für Aktenzeichen-Stamm
        patterns = [
            r'\b(\d{1,4})[/](\d{1,2})\b',  # 1234/01
        ]

        gefundene_staemme = set()  # Vermeide Duplikate

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    zahl1, zahl2 = match
                    # Normalisiere zu Slash-Format mit gepaddetem Jahr
                    stamm = f"{zahl1}/{zahl2.zfill(2)}"
                else:
                    stamm = match
                gefundene_staemme.add(stamm)

        # Prüfe alle gefundenen Stämme gegen Register
        for stamm in gefundene_staemme:
            register_info = self._pruefe_register(stamm)
            if register_info:
                return register_info

        return None

    def _suche_globale_muster(self, text: str) -> Optional[Dict]:
        """
        Globale Suche nach Aktenzeichen-Mustern im GESAMTEN Text.
        Wird als letzte Fallback-Methode verwendet, wenn andere Methoden fehlschlagen.

        Strategie:
        1. Suche alle Muster im Text
        2. Zähle Häufigkeiten
        3. Wähle das häufigste/konsistenteste Muster

        OCR-tolerant: Normalisiert Text vor der Suche
        """
        # OCR-Normalisierung
        text = self._normalisiere_ocr_text(text)

        # Sammle alle gefundenen Aktenzeichen mit Häufigkeit
        found_patterns = {}

        # Suche nach Vollmustern (mit Kürzel)
        patterns = self._get_patterns_erweitert() + self._get_patterns_standard()

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match_data in matches:
                # Erweiterte Formate (5 Gruppen)
                if len(match_data) == 5:
                    zahl1, zahl2, kuerzel, bereich, reno = match_data
                    stamm = f"{zahl1}/{zahl2.zfill(2)}"
                    kuerzel = kuerzel.upper()
                    kuerzel_norm = self.KUERZEL_NORMALISIERT.get(kuerzel, kuerzel)
                    internes_az = f"{stamm}{kuerzel_norm}"

                    # Zähle Vorkommen
                    if internes_az not in found_patterns:
                        found_patterns[internes_az] = {
                            'count': 0,
                            'stamm': stamm,
                            'kuerzel': kuerzel_norm,
                            'bereich': bereich,
                            'reno': reno.upper()
                        }
                    found_patterns[internes_az]['count'] += 1

                # Standard-Formate (3 Gruppen)
                elif len(match_data) == 3:
                    zahl1, zahl2, kuerzel = match_data
                    stamm = f"{zahl1}/{zahl2.zfill(2)}"
                    kuerzel = kuerzel.upper()
                    kuerzel_norm = self.KUERZEL_NORMALISIERT.get(kuerzel, kuerzel)
                    internes_az = f"{stamm}{kuerzel_norm}"

                    # Zähle Vorkommen
                    if internes_az not in found_patterns:
                        found_patterns[internes_az] = {
                            'count': 0,
                            'stamm': stamm,
                            'kuerzel': kuerzel_norm
                        }
                    found_patterns[internes_az]['count'] += 1

        # Wähle das häufigste Muster (mindestens 2 Vorkommen für Konfidenz)
        if found_patterns:
            # Sortiere nach Häufigkeit
            sorted_patterns = sorted(found_patterns.items(), key=lambda x: x[1]['count'], reverse=True)

            # Nehme häufigstes Muster (mindestens 1 Vorkommen)
            best_az, best_data = sorted_patterns[0]

            result = {
                'internes_az': best_az,
                'stamm': best_data['stamm'],
                'kuerzel': best_data['kuerzel'],
                'confidence': 'high' if best_data['count'] >= 2 else 'medium'
            }

            # Füge erweiterte Felder hinzu wenn vorhanden
            if 'bereich' in best_data:
                result['bereich'] = best_data['bereich']
            if 'reno' in best_data:
                result['reno'] = best_data['reno']

            # Reichere mit Register-Daten an
            return self._anreichern_mit_register_daten(result)

        return None

    def _anreichern_mit_register_daten(self, result: Dict) -> Dict:
        """
        Reichert ein Ergebnis mit Daten aus dem Register an (falls vorhanden).
        WICHTIG: Verwendet IMMER das Kürzel aus dem Register (falls vorhanden),
        nicht das aus dem Text extrahierte.

        Args:
            result: Dict mit 'stamm' und optional 'kuerzel'

        Returns:
            Angereichertes Dict mit Register-Kürzel, Aktenkurzbezeichnung und register_data
        """
        if not result or 'stamm' not in result:
            return result

        stamm = result['stamm']

        # Prüfe Register
        if 'Akte' not in self.akten_register.columns:
            return result

        treffer = self.akten_register[self.akten_register['Akte'] == stamm]

        if not treffer.empty:
            row = treffer.iloc[0]

            # WICHTIG: Verwende Kürzel aus Register (überschreibt Text-Kürzel)
            sb = row.get('SB', 'nicht-zugeordnet')
            sb_norm = self.KUERZEL_NORMALISIERT.get(sb, sb)

            # Aktualisiere Kürzel und internes_az mit Register-Daten
            result['kuerzel'] = sb_norm
            result['internes_az'] = f"{stamm}{sb_norm}"
            result['register_data'] = row.to_dict()

            # Suche nach Aktenkurzbezeichnung
            kurzbezeichnung_spalten = ['Kurzbezeichnung', 'Aktenkurzbezeichnung', 'Bez', 'Bezeichnung', 'KurzBez']

            for spalte in kurzbezeichnung_spalten:
                if spalte in self.akten_register.columns:
                    wert = row.get(spalte)
                    if pd.notna(wert) and str(wert).strip():
                        result['aktenkurzbezeichnung'] = str(wert).strip()
                        break

            # Markiere, dass Register verwendet wurde
            if result.get('quelle'):
                result['quelle'] = f"{result['quelle']}_mit_register"

        return result

    def _pruefe_register(self, stamm: str) -> Optional[Dict]:
        """
        Prüft, ob ein Stamm im Aktenregister existiert
        Returns internes AZ = Akte + SB aus Register + Aktenkurzbezeichnung (falls vorhanden)
        """
        # Prüfe ob erforderliche Spalten vorhanden sind
        if 'Akte' not in self.akten_register.columns:
            return None

        treffer = self.akten_register[self.akten_register['Akte'] == stamm]

        if not treffer.empty:
            row = treffer.iloc[0]
            sb = row.get('SB', 'nicht-zugeordnet')
            sb_norm = self.KUERZEL_NORMALISIERT.get(sb, sb)

            # Suche nach Aktenkurzbezeichnung in verschiedenen möglichen Spalten
            aktenkurzbezeichnung = None
            kurzbezeichnung_spalten = ['Kurzbezeichnung', 'Aktenkurzbezeichnung', 'Bez', 'Bezeichnung', 'KurzBez']

            for spalte in kurzbezeichnung_spalten:
                if spalte in self.akten_register.columns:
                    wert = row.get(spalte)
                    if pd.notna(wert) and str(wert).strip():
                        aktenkurzbezeichnung = str(wert).strip()
                        break

            result = {
                'internes_az': f"{stamm}{sb_norm}",
                'stamm': stamm,
                'kuerzel': sb_norm,
                'register_data': row.to_dict()
            }

            # Füge Aktenkurzbezeichnung hinzu, falls gefunden
            if aktenkurzbezeichnung:
                result['aktenkurzbezeichnung'] = aktenkurzbezeichnung

            return result

        return None

    def _suche_nach_kurzbezeichnung_im_text(self, text: str) -> Optional[Dict]:
        """
        Sucht nach Aktenkurzbezeichnungen im Text und findet das zugehörige
        Aktenzeichen aus dem Register.

        Bidirektionale Verknüpfung:
        - Kurzbezeichnung im Text → Aktenzeichen aus Register

        Returns:
            Dict mit internes_az, stamm, kuerzel, aktenkurzbezeichnung
        """
        if self.akten_register.empty or 'Akte' not in self.akten_register.columns:
            return None

        # Mögliche Spalten für Kurzbezeichnung
        kurzbezeichnung_spalten = ['Kurzbezeichnung', 'Aktenkurzbezeichnung', 'Bez', 'Bezeichnung', 'KurzBez', 'Kurzbez.']

        # Finde alle Kurzbezeichnungen im Register
        for spalte in kurzbezeichnung_spalten:
            if spalte not in self.akten_register.columns:
                continue

            for idx, row in self.akten_register.iterrows():
                kurzbez = row.get(spalte)

                if pd.isna(kurzbez) or not str(kurzbez).strip():
                    continue

                kurzbez_str = str(kurzbez).strip()

                # Suche diese Kurzbezeichnung im Text
                # Verwende Wortgrenzen für präzise Suche
                if len(kurzbez_str) >= 5:  # Mindestlänge für verlässliche Suche
                    # Escape special regex characters
                    kurzbez_escaped = re.escape(kurzbez_str)

                    # Suche case-insensitive
                    if re.search(rf'\b{kurzbez_escaped}\b', text, re.IGNORECASE):
                        # Kurzbezeichnung gefunden! Hole zugehöriges AZ
                        stamm = row.get('Akte')
                        sb = row.get('SB', 'nicht-zugeordnet')
                        sb_norm = self.KUERZEL_NORMALISIERT.get(sb, sb)

                        result = {
                            'internes_az': f"{stamm}{sb_norm}",
                            'stamm': stamm,
                            'kuerzel': sb_norm,
                            'aktenkurzbezeichnung': kurzbez_str,
                            'register_data': row.to_dict(),
                            'quelle': 'kurzbezeichnung_im_text'
                        }

                        return result

        return None

    def _suche_nach_parteien_im_text(self, text: str) -> Optional[Dict]:
        """
        Sucht nach Parteibezeichnungen im Text (z.B. "Müller ./. Stadtwerke")
        und findet das zugehörige Aktenzeichen aus dem Register.

        Erkennt Muster wie:
        - "Sache Stadtwerke / Müller"
        - "Müller ./. Stadtwerke"
        - "In der Angelegenheit Müller gegen Stadtwerke"
        - "Stadtwerke Hamburg ./. Müller"

        Verwendet Fuzzy-Matching für ungenaue Übereinstimmungen.

        Returns:
            Dict mit internes_az, stamm, kuerzel, aktenkurzbezeichnung
        """
        if self.akten_register.empty or 'Akte' not in self.akten_register.columns:
            return None

        # Patterns für Parteibezeichnungen
        # Format: Partei1 [Trennzeichen] Partei2
        parteien_patterns = [
            r'(?:sache|angelegenheit|betreff|re:|in der sache)\s*[:\-]?\s*([^./\n]{3,40})\s*(?:\./\.|/|gegen|vs\.?|v\.)\s*([^./\n]{3,40})',
            r'([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)\s*(?:\./\.|/|gegen|vs\.?|v\.)\s*([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)',
        ]

        gefundene_parteien = []

        for pattern in parteien_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                partei1 = match.group(1).strip()
                partei2 = match.group(2).strip()

                # Bereinige Parteien (entferne Satzzeichen am Ende)
                partei1 = re.sub(r'[,;.!?]+$', '', partei1).strip()
                partei2 = re.sub(r'[,;.!?]+$', '', partei2).strip()

                # Mindestlänge für verlässliche Suche
                if len(partei1) >= 3 and len(partei2) >= 3:
                    gefundene_parteien.append((partei1, partei2))

        if not gefundene_parteien:
            return None

        # Durchsuche Register nach passenden Parteien
        kurzbezeichnung_spalten = ['Kurzbezeichnung', 'Aktenkurzbezeichnung', 'Bez', 'Bezeichnung', 'KurzBez', 'Kurzbez.']

        for partei1, partei2 in gefundene_parteien:
            # Normalisiere für Vergleich
            partei1_norm = partei1.lower()
            partei2_norm = partei2.lower()

            for spalte in kurzbezeichnung_spalten:
                if spalte not in self.akten_register.columns:
                    continue

                for idx, row in self.akten_register.iterrows():
                    kurzbez = row.get(spalte)

                    if pd.isna(kurzbez) or not str(kurzbez).strip():
                        continue

                    kurzbez_str = str(kurzbez).strip().lower()

                    # Prüfe ob beide Parteien in Kurzbezeichnung vorkommen
                    # (in beliebiger Reihenfolge)
                    if partei1_norm in kurzbez_str and partei2_norm in kurzbez_str:
                        # Treffer! Hole zugehöriges AZ
                        stamm = row.get('Akte')
                        sb = row.get('SB', 'nicht-zugeordnet')
                        sb_norm = self.KUERZEL_NORMALISIERT.get(sb, sb)

                        result = {
                            'internes_az': f"{stamm}{sb_norm}",
                            'stamm': stamm,
                            'kuerzel': sb_norm,
                            'aktenkurzbezeichnung': str(row.get(spalte)).strip(),
                            'register_data': row.to_dict(),
                            'quelle': 'parteien_im_text',
                            'matched_parties': f"{partei1} / {partei2}"
                        }

                        return result

                    # Erweiterte Fuzzy-Suche: Prüfe auch einzelne Partei-Matches
                    # wenn Kurzbezeichnung Format "X ./. Y" hat
                    if './' in kurzbez_str or ' / ' in kurzbez_str or ' gegen ' in kurzbez_str:
                        kurzbez_parts = re.split(r'\s*(?:\./\.|/|gegen)\s*', kurzbez_str)
                        if len(kurzbez_parts) >= 2:
                            kbez_p1 = kurzbez_parts[0].strip()
                            kbez_p2 = kurzbez_parts[1].strip()

                            # Prüfe ob Parteien matchen (auch in umgekehrter Reihenfolge)
                            match1 = (partei1_norm in kbez_p1 and partei2_norm in kbez_p2)
                            match2 = (partei1_norm in kbez_p2 and partei2_norm in kbez_p1)

                            if match1 or match2:
                                stamm = row.get('Akte')
                                sb = row.get('SB', 'nicht-zugeordnet')
                                sb_norm = self.KUERZEL_NORMALISIERT.get(sb, sb)

                                result = {
                                    'internes_az': f"{stamm}{sb_norm}",
                                    'stamm': stamm,
                                    'kuerzel': sb_norm,
                                    'aktenkurzbezeichnung': str(row.get(spalte)).strip(),
                                    'register_data': row.to_dict(),
                                    'quelle': 'parteien_fuzzy_match',
                                    'matched_parties': f"{partei1} / {partei2}"
                                }

                                return result

        return None

    def _finde_kuerzel_im_text(self, text: str, position_sensitive: bool = False) -> Optional[str]:
        """
        Findet Kürzel im Text
        position_sensitive: Wenn True, muss Kürzel am Anfang sein (für Suffix)
        """
        text_upper = text.upper()

        if position_sensitive:
            # Kürzel muss am Anfang sein (mit max 1-2 Zeichen Abstand)
            for kuerzel in self.KUERZEL:
                if text_upper[:5].find(kuerzel) in [0, 1, 2]:
                    return kuerzel
        else:
            # Irgendwo im Text
            for kuerzel in self.KUERZEL:
                if kuerzel in text_upper:
                    return kuerzel

        return None

    def _suche_externe_aktenzeichen(self, text: str) -> List[str]:
        """
        Sucht nach externen Aktenzeichen (Gerichte, Versicherungen, etc.)
        """
        externe = []
        lines = text.split('\n')

        for line in lines:
            line_lower = line.lower()

            # Prüfe auf externe Keywords
            if any(kw in line_lower for kw in self.EXTERNE_KEYWORDS):
                # Extrahiere alles, was wie ein AZ aussieht
                # Typische Muster: 123 C 456/78, 12 O 345/24, Schaden-Nr. 123456789
                patterns = [
                    r'\b\d+\s+[A-Z]+\s+\d+/\d+\b',  # Gerichts-AZ
                    r'\b[A-Z]{2,}\d{6,}\b',  # Versicherungsnummern
                    r'\b\d{6,}\b'  # Schadensnummern
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, line)
                    externe.extend(matches)

        return list(set(externe))  # Duplikate entfernen

    def ermittle_sachbearbeiter(self, akt_info: Dict, analyse: Dict, sachbearbeiter_aus_text: Optional[str] = None) -> str:
        """
        Ermittelt den Sachbearbeiter basierend auf verschiedenen Quellen

        Priorität:
        0. Sachbearbeiter aus Anrede/Anschrift (HÖCHSTE PRIORITÄT!)
        1. Kürzel aus internem AZ
        2. Register-Daten
        3. "nicht-zugeordnet"
        """
        # 0. Sachbearbeiter aus Text (Anrede/Anschrift) - HÖCHSTE PRIORITÄT
        if sachbearbeiter_aus_text:
            return sachbearbeiter_aus_text

        # 1. Kürzel aus internem AZ
        if akt_info.get('kuerzel'):
            return akt_info['kuerzel']

        # 2. Register-Daten
        if 'register_data' in akt_info:
            sb = akt_info['register_data'].get('SB')
            if sb:
                return self.KUERZEL_NORMALISIERT.get(sb, sb)

        # 3. Fallback
        return 'nicht-zugeordnet'

    def generiere_dateiname(self, internes_az: Optional[str], mandant: Optional[str],
                           gegner: Optional[str], datum: Optional[str],
                           stichworte: List[str], aktenkurzbezeichnung: Optional[str] = None) -> str:
        """
        Generiert Dateinamen nach Schema:
        [Aktenzeichen]_[Aktenkurzbezeichnung]_[Mandant]_[Gegner]_[Datum]_[Stichworte].pdf

        Aktenkurzbezeichnung wird nur eingefügt, falls im Register vorhanden.
        """
        teile = []

        # 1. Aktenzeichen
        if internes_az:
            teile.append(self._bereinige_text(internes_az))
        else:
            teile.append("ohne-az")

        # 2. Aktenkurzbezeichnung (falls vorhanden)
        if aktenkurzbezeichnung:
            teile.append(self._bereinige_text(aktenkurzbezeichnung)[:30])

        # 3. Mandant
        if mandant:
            teile.append(self._bereinige_text(mandant)[:30])

        # 4. Gegner
        if gegner:
            teile.append(self._bereinige_text(gegner)[:30])

        # 5. Datum
        if datum:
            teile.append(self._bereinige_text(datum))

        # 6. Stichworte (max 3)
        if stichworte:
            stichworte_str = "_".join([self._bereinige_text(s) for s in stichworte[:3]])
            teile.append(stichworte_str[:40])

        dateiname = "_".join(teile) + ".pdf"
        return dateiname

    def _bereinige_text(self, text: str) -> str:
        """
        Bereinigt Text für Dateinamen:
        - Umlaute ersetzen
        - Sonderzeichen entfernen
        - Leerzeichen durch Unterstrich
        """
        if not text:
            return ""

        # Umlaute
        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
            'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'
        }
        for alt, neu in replacements.items():
            text = text.replace(alt, neu)

        # Nur alphanumerisch, Unterstrich, Bindestrich
        text = re.sub(r'[^a-zA-Z0-9_\-]', '_', text)

        # Mehrfache Unterstriche vermeiden
        text = re.sub(r'_+', '_', text)

        return text.strip('_')

    def hole_register_info(self, stamm: str) -> Optional[Dict]:
        """
        Holt zusätzliche Informationen aus dem Register
        (Mandant, Gegner, Kurzbez, etc.)
        """
        # Prüfe ob erforderliche Spalten vorhanden sind
        if 'Akte' not in self.akten_register.columns:
            return None

        treffer = self.akten_register[self.akten_register['Akte'] == stamm]

        if not treffer.empty:
            row = treffer.iloc[0]
            info = {
                'art': row.get('Art'),
                'kurzbez': row.get('Kurzbez.'),
                'gegner': row.get('Gegner'),
                'sb': row.get('SB')
            }

            # Parse Kurzbez nach "Mandant ./. Gegner"
            kurzbez = info.get('kurzbez', '')
            if isinstance(kurzbez, str) and './' in kurzbez:
                teile = kurzbez.split('./')
                if len(teile) >= 2:
                    info['mandant'] = teile[0].strip()
                    info['gegner_aus_kurzbez'] = teile[1].strip()

            return info

        return None

    def _erkenne_beteiligte_im_text(self, text: str) -> List[str]:
        """
        Extrahiert mögliche Beteiligte (Personen, Firmen) aus dem Text.

        Sucht nach:
        - Namen in typischen Kontexten (Absender, Empfänger, Betreff)
        - Firmennamen (GmbH, AG, e.V., etc.)
        - Personen mit Titeln (Dr., Prof., etc.)

        Returns:
            Liste von erkannten Beteiligten
        """
        beteiligte = []

        # 1. Firmennamen erkennen (mit Rechtsform)
        firmen_patterns = [
            r'([A-ZÄÖÜ][a-zäöüß\s&-]+(?:GmbH|AG|e\.V\.|KG|OHG|PartG|mbH|UG))',
            r'([A-ZÄÖÜ][a-zäöüß\s&-]+(?:Gesellschaft|Versicherung|Bank|Sparkasse|Stadtwerke|Gemeinde|Stadt))',
        ]

        for pattern in firmen_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                firma = match.strip()
                if len(firma) >= 5:  # Mindestlänge
                    beteiligte.append(firma)

        # 2. Personen mit Titeln
        personen_patterns = [
            r'(?:Dr\.|Prof\.|Dipl\.-Ing\.|RA|RAin)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)',
            r'(?:Herr|Frau)\s+(?:Dr\.\s+)?([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)',
        ]

        for pattern in personen_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                person = match.strip()
                if len(person) >= 3:
                    beteiligte.append(person)

        # 3. Namen aus typischen Kontexten
        kontext_patterns = [
            r'(?:Absender|Von|From):\s*([A-ZÄÖÜ][a-zäöüß\s&-]+)',
            r'(?:Mandant|Auftraggeber):\s*([A-ZÄÖÜ][a-zäöüß\s&-]+)',
            r'(?:Gegner|Beklagter|Kläger):\s*([A-ZÄÖÜ][a-zäöüß\s&-]+)',
            r'(?:Betreff|Betrifft|Re):\s*.*?([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)',
        ]

        for pattern in kontext_patterns:
            matches = re.findall(pattern, text[:2000], re.MULTILINE)  # Nur erste 2000 Zeichen
            for match in matches:
                name = match.strip()
                # Bereinige (entferne Satzzeichen am Ende)
                name = re.sub(r'[,;:.!?]+$', '', name).strip()
                if len(name) >= 3 and len(name) <= 50:
                    beteiligte.append(name)

        # Deduplizierung und Normalisierung
        beteiligte_unique = []
        seen = set()

        for b in beteiligte:
            b_norm = b.lower().strip()
            if b_norm not in seen and len(b_norm) >= 3:
                seen.add(b_norm)
                beteiligte_unique.append(b)

        return beteiligte_unique

    def _finde_akten_nach_beteiligten(self, beteiligte: List[str]) -> List[Dict]:
        """
        Findet passende Akten im Register basierend auf Beteiligten.

        Args:
            beteiligte: Liste von erkannten Beteiligten aus dem Text

        Returns:
            Liste von Treffern mit Score (sortiert nach Relevanz)
            Jeder Treffer: {'az': ..., 'stamm': ..., 'kuerzel': ..., 'score': ...,
                           'matched_beteiligte': [...], 'aktenkurzbezeichnung': ...}
        """
        if not beteiligte or self.akten_register.empty:
            return []

        treffer = []
        kurzbezeichnung_spalten = ['Kurzbezeichnung', 'Aktenkurzbezeichnung', 'Bez', 'Bezeichnung', 'KurzBez', 'Kurzbez.']

        # Durchsuche jede Akte im Register
        for idx, row in self.akten_register.iterrows():
            stamm = row.get('Akte')
            if pd.isna(stamm):
                continue

            # Sammle alle suchbaren Texte aus der Akte
            akte_texte = []

            # Kurzbezeichnung
            for spalte in kurzbezeichnung_spalten:
                if spalte in self.akten_register.columns:
                    wert = row.get(spalte)
                    if pd.notna(wert) and str(wert).strip():
                        akte_texte.append(str(wert).strip().lower())

            # Weitere relevante Spalten
            for spalte in ['Mandant', 'Gegner', 'Bemerkung', 'Notiz']:
                if spalte in self.akten_register.columns:
                    wert = row.get(spalte)
                    if pd.notna(wert) and str(wert).strip():
                        akte_texte.append(str(wert).strip().lower())

            if not akte_texte:
                continue

            # Prüfe, wie viele Beteiligte in dieser Akte vorkommen
            matched_beteiligte = []
            for beteiligter in beteiligte:
                beteiligter_norm = beteiligter.lower()

                # Prüfe ob Beteiligter in einem der Akte-Texte vorkommt
                for akte_text in akte_texte:
                    if beteiligter_norm in akte_text:
                        matched_beteiligte.append(beteiligter)
                        break

            # Wenn mindestens ein Beteiligter matched
            if matched_beteiligte:
                sb = row.get('SB', 'nicht-zugeordnet')
                sb_norm = self.KUERZEL_NORMALISIERT.get(sb, sb)

                # Hole Kurzbezeichnung
                aktenkurzbezeichnung = None
                for spalte in kurzbezeichnung_spalten:
                    if spalte in self.akten_register.columns:
                        wert = row.get(spalte)
                        if pd.notna(wert) and str(wert).strip():
                            aktenkurzbezeichnung = str(wert).strip()
                            break

                # Score: Anzahl gematchter Beteiligter
                score = len(matched_beteiligte)

                treffer.append({
                    'internes_az': f"{stamm}{sb_norm}",
                    'stamm': stamm,
                    'kuerzel': sb_norm,
                    'aktenkurzbezeichnung': aktenkurzbezeichnung,
                    'register_data': row.to_dict(),
                    'score': score,
                    'matched_beteiligte': matched_beteiligte,
                    'quelle': 'beteiligte_abgleich'
                })

        # Sortiere nach Score (höchster zuerst)
        treffer.sort(key=lambda x: x['score'], reverse=True)

        return treffer
