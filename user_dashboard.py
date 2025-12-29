"""
Personalisierte Benutzer-Dashboards

Features:
- Rollen-basierter Dokumentenzugriff
- Personalisierte Dokument-Listen
- Download-Management
- Benutzer-spezifische Statistiken
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class UserDashboard:
    """Verwaltet personalisierte Dashboards"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Dashboard-Manager

        Args:
            storage_dir: Storage-Verzeichnis
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.downloads_file = self.storage_dir / "user_downloads.json"
        self.downloads = self._load_downloads()

    def _load_downloads(self) -> Dict:
        """Lädt Download-Historie"""
        if self.downloads_file.exists():
            try:
                with open(self.downloads_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_downloads(self):
        """Speichert Download-Historie"""
        try:
            with open(self.downloads_file, 'w', encoding='utf-8') as f:
                json.dump(self.downloads, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")

    def get_user_documents(
        self,
        user: Dict,
        storage,
        include_all: bool = False
    ) -> List[Dict]:
        """
        Liefert Dokumente für Benutzer basierend auf Rolle

        Args:
            user: Benutzer-Dict
            storage: DocumentStorage-Instanz
            include_all: Admin/Empfang sehen alle Dokumente

        Returns:
            Liste von Dokumenten
        """
        role = user['role']
        kuerzel = user.get('kuerzel', '')

        all_docs = storage.get_all_documents()

        # Admin und Empfang sehen alles
        if include_all and role in ['Administrator', 'Empfang']:
            return all_docs

        # Rechtsanwälte/Sachbearbeiter sehen nur ihre eigenen
        filtered_docs = []

        for doc in all_docs:
            doc_sachbearbeiter = doc.get('sachbearbeiter', '')

            # Prüfe ob Dokument dem Benutzer zugeordnet ist
            if doc_sachbearbeiter == kuerzel:
                filtered_docs.append(doc)

        return filtered_docs

    def get_new_documents(
        self,
        user: Dict,
        storage,
        since_days: int = 1
    ) -> List[Dict]:
        """
        Liefert neue Dokumente seit X Tagen

        Args:
            user: Benutzer-Dict
            storage: DocumentStorage-Instanz
            since_days: Anzahl Tage

        Returns:
            Liste neuer Dokumente
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=since_days)

        all_user_docs = self.get_user_documents(user, storage)

        new_docs = []
        for doc in all_user_docs:
            verarbeitet = doc.get('verarbeitet_am', '')
            if verarbeitet:
                try:
                    doc_date = datetime.fromisoformat(verarbeitet)
                    if doc_date >= cutoff:
                        new_docs.append(doc)
                except:
                    pass

        return new_docs

    def get_user_statistics(
        self,
        user: Dict,
        storage
    ) -> Dict:
        """
        Liefert Statistiken für Benutzer

        Args:
            user: Benutzer-Dict
            storage: DocumentStorage-Instanz

        Returns:
            Dict mit Statistiken
        """
        docs = self.get_user_documents(user, storage)
        new_docs = self.get_new_documents(user, storage, since_days=7)

        # Zähle nach Priorität
        by_priority = {
            'CRITICAL': 0,
            'HIGH': 0,
            'MEDIUM': 0,
            'NORMAL': 0
        }

        for doc in docs:
            priority = doc.get('analyse', {}).get('deadline_info', {}).get('priority', 'NORMAL')
            if priority in by_priority:
                by_priority[priority] += 1

        # Downloads
        user_downloads = self.get_user_download_history(user['id'])

        return {
            'total_documents': len(docs),
            'new_this_week': len(new_docs),
            'by_priority': by_priority,
            'total_downloads': len(user_downloads),
            'last_download': user_downloads[-1]['downloaded_at'] if user_downloads else None
        }

    def log_download(
        self,
        user_id: str,
        document_id: str,
        document_name: str
    ):
        """
        Loggt Download

        Args:
            user_id: Benutzer-ID
            document_id: Dokument-ID
            document_name: Dateiname
        """
        if user_id not in self.downloads:
            self.downloads[user_id] = []

        self.downloads[user_id].append({
            'document_id': document_id,
            'document_name': document_name,
            'downloaded_at': datetime.now().isoformat()
        })

        self._save_downloads()

    def get_user_download_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """
        Liefert Download-Historie

        Args:
            user_id: Benutzer-ID
            limit: Maximale Anzahl

        Returns:
            Liste von Downloads
        """
        if user_id not in self.downloads:
            return []

        # Neueste zuerst
        history = self.downloads[user_id]
        return list(reversed(history[-limit:]))

    def mark_documents_as_seen(
        self,
        user_id: str,
        document_ids: List[str]
    ):
        """
        Markiert Dokumente als gesehen

        Args:
            user_id: Benutzer-ID
            document_ids: Liste von Dokument-IDs
        """
        seen_file = self.storage_dir / f"seen_{user_id}.json"

        seen = []
        if seen_file.exists():
            try:
                with open(seen_file, 'r', encoding='utf-8') as f:
                    seen = json.load(f)
            except:
                pass

        for doc_id in document_ids:
            if doc_id not in seen:
                seen.append(doc_id)

        try:
            with open(seen_file, 'w', encoding='utf-8') as f:
                json.dump(seen, f)
        except Exception as e:
            print(f"Fehler: {e}")

    def get_unseen_documents(
        self,
        user_id: str,
        all_user_docs: List[Dict]
    ) -> List[Dict]:
        """
        Liefert ungesehene Dokumente

        Args:
            user_id: Benutzer-ID
            all_user_docs: Alle Dokumente des Benutzers

        Returns:
            Liste ungesehener Dokumente
        """
        seen_file = self.storage_dir / f"seen_{user_id}.json"

        seen = []
        if seen_file.exists():
            try:
                with open(seen_file, 'r', encoding='utf-8') as f:
                    seen = json.load(f)
            except:
                pass

        unseen = []
        for doc in all_user_docs:
            doc_id = doc.get('dateiname', '')
            if doc_id and doc_id not in seen:
                unseen.append(doc)

        return unseen

    def get_dashboard_data(
        self,
        user: Dict,
        storage
    ) -> Dict:
        """
        Liefert vollständige Dashboard-Daten

        Args:
            user: Benutzer-Dict
            storage: DocumentStorage-Instanz

        Returns:
            Umfassendes Dashboard-Dict
        """
        all_docs = self.get_user_documents(user, storage)
        new_docs = self.get_new_documents(user, storage, since_days=1)
        unseen_docs = self.get_unseen_documents(user['id'], all_docs)
        stats = self.get_user_statistics(user, storage)

        # Sortiere nach Datum (neueste zuerst)
        all_docs_sorted = sorted(
            all_docs,
            key=lambda x: x.get('verarbeitet_am', ''),
            reverse=True
        )

        return {
            'user': user,
            'statistics': stats,
            'all_documents': all_docs_sorted,
            'new_documents': new_docs,
            'unseen_documents': unseen_docs,
            'total': len(all_docs),
            'new_count': len(new_docs),
            'unseen_count': len(unseen_docs)
        }

    def can_access_document(
        self,
        user: Dict,
        document: Dict
    ) -> bool:
        """
        Prüft ob Benutzer auf Dokument zugreifen darf

        Args:
            user: Benutzer-Dict
            document: Dokument-Dict

        Returns:
            True wenn Zugriff erlaubt
        """
        role = user['role']
        kuerzel = user.get('kuerzel', '')

        # Admin und Empfang haben vollen Zugriff
        if role in ['Administrator', 'Empfang']:
            return True

        # Andere nur auf eigene Dokumente
        doc_sachbearbeiter = document.get('sachbearbeiter', '')
        return doc_sachbearbeiter == kuerzel

    def get_document_by_id(
        self,
        document_id: str,
        storage
    ) -> Optional[Dict]:
        """
        Holt Dokument nach ID

        Args:
            document_id: Dokument-ID (Dateiname)
            storage: DocumentStorage-Instanz

        Returns:
            Dokument-Dict oder None
        """
        all_docs = storage.get_all_documents()

        for doc in all_docs:
            if doc.get('dateiname') == document_id:
                return doc

        return None
