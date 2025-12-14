"""
Frist-Benachrichtigungen (Email, Desktop, Slack/Teams)

Features:
- Email-Benachrichtigungen für kritische Fristen
- Tägliche Zusammenfassungen
- Desktop-Benachrichtigungen
- Optional: Slack/Teams-Webhooks
- Konfigurierbare Erinnerungs-Zeiten
"""

import smtplib
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import requests


class NotificationManager:
    """Verwaltet Frist-Benachrichtigungen"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Notification Manager

        Args:
            storage_dir: Storage-Verzeichnis für Konfiguration
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.storage_dir / "notification_config.json"
        self.log_file = self.storage_dir / "notification_log.jsonl"

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
            'email_enabled': False,
            'desktop_enabled': False,
            'slack_enabled': False,
            'teams_enabled': False,

            # Email-Einstellungen
            'smtp_server': '',
            'smtp_port': 587,
            'smtp_use_tls': True,
            'smtp_username': '',
            'smtp_password': '',
            'email_from': '',
            'email_recipients': [],  # Liste von Email-Adressen

            # Benachrichtigungs-Regeln
            'notify_critical_immediately': True,  # < 3 Tage
            'notify_high_threshold': 7,  # Benachrichtige wenn < 7 Tage
            'notify_medium_threshold': 14,  # Benachrichtige wenn < 14 Tage
            'daily_summary_enabled': True,
            'daily_summary_time': '08:00',  # HH:MM

            # Slack/Teams
            'slack_webhook_url': '',
            'teams_webhook_url': ''
        }

    def _save_config(self):
        """Speichert Konfiguration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")

    def _log_event(self, notification_type: str, recipient: str, status: str, message: str = ""):
        """Loggt Benachrichtigungs-Event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': notification_type,
            'recipient': recipient,
            'status': status,
            'message': message
        }

        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"Fehler beim Loggen: {e}")

    def configure_email(
        self,
        smtp_server: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        email_from: str,
        email_recipients: List[str],
        use_tls: bool = True
    ):
        """
        Konfiguriert Email-Benachrichtigungen

        Args:
            smtp_server: SMTP-Server
            smtp_port: SMTP-Port
            smtp_username: SMTP-Benutzername
            smtp_password: SMTP-Passwort
            email_from: Absender-Email
            email_recipients: Liste von Empfänger-Emails
            use_tls: TLS verwenden
        """
        self.config['smtp_server'] = smtp_server
        self.config['smtp_port'] = smtp_port
        self.config['smtp_username'] = smtp_username
        self.config['smtp_password'] = smtp_password
        self.config['email_from'] = email_from
        self.config['email_recipients'] = email_recipients
        self.config['smtp_use_tls'] = use_tls
        self.config['email_enabled'] = True
        self._save_config()

    def configure_slack(self, webhook_url: str):
        """
        Konfiguriert Slack-Benachrichtigungen

        Args:
            webhook_url: Slack Webhook URL
        """
        self.config['slack_webhook_url'] = webhook_url
        self.config['slack_enabled'] = True
        self._save_config()

    def configure_teams(self, webhook_url: str):
        """
        Konfiguriert Teams-Benachrichtigungen

        Args:
            webhook_url: Teams Webhook URL
        """
        self.config['teams_webhook_url'] = webhook_url
        self.config['teams_enabled'] = True
        self._save_config()

    def enable_desktop_notifications(self):
        """Aktiviert Desktop-Benachrichtigungen"""
        self.config['desktop_enabled'] = True
        self._save_config()

    def disable_desktop_notifications(self):
        """Deaktiviert Desktop-Benachrichtigungen"""
        self.config['desktop_enabled'] = False
        self._save_config()

    def send_deadline_alert(
        self,
        deadline_info: Dict,
        document_info: Dict,
        channels: Optional[List[str]] = None
    ) -> bool:
        """
        Sendet Frist-Benachrichtigung

        Args:
            deadline_info: Deadline-Informationen aus DeadlineDetector
            document_info: Dokument-Informationen
            channels: Optional Liste von Kanälen ('email', 'desktop', 'slack', 'teams')

        Returns:
            True bei Erfolg
        """
        if not channels:
            channels = []
            if self.config.get('email_enabled'): channels.append('email')
            if self.config.get('desktop_enabled'): channels.append('desktop')
            if self.config.get('slack_enabled'): channels.append('slack')
            if self.config.get('teams_enabled'): channels.append('teams')

        # Extrahiere Informationen
        earliest_deadline = deadline_info.get('earliest_deadline', {})
        deadline_date = earliest_deadline.get('datum', 'Unbekannt')
        deadline_text = earliest_deadline.get('text', '')
        priority = deadline_info.get('priority', 'NORMAL')
        days_remaining = earliest_deadline.get('days_remaining', 999)

        sachbearbeiter = document_info.get('sachbearbeiter', 'Unbekannt')
        aktenzeichen = document_info.get('aktenzeichen_info', {}).get('internes_az', 'Ohne AZ')
        dateiname = document_info.get('dateiname', 'Unbekannt')

        # Erstelle Nachricht
        subject = f"⚠️ Frist-Erinnerung: {aktenzeichen} ({priority})"

        body = f"""
Frist-Erinnerung für Dokument

📋 Aktenzeichen: {aktenzeichen}
👤 Sachbearbeiter: {sachbearbeiter}
📄 Dokument: {dateiname}

⏰ Frist: {deadline_date}
📅 Verbleibende Tage: {days_remaining}
🎯 Priorität: {priority}

📝 Frist-Text: "{deadline_text}"

---
Diese Benachrichtigung wurde automatisch erstellt.
"""

        success = True

        # Email
        if 'email' in channels:
            email_success = self._send_email(subject, body)
            success = success and email_success

        # Desktop
        if 'desktop' in channels:
            desktop_success = self._send_desktop_notification(subject, deadline_text)
            success = success and desktop_success

        # Slack
        if 'slack' in channels:
            slack_success = self._send_slack_notification(subject, body, priority)
            success = success and slack_success

        # Teams
        if 'teams' in channels:
            teams_success = self._send_teams_notification(subject, body, priority)
            success = success and teams_success

        return success

    def _send_email(self, subject: str, body: str, attachment_path: Optional[Path] = None) -> bool:
        """
        Sendet Email

        Args:
            subject: Betreff
            body: Email-Text
            attachment_path: Optional Anhang

        Returns:
            True bei Erfolg
        """
        if not self.config.get('email_enabled'):
            return False

        try:
            # Erstelle Email
            msg = MIMEMultipart()
            msg['From'] = self.config['email_from']
            msg['To'] = ', '.join(self.config['email_recipients'])
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Optional: Anhang
            if attachment_path and Path(attachment_path).exists():
                with open(attachment_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {Path(attachment_path).name}'
                    )
                    msg.attach(part)

            # Verbinde zu SMTP
            if self.config.get('smtp_use_tls', True):
                server = smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port'])
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.config['smtp_server'], self.config['smtp_port'])

            # Login
            if self.config.get('smtp_username') and self.config.get('smtp_password'):
                server.login(self.config['smtp_username'], self.config['smtp_password'])

            # Sende
            server.send_message(msg)
            server.quit()

            self._log_event('email', ', '.join(self.config['email_recipients']), 'success', subject)
            return True

        except Exception as e:
            self._log_event('email', '', 'error', str(e))
            print(f"Fehler beim Email-Versand: {e}")
            return False

    def _send_desktop_notification(self, title: str, message: str) -> bool:
        """
        Sendet Desktop-Benachrichtigung

        Args:
            title: Titel
            message: Nachricht

        Returns:
            True bei Erfolg
        """
        if not self.config.get('desktop_enabled'):
            return False

        try:
            # Plyer für Cross-Platform Desktop-Benachrichtigungen
            try:
                from plyer import notification
                notification.notify(
                    title=title,
                    message=message[:200],  # Limitiere Länge
                    app_name='RHM Document Processor',
                    timeout=10
                )
                self._log_event('desktop', 'local', 'success', title)
                return True
            except ImportError:
                # Fallback für Windows
                import platform
                if platform.system() == 'Windows':
                    from win10toast import ToastNotifier
                    toaster = ToastNotifier()
                    toaster.show_toast(
                        title,
                        message[:200],
                        duration=10,
                        threaded=True
                    )
                    self._log_event('desktop', 'local', 'success', title)
                    return True
                else:
                    # Kein Desktop-Notification verfügbar
                    self._log_event('desktop', 'local', 'error', 'Keine Library verfügbar')
                    return False

        except Exception as e:
            self._log_event('desktop', 'local', 'error', str(e))
            print(f"Fehler bei Desktop-Benachrichtigung: {e}")
            return False

    def _send_slack_notification(self, title: str, message: str, priority: str) -> bool:
        """
        Sendet Slack-Benachrichtigung

        Args:
            title: Titel
            message: Nachricht
            priority: Priorität

        Returns:
            True bei Erfolg
        """
        if not self.config.get('slack_enabled'):
            return False

        webhook_url = self.config.get('slack_webhook_url', '')
        if not webhook_url:
            return False

        try:
            # Emoji basierend auf Priorität
            emoji_map = {
                'CRITICAL': '🔴',
                'HIGH': '🟠',
                'MEDIUM': '🟡',
                'NORMAL': '🟢'
            }
            emoji = emoji_map.get(priority, '📋')

            payload = {
                'text': f"{emoji} {title}",
                'blocks': [
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': f"*{title}*"
                        }
                    },
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': message
                        }
                    }
                ]
            }

            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                self._log_event('slack', 'webhook', 'success', title)
                return True
            else:
                self._log_event('slack', 'webhook', 'error', f"HTTP {response.status_code}")
                return False

        except Exception as e:
            self._log_event('slack', 'webhook', 'error', str(e))
            print(f"Fehler bei Slack-Benachrichtigung: {e}")
            return False

    def _send_teams_notification(self, title: str, message: str, priority: str) -> bool:
        """
        Sendet Teams-Benachrichtigung

        Args:
            title: Titel
            message: Nachricht
            priority: Priorität

        Returns:
            True bei Erfolg
        """
        if not self.config.get('teams_enabled'):
            return False

        webhook_url = self.config.get('teams_webhook_url', '')
        if not webhook_url:
            return False

        try:
            # Teams verwendet Adaptive Cards
            color_map = {
                'CRITICAL': 'FF0000',
                'HIGH': 'FF8C00',
                'MEDIUM': 'FFD700',
                'NORMAL': '00FF00'
            }
            color = color_map.get(priority, '0078D7')

            payload = {
                '@type': 'MessageCard',
                '@context': 'https://schema.org/extensions',
                'summary': title,
                'themeColor': color,
                'title': title,
                'text': message
            }

            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                self._log_event('teams', 'webhook', 'success', title)
                return True
            else:
                self._log_event('teams', 'webhook', 'error', f"HTTP {response.status_code}")
                return False

        except Exception as e:
            self._log_event('teams', 'webhook', 'error', str(e))
            print(f"Fehler bei Teams-Benachrichtigung: {e}")
            return False

    def send_daily_summary(self, deadlines: List[Dict]) -> bool:
        """
        Sendet tägliche Zusammenfassung aller Fristen

        Args:
            deadlines: Liste von Deadline-Informationen

        Returns:
            True bei Erfolg
        """
        if not self.config.get('daily_summary_enabled'):
            return False

        # Gruppiere nach Priorität
        by_priority = {
            'CRITICAL': [],
            'HIGH': [],
            'MEDIUM': [],
            'NORMAL': []
        }

        for deadline in deadlines:
            priority = deadline.get('priority', 'NORMAL')
            by_priority.get(priority, []).append(deadline)

        # Erstelle Zusammenfassung
        subject = f"📅 Tägliche Frist-Übersicht ({datetime.now().strftime('%d.%m.%Y')})"

        body = f"""
Tägliche Frist-Übersicht
========================

Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}

"""

        for priority in ['CRITICAL', 'HIGH', 'MEDIUM', 'NORMAL']:
            items = by_priority[priority]
            if not items:
                continue

            emoji_map = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'NORMAL': '🟢'}
            body += f"\n{emoji_map[priority]} {priority} ({len(items)})\n"
            body += "-" * 50 + "\n"

            for item in items:
                aktenzeichen = item.get('aktenzeichen', 'Ohne AZ')
                sachbearbeiter = item.get('sachbearbeiter', 'Unbekannt')
                deadline_date = item.get('deadline_date', 'Unbekannt')
                days_remaining = item.get('days_remaining', '?')

                body += f"  • {aktenzeichen} ({sachbearbeiter})\n"
                body += f"    Frist: {deadline_date} ({days_remaining} Tage)\n\n"

        body += "\n---\nDiese Zusammenfassung wurde automatisch erstellt.\n"

        # Sende Email
        return self._send_email(subject, body)

    def test_email_connection(self) -> tuple[bool, str]:
        """
        Testet Email-Konfiguration

        Returns:
            (success, message)
        """
        if not self.config.get('email_enabled'):
            return False, "Email-Benachrichtigungen nicht aktiviert"

        try:
            if self.config.get('smtp_use_tls', True):
                server = smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port'])
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.config['smtp_server'], self.config['smtp_port'])

            if self.config.get('smtp_username') and self.config.get('smtp_password'):
                server.login(self.config['smtp_username'], self.config['smtp_password'])

            server.quit()
            return True, "Email-Verbindung erfolgreich"

        except Exception as e:
            return False, f"Fehler: {str(e)}"

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken

        Returns:
            Dict mit Statistiken
        """
        stats = {
            'email_enabled': self.config.get('email_enabled', False),
            'desktop_enabled': self.config.get('desktop_enabled', False),
            'slack_enabled': self.config.get('slack_enabled', False),
            'teams_enabled': self.config.get('teams_enabled', False),
            'total_sent': 0,
            'total_errors': 0,
            'by_type': {}
        }

        # Lese Logs
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            notification_type = event['type']

                            if notification_type not in stats['by_type']:
                                stats['by_type'][notification_type] = {'success': 0, 'error': 0}

                            if event['status'] == 'success':
                                stats['total_sent'] += 1
                                stats['by_type'][notification_type]['success'] += 1
                            elif event['status'] == 'error':
                                stats['total_errors'] += 1
                                stats['by_type'][notification_type]['error'] += 1

                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen der Logs: {e}")

        return stats
