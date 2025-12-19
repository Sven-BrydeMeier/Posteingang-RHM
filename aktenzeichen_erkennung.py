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

    # Schlagwörter für "Ihr Zeichen" etc. (erweitert für bessere Erkennung)
    ZEICHEN_KEYWORDS = [
        'ihr zeichen', 'ihr zeichen:', 'ihr-zeichen', 'ihr-zeichen:',
        'unser zeichen', 'unser zeichen:', 'unser-zeichen', 'unser-zeichen:',
        'ihr az', 'ihr az.', 'ihr az:', 'ihr az.:',
        'ihr aktenzeichen', 'ihr aktenzeichen:', 'ihr-aktenzeichen',
        'dortiges aktenzeichen', 'dortiges aktenzeichen:',
        'verwendungszweck', 'verwendungszweck:',
        'aktenzeichen:', 'az:', 'az.:',
        'iz', 'iz:', 'iz.',  # Kurzform für "Ihr Zeichen"
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
        """Lädt aktenregister.xlsx, Blatt 'akten'"""
        df = pd.read_excel(excel_path, sheet_name='akten', header=1)

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

    def _get_patterns_erweitert(self):
        """Generiert erweiterte Patterns dynamisch mit allen Kürzeln. Unterstützt 1-4 Stellen."""
        kuerzel_regex = self.get_all_kuerzel_regex()
        return [
            rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})/([A-Z]{{2,3}})\b',  # 111/24SQ09/BO
            rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})([A-Z]{{2,3}})\b',   # 111/24SQ08BO
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

        # Priorität 1: "Ihr Zeichen / Unser Zeichen" etc.
        zeichen_az = self._suche_in_zeichen_feldern(text)
        if zeichen_az:
            result.update(zeichen_az)
            result['quelle'] = 'zeichen_feld'
            return result

        # Priorität 2: Vollmuster im Text
        vollmuster = self._suche_vollmuster(text)
        if vollmuster:
            result.update(vollmuster)
            result['quelle'] = 'vollmuster'
            return result

        # Priorität 3: Stämme mit Registertreffer
        register_az = self._suche_stamm_mit_register(text)
        if register_az:
            result.update(register_az)
            result['quelle'] = 'register'
            return result

        # Externe Aktenzeichen sammeln (immer)
        result['externe_az'] = self._suche_externe_aktenzeichen(text)

        return result

    def _suche_in_zeichen_feldern(self, text: str) -> Optional[Dict]:
        """
        Sucht nach Aktenzeichen in "Ihr Zeichen / Unser Zeichen" etc. Zeilen
        Höchste Priorität!

        Erweitert: Durchsucht 2 Zeilen VOR und 2 Zeilen NACH dem Keyword
        sowie die gleiche Zeile (insgesamt 5 Zeilen Kontext)
        """
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Prüfe, ob Zeile ein Zeichen-Keyword enthält
            if any(kw in line_lower for kw in self.ZEICHEN_KEYWORDS):
                # Suche in den 2 Zeilen VOR, der aktuellen Zeile, und den 2 Zeilen NACH dem Keyword
                such_text = ""

                # 2 Zeilen vorher
                for offset in range(2, 0, -1):
                    if i - offset >= 0:
                        such_text += lines[i - offset] + " "

                # Aktuelle Zeile
                such_text += line + " "

                # 2 Zeilen nachher
                for offset in range(1, 3):
                    if i + offset < len(lines):
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
                        suffix = such_text[start_pos:start_pos + 20]  # max 20 Zeichen

                        # Suche Kürzel im Suffix (direkt nach Stamm, ohne Leerzeichen)
                        kuerzel = self._finde_kuerzel_im_text(suffix, position_sensitive=True)

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
        """
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
        """
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

    def _anreichern_mit_register_daten(self, result: Dict) -> Dict:
        """
        Reichert ein Ergebnis mit Daten aus dem Register an (falls vorhanden).

        Args:
            result: Dict mit 'stamm' und 'kuerzel'

        Returns:
            Angereichertes Dict mit 'aktenkurzbezeichnung' (falls im Register gefunden)
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

            # Suche nach Aktenkurzbezeichnung
            kurzbezeichnung_spalten = ['Kurzbezeichnung', 'Aktenkurzbezeichnung', 'Bez', 'Bezeichnung', 'KurzBez']

            for spalte in kurzbezeichnung_spalten:
                if spalte in self.akten_register.columns:
                    wert = row.get(spalte)
                    if pd.notna(wert) and str(wert).strip():
                        result['aktenkurzbezeichnung'] = str(wert).strip()
                        break

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
