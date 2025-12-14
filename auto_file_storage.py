"""
Automatische Ablage auf Cloud/Netzlaufwerk

Unterstützt:
- Lokale Netzlaufwerke (SMB/CIFS)
- Dropbox
- Google Drive
- OneDrive
- Strukturierte Ablage nach Sachbearbeiter/Aktenzeichen
"""

import shutil
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum
import json


class StorageType(Enum):
    """Storage-Typen"""
    LOCAL = "Lokal"
    NETWORK = "Netzlaufwerk"
    DROPBOX = "Dropbox"
    GOOGLE_DRIVE = "Google Drive"
    ONEDRIVE = "OneDrive"


class AutoFileStorage:
    """Automatische Datei-Ablage"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Auto-Ablage

        Args:
            storage_dir: Basis-Verzeichnis für Konfiguration
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.storage_dir / "auto_storage_config.json"
        self.log_file = self.storage_dir / "auto_storage_log.jsonl"

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
            'storage_type': StorageType.LOCAL.value,
            'base_path': '',
            'structure_template': '{sachbearbeiter}/{internes_az}',
            'filename_template': '{datum}_{dateiname}',
            'create_subfolders': True,
            'copy_mode': 'copy',  # 'copy' oder 'move'

            # Cloud-spezifische Einstellungen
            'dropbox_access_token': '',
            'google_drive_credentials': '',
            'onedrive_client_id': '',
            'onedrive_client_secret': ''
        }

    def _save_config(self):
        """Speichert Konfiguration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")

    def _log_event(self, event_type: str, source: str, destination: str, status: str, message: str = ""):
        """Loggt Ablage-Event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'source': source,
            'destination': destination,
            'status': status,
            'message': message
        }

        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"Fehler beim Loggen: {e}")

    def is_enabled(self) -> bool:
        """Prüft ob Auto-Ablage aktiviert ist"""
        return self.config.get('enabled', False)

    def enable(self, base_path: str, storage_type: str = StorageType.LOCAL.value):
        """
        Aktiviert Auto-Ablage

        Args:
            base_path: Basis-Pfad für Ablage
            storage_type: Storage-Typ
        """
        self.config['enabled'] = True
        self.config['base_path'] = base_path
        self.config['storage_type'] = storage_type
        self._save_config()

    def disable(self):
        """Deaktiviert Auto-Ablage"""
        self.config['enabled'] = False
        self._save_config()

    def set_structure_template(self, template: str):
        """
        Setzt Ordnerstruktur-Template

        Args:
            template: Template mit Platzhaltern wie {sachbearbeiter}/{internes_az}
        """
        self.config['structure_template'] = template
        self._save_config()

    def set_filename_template(self, template: str):
        """
        Setzt Dateiname-Template

        Args:
            template: Template mit Platzhaltern wie {datum}_{dateiname}
        """
        self.config['filename_template'] = template
        self._save_config()

    def _build_target_path(self, document_info: Dict, original_filename: str) -> Path:
        """
        Erstellt Ziel-Pfad basierend auf Templates

        Args:
            document_info: Dokument-Informationen
            original_filename: Original-Dateiname

        Returns:
            Ziel-Pfad
        """
        base_path = Path(self.config['base_path'])

        # Extrahiere Informationen
        sachbearbeiter = document_info.get('sachbearbeiter', 'Unbekannt')
        internes_az = document_info.get('aktenzeichen_info', {}).get('internes_az', 'Ohne_AZ')
        datum = document_info.get('analyse', {}).get('datum', datetime.now().strftime('%Y-%m-%d'))
        mandant = document_info.get('analyse', {}).get('mandant', '')
        gegner = document_info.get('analyse', {}).get('gegner', '')

        # Bereinige für Dateisystem
        def clean_for_fs(s: str) -> str:
            """Bereinigt String für Dateisystem"""
            s = str(s).strip()
            # Ersetze ungültige Zeichen
            invalid_chars = '<>:"|?*/'
            for char in invalid_chars:
                s = s.replace(char, '_')
            return s

        sachbearbeiter = clean_for_fs(sachbearbeiter)
        internes_az = clean_for_fs(internes_az)
        mandant = clean_for_fs(mandant)
        gegner = clean_for_fs(gegner)

        # Baue Ordnerstruktur
        structure = self.config['structure_template'].format(
            sachbearbeiter=sachbearbeiter,
            internes_az=internes_az,
            mandant=mandant,
            gegner=gegner
        )

        target_dir = base_path / structure

        # Baue Dateiname
        dateiname_ohne_ext = Path(original_filename).stem
        ext = Path(original_filename).suffix

        filename = self.config['filename_template'].format(
            datum=datum,
            dateiname=dateiname_ohne_ext,
            sachbearbeiter=sachbearbeiter,
            internes_az=internes_az
        )

        filename = clean_for_fs(filename) + ext

        return target_dir / filename

    def store_file(
        self,
        source_file: Path,
        document_info: Dict,
        create_folders: bool = True
    ) -> Optional[Path]:
        """
        Speichert Datei in Ziel-Storage

        Args:
            source_file: Quell-Datei
            document_info: Dokument-Informationen
            create_folders: Ordner automatisch erstellen

        Returns:
            Ziel-Pfad bei Erfolg, None bei Fehler
        """
        if not self.is_enabled():
            return None

        if not source_file.exists():
            self._log_event('store', str(source_file), '', 'error', 'Quell-Datei existiert nicht')
            return None

        try:
            # Bestimme Ziel-Pfad
            target_path = self._build_target_path(document_info, source_file.name)

            # Erstelle Ordner
            if create_folders:
                target_path.parent.mkdir(parents=True, exist_ok=True)

            # Prüfe ob Datei bereits existiert
            if target_path.exists():
                # Füge Suffix hinzu
                stem = target_path.stem
                suffix = target_path.suffix
                counter = 1
                while target_path.exists():
                    target_path = target_path.parent / f"{stem}_{counter}{suffix}"
                    counter += 1

            # Kopiere oder verschiebe
            copy_mode = self.config.get('copy_mode', 'copy')

            storage_type = self.config.get('storage_type', StorageType.LOCAL.value)

            if storage_type in [StorageType.LOCAL.value, StorageType.NETWORK.value]:
                # Lokaler/Netzwerk-Storage
                if copy_mode == 'move':
                    shutil.move(str(source_file), str(target_path))
                else:
                    shutil.copy2(str(source_file), str(target_path))

                self._log_event('store', str(source_file), str(target_path), 'success')
                return target_path

            elif storage_type == StorageType.DROPBOX.value:
                return self._store_to_dropbox(source_file, target_path, document_info)

            elif storage_type == StorageType.GOOGLE_DRIVE.value:
                return self._store_to_google_drive(source_file, target_path, document_info)

            elif storage_type == StorageType.ONEDRIVE.value:
                return self._store_to_onedrive(source_file, target_path, document_info)

        except Exception as e:
            self._log_event('store', str(source_file), '', 'error', str(e))
            return None

    def _store_to_dropbox(self, source_file: Path, target_path: Path, document_info: Dict) -> Optional[Path]:
        """
        Speichert Datei auf Dropbox

        Args:
            source_file: Quell-Datei
            target_path: Ziel-Pfad
            document_info: Dokument-Infos

        Returns:
            Virtueller Pfad bei Erfolg
        """
        try:
            import dropbox

            access_token = self.config.get('dropbox_access_token', '')
            if not access_token:
                raise ValueError("Kein Dropbox Access Token konfiguriert")

            dbx = dropbox.Dropbox(access_token)

            # Dropbox-Pfad (beginnt mit /)
            dropbox_path = '/' + str(target_path).replace('\\', '/')

            # Upload
            with open(source_file, 'rb') as f:
                dbx.files_upload(
                    f.read(),
                    dropbox_path,
                    mode=dropbox.files.WriteMode.add,
                    autorename=True
                )

            self._log_event('store', str(source_file), dropbox_path, 'success', 'Dropbox')
            return Path(dropbox_path)

        except Exception as e:
            self._log_event('store', str(source_file), '', 'error', f'Dropbox: {str(e)}')
            return None

    def _store_to_google_drive(self, source_file: Path, target_path: Path, document_info: Dict) -> Optional[Path]:
        """
        Speichert Datei auf Google Drive

        Args:
            source_file: Quell-Datei
            target_path: Ziel-Pfad
            document_info: Dokument-Infos

        Returns:
            Google Drive File ID bei Erfolg
        """
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2 import service_account

            credentials_path = self.config.get('google_drive_credentials', '')
            if not credentials_path:
                raise ValueError("Keine Google Drive Credentials konfiguriert")

            # Authentifizierung
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )

            service = build('drive', 'v3', credentials=credentials)

            # Erstelle Ordnerstruktur
            folder_id = self._get_or_create_drive_folder(service, target_path.parent)

            # Upload Datei
            file_metadata = {
                'name': target_path.name,
                'parents': [folder_id]
            }

            media = MediaFileUpload(str(source_file), resumable=True)

            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            file_id = file.get('id')

            self._log_event('store', str(source_file), file_id, 'success', 'Google Drive')
            return Path(file_id)

        except Exception as e:
            self._log_event('store', str(source_file), '', 'error', f'Google Drive: {str(e)}')
            return None

    def _get_or_create_drive_folder(self, service, folder_path: Path) -> str:
        """Erstellt Google Drive Ordnerstruktur und gibt Folder-ID zurück"""
        # Vereinfachte Implementierung - würde Ordner-Cache benötigen
        # Für jetzt: Erstelle in Root
        return 'root'

    def _store_to_onedrive(self, source_file: Path, target_path: Path, document_info: Dict) -> Optional[Path]:
        """
        Speichert Datei auf OneDrive

        Args:
            source_file: Quell-Datei
            target_path: Ziel-Pfad
            document_info: Dokument-Infos

        Returns:
            OneDrive Item ID bei Erfolg
        """
        try:
            # OneDrive integration würde O365 oder requests-basierte API benötigen
            # Vereinfachte Stub-Implementierung
            raise NotImplementedError("OneDrive-Integration noch nicht implementiert")

        except Exception as e:
            self._log_event('store', str(source_file), '', 'error', f'OneDrive: {str(e)}')
            return None

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken

        Returns:
            Dict mit Statistiken
        """
        import json

        stats = {
            'enabled': self.is_enabled(),
            'storage_type': self.config.get('storage_type', ''),
            'base_path': self.config.get('base_path', ''),
            'total_stored': 0,
            'total_errors': 0,
            'recent_files': []
        }

        # Lese Logs
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            if event['status'] == 'success':
                                stats['total_stored'] += 1
                            elif event['status'] == 'error':
                                stats['total_errors'] += 1
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen der Logs: {e}")

        return stats

    def get_recent_logs(self, count: int = 50) -> List[Dict]:
        """
        Liefert letzte Log-Einträge

        Args:
            count: Anzahl Einträge

        Returns:
            Liste von Log-Events
        """
        import json

        logs = []

        if not self.log_file.exists():
            return logs

        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line in lines[-count:]:
                try:
                    logs.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            print(f"Fehler beim Lesen der Logs: {e}")

        return logs

    def test_connection(self) -> tuple[bool, str]:
        """
        Testet Verbindung zum Storage

        Returns:
            (success, message)
        """
        storage_type = self.config.get('storage_type', StorageType.LOCAL.value)
        base_path = self.config.get('base_path', '')

        if not base_path:
            return False, "Kein Basis-Pfad konfiguriert"

        try:
            if storage_type in [StorageType.LOCAL.value, StorageType.NETWORK.value]:
                # Prüfe ob Pfad existiert oder erstellt werden kann
                path = Path(base_path)
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)

                # Teste Schreibrechte
                test_file = path / '.rhm_test'
                test_file.touch()
                test_file.unlink()

                return True, f"Verbindung erfolgreich: {base_path}"

            elif storage_type == StorageType.DROPBOX.value:
                import dropbox
                access_token = self.config.get('dropbox_access_token', '')
                if not access_token:
                    return False, "Kein Dropbox Access Token"

                dbx = dropbox.Dropbox(access_token)
                dbx.users_get_current_account()
                return True, "Dropbox-Verbindung erfolgreich"

            elif storage_type == StorageType.GOOGLE_DRIVE.value:
                from googleapiclient.discovery import build
                from google.oauth2 import service_account

                credentials_path = self.config.get('google_drive_credentials', '')
                if not credentials_path:
                    return False, "Keine Google Drive Credentials"

                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=['https://www.googleapis.com/auth/drive.file']
                )

                service = build('drive', 'v3', credentials=credentials)
                service.files().list(pageSize=1).execute()

                return True, "Google Drive-Verbindung erfolgreich"

            else:
                return False, f"Storage-Typ '{storage_type}' noch nicht unterstützt"

        except Exception as e:
            return False, f"Fehler: {str(e)}"
