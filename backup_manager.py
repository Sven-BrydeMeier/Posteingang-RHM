"""
Backup-System mit Scheduling

Features:
- Automatische Backups der Storage-Daten
- Komprimierung (ZIP/TAR.GZ)
- Cloud-Upload (optional)
- Scheduling (täglich/wöchentlich/monatlich)
- Backup-Rotation (max. X Backups behalten)
"""

import shutil
import tarfile
import zipfile
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum


class BackupFormat(Enum):
    """Backup-Formate"""
    ZIP = "ZIP"
    TARGZ = "TAR.GZ"


class BackupFrequency(Enum):
    """Backup-Frequenz"""
    TAEGLICH = "Täglich"
    WOECHENTLICH = "Wöchentlich"
    MONATLICH = "Monatlich"
    MANUELL = "Manuell"


class BackupManager:
    """Verwaltet Backups"""

    def __init__(self, storage_dir: Path, backup_dir: Optional[Path] = None):
        """
        Initialisiert Backup-Manager

        Args:
            storage_dir: Zu sicherndes Storage-Verzeichnis
            backup_dir: Backup-Zielverzeichnis (default: storage_dir/backups)
        """
        self.storage_dir = Path(storage_dir)
        self.backup_dir = Path(backup_dir) if backup_dir else (self.storage_dir / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.storage_dir / "backup_config.json"
        self.log_file = self.storage_dir / "backup_log.jsonl"

        # Lade Konfiguration
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Lädt Konfiguration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        # Default-Konfiguration
        return {
            'enabled': False,
            'format': BackupFormat.ZIP.value,
            'frequency': BackupFrequency.TAEGLICH.value,
            'max_backups': 14,  # Behalte letzte 14 Backups
            'compress': True,
            'last_backup': None,

            # Cloud-Upload (optional)
            'cloud_upload_enabled': False,
            'cloud_type': '',  # 'dropbox', 'google_drive', etc.
            'cloud_path': ''
        }

    def _save_config(self):
        """Speichert Konfiguration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")

    def _log_event(self, event_type: str, status: str, message: str = "", details: Optional[Dict] = None):
        """Loggt Backup-Event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'status': status,
            'message': message,
            'details': details or {}
        }

        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"Fehler beim Loggen: {e}")

    def enable(self, frequency: BackupFrequency = BackupFrequency.TAEGLICH, max_backups: int = 14):
        """
        Aktiviert automatische Backups

        Args:
            frequency: Backup-Frequenz
            max_backups: Maximale Anzahl Backups
        """
        self.config['enabled'] = True
        self.config['frequency'] = frequency.value
        self.config['max_backups'] = max_backups
        self._save_config()

    def disable(self):
        """Deaktiviert automatische Backups"""
        self.config['enabled'] = False
        self._save_config()

    def is_enabled(self) -> bool:
        """Prüft ob Backups aktiviert sind"""
        return self.config.get('enabled', False)

    def should_create_backup(self) -> bool:
        """
        Prüft ob Backup fällig ist

        Returns:
            True wenn Backup erstellt werden sollte
        """
        if not self.is_enabled():
            return False

        last_backup_str = self.config.get('last_backup')
        if not last_backup_str:
            return True

        last_backup = datetime.fromisoformat(last_backup_str)
        now = datetime.now()

        frequency = self.config.get('frequency', BackupFrequency.TAEGLICH.value)

        if frequency == BackupFrequency.TAEGLICH.value:
            # Täglich um 2 Uhr nachts
            if now.hour >= 2 and (now - last_backup).days >= 1:
                return True

        elif frequency == BackupFrequency.WOECHENTLICH.value:
            # Wöchentlich Sonntag
            if now.weekday() == 6 and (now - last_backup).days >= 7:
                return True

        elif frequency == BackupFrequency.MONATLICH.value:
            # Monatlich am 1.
            if now.day == 1 and (now - last_backup).days >= 28:
                return True

        return False

    def create_backup(self, custom_name: Optional[str] = None) -> Optional[Path]:
        """
        Erstellt Backup

        Args:
            custom_name: Optional benutzerdefinierter Name

        Returns:
            Pfad zum Backup bei Erfolg
        """
        try:
            # Backup-Name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_format = self.config.get('format', BackupFormat.ZIP.value)

            if custom_name:
                backup_name = f"{custom_name}_{timestamp}"
            else:
                backup_name = f"rhm_backup_{timestamp}"

            if backup_format == BackupFormat.ZIP.value:
                backup_path = self.backup_dir / f"{backup_name}.zip"
                success = self._create_zip_backup(backup_path)
            else:
                backup_path = self.backup_dir / f"{backup_name}.tar.gz"
                success = self._create_targz_backup(backup_path)

            if not success:
                return None

            # Update last backup
            self.config['last_backup'] = datetime.now().isoformat()
            self._save_config()

            # Rotation: Lösche alte Backups
            self._rotate_backups()

            # Optional: Cloud-Upload
            if self.config.get('cloud_upload_enabled', False):
                self._upload_to_cloud(backup_path)

            self._log_event(
                'create_backup',
                'success',
                f"Backup erstellt: {backup_path.name}",
                {'size_mb': backup_path.stat().st_size / (1024 * 1024)}
            )

            return backup_path

        except Exception as e:
            self._log_event('create_backup', 'error', str(e))
            print(f"Fehler beim Erstellen des Backups: {e}")
            return None

    def _create_zip_backup(self, backup_path: Path) -> bool:
        """Erstellt ZIP-Backup"""
        try:
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Alle Dateien im Storage-Verzeichnis
                for file_path in self.storage_dir.rglob('*'):
                    # Überspringe Backup-Verzeichnis selbst
                    if file_path.is_relative_to(self.backup_dir):
                        continue

                    if file_path.is_file():
                        arcname = file_path.relative_to(self.storage_dir)
                        zipf.write(file_path, arcname)

            return True

        except Exception as e:
            print(f"Fehler beim Erstellen des ZIP-Backups: {e}")
            return False

    def _create_targz_backup(self, backup_path: Path) -> bool:
        """Erstellt TAR.GZ-Backup"""
        try:
            with tarfile.open(backup_path, 'w:gz') as tar:
                # Alle Dateien im Storage-Verzeichnis
                for file_path in self.storage_dir.rglob('*'):
                    # Überspringe Backup-Verzeichnis selbst
                    if file_path.is_relative_to(self.backup_dir):
                        continue

                    if file_path.is_file():
                        arcname = file_path.relative_to(self.storage_dir)
                        tar.add(file_path, arcname=arcname)

            return True

        except Exception as e:
            print(f"Fehler beim Erstellen des TAR.GZ-Backups: {e}")
            return False

    def _rotate_backups(self):
        """Löscht alte Backups (Rotation)"""
        max_backups = self.config.get('max_backups', 14)

        # Finde alle Backups
        backups = sorted(
            self.backup_dir.glob("rhm_backup_*.{zip,tar.gz}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # Lösche alte Backups
        for old_backup in backups[max_backups:]:
            try:
                old_backup.unlink()
                self._log_event('rotate', 'success', f"Altes Backup gelöscht: {old_backup.name}")
            except Exception as e:
                print(f"Fehler beim Löschen von {old_backup}: {e}")

    def _upload_to_cloud(self, backup_path: Path) -> bool:
        """
        Lädt Backup in Cloud hoch

        Args:
            backup_path: Pfad zum Backup

        Returns:
            True bei Erfolg
        """
        cloud_type = self.config.get('cloud_type', '')

        try:
            if cloud_type == 'dropbox':
                return self._upload_to_dropbox(backup_path)
            elif cloud_type == 'google_drive':
                return self._upload_to_google_drive(backup_path)
            # Weitere Cloud-Anbieter können hier hinzugefügt werden

        except Exception as e:
            self._log_event('cloud_upload', 'error', str(e))
            print(f"Fehler beim Cloud-Upload: {e}")

        return False

    def _upload_to_dropbox(self, backup_path: Path) -> bool:
        """Upload zu Dropbox"""
        try:
            import dropbox

            # Dropbox-Token aus Auto-Storage-Config laden
            # (Vereinfachte Implementierung)
            # In realer Implementierung: Eigene Config oder gemeinsame Nutzung

            dbx = dropbox.Dropbox(self.config.get('dropbox_token', ''))
            cloud_path = self.config.get('cloud_path', '/backups')

            with open(backup_path, 'rb') as f:
                dbx.files_upload(
                    f.read(),
                    f"{cloud_path}/{backup_path.name}",
                    mode=dropbox.files.WriteMode.add
                )

            self._log_event('cloud_upload', 'success', f"Dropbox-Upload: {backup_path.name}")
            return True

        except Exception as e:
            print(f"Dropbox-Upload-Fehler: {e}")
            return False

    def _upload_to_google_drive(self, backup_path: Path) -> bool:
        """Upload zu Google Drive"""
        # Stub - würde GoogleApiclient benötigen
        return False

    def restore_backup(self, backup_path: Path, target_dir: Optional[Path] = None) -> bool:
        """
        Stellt Backup wieder her

        Args:
            backup_path: Pfad zum Backup
            target_dir: Zielverzeichnis (default: storage_dir)

        Returns:
            True bei Erfolg
        """
        if not backup_path.exists():
            return False

        target = Path(target_dir) if target_dir else self.storage_dir

        try:
            if backup_path.suffix == '.zip':
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(target)

            elif backup_path.suffix == '.gz':
                with tarfile.open(backup_path, 'r:gz') as tar:
                    tar.extractall(target)

            self._log_event('restore', 'success', f"Backup wiederhergestellt: {backup_path.name}")
            return True

        except Exception as e:
            self._log_event('restore', 'error', str(e))
            print(f"Fehler beim Wiederherstellen: {e}")
            return False

    def list_backups(self) -> List[Dict]:
        """
        Listet alle Backups auf

        Returns:
            Liste von Backup-Informationen
        """
        backups = []

        for backup_path in sorted(self.backup_dir.glob("rhm_backup_*.*"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = backup_path.stat()

            backups.append({
                'name': backup_path.name,
                'path': str(backup_path),
                'size_mb': stat.st_size / (1024 * 1024),
                'created': datetime.fromtimestamp(stat.st_mtime).strftime('%d.%m.%Y %H:%M'),
                'age_days': (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days
            })

        return backups

    def delete_backup(self, backup_name: str) -> bool:
        """
        Löscht Backup

        Args:
            backup_name: Backup-Name

        Returns:
            True bei Erfolg
        """
        backup_path = self.backup_dir / backup_name

        if backup_path.exists():
            try:
                backup_path.unlink()
                self._log_event('delete', 'success', f"Backup gelöscht: {backup_name}")
                return True
            except Exception as e:
                print(f"Fehler beim Löschen: {e}")

        return False

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken

        Returns:
            Dict mit Statistiken
        """
        backups = self.list_backups()

        total_size_mb = sum(b['size_mb'] for b in backups)

        stats = {
            'enabled': self.is_enabled(),
            'frequency': self.config.get('frequency', ''),
            'max_backups': self.config.get('max_backups', 0),
            'total_backups': len(backups),
            'total_size_mb': total_size_mb,
            'last_backup': self.config.get('last_backup', ''),
            'oldest_backup': backups[-1]['created'] if backups else '',
            'newest_backup': backups[0]['created'] if backups else ''
        }

        return stats
