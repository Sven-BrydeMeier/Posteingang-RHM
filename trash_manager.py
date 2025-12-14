"""
Papierkorb-Manager für gelöschte Dokumente

Features:
- Temporäre Speicherung gelöschter Dokumente
- Automatisches Löschen nach konfigurierbarer Zeit (Default: 48h)
- Wiederherstellung möglich
- Einstellungen für Aufbewahrungszeit
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import hashlib


class TrashManager:
    """Verwaltet gelöschte Dokumente mit zeitgesteuerter Auto-Löschung"""

    DEFAULT_RETENTION_HOURS = 48

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Trash-Manager

        Args:
            storage_dir: Basis-Verzeichnis für Storage
        """
        self.storage_dir = Path(storage_dir)
        self.trash_dir = self.storage_dir / "trash"
        self.trash_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.trash_dir / "trash_metadata.json"
        self.settings_file = self.storage_dir / "trash_settings.json"

        # Lade Einstellungen
        self.settings = self._load_settings()

        # Lade Metadaten
        self.metadata = self._load_metadata()

    def _load_settings(self) -> Dict:
        """Lädt Papierkorb-Einstellungen"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        # Default-Einstellungen
        return {
            'retention_hours': self.DEFAULT_RETENTION_HOURS,
            'auto_cleanup_enabled': True
        }

    def _save_settings(self):
        """Speichert Einstellungen"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Einstellungen: {e}")

    def _load_metadata(self) -> Dict:
        """Lädt Metadaten aller gelöschten Dokumente"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_metadata(self):
        """Speichert Metadaten"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Metadaten: {e}")

    def get_retention_hours(self) -> int:
        """Liefert aktuelle Aufbewahrungszeit in Stunden"""
        return self.settings.get('retention_hours', self.DEFAULT_RETENTION_HOURS)

    def set_retention_hours(self, hours: int):
        """
        Setzt Aufbewahrungszeit

        Args:
            hours: Stunden (min: 1, max: 720 = 30 Tage)
        """
        hours = max(1, min(720, hours))
        self.settings['retention_hours'] = hours
        self._save_settings()

    def _generate_trash_id(self, original_path: str) -> str:
        """Generiert eindeutige ID für gelöschtes Dokument"""
        timestamp = datetime.now().isoformat()
        unique_string = f"{original_path}_{timestamp}"
        return hashlib.md5(unique_string.encode()).hexdigest()

    def move_to_trash(
        self,
        file_path: Path,
        document_info: Optional[Dict] = None
    ) -> str:
        """
        Verschiebt Datei in Papierkorb

        Args:
            file_path: Pfad zur zu löschenden Datei
            document_info: Optional zusätzliche Dokument-Infos

        Returns:
            Trash-ID für Wiederherstellung
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {file_path}")

        # Generiere Trash-ID
        trash_id = self._generate_trash_id(str(file_path))

        # Ziel-Pfad im Papierkorb
        trash_file_path = self.trash_dir / f"{trash_id}_{file_path.name}"

        # Verschiebe Datei
        shutil.move(str(file_path), str(trash_file_path))

        # Speichere Metadaten
        self.metadata[trash_id] = {
            'original_path': str(file_path),
            'original_name': file_path.name,
            'trash_path': str(trash_file_path),
            'deleted_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=self.get_retention_hours())).isoformat(),
            'size_bytes': trash_file_path.stat().st_size,
            'document_info': document_info or {}
        }

        self._save_metadata()

        return trash_id

    def restore_from_trash(self, trash_id: str, restore_path: Optional[Path] = None) -> bool:
        """
        Stellt Datei aus Papierkorb wieder her

        Args:
            trash_id: ID des gelöschten Dokuments
            restore_path: Optional anderer Wiederherstellungs-Pfad

        Returns:
            True bei Erfolg
        """
        if trash_id not in self.metadata:
            raise ValueError(f"Trash-ID nicht gefunden: {trash_id}")

        meta = self.metadata[trash_id]
        trash_path = Path(meta['trash_path'])

        if not trash_path.exists():
            raise FileNotFoundError(f"Datei im Papierkorb nicht mehr vorhanden")

        # Bestimme Ziel-Pfad
        if restore_path:
            target_path = Path(restore_path)
        else:
            target_path = Path(meta['original_path'])

        # Stelle sicher dass Zielverzeichnis existiert
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Wenn Zieldatei bereits existiert, füge Suffix hinzu
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            counter = 1
            while target_path.exists():
                target_path = target_path.parent / f"{stem}_wiederhergestellt_{counter}{suffix}"
                counter += 1

        # Stelle wieder her
        shutil.move(str(trash_path), str(target_path))

        # Entferne aus Metadaten
        del self.metadata[trash_id]
        self._save_metadata()

        return True

    def permanent_delete(self, trash_id: str) -> bool:
        """
        Löscht Datei endgültig aus Papierkorb

        Args:
            trash_id: ID des zu löschenden Dokuments

        Returns:
            True bei Erfolg
        """
        if trash_id not in self.metadata:
            return False

        meta = self.metadata[trash_id]
        trash_path = Path(meta['trash_path'])

        # Lösche Datei
        if trash_path.exists():
            trash_path.unlink()

        # Entferne Metadaten
        del self.metadata[trash_id]
        self._save_metadata()

        return True

    def cleanup_expired(self) -> int:
        """
        Löscht abgelaufene Dokumente automatisch

        Returns:
            Anzahl gelöschter Dokumente
        """
        if not self.settings.get('auto_cleanup_enabled', True):
            return 0

        now = datetime.now()
        deleted_count = 0
        to_delete = []

        # Finde abgelaufene Einträge
        for trash_id, meta in self.metadata.items():
            expires_at = datetime.fromisoformat(meta['expires_at'])

            if now > expires_at:
                to_delete.append(trash_id)

        # Lösche abgelaufene Einträge
        for trash_id in to_delete:
            try:
                self.permanent_delete(trash_id)
                deleted_count += 1
            except Exception as e:
                print(f"Fehler beim Löschen von {trash_id}: {e}")

        return deleted_count

    def empty_trash(self) -> int:
        """
        Leert Papierkorb komplett

        Returns:
            Anzahl gelöschter Dokumente
        """
        trash_ids = list(self.metadata.keys())
        deleted_count = 0

        for trash_id in trash_ids:
            try:
                self.permanent_delete(trash_id)
                deleted_count += 1
            except Exception as e:
                print(f"Fehler beim Löschen von {trash_id}: {e}")

        return deleted_count

    def get_trash_items(self) -> List[Dict]:
        """
        Liefert alle Papierkorb-Einträge mit Status

        Returns:
            Liste von Dokumenten mit Metadaten
        """
        items = []
        now = datetime.now()

        for trash_id, meta in self.metadata.items():
            expires_at = datetime.fromisoformat(meta['expires_at'])
            deleted_at = datetime.fromisoformat(meta['deleted_at'])

            time_until_deletion = expires_at - now
            hours_remaining = max(0, time_until_deletion.total_seconds() / 3600)

            item = {
                'trash_id': trash_id,
                'name': meta['original_name'],
                'original_path': meta['original_path'],
                'deleted_at': deleted_at.strftime('%d.%m.%Y %H:%M'),
                'expires_at': expires_at.strftime('%d.%m.%Y %H:%M'),
                'hours_remaining': hours_remaining,
                'size_kb': meta['size_bytes'] / 1024,
                'is_expired': hours_remaining == 0,
                'document_info': meta.get('document_info', {})
            }

            items.append(item)

        # Sortiere nach Löschdatum (neueste zuerst)
        items.sort(key=lambda x: x['deleted_at'], reverse=True)

        return items

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken über Papierkorb

        Returns:
            Dict mit Statistiken
        """
        items = self.get_trash_items()

        total_size = sum(item['size_kb'] for item in items)
        expired_count = sum(1 for item in items if item['is_expired'])

        return {
            'total_items': len(items),
            'expired_items': expired_count,
            'active_items': len(items) - expired_count,
            'total_size_mb': total_size / 1024,
            'retention_hours': self.get_retention_hours(),
            'auto_cleanup_enabled': self.settings.get('auto_cleanup_enabled', True)
        }

    def search_trash(self, query: str) -> List[Dict]:
        """
        Durchsucht Papierkorb

        Args:
            query: Suchbegriff

        Returns:
            Liste passender Dokumente
        """
        items = self.get_trash_items()
        query_lower = query.lower()

        results = []
        for item in items:
            # Suche in Name und Original-Pfad
            if (query_lower in item['name'].lower() or
                query_lower in item['original_path'].lower()):
                results.append(item)

        return results

    def get_expiring_soon(self, hours: int = 6) -> List[Dict]:
        """
        Liefert Dokumente die bald gelöscht werden

        Args:
            hours: Schwellwert in Stunden

        Returns:
            Liste von bald ablaufenden Dokumenten
        """
        items = self.get_trash_items()

        expiring_soon = [
            item for item in items
            if 0 < item['hours_remaining'] <= hours
        ]

        return expiring_soon

    def extend_retention(self, trash_id: str, additional_hours: int = 24) -> bool:
        """
        Verlängert Aufbewahrungszeit für bestimmtes Dokument

        Args:
            trash_id: ID des Dokuments
            additional_hours: Zusätzliche Stunden

        Returns:
            True bei Erfolg
        """
        if trash_id not in self.metadata:
            return False

        # Verlängere Ablaufdatum
        current_expires = datetime.fromisoformat(self.metadata[trash_id]['expires_at'])
        new_expires = current_expires + timedelta(hours=additional_hours)

        self.metadata[trash_id]['expires_at'] = new_expires.isoformat()
        self._save_metadata()

        return True

    def export_trash_list(self, output_path: Path):
        """
        Exportiert Papierkorb-Liste als Excel

        Args:
            output_path: Pfad zur Excel-Datei
        """
        import pandas as pd

        items = self.get_trash_items()

        if not items:
            return

        df = pd.DataFrame([{
            'Name': item['name'],
            'Original-Pfad': item['original_path'],
            'Gelöscht am': item['deleted_at'],
            'Läuft ab am': item['expires_at'],
            'Verbleibende Stunden': f"{item['hours_remaining']:.1f}",
            'Größe (KB)': f"{item['size_kb']:.1f}",
            'Status': 'Abgelaufen' if item['is_expired'] else 'Aktiv'
        } for item in items])

        df.to_excel(output_path, index=False)
