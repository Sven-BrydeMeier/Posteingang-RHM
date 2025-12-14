"""
Dashboard-Daten-Manager

Aggregiert Statistiken für Dashboard-Visualisierung mit Plotly:
- Dokumente pro Tag/Woche/Monat
- Verteilung nach Sachbearbeiter
- Prioritäten-Übersicht
- API-Nutzung
- Performance-Metriken
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class DashboardManager:
    """Verwaltet Dashboard-Daten und Statistiken"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Dashboard-Manager

        Args:
            storage_dir: Storage-Verzeichnis
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def get_documents_timeline(self, days: int = 30) -> Dict:
        """
        Liefert Dokumente-Zeitlinie für Chart

        Args:
            days: Anzahl Tage zurück

        Returns:
            Dict mit Daten für Timeline-Chart
        """
        from datetime import timedelta

        # Lese Audit-Log
        audit_log_file = self.storage_dir / "audit_log.jsonl"

        # Initialisiere Zähler für jeden Tag
        start_date = datetime.now() - timedelta(days=days)
        counts_by_day = defaultdict(int)

        # Fülle alle Tage mit 0
        for i in range(days + 1):
            day = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            counts_by_day[day] = 0

        # Zähle Dokumente aus Audit-Log
        if audit_log_file.exists():
            try:
                with open(audit_log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())

                            if event.get('event_type') == 'PDF verarbeitet':
                                event_date = datetime.fromisoformat(event['timestamp'])

                                if event_date >= start_date:
                                    day_key = event_date.strftime('%Y-%m-%d')
                                    doc_count = event.get('metadata', {}).get('document_count', 1)
                                    counts_by_day[day_key] += doc_count

                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen des Audit-Logs: {e}")

        # Formatiere für Chart
        dates = sorted(counts_by_day.keys())
        counts = [counts_by_day[date] for date in dates]

        return {
            'dates': dates,
            'counts': counts,
            'total': sum(counts)
        }

    def get_sachbearbeiter_distribution(self) -> Dict:
        """
        Liefert Verteilung nach Sachbearbeiter

        Returns:
            Dict mit Daten für Pie/Bar-Chart
        """
        counts = defaultdict(int)

        # Lese aus Audit-Log
        audit_log_file = self.storage_dir / "audit_log.jsonl"

        if audit_log_file.exists():
            try:
                with open(audit_log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())

                            if event.get('event_type') in ['Manuelle Zuordnung', 'Automatische Zuordnung']:
                                sb = event.get('metadata', {}).get('sachbearbeiter', 'Unbekannt')
                                if sb:
                                    counts[sb] += 1

                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen des Audit-Logs: {e}")

        # Formatiere für Chart
        sachbearbeiter = list(counts.keys())
        values = list(counts.values())

        return {
            'sachbearbeiter': sachbearbeiter,
            'counts': values,
            'total': sum(values)
        }

    def get_priority_distribution(self, storage) -> Dict:
        """
        Liefert Prioritäten-Verteilung

        Args:
            storage: DocumentStorage-Instanz

        Returns:
            Dict mit Daten für Pie-Chart
        """
        counts = {
            'CRITICAL': 0,
            'HIGH': 0,
            'MEDIUM': 0,
            'NORMAL': 0
        }

        try:
            # Alle Dokumente durchgehen
            all_docs = storage.get_all_documents()

            for doc in all_docs:
                priority = doc.get('analyse', {}).get('deadline_info', {}).get('priority', 'NORMAL')
                if priority in counts:
                    counts[priority] += 1

        except Exception as e:
            print(f"Fehler beim Abrufen der Dokumente: {e}")

        return {
            'priorities': list(counts.keys()),
            'counts': list(counts.values()),
            'total': sum(counts.values())
        }

    def get_api_usage_stats(self) -> Dict:
        """
        Liefert API-Nutzungs-Statistiken

        Returns:
            Dict mit API-Stats
        """
        api_counts = defaultdict(int)

        # Lese aus Audit-Log
        audit_log_file = self.storage_dir / "audit_log.jsonl"

        if audit_log_file.exists():
            try:
                with open(audit_log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())

                            if event.get('event_type') == 'API-Aufruf':
                                provider = event.get('metadata', {}).get('provider', 'Unbekannt')
                                api_counts[provider] += 1

                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen des Audit-Logs: {e}")

        return {
            'providers': list(api_counts.keys()),
            'counts': list(api_counts.values()),
            'total': sum(api_counts.values())
        }

    def get_deadline_summary(self, storage) -> Dict:
        """
        Liefert Fristen-Zusammenfassung

        Args:
            storage: DocumentStorage-Instanz

        Returns:
            Dict mit Fristen-Übersicht
        """
        summary = {
            'total_deadlines': 0,
            'critical': 0,  # < 3 Tage
            'high': 0,      # 3-7 Tage
            'medium': 0,    # 7-14 Tage
            'normal': 0,    # > 14 Tage
            'overdue': 0    # Überfällig
        }

        now = datetime.now()

        try:
            all_docs = storage.get_all_documents()

            for doc in all_docs:
                deadline_info = doc.get('analyse', {}).get('deadline_info', {})
                earliest = deadline_info.get('earliest_deadline', {})

                if earliest:
                    summary['total_deadlines'] += 1

                    days_remaining = earliest.get('days_remaining', 999)

                    if days_remaining < 0:
                        summary['overdue'] += 1
                    elif days_remaining <= 3:
                        summary['critical'] += 1
                    elif days_remaining <= 7:
                        summary['high'] += 1
                    elif days_remaining <= 14:
                        summary['medium'] += 1
                    else:
                        summary['normal'] += 1

        except Exception as e:
            print(f"Fehler beim Abrufen der Fristen: {e}")

        return summary

    def get_processing_performance(self, days: int = 7) -> Dict:
        """
        Liefert Performance-Metriken

        Args:
            days: Anzahl Tage

        Returns:
            Dict mit Performance-Daten
        """
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)

        stats = {
            'total_processed': 0,
            'total_errors': 0,
            'avg_processing_time': 0,
            'success_rate': 0
        }

        processing_times = []

        # Lese Audit-Log
        audit_log_file = self.storage_dir / "audit_log.jsonl"

        if audit_log_file.exists():
            try:
                with open(audit_log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            event_date = datetime.fromisoformat(event['timestamp'])

                            if event_date < start_date:
                                continue

                            if event.get('event_type') == 'PDF verarbeitet':
                                stats['total_processed'] += event.get('metadata', {}).get('document_count', 1)

                            elif event.get('event_type') == 'Fehler':
                                stats['total_errors'] += 1

                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen des Audit-Logs: {e}")

        # Success Rate
        total = stats['total_processed'] + stats['total_errors']
        if total > 0:
            stats['success_rate'] = (stats['total_processed'] / total) * 100

        return stats

    def get_storage_stats(self) -> Dict:
        """
        Liefert Storage-Statistiken

        Returns:
            Dict mit Storage-Stats
        """
        stats = {
            'total_size_mb': 0,
            'pdf_count': 0,
            'text_count': 0,
            'json_count': 0
        }

        try:
            # Durchsuche Storage-Verzeichnis
            for file_path in self.storage_dir.rglob('*'):
                if file_path.is_file():
                    stats['total_size_mb'] += file_path.stat().st_size / (1024 * 1024)

                    if file_path.suffix == '.pdf':
                        stats['pdf_count'] += 1
                    elif file_path.suffix == '.txt':
                        stats['text_count'] += 1
                    elif file_path.suffix == '.json':
                        stats['json_count'] += 1

        except Exception as e:
            print(f"Fehler beim Abrufen der Storage-Stats: {e}")

        return stats

    def get_top_mandanten(self, storage, limit: int = 10) -> Dict:
        """
        Liefert Top-Mandanten nach Dokumentanzahl

        Args:
            storage: DocumentStorage-Instanz
            limit: Anzahl Top-Einträge

        Returns:
            Dict mit Top-Mandanten
        """
        mandant_counts = defaultdict(int)

        try:
            all_docs = storage.get_all_documents()

            for doc in all_docs:
                mandant = doc.get('analyse', {}).get('mandant', 'Unbekannt')
                if mandant and mandant != 'Unbekannt':
                    mandant_counts[mandant] += 1

        except Exception as e:
            print(f"Fehler beim Abrufen der Dokumente: {e}")

        # Sortiere nach Anzahl (absteigend)
        top_mandanten = sorted(mandant_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        return {
            'mandanten': [m[0] for m in top_mandanten],
            'counts': [m[1] for m in top_mandanten]
        }

    def get_comprehensive_stats(self, storage) -> Dict:
        """
        Liefert umfassende Statistiken für Dashboard

        Args:
            storage: DocumentStorage-Instanz

        Returns:
            Dict mit allen Stats
        """
        return {
            'timeline': self.get_documents_timeline(days=30),
            'sachbearbeiter': self.get_sachbearbeiter_distribution(),
            'priorities': self.get_priority_distribution(storage),
            'api_usage': self.get_api_usage_stats(),
            'deadlines': self.get_deadline_summary(storage),
            'performance': self.get_processing_performance(days=7),
            'storage': self.get_storage_stats(),
            'top_mandanten': self.get_top_mandanten(storage, limit=10)
        }
