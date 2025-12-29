"""
Automatische Posteingangsbestätigung

Features:
- Generiert PDF-Posteingangsbestätigungen
- Automatischer Versand per Email
- Anpassbare Templates
- Tracking versendeter Bestätigungen
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from io import BytesIO


class PosteingangsBestaetigung:
    """Erstellt und versendet Posteingangsbestätigungen"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Posteingangsbestätigungs-Manager

        Args:
            storage_dir: Storage-Verzeichnis
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.storage_dir / "bestaetigung_config.json"
        self.log_file = self.storage_dir / "bestaetigung_log.jsonl"

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
            'auto_send': False,  # Automatisch versenden

            # Template-Einstellungen
            'kanzlei_name': 'Rechtsanwaltskanzlei',
            'kanzlei_adresse': '',
            'kanzlei_telefon': '',
            'kanzlei_email': '',

            # Email-Versand (verwendet NotificationManager)
            'email_enabled': False,
            'email_subject': 'Posteingangsbestätigung',
            'email_body_template': '''
Sehr geehrte Damen und Herren,

wir bestätigen den Eingang Ihres Schreibens vom {datum}.

Aktenzeichen: {aktenzeichen}

Mit freundlichen Grüßen
{kanzlei_name}
''',

            # PDF-Einstellungen
            'include_qr_code': False,
            'include_logo': False,
            'logo_path': ''
        }

    def _save_config(self):
        """Speichert Konfiguration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")

    def _log_event(self, event_type: str, status: str, message: str = "", details: Optional[Dict] = None):
        """Loggt Event"""
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

    def is_enabled(self) -> bool:
        """Prüft ob Feature aktiviert ist"""
        return self.config.get('enabled', False)

    def configure(
        self,
        kanzlei_name: str,
        kanzlei_adresse: str,
        kanzlei_telefon: str,
        kanzlei_email: str
    ):
        """
        Konfiguriert Kanzlei-Informationen

        Args:
            kanzlei_name: Name der Kanzlei
            kanzlei_adresse: Adresse
            kanzlei_telefon: Telefon
            kanzlei_email: Email
        """
        self.config['kanzlei_name'] = kanzlei_name
        self.config['kanzlei_adresse'] = kanzlei_adresse
        self.config['kanzlei_telefon'] = kanzlei_telefon
        self.config['kanzlei_email'] = kanzlei_email
        self.config['enabled'] = True
        self._save_config()

    def generate_pdf(self, document_info: Dict) -> Optional[bytes]:
        """
        Generiert Posteingangsbestätigung als PDF

        Args:
            document_info: Dokument-Informationen

        Returns:
            PDF als Bytes oder None bei Fehler
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
            from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

            buffer = BytesIO()

            # Erstelle PDF
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                                   topMargin=2*cm, bottomMargin=2*cm)

            styles = getSampleStyleSheet()

            # Custom Styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor='black',
                spaceAfter=30,
                alignment=TA_CENTER
            )

            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontSize=11,
                spaceAfter=12
            )

            # Baue PDF-Inhalt
            story = []

            # Optional: Logo
            if self.config.get('include_logo', False):
                logo_path = self.config.get('logo_path', '')
                if logo_path and Path(logo_path).exists():
                    logo = Image(logo_path, width=5*cm, height=2*cm)
                    story.append(logo)
                    story.append(Spacer(1, 1*cm))

            # Kanzlei-Header
            kanzlei_info = f"""
<b>{self.config.get('kanzlei_name', 'Rechtsanwaltskanzlei')}</b><br/>
{self.config.get('kanzlei_adresse', '')}<br/>
Tel: {self.config.get('kanzlei_telefon', '')}<br/>
Email: {self.config.get('kanzlei_email', '')}
"""
            story.append(Paragraph(kanzlei_info, body_style))
            story.append(Spacer(1, 1.5*cm))

            # Datum
            heute = datetime.now().strftime('%d.%m.%Y')
            story.append(Paragraph(f"<b>Datum:</b> {heute}", body_style))
            story.append(Spacer(1, 0.5*cm))

            # Titel
            story.append(Paragraph("Posteingangsbestätigung", title_style))
            story.append(Spacer(1, 1*cm))

            # Extrahiere Informationen
            aktenzeichen = document_info.get('aktenzeichen_info', {}).get('internes_az', 'Nicht zugeordnet')
            datum_dok = document_info.get('analyse', {}).get('datum', 'Unbekannt')
            absender = document_info.get('analyse', {}).get('absender', 'Unbekannt')

            # Inhalt
            content = f"""
Wir bestätigen den Eingang Ihres Schreibens.
<br/><br/>
<b>Aktenzeichen:</b> {aktenzeichen}<br/>
<b>Ihr Schreiben vom:</b> {datum_dok}<br/>
<b>Absender:</b> {absender}<br/>
<b>Eingangsdatum:</b> {heute}<br/>
<br/>
Ihr Schreiben wird bearbeitet. Bei Rückfragen wenden Sie sich bitte an uns.
<br/><br/>
Mit freundlichen Grüßen<br/>
{self.config.get('kanzlei_name', '')}
"""

            story.append(Paragraph(content, body_style))

            # Optional: QR-Code (für Tracking)
            if self.config.get('include_qr_code', False):
                try:
                    import qrcode
                    from reportlab.graphics import renderPDF
                    from svglib.svglib import svg2rlg

                    qr = qrcode.QRCode(version=1, box_size=10, border=2)
                    qr_data = f"{aktenzeichen}|{heute}"
                    qr.add_data(qr_data)
                    qr.make(fit=True)

                    # Einfache QR-Code-Integration
                    # (Vollständige Implementierung würde PIL benötigen)
                    pass

                except ImportError:
                    pass

            # PDF erstellen
            doc.build(story)

            buffer.seek(0)
            pdf_bytes = buffer.getvalue()

            self._log_event(
                'generate_pdf',
                'success',
                f"Bestätigung erstellt für {aktenzeichen}"
            )

            return pdf_bytes

        except ImportError:
            print("ReportLab nicht installiert. Installiere mit: pip install reportlab")
            return None
        except Exception as e:
            self._log_event('generate_pdf', 'error', str(e))
            print(f"Fehler beim Erstellen der PDF: {e}")
            return None

    def send_bestaetigung(
        self,
        document_info: Dict,
        recipient_email: str,
        notification_manager
    ) -> bool:
        """
        Sendet Posteingangsbestätigung per Email

        Args:
            document_info: Dokument-Informationen
            recipient_email: Empfänger-Email
            notification_manager: NotificationManager-Instanz

        Returns:
            True bei Erfolg
        """
        if not self.is_enabled():
            return False

        # Generiere PDF
        pdf_bytes = self.generate_pdf(document_info)
        if not pdf_bytes:
            return False

        # Speichere PDF temporär
        temp_pdf = self.storage_dir / f"temp_bestaetigung_{datetime.now().timestamp()}.pdf"
        with open(temp_pdf, 'wb') as f:
            f.write(pdf_bytes)

        # Erstelle Email-Text
        aktenzeichen = document_info.get('aktenzeichen_info', {}).get('internes_az', 'Nicht zugeordnet')
        datum = document_info.get('analyse', {}).get('datum', datetime.now().strftime('%d.%m.%Y'))

        email_body = self.config.get('email_body_template', '').format(
            datum=datum,
            aktenzeichen=aktenzeichen,
            kanzlei_name=self.config.get('kanzlei_name', '')
        )

        # Sende Email via NotificationManager
        try:
            # Temporär: Setze Empfänger
            original_recipients = notification_manager.config.get('email_recipients', [])
            notification_manager.config['email_recipients'] = [recipient_email]

            success = notification_manager._send_email(
                subject=self.config.get('email_subject', 'Posteingangsbestätigung'),
                body=email_body,
                attachment_path=temp_pdf
            )

            # Stelle Original-Empfänger wieder her
            notification_manager.config['email_recipients'] = original_recipients

            # Lösche temporäre PDF
            temp_pdf.unlink()

            if success:
                self._log_event(
                    'send',
                    'success',
                    f"Bestätigung versendet an {recipient_email}",
                    {'aktenzeichen': aktenzeichen}
                )

            return success

        except Exception as e:
            self._log_event('send', 'error', str(e))
            print(f"Fehler beim Versenden: {e}")

            # Cleanup
            if temp_pdf.exists():
                temp_pdf.unlink()

            return False

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken

        Returns:
            Dict mit Statistiken
        """
        stats = {
            'enabled': self.is_enabled(),
            'auto_send': self.config.get('auto_send', False),
            'total_generated': 0,
            'total_sent': 0,
            'total_errors': 0
        }

        # Lese Logs
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())

                            if event['event_type'] == 'generate_pdf' and event['status'] == 'success':
                                stats['total_generated'] += 1

                            if event['event_type'] == 'send':
                                if event['status'] == 'success':
                                    stats['total_sent'] += 1
                                elif event['status'] == 'error':
                                    stats['total_errors'] += 1

                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Fehler beim Lesen der Logs: {e}")

        return stats
