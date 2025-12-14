"""
Kalender-Integration (Outlook/Exchange, Google Calendar)

Features:
- Automatische Termin-Erstellung für Fristen
- Erinnerungen konfigurierbar
- Unterstützung für Outlook/Exchange (O365)
- Unterstützung für Google Calendar
- Sync-Status-Tracking
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum


class CalendarType(Enum):
    """Kalender-Typen"""
    OUTLOOK = "Outlook/Exchange"
    GOOGLE = "Google Calendar"


class CalendarIntegration:
    """Kalender-Integration für Fristen"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Kalender-Integration

        Args:
            storage_dir: Storage-Verzeichnis für Konfiguration
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.storage_dir / "calendar_config.json"
        self.sync_log_file = self.storage_dir / "calendar_sync_log.jsonl"

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
            'calendar_type': CalendarType.OUTLOOK.value,

            # Outlook/Exchange (O365)
            'outlook_client_id': '',
            'outlook_client_secret': '',
            'outlook_tenant_id': '',
            'outlook_redirect_uri': 'http://localhost:8080',
            'outlook_calendar_id': '',  # Optional: Spezifischer Kalender

            # Google Calendar
            'google_credentials_path': '',
            'google_calendar_id': 'primary',  # 'primary' für Haupt-Kalender

            # Termin-Einstellungen
            'reminder_minutes_before': [1440, 60],  # 24h und 1h vorher
            'event_duration_minutes': 60,
            'add_to_description': True,  # Dokument-Infos in Beschreibung
            'auto_sync': True,

            # Token-Speicher
            'outlook_access_token': '',
            'outlook_refresh_token': '',
            'google_token': {}
        }

    def _save_config(self):
        """Speichert Konfiguration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")

    def _log_event(self, event_type: str, status: str, message: str = "", details: Optional[Dict] = None):
        """Loggt Sync-Event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'status': status,
            'message': message,
            'details': details or {}
        }

        try:
            with open(self.sync_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"Fehler beim Loggen: {e}")

    def configure_outlook(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        redirect_uri: str = 'http://localhost:8080'
    ):
        """
        Konfiguriert Outlook/Exchange-Integration

        Args:
            client_id: Azure AD App Client ID
            client_secret: Azure AD App Client Secret
            tenant_id: Azure AD Tenant ID
            redirect_uri: Redirect URI
        """
        self.config['calendar_type'] = CalendarType.OUTLOOK.value
        self.config['outlook_client_id'] = client_id
        self.config['outlook_client_secret'] = client_secret
        self.config['outlook_tenant_id'] = tenant_id
        self.config['outlook_redirect_uri'] = redirect_uri
        self.config['enabled'] = True
        self._save_config()

    def configure_google(self, credentials_path: str, calendar_id: str = 'primary'):
        """
        Konfiguriert Google Calendar-Integration

        Args:
            credentials_path: Pfad zu Google API Credentials JSON
            calendar_id: Kalender-ID (default: 'primary')
        """
        self.config['calendar_type'] = CalendarType.GOOGLE.value
        self.config['google_credentials_path'] = credentials_path
        self.config['google_calendar_id'] = calendar_id
        self.config['enabled'] = True
        self._save_config()

    def is_enabled(self) -> bool:
        """Prüft ob Integration aktiviert ist"""
        return self.config.get('enabled', False)

    def _authenticate_outlook(self) -> bool:
        """
        Authentifiziert mit Outlook/Exchange

        Returns:
            True bei Erfolg
        """
        try:
            from O365 import Account

            credentials = (
                self.config['outlook_client_id'],
                self.config['outlook_client_secret']
            )

            account = Account(credentials, tenant_id=self.config.get('outlook_tenant_id'))

            # Prüfe ob Token bereits vorhanden
            if self.config.get('outlook_access_token'):
                # Verwende gespeicherten Token
                account.connection.token_backend.token = {
                    'access_token': self.config['outlook_access_token'],
                    'refresh_token': self.config['outlook_refresh_token']
                }

                if account.is_authenticated:
                    return True

            # Authentifiziere neu
            if account.authenticate(scopes=['basic', 'calendar']):
                # Speichere Token
                token = account.connection.token_backend.token
                self.config['outlook_access_token'] = token.get('access_token', '')
                self.config['outlook_refresh_token'] = token.get('refresh_token', '')
                self._save_config()
                return True

            return False

        except ImportError:
            print("O365-Bibliothek nicht installiert. Installiere mit: pip install O365")
            return False
        except Exception as e:
            print(f"Fehler bei Outlook-Authentifizierung: {e}")
            return False

    def _get_google_service(self):
        """
        Erstellt Google Calendar Service

        Returns:
            Google Calendar Service object
        """
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow

            SCOPES = ['https://www.googleapis.com/auth/calendar']

            creds = None

            # Lade gespeicherten Token
            if self.config.get('google_token'):
                token_info = self.config['google_token']
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)

            # Wenn kein Token oder abgelaufen
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.config['google_credentials_path'],
                        SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # Speichere Token
                self.config['google_token'] = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes
                }
                self._save_config()

            service = build('calendar', 'v3', credentials=creds)
            return service

        except ImportError:
            print("Google API Bibliotheken nicht installiert. Installiere mit: pip install google-api-python-client google-auth-oauthlib")
            return None
        except Exception as e:
            print(f"Fehler bei Google-Authentifizierung: {e}")
            return None

    def create_deadline_event(
        self,
        deadline_info: Dict,
        document_info: Dict
    ) -> Optional[str]:
        """
        Erstellt Kalender-Termin für Frist

        Args:
            deadline_info: Deadline-Informationen
            document_info: Dokument-Informationen

        Returns:
            Event-ID bei Erfolg, None bei Fehler
        """
        if not self.is_enabled():
            return None

        calendar_type = self.config.get('calendar_type')

        if calendar_type == CalendarType.OUTLOOK.value:
            return self._create_outlook_event(deadline_info, document_info)
        elif calendar_type == CalendarType.GOOGLE.value:
            return self._create_google_event(deadline_info, document_info)

        return None

    def _create_outlook_event(
        self,
        deadline_info: Dict,
        document_info: Dict
    ) -> Optional[str]:
        """
        Erstellt Outlook-Termin

        Args:
            deadline_info: Deadline-Informationen
            document_info: Dokument-Informationen

        Returns:
            Event-ID bei Erfolg
        """
        try:
            from O365 import Account

            if not self._authenticate_outlook():
                return None

            credentials = (
                self.config['outlook_client_id'],
                self.config['outlook_client_secret']
            )

            account = Account(credentials, tenant_id=self.config.get('outlook_tenant_id'))

            # Hole Kalender
            schedule = account.schedule()
            calendar = schedule.get_default_calendar()

            # Extrahiere Informationen
            earliest_deadline = deadline_info.get('earliest_deadline', {})
            deadline_date_str = earliest_deadline.get('datum', '')
            deadline_text = earliest_deadline.get('text', '')
            priority = deadline_info.get('priority', 'NORMAL')

            aktenzeichen = document_info.get('aktenzeichen_info', {}).get('internes_az', 'Ohne AZ')
            sachbearbeiter = document_info.get('sachbearbeiter', 'Unbekannt')
            dateiname = document_info.get('dateiname', '')

            # Parse Datum
            try:
                # Versuche verschiedene Formate
                for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d.%m.%y']:
                    try:
                        deadline_date = datetime.strptime(deadline_date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # Kein Format passte
                    deadline_date = datetime.now() + timedelta(days=7)
            except:
                deadline_date = datetime.now() + timedelta(days=7)

            # Erstelle Event
            event = calendar.new_event()

            # Titel mit Prioritäts-Emoji
            emoji_map = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'NORMAL': '🟢'}
            emoji = emoji_map.get(priority, '📋')

            event.subject = f"{emoji} Frist: {aktenzeichen}"

            # Beschreibung
            description = f"""
Frist-Erinnerung

Aktenzeichen: {aktenzeichen}
Sachbearbeiter: {sachbearbeiter}
Dokument: {dateiname}

Frist-Text: "{deadline_text}"

Priorität: {priority}
"""

            event.body = description

            # Zeitpunkt
            event.start = deadline_date.replace(hour=9, minute=0, second=0)
            event.end = event.start + timedelta(minutes=self.config.get('event_duration_minutes', 60))

            # Erinnerungen
            for minutes in self.config.get('reminder_minutes_before', [1440, 60]):
                event.remind_before_minutes = minutes

            # Speichern
            event.save()

            event_id = event.object_id

            self._log_event(
                'create_event',
                'success',
                f"Outlook-Termin erstellt: {aktenzeichen}",
                {'event_id': event_id, 'deadline_date': deadline_date_str}
            )

            return event_id

        except Exception as e:
            self._log_event('create_event', 'error', f"Outlook-Fehler: {str(e)}")
            print(f"Fehler beim Erstellen des Outlook-Termins: {e}")
            return None

    def _create_google_event(
        self,
        deadline_info: Dict,
        document_info: Dict
    ) -> Optional[str]:
        """
        Erstellt Google Calendar-Termin

        Args:
            deadline_info: Deadline-Informationen
            document_info: Dokument-Informationen

        Returns:
            Event-ID bei Erfolg
        """
        try:
            service = self._get_google_service()
            if not service:
                return None

            # Extrahiere Informationen
            earliest_deadline = deadline_info.get('earliest_deadline', {})
            deadline_date_str = earliest_deadline.get('datum', '')
            deadline_text = earliest_deadline.get('text', '')
            priority = deadline_info.get('priority', 'NORMAL')

            aktenzeichen = document_info.get('aktenzeichen_info', {}).get('internes_az', 'Ohne AZ')
            sachbearbeiter = document_info.get('sachbearbeiter', 'Unbekannt')
            dateiname = document_info.get('dateiname', '')

            # Parse Datum
            try:
                for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d.%m.%y']:
                    try:
                        deadline_date = datetime.strptime(deadline_date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    deadline_date = datetime.now() + timedelta(days=7)
            except:
                deadline_date = datetime.now() + timedelta(days=7)

            # Erstelle Event
            emoji_map = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'NORMAL': '🟢'}
            emoji = emoji_map.get(priority, '📋')

            event = {
                'summary': f"{emoji} Frist: {aktenzeichen}",
                'description': f"""
Frist-Erinnerung

Aktenzeichen: {aktenzeichen}
Sachbearbeiter: {sachbearbeiter}
Dokument: {dateiname}

Frist-Text: "{deadline_text}"

Priorität: {priority}
""",
                'start': {
                    'dateTime': deadline_date.replace(hour=9, minute=0, second=0).isoformat(),
                    'timeZone': 'Europe/Berlin',
                },
                'end': {
                    'dateTime': (deadline_date.replace(hour=9, minute=0, second=0) +
                                timedelta(minutes=self.config.get('event_duration_minutes', 60))).isoformat(),
                    'timeZone': 'Europe/Berlin',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': minutes}
                        for minutes in self.config.get('reminder_minutes_before', [1440, 60])
                    ],
                },
            }

            # Optional: Farbe basierend auf Priorität
            color_map = {'CRITICAL': '11', 'HIGH': '6', 'MEDIUM': '5', 'NORMAL': '2'}
            event['colorId'] = color_map.get(priority, '1')

            # Event erstellen
            calendar_id = self.config.get('google_calendar_id', 'primary')
            created_event = service.events().insert(calendarId=calendar_id, body=event).execute()

            event_id = created_event.get('id')

            self._log_event(
                'create_event',
                'success',
                f"Google Calendar-Termin erstellt: {aktenzeichen}",
                {'event_id': event_id, 'deadline_date': deadline_date_str}
            )

            return event_id

        except Exception as e:
            self._log_event('create_event', 'error', f"Google-Fehler: {str(e)}")
            print(f"Fehler beim Erstellen des Google Calendar-Termins: {e}")
            return None

    def delete_event(self, event_id: str) -> bool:
        """
        Löscht Kalender-Termin

        Args:
            event_id: Event-ID

        Returns:
            True bei Erfolg
        """
        if not self.is_enabled():
            return False

        calendar_type = self.config.get('calendar_type')

        try:
            if calendar_type == CalendarType.OUTLOOK.value:
                from O365 import Account

                if not self._authenticate_outlook():
                    return False

                credentials = (
                    self.config['outlook_client_id'],
                    self.config['outlook_client_secret']
                )

                account = Account(credentials, tenant_id=self.config.get('outlook_tenant_id'))
                schedule = account.schedule()
                calendar = schedule.get_default_calendar()

                event = calendar.get_event(event_id)
                if event:
                    event.delete()
                    self._log_event('delete_event', 'success', f"Event gelöscht: {event_id}")
                    return True

            elif calendar_type == CalendarType.GOOGLE.value:
                service = self._get_google_service()
                if not service:
                    return False

                calendar_id = self.config.get('google_calendar_id', 'primary')
                service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

                self._log_event('delete_event', 'success', f"Event gelöscht: {event_id}")
                return True

        except Exception as e:
            self._log_event('delete_event', 'error', f"Fehler: {str(e)}")
            print(f"Fehler beim Löschen des Events: {e}")

        return False

    def test_connection(self) -> Tuple[bool, str]:
        """
        Testet Kalender-Verbindung

        Returns:
            (success, message)
        """
        if not self.is_enabled():
            return False, "Kalender-Integration nicht aktiviert"

        calendar_type = self.config.get('calendar_type')

        try:
            if calendar_type == CalendarType.OUTLOOK.value:
                if self._authenticate_outlook():
                    return True, "Outlook-Verbindung erfolgreich"
                else:
                    return False, "Outlook-Authentifizierung fehlgeschlagen"

            elif calendar_type == CalendarType.GOOGLE.value:
                service = self._get_google_service()
                if service:
                    # Teste Zugriff
                    calendar_id = self.config.get('google_calendar_id', 'primary')
                    service.events().list(calendarId=calendar_id, maxResults=1).execute()
                    return True, "Google Calendar-Verbindung erfolgreich"
                else:
                    return False, "Google Calendar-Authentifizierung fehlgeschlagen"

        except Exception as e:
            return False, f"Fehler: {str(e)}"

        return False, "Unbekannter Kalender-Typ"

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken

        Returns:
            Dict mit Statistiken
        """
        stats = {
            'enabled': self.is_enabled(),
            'calendar_type': self.config.get('calendar_type', ''),
            'total_created': 0,
            'total_errors': 0
        }

        # Lese Logs
        if self.sync_log_file.exists():
            try:
                with open(self.sync_log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            if event['event_type'] == 'create_event':
                                if event['status'] == 'success':
                                    stats['total_created'] += 1
                                elif event['status'] == 'error':
                                    stats['total_errors'] += 1
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen der Logs: {e}")

        return stats
