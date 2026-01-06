"""
Excel-basierter Sync zwischen RHM-App und Kanzleisoftware (RA-MICRO, DATEV)

Workflow:
1. Export aus RA-MICRO/DATEV → Excel
2. Import in RHM-App als Aktenregister
3. RHM-App verarbeitet Dokumente
4. Export aus RHM-App → Excel
5. Import in RA-MICRO/DATEV

Vorteile:
- Keine API-Abhängigkeiten
- Funktioniert mit allen Versionen
- Keine zusätzlichen Kosten
- Flexibel und erweiterbar
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from io import BytesIO
import re


class KanzleiSoftwareSync:
    """Excel-basierter Sync mit RA-MICRO und DATEV"""

    # Bekannte Spalten-Mappings
    RAMICRO_COLUMN_MAPPING = {
        'AktenNr': 'internes_az',
        'Akte': 'internes_az',
        'Aktenzeichen': 'internes_az',
        'Mandant': 'mandant',
        'Mandantenname': 'mandant',
        'Gegner': 'gegner',
        'Gegenpartei': 'gegner',
        'Sachbearbeiter': 'kuerzel',
        'SB': 'kuerzel',
        'Bearbeiter': 'kuerzel',
        'Anlage': 'angelegt',
        'Anlagedatum': 'angelegt'
    }

    DATEV_COLUMN_MAPPING = {
        'Aktennummer': 'internes_az',
        'Akten-Nr': 'internes_az',
        'Akten-Nr.': 'internes_az',
        'Mandant': 'mandant',
        'Mandantenname': 'mandant',
        'Gegner': 'gegner',
        'Bearbeiter': 'kuerzel',
        'Sachbearbeiter': 'kuerzel',
        'Anlagedatum': 'angelegt',
        'Datum': 'angelegt'
    }

    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialisiert Sync-Manager

        Args:
            storage_dir: Optional storage directory für Logs
        """
        self.storage_dir = Path(storage_dir) if storage_dir else Path(".")

    def detect_format(self, df: pd.DataFrame) -> str:
        """
        Erkennt automatisch das Format (RA-MICRO, DATEV oder Unbekannt)

        Args:
            df: DataFrame mit Import-Daten

        Returns:
            'ramicro', 'datev' oder 'unknown'
        """
        columns_lower = [col.lower() for col in df.columns]

        # RA-MICRO typische Spalten
        ramicro_indicators = ['aktennr', 'akte', 'sb']
        ramicro_score = sum(1 for ind in ramicro_indicators if any(ind in col for col in columns_lower))

        # DATEV typische Spalten
        datev_indicators = ['akten-nr', 'aktennummer', 'bearbeiter']
        datev_score = sum(1 for ind in datev_indicators if any(ind in col for col in columns_lower))

        if ramicro_score > datev_score:
            return 'ramicro'
        elif datev_score > ramicro_score:
            return 'datev'
        else:
            return 'unknown'

    def import_from_ramicro_export(self, excel_path_or_bytes) -> pd.DataFrame:
        """
        Importiert RA-MICRO Excel-Export als RHM Aktenregister

        Args:
            excel_path_or_bytes: Pfad zur Excel-Datei oder BytesIO

        Returns:
            DataFrame im RHM-Format
        """
        # Lese Excel
        if isinstance(excel_path_or_bytes, (str, Path)):
            df = pd.read_excel(excel_path_or_bytes)
        else:
            df = pd.read_excel(excel_path_or_bytes)

        # Automatisches Mapping
        rhm_data = {}

        for ramicro_col, rhm_col in self.RAMICRO_COLUMN_MAPPING.items():
            # Suche Spalte (case-insensitive)
            matching_col = None
            for col in df.columns:
                if col.lower() == ramicro_col.lower():
                    matching_col = col
                    break

            if matching_col:
                rhm_data[rhm_col] = df[matching_col]

        # Erstelle RHM DataFrame
        rhm_df = pd.DataFrame(rhm_data)

        # Füge Quelle hinzu
        rhm_df['quelle'] = 'RA-MICRO'

        # Bereinige Aktenzeichen
        if 'internes_az' in rhm_df.columns:
            rhm_df['internes_az'] = rhm_df['internes_az'].astype(str).str.strip()

        return rhm_df

    def import_from_datev_export(self, excel_path_or_bytes) -> pd.DataFrame:
        """
        Importiert DATEV Excel-Export als RHM Aktenregister

        Args:
            excel_path_or_bytes: Pfad zur Excel-Datei oder BytesIO

        Returns:
            DataFrame im RHM-Format
        """
        # Lese Excel
        if isinstance(excel_path_or_bytes, (str, Path)):
            df = pd.read_excel(excel_path_or_bytes)
        else:
            df = pd.read_excel(excel_path_or_bytes)

        # Automatisches Mapping
        rhm_data = {}

        for datev_col, rhm_col in self.DATEV_COLUMN_MAPPING.items():
            # Suche Spalte (case-insensitive)
            matching_col = None
            for col in df.columns:
                if col.lower() == datev_col.lower():
                    matching_col = col
                    break

            if matching_col:
                rhm_data[rhm_col] = df[matching_col]

        # Erstelle RHM DataFrame
        rhm_df = pd.DataFrame(rhm_data)

        # Füge Quelle hinzu
        rhm_df['quelle'] = 'DATEV'

        # Bereinige Aktenzeichen
        if 'internes_az' in rhm_df.columns:
            rhm_df['internes_az'] = rhm_df['internes_az'].astype(str).str.strip()

        return rhm_df

    def import_auto(self, excel_path_or_bytes) -> Tuple[pd.DataFrame, str]:
        """
        Automatischer Import mit Format-Erkennung

        Args:
            excel_path_or_bytes: Pfad zur Excel-Datei oder BytesIO

        Returns:
            (DataFrame im RHM-Format, erkanntes Format)
        """
        # Lese Excel temporär für Format-Erkennung
        if isinstance(excel_path_or_bytes, (str, Path)):
            df_temp = pd.read_excel(excel_path_or_bytes)
        else:
            # Reset stream position
            excel_path_or_bytes.seek(0)
            df_temp = pd.read_excel(excel_path_or_bytes)

        # Erkenne Format
        detected_format = self.detect_format(df_temp)

        # Import basierend auf Format
        if detected_format == 'ramicro':
            # Reset stream wenn BytesIO
            if hasattr(excel_path_or_bytes, 'seek'):
                excel_path_or_bytes.seek(0)
            return self.import_from_ramicro_export(excel_path_or_bytes), 'RA-MICRO'

        elif detected_format == 'datev':
            if hasattr(excel_path_or_bytes, 'seek'):
                excel_path_or_bytes.seek(0)
            return self.import_from_datev_export(excel_path_or_bytes), 'DATEV'

        else:
            # Fallback: Versuche generisches Mapping
            return self._import_generic(excel_path_or_bytes), 'Unbekannt'

    def _import_generic(self, excel_path_or_bytes) -> pd.DataFrame:
        """Generischer Import für unbekannte Formate"""
        if isinstance(excel_path_or_bytes, (str, Path)):
            df = pd.read_excel(excel_path_or_bytes)
        else:
            df = pd.read_excel(excel_path_or_bytes)

        # Versuche intelligentes Mapping basierend auf Spaltennamen
        rhm_data = {}

        columns_lower = {col: col.lower() for col in df.columns}

        # Suche nach Aktenzeichen
        for col, col_lower in columns_lower.items():
            if any(keyword in col_lower for keyword in ['akte', 'zeichen', 'nummer', 'nr']):
                rhm_data['internes_az'] = df[col]
                break

        # Suche nach Mandant
        for col, col_lower in columns_lower.items():
            if 'mandant' in col_lower or 'client' in col_lower:
                rhm_data['mandant'] = df[col]
                break

        # Suche nach Gegner
        for col, col_lower in columns_lower.items():
            if 'gegner' in col_lower or 'gegenpartei' in col_lower:
                rhm_data['gegner'] = df[col]
                break

        # Suche nach Sachbearbeiter
        for col, col_lower in columns_lower.items():
            if any(keyword in col_lower for keyword in ['sachbearbeiter', 'bearbeiter', 'sb']):
                rhm_data['kuerzel'] = df[col]
                break

        rhm_df = pd.DataFrame(rhm_data) if rhm_data else pd.DataFrame()
        rhm_df['quelle'] = 'Import'

        return rhm_df

    def export_for_ramicro_import(self, processed_docs: List[Dict], include_postkorb: bool = True) -> bytes:
        """
        Exportiert verarbeitete Dokumente für RA-MICRO 2025 Import

        Unterstützt:
        - E-Akte Ablage (basierend auf Aktenzeichen)
        - Postkorb-Zuordnung (basierend auf Sachbearbeiter/Diktatzeichen)

        Args:
            processed_docs: Liste von verarbeiteten Dokumenten
            include_postkorb: Wenn True, werden Dokumente auch dem Postkorb zugeordnet

        Returns:
            Excel-Datei als Bytes (kompatibel mit RA-MICRO Akten Import)
        """
        rows = []

        # RA-MICRO Sachbearbeiter-Mapping (Diktatzeichen → Vollname für Postkorb)
        sb_vollnamen = {
            'SQ': 'RA Meier',
            'TS': 'RAin Meyer',
            'M': 'RAin Marquardsen',
            'CV': 'RA Ostertun',
            'FÜ': 'RA Dr. Fürsen'
        }

        for idx, doc in enumerate(processed_docs, start=1):
            # Basis-Infos extrahieren
            akt_info = doc.get('aktenzeichen_info', {})
            analyse = doc.get('analyse', {})
            deadline_info = analyse.get('deadline_info', {})
            earliest_deadline = deadline_info.get('earliest_deadline', {})

            aktenzeichen = akt_info.get('internes_az', '')
            sachbearbeiter = doc.get('sachbearbeiter', '')
            dateiname = doc.get('dateiname', '')

            # Dokumentdatum (für RA-MICRO Format TT.MM.JJJJ)
            dok_datum = analyse.get('datum', datetime.now().strftime('%d.%m.%Y'))

            # Betreff aus Stichworte
            stichworte = analyse.get('stichworte', [])
            betreff = ', '.join(stichworte[:3]) if stichworte else 'Posteingang'

            row = {
                # === E-AKTE FELDER ===
                'Akte': aktenzeichen,                    # Aktenzeichen für E-Akte Zuordnung
                'AktenNr': aktenzeichen,                 # Alternative Spalte
                'Rubrik': 'Posteingang',                 # E-Akte Rubrik/Kategorie
                'Dokumenttyp': 'Schriftsatz',            # RA-MICRO Dokumenttyp
                'Dokumentart': 'Eingehend',              # Eingehend/Ausgehend

                # === POSTKORB FELDER ===
                'Diktatzeichen': sachbearbeiter,         # Für Postkorb-Zuordnung
                'SB': sachbearbeiter,                    # Sachbearbeiter-Kürzel
                'Postkorb': 'J' if include_postkorb else 'N',  # J = In Postkorb ablegen
                'PostkorbEmpfänger': sachbearbeiter,     # Welcher Postkorb

                # === DOKUMENT-METADATEN ===
                'Datum': dok_datum,                      # Dokumentdatum
                'Eingangsdatum': datetime.now().strftime('%d.%m.%Y'),  # Eingangsdatum
                'Betreff': betreff,                      # Betreff/Kurztext
                'Bemerkung': f"Absender: {analyse.get('gegner', 'Unbekannt')}",
                'Absender': analyse.get('gegner', ''),
                'Empfänger': analyse.get('mandant', ''),

                # === DATEI-REFERENZ ===
                'Dateiname': dateiname,                  # Original-Dateiname
                'DateiPfad': f"./{sachbearbeiter}/{dateiname}",  # Relativer Pfad in ZIP
                'LfdNr': idx,                            # Laufende Nummer

                # === FRISTEN ===
                'Frist': earliest_deadline.get('datum', ''),
                'Wiedervorlage': earliest_deadline.get('datum', ''),
                'Priorität': deadline_info.get('priority', 'Normal'),

                # === VERARBEITUNGS-INFO ===
                'Verarbeitet': datetime.now().strftime('%d.%m.%Y %H:%M'),
                'Quelle': 'RHM Posteingang'
            }

            rows.append(row)

        df = pd.DataFrame(rows)

        # Exportiere als Excel mit mehreren Sheets
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Haupt-Sheet: Alle Daten
            df.to_excel(writer, sheet_name='RA-MICRO Import', index=False)

            # Formatiere Spaltenbreiten
            worksheet = writer.sheets['RA-MICRO Import']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).map(len).max() if len(df) > 0 else 10,
                    len(col)
                )
                # Excel Spalten: A, B, C, ... AA, AB, etc.
                col_letter = self._get_column_letter(idx)
                worksheet.column_dimensions[col_letter].width = min(max_length + 2, 50)

            # Zusätzliches Sheet: Import-Anleitung
            anleitung_df = pd.DataFrame({
                'Schritt': [
                    '1. ZIP-Datei entpacken',
                    '2. RA-MICRO öffnen',
                    '3. Akten → Import/Export → Dokumente importieren',
                    '4. Diese Excel-Datei auswählen',
                    '5. Spalten-Mapping prüfen',
                    '6. Import starten'
                ],
                'Hinweis': [
                    'Die PDFs liegen in Unterordnern nach Sachbearbeiter sortiert',
                    'Version 2025 oder höher empfohlen',
                    'Alternativ: E-Akte → Sammelimport',
                    'Sheet "RA-MICRO Import" wird verwendet',
                    'Akte, Diktatzeichen, Dateiname müssen gemappt sein',
                    'Dokumente werden in E-Akte UND Postkorb abgelegt'
                ]
            })
            anleitung_df.to_excel(writer, sheet_name='Anleitung', index=False)

            # Sheet: Postkorb-Übersicht
            postkorb_stats = df.groupby('SB').size().reset_index(name='Anzahl Dokumente')
            postkorb_stats['Postkorb-Empfänger'] = postkorb_stats['SB'].map(
                lambda x: sb_vollnamen.get(x, x)
            )
            postkorb_stats.to_excel(writer, sheet_name='Postkorb-Übersicht', index=False)

        buffer.seek(0)
        return buffer.getvalue()

    def _get_column_letter(self, col_idx: int) -> str:
        """Konvertiert Spaltenindex (0-basiert) zu Excel-Spaltenbuchstabe"""
        result = ""
        while col_idx >= 0:
            result = chr(col_idx % 26 + 65) + result
            col_idx = col_idx // 26 - 1
        return result

    def export_for_datev_import(self, processed_docs: List[Dict]) -> bytes:
        """
        Exportiert verarbeitete Dokumente für DATEV Import

        Args:
            processed_docs: Liste von verarbeiteten Dokumenten

        Returns:
            Excel-Datei als Bytes
        """
        rows = []

        for doc in processed_docs:
            # Deadline-Info extrahieren
            deadline_info = doc.get('analyse', {}).get('deadline_info', {})
            earliest_deadline = deadline_info.get('earliest_deadline', {})

            row = {
                'Akten-Nr.': doc.get('aktenzeichen_info', {}).get('internes_az', ''),
                'Belegart': 'Posteingang',
                'Belegdatum': doc.get('analyse', {}).get('datum', datetime.now().strftime('%d.%m.%Y')),
                'Absender': doc.get('analyse', {}).get('gegner', ''),
                'Empfänger': doc.get('analyse', {}).get('mandant', ''),
                'Bearbeiter': doc.get('sachbearbeiter', ''),
                'Dokumentname': doc.get('dateiname', ''),
                'Beschreibung': ', '.join(doc.get('analyse', {}).get('stichworte', [])[:3]),
                'Wiedervorlagedatum': earliest_deadline.get('datum', ''),
                'Priorität': deadline_info.get('priority', ''),
                'Erfassungsdatum': datetime.now().strftime('%d.%m.%Y')
            }

            rows.append(row)

        df = pd.DataFrame(rows)

        # Exportiere als Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Belege', index=False)

            # Formatiere Spaltenbreiten
            worksheet = writer.sheets['Belege']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).map(len).max(),
                    len(col)
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)

        buffer.seek(0)
        return buffer.getvalue()

    def create_mapping_template(self) -> bytes:
        """
        Erstellt Excel-Template mit Beispiel-Daten für Mapping

        Returns:
            Excel-Template als Bytes
        """
        # Beispieldaten
        examples = {
            'RHM-Standard': pd.DataFrame({
                'internes_az': ['12345/25SQ', '67890/25TS'],
                'kuerzel': ['SQ', 'TS'],
                'mandant': ['Max Mustermann', 'Erika Musterfrau'],
                'gegner': ['Amtsgericht Hamburg', 'Versicherung XY'],
                'angelegt': ['01.01.2025', '15.02.2025'],
                'quelle': ['Manual', 'Manual']
            }),
            'RA-MICRO-Format': pd.DataFrame({
                'AktenNr': ['12345/25SQ', '67890/25TS'],
                'Sachbearbeiter': ['SQ', 'TS'],
                'Mandant': ['Max Mustermann', 'Erika Musterfrau'],
                'Gegner': ['Amtsgericht Hamburg', 'Versicherung XY'],
                'Anlage': ['01.01.2025', '15.02.2025']
            }),
            'DATEV-Format': pd.DataFrame({
                'Akten-Nr.': ['12345/25SQ', '67890/25TS'],
                'Bearbeiter': ['SQ', 'TS'],
                'Mandantenname': ['Max Mustermann', 'Erika Musterfrau'],
                'Gegenpartei': ['Amtsgericht Hamburg', 'Versicherung XY'],
                'Anlagedatum': ['01.01.2025', '15.02.2025']
            })
        }

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            for sheet_name, df in examples.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        buffer.seek(0)
        return buffer.getvalue()

    def validate_import(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Validiert importierte Daten

        Args:
            df: DataFrame mit importierten Daten

        Returns:
            Validierungs-Bericht
        """
        report = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'statistics': {}
        }

        # Prüfe erforderliche Spalten
        required_columns = ['internes_az']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            report['valid'] = False
            report['errors'].append(f"Fehlende Spalten: {', '.join(missing_columns)}")

        # Prüfe leere Aktenzeichen
        if 'internes_az' in df.columns:
            empty_az = df['internes_az'].isna() | (df['internes_az'] == '')
            empty_count = empty_az.sum()

            if empty_count > 0:
                report['warnings'].append(f"{empty_count} Zeilen ohne Aktenzeichen")

        # Statistiken
        report['statistics'] = {
            'total_rows': len(df),
            'unique_aktenzeichen': df['internes_az'].nunique() if 'internes_az' in df.columns else 0,
            'columns': list(df.columns)
        }

        return report
