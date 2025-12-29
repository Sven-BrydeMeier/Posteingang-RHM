"""
Audit-Log für Nachvollziehbarkeit und Compliance

Trackt:
- Manuelle Zuordnungen
- Änderungen an Aktenzeichen
- API-Nutzung
- System-Events
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import pandas as pd


class EventType(Enum):
    """Event-Typen"""
    MANUAL_ASSIGNMENT = "Manuelle Zuordnung"
    AUTO_ASSIGNMENT = "Automatische Zuordnung"
    AKTENZEICHEN_CHANGE = "Aktenzeichen geändert"
    PDF_PROCESSED = "PDF verarbeitet"
    DUPLICATE_DETECTED = "Duplikat erkannt"
    TRAINING_UPDATE = "Training-DB aktualisiert"
    ZIP_GENERATED = "ZIP-Dateien erstellt"
    BATCH_COMPLETED = "Batch abgeschlossen"
    ERROR = "Fehler"
    API_CALL = "API-Aufruf"


class AuditLog:
    """Audit-Log für System-Events"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Audit-Log

        Args:
            storage_dir: Verzeichnis für Log-Dateien
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Monatliche Log-Dateien
        current_month = datetime.now().strftime('%Y-%m')
        self.current_log_file = self.storage_dir / f"audit_log_{current_month}.jsonl"

    def log_event(
        self,
        event_type: EventType,
        description: str,
        metadata: Optional[Dict] = None,
        user: str = "System"
    ):
        """
        Loggt ein Event

        Args:
            event_type: Typ des Events
            description: Beschreibung
            metadata: Zusätzliche Metadaten
            user: Benutzer (falls vorhanden)
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type.value,
            'description': description,
            'user': user,
            'metadata': metadata or {}
        }

        # Append to JSONL file
        try:
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"Fehler beim Loggen: {e}")

    def log_manual_assignment(
        self,
        document_name: str,
        sachbearbeiter: str,
        aktenzeichen: Optional[str] = None,
        absender: Optional[str] = None
    ):
        """Loggt manuelle Zuordnung"""
        self.log_event(
            EventType.MANUAL_ASSIGNMENT,
            f"Dokument '{document_name}' zu {sachbearbeiter} zugeordnet",
            metadata={
                'document': document_name,
                'sachbearbeiter': sachbearbeiter,
                'aktenzeichen': aktenzeichen,
                'absender': absender
            }
        )

    def log_pdf_processing(
        self,
        filename: str,
        document_count: int,
        batch_number: Optional[int] = None
    ):
        """Loggt PDF-Verarbeitung"""
        desc = f"PDF '{filename}' verarbeitet: {document_count} Dokumente"
        if batch_number:
            desc += f" (Batch #{batch_number})"

        self.log_event(
            EventType.PDF_PROCESSED,
            desc,
            metadata={
                'filename': filename,
                'document_count': document_count,
                'batch_number': batch_number
            }
        )

    def log_duplicate(self, filename: str, original_date: str):
        """Loggt Duplikat-Erkennung"""
        self.log_event(
            EventType.DUPLICATE_DETECTED,
            f"Duplikat erkannt: '{filename}' (Original vom {original_date})",
            metadata={
                'filename': filename,
                'original_date': original_date
            }
        )

    def log_api_call(self, provider: str, tokens: Optional[int] = None):
        """Loggt API-Aufruf"""
        self.log_event(
            EventType.API_CALL,
            f"API-Aufruf: {provider}",
            metadata={
                'provider': provider,
                'tokens': tokens
            }
        )

    def log_error(self, error_message: str, context: Optional[Dict] = None):
        """Loggt Fehler"""
        self.log_event(
            EventType.ERROR,
            error_message,
            metadata=context
        )

    def get_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[EventType] = None
    ) -> List[Dict]:
        """
        Lädt Events mit Filtern

        Args:
            start_date: Start-Datum (optional)
            end_date: End-Datum (optional)
            event_type: Event-Typ-Filter (optional)

        Returns:
            Liste von Events
        """
        events = []

        # Lese alle relevanten Log-Dateien
        log_files = sorted(self.storage_dir.glob("audit_log_*.jsonl"))

        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())

                            # Datum-Filter
                            event_time = datetime.fromisoformat(event['timestamp'])
                            if start_date and event_time < start_date:
                                continue
                            if end_date and event_time > end_date:
                                continue

                            # Event-Typ-Filter
                            if event_type and event['event_type'] != event_type.value:
                                continue

                            events.append(event)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen von {log_file}: {e}")

        return events

    def get_statistics(self, days: int = 30) -> Dict:
        """
        Liefert Statistiken für die letzten X Tage

        Args:
            days: Anzahl Tage

        Returns:
            Statistiken
        """
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)
        events = self.get_events(start_date=start_date)

        stats = {
            'total_events': len(events),
            'events_by_type': {},
            'manual_assignments': 0,
            'auto_assignments': 0,
            'pdfs_processed': 0,
            'documents_processed': 0,
            'duplicates_detected': 0,
            'errors': 0,
            'api_calls': 0
        }

        # Zähle nach Typ
        for event in events:
            event_type = event['event_type']
            stats['events_by_type'][event_type] = stats['events_by_type'].get(event_type, 0) + 1

            if event_type == EventType.MANUAL_ASSIGNMENT.value:
                stats['manual_assignments'] += 1
            elif event_type == EventType.AUTO_ASSIGNMENT.value:
                stats['auto_assignments'] += 1
            elif event_type == EventType.PDF_PROCESSED.value:
                stats['pdfs_processed'] += 1
                stats['documents_processed'] += event.get('metadata', {}).get('document_count', 0)
            elif event_type == EventType.DUPLICATE_DETECTED.value:
                stats['duplicates_detected'] += 1
            elif event_type == EventType.ERROR.value:
                stats['errors'] += 1
            elif event_type == EventType.API_CALL.value:
                stats['api_calls'] += 1

        return stats

    def export_to_excel(self, output_path: Path, days: int = 90):
        """
        Exportiert Audit-Log nach Excel

        Args:
            output_path: Pfad zur Excel-Datei
            days: Anzahl Tage zurück
        """
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)
        events = self.get_events(start_date=start_date)

        if not events:
            return

        # Konvertiere zu DataFrame
        rows = []
        for event in events:
            row = {
                'Timestamp': event['timestamp'],
                'Event-Typ': event['event_type'],
                'Beschreibung': event['description'],
                'Benutzer': event.get('user', 'System')
            }

            # Füge wichtige Metadaten hinzu
            metadata = event.get('metadata', {})
            if 'sachbearbeiter' in metadata:
                row['Sachbearbeiter'] = metadata['sachbearbeiter']
            if 'aktenzeichen' in metadata:
                row['Aktenzeichen'] = metadata['aktenzeichen']
            if 'document_count' in metadata:
                row['Dokumente'] = metadata['document_count']

            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_excel(output_path, index=False)

    def generate_pdf_report(self, output_path: Path, days: int = 30):
        """
        Generiert PDF-Bericht

        Args:
            output_path: Pfad zur PDF-Datei
            days: Anzahl Tage
        """
        # TODO: Implementiere PDF-Report-Generierung mit ReportLab
        pass

    def cleanup_old_logs(self, months_to_keep: int = 12):
        """
        Löscht alte Log-Dateien

        Args:
            months_to_keep: Monate die behalten werden sollen
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=months_to_keep * 30)
        cutoff_month = cutoff_date.strftime('%Y-%m')

        log_files = self.storage_dir.glob("audit_log_*.jsonl")

        for log_file in log_files:
            # Extrahiere Monat aus Dateiname
            try:
                month = log_file.stem.split('_')[-1]  # audit_log_2024-12.jsonl -> 2024-12
                if month < cutoff_month:
                    log_file.unlink()
                    print(f"Alte Log-Datei gelöscht: {log_file}")
            except Exception as e:
                print(f"Fehler beim Löschen von {log_file}: {e}")
