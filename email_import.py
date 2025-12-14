"""
Email-Import via IMAP

Features:
- Automatischer Import von PDF-Anhängen aus Postfach
- Unterstützung für IMAP (Gmail, Outlook, etc.)
- Filter nach Absender/Betreff
- Automatische Verarbeitung
- Markierung verarbeiteter Emails
"""

import imaplib
import email
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from email.header import decode_header
import io


class EmailImporter:
    """Importiert PDFs aus Email-Postfach"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Email-Importer

        Args:
            storage_dir: Storage-Verzeichnis für Konfiguration und Logs
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.storage_dir / "email_import_config.json"
        self.log_file = self.storage_dir / "email_import_log.jsonl"
        self.processed_file = self.storage_dir / "processed_emails.json"

        # Lade Konfiguration
        self.config = self._load_config()

        # Lade verarbeitete Email-IDs
        self.processed_emails = self._load_processed_emails()

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

            # IMAP-Einstellungen
            'imap_server': '',
            'imap_port': 993,
            'imap_use_ssl': True,
            'username': '',
            'password': '',

            # Filter
            'inbox_folder': 'INBOX',
            'filter_sender': [],  # Liste von Absendern
            'filter_subject_contains': [],  # Liste von Stichworten
            'only_unread': True,

            # Verarbeitung
            'mark_as_read': True,
            'move_to_folder': '',  # Optional: Verschiebe nach Verarbeitung
            'delete_after_processing': False,

            # Auto-Import
            'auto_import_enabled': False,
            'auto_import_interval_minutes': 15
        }

    def _save_config(self):
        """Speichert Konfiguration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")

    def _load_processed_emails(self) -> set:
        """Lädt bereits verarbeitete Email-IDs"""
        if self.processed_file.exists():
            try:
                with open(self.processed_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get('email_ids', []))
            except:
                pass
        return set()

    def _save_processed_emails(self):
        """Speichert verarbeitete Email-IDs"""
        try:
            with open(self.processed_file, 'w', encoding='utf-8') as f:
                json.dump({'email_ids': list(self.processed_emails)}, f)
        except Exception as e:
            print(f"Fehler beim Speichern der Email-IDs: {e}")

    def _log_event(self, event_type: str, status: str, message: str = "", details: Optional[Dict] = None):
        """Loggt Email-Import-Event"""
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

    def configure(
        self,
        imap_server: str,
        username: str,
        password: str,
        imap_port: int = 993,
        use_ssl: bool = True
    ):
        """
        Konfiguriert Email-Import

        Args:
            imap_server: IMAP-Server (z.B. 'imap.gmail.com')
            username: Email-Adresse / Benutzername
            password: Passwort oder App-Passwort
            imap_port: IMAP-Port (Standard: 993)
            use_ssl: SSL verwenden (Standard: True)
        """
        self.config['imap_server'] = imap_server
        self.config['imap_port'] = imap_port
        self.config['imap_use_ssl'] = use_ssl
        self.config['username'] = username
        self.config['password'] = password
        self.config['enabled'] = True
        self._save_config()

    def set_filters(
        self,
        sender_filter: Optional[List[str]] = None,
        subject_filter: Optional[List[str]] = None,
        only_unread: bool = True
    ):
        """
        Setzt Filter für Email-Import

        Args:
            sender_filter: Nur Emails von diesen Absendern
            subject_filter: Nur Emails mit diesen Stichworten im Betreff
            only_unread: Nur ungelesene Emails
        """
        if sender_filter is not None:
            self.config['filter_sender'] = sender_filter
        if subject_filter is not None:
            self.config['filter_subject_contains'] = subject_filter
        self.config['only_unread'] = only_unread
        self._save_config()

    def is_enabled(self) -> bool:
        """Prüft ob Email-Import aktiviert ist"""
        return self.config.get('enabled', False)

    def _connect(self) -> Optional[imaplib.IMAP4_SSL]:
        """
        Verbindet zu IMAP-Server

        Returns:
            IMAP-Verbindung oder None bei Fehler
        """
        try:
            if self.config.get('imap_use_ssl', True):
                mail = imaplib.IMAP4_SSL(
                    self.config['imap_server'],
                    self.config['imap_port']
                )
            else:
                mail = imaplib.IMAP4(
                    self.config['imap_server'],
                    self.config['imap_port']
                )

            mail.login(
                self.config['username'],
                self.config['password']
            )

            return mail

        except Exception as e:
            self._log_event('connect', 'error', f"Verbindungsfehler: {str(e)}")
            print(f"Fehler bei IMAP-Verbindung: {e}")
            return None

    def _decode_header_value(self, value: str) -> str:
        """Dekodiert Email-Header"""
        if not value:
            return ""

        decoded_parts = []
        for part, encoding in decode_header(value):
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
            else:
                decoded_parts.append(part)

        return ''.join(decoded_parts)

    def fetch_emails_with_pdfs(self) -> List[Dict]:
        """
        Holt Emails mit PDF-Anhängen

        Returns:
            Liste von Dictionaries mit Email-Info und PDFs
        """
        if not self.is_enabled():
            return []

        mail = self._connect()
        if not mail:
            return []

        results = []

        try:
            # Wähle Postfach
            inbox = self.config.get('inbox_folder', 'INBOX')
            mail.select(inbox)

            # Baue Such-Kriterium
            search_criteria = []

            if self.config.get('only_unread', True):
                search_criteria.append('UNSEEN')
            else:
                search_criteria.append('ALL')

            # Suche
            search_string = ' '.join(search_criteria)
            status, messages = mail.search(None, search_string)

            if status != 'OK':
                return results

            email_ids = messages[0].split()

            for email_id in email_ids:
                email_id_str = email_id.decode()

                # Prüfe ob bereits verarbeitet
                if email_id_str in self.processed_emails:
                    continue

                # Hole Email
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue

                # Parse Email
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Extrahiere Header
                from_header = self._decode_header_value(msg.get('From', ''))
                subject_header = self._decode_header_value(msg.get('Subject', ''))
                date_header = msg.get('Date', '')

                # Prüfe Filter
                if self.config.get('filter_sender'):
                    # Prüfe ob Absender in Filter-Liste
                    if not any(sender.lower() in from_header.lower()
                              for sender in self.config['filter_sender']):
                        continue

                if self.config.get('filter_subject_contains'):
                    # Prüfe ob Stichwort in Betreff
                    if not any(keyword.lower() in subject_header.lower()
                              for keyword in self.config['filter_subject_contains']):
                        continue

                # Extrahiere PDF-Anhänge
                pdf_attachments = []

                for part in msg.walk():
                    # Nur Anhänge
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue

                    filename = part.get_filename()
                    if not filename:
                        continue

                    filename = self._decode_header_value(filename)

                    # Nur PDFs
                    if not filename.lower().endswith('.pdf'):
                        continue

                    # Hole PDF-Daten
                    pdf_data = part.get_payload(decode=True)

                    pdf_attachments.append({
                        'filename': filename,
                        'data': pdf_data,
                        'size': len(pdf_data)
                    })

                # Wenn PDFs gefunden
                if pdf_attachments:
                    results.append({
                        'email_id': email_id_str,
                        'from': from_header,
                        'subject': subject_header,
                        'date': date_header,
                        'pdf_count': len(pdf_attachments),
                        'pdfs': pdf_attachments
                    })

                    self._log_event(
                        'fetch',
                        'success',
                        f"Email mit {len(pdf_attachments)} PDF(s) gefunden",
                        {'from': from_header, 'subject': subject_header}
                    )

        except Exception as e:
            self._log_event('fetch', 'error', f"Fehler beim Abrufen: {str(e)}")
            print(f"Fehler beim Abrufen der Emails: {e}")

        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass

        return results

    def mark_email_as_processed(self, email_id: str, mark_as_read: bool = True):
        """
        Markiert Email als verarbeitet

        Args:
            email_id: Email-ID
            mark_as_read: Als gelesen markieren
        """
        # Zu verarbeiteten hinzufügen
        self.processed_emails.add(email_id)
        self._save_processed_emails()

        # Optional: Als gelesen markieren
        if mark_as_read and self.config.get('mark_as_read', True):
            mail = self._connect()
            if mail:
                try:
                    inbox = self.config.get('inbox_folder', 'INBOX')
                    mail.select(inbox)

                    # Markiere als gelesen
                    mail.store(email_id.encode(), '+FLAGS', '\\Seen')

                    # Optional: Verschiebe in anderen Ordner
                    move_to = self.config.get('move_to_folder', '')
                    if move_to:
                        mail.copy(email_id.encode(), move_to)
                        if self.config.get('delete_after_processing', False):
                            mail.store(email_id.encode(), '+FLAGS', '\\Deleted')
                            mail.expunge()

                    mail.close()
                    mail.logout()

                except Exception as e:
                    print(f"Fehler beim Markieren der Email: {e}")

    def test_connection(self) -> Tuple[bool, str]:
        """
        Testet IMAP-Verbindung

        Returns:
            (success, message)
        """
        if not self.is_enabled():
            return False, "Email-Import nicht aktiviert"

        mail = self._connect()
        if mail:
            try:
                # Teste Zugriff auf Postfach
                inbox = self.config.get('inbox_folder', 'INBOX')
                status, _ = mail.select(inbox)

                mail.close()
                mail.logout()

                if status == 'OK':
                    return True, f"Verbindung erfolgreich (Postfach: {inbox})"
                else:
                    return False, f"Postfach '{inbox}' nicht gefunden"

            except Exception as e:
                return False, f"Fehler: {str(e)}"
        else:
            return False, "Verbindung fehlgeschlagen"

    def get_mailbox_list(self) -> List[str]:
        """
        Listet verfügbare Postfächer auf

        Returns:
            Liste von Postfach-Namen
        """
        mail = self._connect()
        if not mail:
            return []

        mailboxes = []

        try:
            status, folders = mail.list()
            if status == 'OK':
                for folder in folders:
                    # Parse Folder-Namen
                    parts = folder.decode().split(' ')
                    if len(parts) >= 3:
                        folder_name = parts[-1].strip('"')
                        mailboxes.append(folder_name)

            mail.logout()

        except Exception as e:
            print(f"Fehler beim Abrufen der Postfächer: {e}")

        return mailboxes

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken

        Returns:
            Dict mit Statistiken
        """
        stats = {
            'enabled': self.is_enabled(),
            'imap_server': self.config.get('imap_server', ''),
            'username': self.config.get('username', ''),
            'total_processed': len(self.processed_emails),
            'total_fetched': 0,
            'total_errors': 0
        }

        # Lese Logs
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            if event['event_type'] == 'fetch':
                                if event['status'] == 'success':
                                    stats['total_fetched'] += 1
                                elif event['status'] == 'error':
                                    stats['total_errors'] += 1
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen der Logs: {e}")

        return stats

    def clear_processed_cache(self):
        """Löscht Cache der verarbeiteten Emails"""
        self.processed_emails = set()
        self._save_processed_emails()
