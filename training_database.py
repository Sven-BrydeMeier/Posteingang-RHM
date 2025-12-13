"""
Training-Datenbank für manuelle Zuordnungen
Speichert Absender-Muster und Positionen für verbessertes maschinelles Lernen
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import re
import json


class TrainingDatabase:
    """
    Verwaltet Trainingsdaten für manuelle Dokumentenzuordnungen.

    Speichert:
    - Absender-Name
    - Position im Dokument (Seite, X, Y, Breite, Höhe)
    - Aktenzeichen-Muster
    - Zugeordneter Sachbearbeiter
    - Timestamp
    """

    def __init__(self, storage_path: Path):
        """
        Args:
            storage_path: Verzeichnis für Training-Datenbank
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.db_file = self.storage_path / 'training_data.xlsx'
        self.absender_db_file = self.storage_path / 'absender_patterns.xlsx'

        # Initialisiere Datenbanken
        self._init_databases()

    def _init_databases(self):
        """Initialisiert leere Datenbanken falls nicht vorhanden"""
        # Training-Daten
        if not self.db_file.exists():
            df = pd.DataFrame(columns=[
                'timestamp',
                'absender',
                'absender_normalisiert',
                'aktenzeichen',
                'sachbearbeiter',
                'seite',
                'position_x',
                'position_y',
                'breite',
                'hoehe',
                'dokument_hash',
                'erfolg'  # Bool: War die Zuordnung erfolgreich?
            ])
            df.to_excel(self.db_file, index=False)

        # Absender-Muster
        if not self.absender_db_file.exists():
            df = pd.DataFrame(columns=[
                'absender_normalisiert',
                'sachbearbeiter',
                'aktenzeichen_muster',
                'position_seite',
                'position_x',
                'position_y',
                'haeufigkeit',  # Wie oft kam dieser Absender vor
                'letztes_auftreten'
            ])
            df.to_excel(self.absender_db_file, index=False)

    def save_training_entry(
        self,
        absender: str,
        aktenzeichen: str,
        sachbearbeiter: str,
        seite: int = 1,
        position: Optional[Tuple[float, float, float, float]] = None,
        dokument_hash: Optional[str] = None
    ) -> None:
        """
        Speichert einen neuen Training-Eintrag

        Args:
            absender: Name des Absenders (roh)
            aktenzeichen: Erkanntes Aktenzeichen
            sachbearbeiter: Zugeordneter Sachbearbeiter
            seite: Seitennummer (1-basiert)
            position: Optional (x, y, breite, hoehe) in Prozent (0-100)
            dokument_hash: Optional Hash zur Duplikat-Vermeidung
        """
        df = pd.read_excel(self.db_file)

        # Normalisiere Absender (für Matching)
        absender_norm = self._normalize_absender(absender)

        # Position extrahieren
        pos_x, pos_y, breite, hoehe = (None, None, None, None)
        if position:
            pos_x, pos_y, breite, hoehe = position

        # Neuer Eintrag
        new_entry = pd.DataFrame([{
            'timestamp': datetime.now().isoformat(),
            'absender': absender,
            'absender_normalisiert': absender_norm,
            'aktenzeichen': aktenzeichen,
            'sachbearbeiter': sachbearbeiter,
            'seite': seite,
            'position_x': pos_x,
            'position_y': pos_y,
            'breite': breite,
            'hoehe': hoehe,
            'dokument_hash': dokument_hash,
            'erfolg': True
        }])

        df = pd.concat([df, new_entry], ignore_index=True)
        df.to_excel(self.db_file, index=False)

        # Update Absender-Muster
        self._update_absender_pattern(absender_norm, aktenzeichen, sachbearbeiter, seite, (pos_x, pos_y))

    def _normalize_absender(self, absender: str) -> str:
        """
        Normalisiert Absender-Namen für besseres Matching

        Beispiele:
        - "Amtsgericht Hamburg" → "amtsgericht hamburg"
        - "AG Hamburg" → "ag hamburg"
        - "Versicherung XYZ GmbH" → "versicherung xyz"
        """
        if not absender:
            return ""

        # Kleinbuchstaben
        absender = absender.lower()

        # Entferne Rechtsformen
        rechtsformen = ['gmbh', 'ag', 'kg', 'ohg', 'gbr', 'e.v.', 'e. v.']
        for rf in rechtsformen:
            absender = absender.replace(rf, '')

        # Entferne Sonderzeichen
        absender = re.sub(r'[^\w\s]', ' ', absender)

        # Mehrfache Leerzeichen entfernen
        absender = re.sub(r'\s+', ' ', absender).strip()

        return absender

    def _update_absender_pattern(
        self,
        absender_norm: str,
        aktenzeichen: str,
        sachbearbeiter: str,
        seite: int,
        position: Tuple[Optional[float], Optional[float]]
    ):
        """Aktualisiert Absender-Muster-Datenbank"""
        df = pd.read_excel(self.absender_db_file)

        # Suche existierendes Muster
        mask = (df['absender_normalisiert'] == absender_norm) & (df['sachbearbeiter'] == sachbearbeiter)

        if mask.any():
            # Update existierendes Muster
            idx = df[mask].index[0]
            df.loc[idx, 'haeufigkeit'] = df.loc[idx, 'haeufigkeit'] + 1
            df.loc[idx, 'letztes_auftreten'] = datetime.now().isoformat()

            # Update Position (gewichteter Durchschnitt)
            if position[0] is not None and position[1] is not None:
                old_count = df.loc[idx, 'haeufigkeit'] - 1
                new_count = df.loc[idx, 'haeufigkeit']

                old_x = df.loc[idx, 'position_x'] or 0
                old_y = df.loc[idx, 'position_y'] or 0

                df.loc[idx, 'position_x'] = (old_x * old_count + position[0]) / new_count
                df.loc[idx, 'position_y'] = (old_y * old_count + position[1]) / new_count
        else:
            # Neues Muster
            new_pattern = pd.DataFrame([{
                'absender_normalisiert': absender_norm,
                'sachbearbeiter': sachbearbeiter,
                'aktenzeichen_muster': self._extract_az_pattern(aktenzeichen),
                'position_seite': seite,
                'position_x': position[0],
                'position_y': position[1],
                'haeufigkeit': 1,
                'letztes_auftreten': datetime.now().isoformat()
            }])
            df = pd.concat([df, new_pattern], ignore_index=True)

        df.to_excel(self.absender_db_file, index=False)

    def _extract_az_pattern(self, aktenzeichen: str) -> str:
        """
        Extrahiert Muster aus Aktenzeichen

        Beispiele:
        - "12345/01M" → "XXXXX/XXM" (Zahlen durch X)
        - "54321/25SQ" → "XXXXX/XXSQ"
        """
        if not aktenzeichen:
            return ""

        # Ersetze Zahlen durch X
        pattern = re.sub(r'\d', 'X', aktenzeichen)
        return pattern

    def find_matching_pattern(self, absender: str) -> Optional[Dict]:
        """
        Findet passendes Absender-Muster in der Datenbank

        Args:
            absender: Absender-Name (roh)

        Returns:
            Dict mit Muster-Daten oder None
        """
        absender_norm = self._normalize_absender(absender)

        if not absender_norm:
            return None

        df = pd.read_excel(self.absender_db_file)

        if df.empty:
            return None

        # Exakte Übereinstimmung
        mask = df['absender_normalisiert'] == absender_norm

        if mask.any():
            # Nehme häufigste Übereinstimmung
            matches = df[mask].sort_values('haeufigkeit', ascending=False)
            best_match = matches.iloc[0]

            return {
                'sachbearbeiter': best_match['sachbearbeiter'],
                'aktenzeichen_muster': best_match['aktenzeichen_muster'],
                'position_seite': int(best_match['position_seite']) if pd.notna(best_match['position_seite']) else 1,
                'position_x': float(best_match['position_x']) if pd.notna(best_match['position_x']) else None,
                'position_y': float(best_match['position_y']) if pd.notna(best_match['position_y']) else None,
                'haeufigkeit': int(best_match['haeufigkeit'])
            }

        # Fuzzy-Matching: Teil-String-Übereinstimmung
        for _, row in df.iterrows():
            stored_absender = row['absender_normalisiert']

            # Prüfe ob mindestens 60% Übereinstimmung
            if self._similarity(absender_norm, stored_absender) > 0.6:
                return {
                    'sachbearbeiter': row['sachbearbeiter'],
                    'aktenzeichen_muster': row['aktenzeichen_muster'],
                    'position_seite': int(row['position_seite']) if pd.notna(row['position_seite']) else 1,
                    'position_x': float(row['position_x']) if pd.notna(row['position_x']) else None,
                    'position_y': float(row['position_y']) if pd.notna(row['position_y']) else None,
                    'haeufigkeit': int(row['haeufigkeit']),
                    'fuzzy_match': True
                }

        return None

    def _similarity(self, str1: str, str2: str) -> float:
        """
        Einfache String-Ähnlichkeit (Jaccard-Index)

        Returns:
            Float zwischen 0 und 1
        """
        if not str1 or not str2:
            return 0.0

        set1 = set(str1.split())
        set2 = set(str2.split())

        intersection = set1.intersection(set2)
        union = set1.union(set2)

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def get_statistics(self) -> Dict:
        """Gibt Statistiken über Trainingsdaten zurück"""
        df = pd.read_excel(self.db_file)
        absender_df = pd.read_excel(self.absender_db_file)

        return {
            'total_training_entries': len(df),
            'unique_absender': len(absender_df),
            'sachbearbeiter_counts': df['sachbearbeiter'].value_counts().to_dict() if not df.empty else {},
            'most_common_absender': absender_df.nlargest(5, 'haeufigkeit')[['absender_normalisiert', 'haeufigkeit']].to_dict('records') if not absender_df.empty else []
        }

    def search_training_data(
        self,
        absender: Optional[str] = None,
        sachbearbeiter: Optional[str] = None,
        limit: int = 10
    ) -> pd.DataFrame:
        """
        Durchsucht Trainingsdaten

        Args:
            absender: Optional Absender-Filter
            sachbearbeiter: Optional Sachbearbeiter-Filter
            limit: Max. Anzahl Ergebnisse

        Returns:
            DataFrame mit Ergebnissen
        """
        df = pd.read_excel(self.db_file)

        if absender:
            absender_norm = self._normalize_absender(absender)
            df = df[df['absender_normalisiert'].str.contains(absender_norm, case=False, na=False)]

        if sachbearbeiter:
            df = df[df['sachbearbeiter'] == sachbearbeiter]

        return df.sort_values('timestamp', ascending=False).head(limit)

    def export_to_json(self, output_path: str) -> bool:
        """
        Exportiert Training-Datenbank nach JSON

        Args:
            output_path: Pfad zur JSON-Datei

        Returns:
            True bei Erfolg
        """
        try:
            export_data = {
                'export_date': datetime.now().isoformat(),
                'version': '1.0',
                'training_data': [],
                'absender_patterns': []
            }

            # Training Data
            if self.db_file.exists():
                df = pd.read_excel(self.db_file)
                export_data['training_data'] = df.to_dict('records')

            # Absender Patterns
            if self.absender_file.exists():
                df = pd.read_excel(self.absender_file)
                export_data['absender_patterns'] = df.to_dict('records')

            # Schreibe JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"Export-Fehler: {e}")
            return False

    def import_from_json(self, input_path: str, merge: bool = True) -> bool:
        """
        Importiert Training-Datenbank aus JSON

        Args:
            input_path: Pfad zur JSON-Datei
            merge: True = mit vorhandenen Daten mergen, False = überschreiben

        Returns:
            True bei Erfolg
        """
        try:
            # Lese JSON
            with open(input_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            # Training Data importieren
            if import_data.get('training_data'):
                new_df = pd.DataFrame(import_data['training_data'])

                if merge and self.db_file.exists():
                    # Merge mit vorhandenen Daten
                    existing_df = pd.read_excel(self.db_file)
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    # Entferne Duplikate basierend auf Absender + Aktenzeichen
                    combined_df = combined_df.drop_duplicates(
                        subset=['absender_normalisiert', 'aktenzeichen'],
                        keep='last'
                    )
                    combined_df.to_excel(self.db_file, index=False)
                else:
                    new_df.to_excel(self.db_file, index=False)

            # Absender Patterns importieren
            if import_data.get('absender_patterns'):
                new_df = pd.DataFrame(import_data['absender_patterns'])

                if merge and self.absender_file.exists():
                    existing_df = pd.read_excel(self.absender_file)
                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                    # Gruppiere und aktualisiere Häufigkeiten
                    combined_df = combined_df.groupby(['absender_normalisiert', 'sachbearbeiter']).agg({
                        'haeufigkeit': 'sum',
                        'letztes_vorkommen': 'max',
                        'pattern': 'first'
                    }).reset_index()
                    combined_df.to_excel(self.absender_file, index=False)
                else:
                    new_df.to_excel(self.absender_file, index=False)

            return True

        except Exception as e:
            print(f"Import-Fehler: {e}")
            return False

    def clear_all_data(self) -> bool:
        """
        Löscht alle Training-Daten (mit Bestätigung!)

        Returns:
            True bei Erfolg
        """
        try:
            if self.db_file.exists():
                self.db_file.unlink()
            if self.absender_file.exists():
                self.absender_file.unlink()
            return True
        except Exception as e:
            print(f"Fehler beim Löschen: {e}")
            return False
