import streamlit as st
import os
import tempfile
from pathlib import Path
import zipfile
from io import BytesIO
from datetime import datetime

# Import der Verarbeitungsmodule
from pdf_processor import PDFProcessor
from aktenzeichen_erkennung import AktenzeichenErkenner
from document_analyzer import DocumentAnalyzer
from excel_generator import ExcelGenerator
from storage import PersistentStorage
from email_sender import EmailSender
from duplicate_detector import DuplicateDetector
from kanzleisoftware_sync import KanzleiSoftwareSync
from trash_manager import TrashManager
from hot_folder_watcher import HotFolderWatcher
from auto_file_storage import AutoFileStorage
from notification_manager import NotificationManager
from calendar_integration import CalendarIntegration
from email_import import EmailImporter
from fulltext_search import FulltextSearch
from wiedervorlage_system import WiedervorlageSystem
from backup_manager import BackupManager
from posteingangs_bestaetigung import PosteingangsBestaetigung
from dashboard_manager import DashboardManager
from user_management import UserManager, UserRole
from browser_notifications import BrowserNotificationManager
from user_dashboard import UserDashboard

# Versionsnummer: Zähler.JJ.MM.TT.HH.MM (HH.MM = echte Uhrzeit der letzten Änderung)
_now = datetime.now()
VERSION = f"8.{_now.strftime('%y.%m.%d.%H.%M')}"  # Version 8, Multi-User-System

# Hilfsfunktion: Extrahiere Scanner-Namen aus Dateinamen
def _extract_scanner_name(filename: str) -> str:
    """
    Extrahiert den Scanner-Namen aus dem Dateinamen.
    Beispiele:
    - "Posteingang_Joanna_Hingst_2024-12-15.pdf" -> "Joanna_Hingst"
    - "Scan_Max_Mustermann.pdf" -> "Max_Mustermann"
    - "dokument.pdf" -> ""
    """
    import re
    if not filename:
        return ""

    # Entferne Dateiendung
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename

    # Versuche bekannte Muster
    # Muster 1: Posteingang_Name_Name_Datum
    match = re.search(r'(?:Posteingang|Scan|Post)_([A-Za-zäöüÄÖÜß]+_[A-Za-zäöüÄÖÜß]+)', name, re.IGNORECASE)
    if match:
        return match.group(1)

    # Muster 2: Name_Name am Ende (vor Datum)
    match = re.search(r'([A-Za-zäöüÄÖÜß]+_[A-Za-zäöüÄÖÜß]+)(?:_\d{4}[-_]\d{2}[-_]\d{2})?$', name)
    if match:
        # Prüfe ob es nicht ein Keyword ist
        candidate = match.group(1)
        keywords = ['nicht_zugeordnet', 'Fristen_und', 'Gesamt_Excel']
        if candidate.lower() not in [k.lower() for k in keywords]:
            return candidate

    # Muster 3: Nur ein Name
    match = re.search(r'(?:Posteingang|Scan|Post)_([A-Za-zäöüÄÖÜß]+)', name, re.IGNORECASE)
    if match:
        return match.group(1)

    return ""

st.set_page_config(
    page_title="RHM Posteingangsverarbeitung",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="auto"  # Auto-collapse auf Mobile
)

# Responsive CSS für Mobile, Tablet, Desktop
st.markdown("""
<style>
    /* Mobile-First: Basis-Styles */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    /* Buttons mobil-freundlich */
    .stDownloadButton button {
        width: 100%;
        padding: 0.5rem 1rem;
        font-size: 0.95rem;
    }

    /* Upload-Bereiche optimiert */
    .uploadedFile {
        font-size: 0.9rem;
    }

    /* Metriken responsive */
    [data-testid="stMetricValue"] {
        font-size: 1.2rem;
    }

    /* Mobile: Spalten stacken */
    @media (max-width: 640px) {
        .row-widget.stHorizontalBlock {
            flex-direction: column !important;
        }

        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }

        /* Title auf Mobile kleiner */
        h1 {
            font-size: 1.5rem !important;
        }

        h2 {
            font-size: 1.3rem !important;
        }

        h3 {
            font-size: 1.1rem !important;
        }
    }

    /* Tablet: ab 641px */
    @media (min-width: 641px) and (max-width: 1023px) {
        .main .block-container {
            padding-left: 1.5rem;
            padding-right: 1.5rem;
        }
    }

    /* Tablet: ab 768px */
    @media (min-width: 768px) {
        .main .block-container {
            padding-left: 2rem;
            padding-right: 2rem;
        }

        .stDownloadButton button {
            font-size: 1rem;
        }
    }

    /* Desktop: ab 1024px */
    @media (min-width: 1024px) {
        .main .block-container {
            padding-left: 3rem;
            padding-right: 3rem;
            max-width: 1400px;
        }
    }

    /* Sidebar mobile optimiert */
    @media (max-width: 768px) {
        /* Sidebar komplett ausblenden wenn collapsed */
        [data-testid="stSidebar"][aria-expanded="false"] {
            margin-left: -100%;
            transform: translateX(-100%);
            transition: transform 0.3s ease-in-out;
        }

        [data-testid="stSidebar"][aria-expanded="true"] {
            margin-left: 0;
            transform: translateX(0);
            transition: transform 0.3s ease-in-out;
        }

        [data-testid="stSidebar"] {
            min-width: 100%;
            max-width: 100%;
            width: 100%;
            z-index: 999999;
        }

        /* Sidebar-Button größer und besser sichtbar auf Mobile */
        [data-testid="collapsedControl"] {
            width: 50px !important;
            height: 50px !important;
            z-index: 999999;
            position: fixed !important;
            top: 10px !important;
            left: 10px !important;
        }

        /* Overlay wenn Sidebar offen */
        [data-testid="stSidebar"][aria-expanded="true"]::before {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: -1;
        }
    }

    /* Touch-friendly spacing */
    @media (pointer: coarse) {
        button {
            min-height: 44px;
            padding: 0.75rem 1rem;
        }

        input, select, textarea {
            min-height: 44px;
            font-size: 16px; /* Verhindert Auto-Zoom auf iOS */
        }

        /* Expander touch-friendly */
        .streamlit-expanderHeader {
            min-height: 44px;
            padding: 0.75rem !important;
        }
    }

    /* Optimierte Scroll-Bereiche */
    @media (max-width: 640px) {
        .stExpander {
            margin-bottom: 1rem;
        }

        /* File uploader mobil optimiert */
        [data-testid="stFileUploader"] {
            margin-bottom: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# MULTI-USER SYSTEM & AUTHENTIFIZIERUNG
# ============================================================================

# Initialisiere Storage (benötigt für User-Management)
if 'storage' not in st.session_state:
    st.session_state.storage = PersistentStorage()

storage = st.session_state.storage

# Initialisiere User-Management
if 'user_manager' not in st.session_state:
    st.session_state.user_manager = UserManager(storage.storage_dir)

if 'browser_notifications' not in st.session_state:
    st.session_state.browser_notifications = BrowserNotificationManager(storage.storage_dir)

if 'user_dashboard' not in st.session_state:
    st.session_state.user_dashboard = UserDashboard(storage.storage_dir)

user_manager = st.session_state.user_manager
browser_notif = st.session_state.browser_notifications
user_dash = st.session_state.user_dashboard

# Session Management
if 'session_token' not in st.session_state:
    st.session_state.session_token = None

if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# Prüfe Session
if st.session_state.session_token:
    user = user_manager.validate_session(st.session_state.session_token)
    if user:
        st.session_state.current_user = user
    else:
        st.session_state.session_token = None
        st.session_state.current_user = None

# ============================================================================
# LOGIN / REGISTRIERUNG
# ============================================================================

# Landing-Page State
if 'show_demo' not in st.session_state:
    st.session_state.show_demo = False

if not st.session_state.current_user:
    # Zeige Landing-Page, wenn show_demo=False
    if not st.session_state.show_demo:
        # LANDING PAGE
        st.markdown("""
        <div style="text-align: center; padding: 2rem 0;">
            <h1 style="font-size: 3rem; margin-bottom: 1rem;">📄 RHM Posteingangsverarbeitung</h1>
            <p style="font-size: 1.3rem; color: #666; margin-bottom: 2rem;">
                Automatisierte KI-gestützte Dokumentenverarbeitung für Kanzleien
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Features in 3 Spalten
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            ### 🤖 KI-Powered
            - Automatische Aktenzeichen-Erkennung
            - OCR-tolerante Texterkennung
            - Intelligente Sachbearbeiter-Zuordnung
            - Deadline-Erkennung
            """)

        with col2:
            st.markdown("""
            ### 📦 Multi-Format
            - Multi-PDF-Upload
            - Automatische Dokumententrennung
            - RA-MICRO / DATEV Export
            - ZIP-Download nach Sachbearbeiter
            """)

        with col3:
            st.markdown("""
            ### 🔐 Enterprise-Ready
            - Multi-User-System
            - Rollenbasierte Zugriffe
            - Audit-Logging
            - Backup-Management
            """)

        st.markdown("---")

        # Call-to-Action
        col_left, col_center, col_right = st.columns([1, 2, 1])

        with col_center:
            st.markdown("<br>", unsafe_allow_html=True)

            # Direkt-Start Button (ohne Login)
            if st.button("🚀 Demo starten", type="primary", width="stretch", key="demo_start_button"):
                # Erstelle Demo-User Session
                demo_user = {
                    'id': 'demo_user',
                    'email': 'demo@rhm.de',
                    'name': 'Demo Benutzer',
                    'role': UserRole.ADMIN.value,
                    'created_at': datetime.now().isoformat()
                }
                st.session_state.current_user = demo_user
                st.session_state.session_token = 'demo_session'
                st.rerun()

            st.markdown("<p style='text-align: center; margin: 1rem 0 0.5rem 0; color: #888;'>oder</p>", unsafe_allow_html=True)

            # Optionaler Login-Button
            if st.button("🔐 Mit Account anmelden", width="stretch", key="login_button"):
                st.session_state.show_demo = True
                st.rerun()

            st.caption(f"Version {VERSION}")

        st.markdown("<br><br>", unsafe_allow_html=True)

        # Footer
        st.markdown("""
        <div style="text-align: center; color: #888; margin-top: 3rem;">
            <p>© 2025 RHM Rechtsanwälte | Entwickelt mit Streamlit & Claude AI</p>
        </div>
        """, unsafe_allow_html=True)

        st.stop()  # Stoppe hier, zeige nur Landing-Page

    # LOGIN-BEREICH (wird nur gezeigt wenn show_demo=True)
    # Zurück-Button zur Landing-Page
    if st.button("← Zurück zur Startseite", key="back_to_landing"):
        st.session_state.show_demo = False
        st.rerun()

    st.title("🔐 RHM Posteingang | Login")
    st.caption(f"Version {VERSION}")
    st.markdown("---")

    # Browser-Benachrichtigungen-Script einbinden
    st.components.v1.html(browser_notif.get_browser_support_script(), height=0)

    tab1, tab2, tab3 = st.tabs(["Login", "Registrierung (Einladung)", "Passwort vergessen"])

    with tab1:
        st.subheader("📧 Anmelden")

        login_email = st.text_input("Email:", key="login_email")
        login_password = st.text_input("Passwort:", type="password", key="login_password")

        col1, col2 = st.columns([1, 3])

        with col1:
            if st.button("🔓 Login", type="primary", width="stretch"):
                if login_email and login_password:
                    user = user_manager.authenticate(login_email, login_password)

                    if user:
                        # Erstelle Session
                        session_token = user_manager.create_session(user['id'])
                        st.session_state.session_token = session_token
                        st.session_state.current_user = user

                        st.success(f"✅ Willkommen, {user['name']}!")
                        st.rerun()
                    else:
                        st.error("❌ Email oder Passwort falsch")
                else:
                    st.warning("⚠️ Bitte Email und Passwort eingeben")

        with col2:
            st.info("""
            **Demo-Zugänge:**

            👤 **Admin**: admin@rhm-kanzlei.de / admin123

            📬 **Empfang**: empfang@rhm-kanzlei.de / empfang123

            ⚠️ Bitte Passwörter nach erstem Login ändern!
            """)

            # Reset Demo Users Button
            if st.button("🔄 Demo-Benutzer zurücksetzen", help="Setzt Admin und Empfang mit Standard-Passwörtern zurück"):
                if user_manager.reset_demo_users():
                    st.success("✅ Demo-Benutzer wurden zurückgesetzt!")
                    st.info("Sie können sich jetzt mit den Standard-Zugangsdaten anmelden.")
                else:
                    st.error("❌ Fehler beim Zurücksetzen der Demo-Benutzer")

        # TESTPHASE: Quick-Login-Buttons ohne Passwort-Eingabe
        st.markdown("---")
        st.markdown("#### 🧪 Schnell-Login (Testphase)")
        st.caption("Klicken Sie auf einen Button, um sich direkt einzuloggen:")

        col_q1, col_q2, col_q3 = st.columns(3)

        with col_q1:
            if st.button("👤 Als Admin anmelden", key="quick_login_admin", type="secondary"):
                user = user_manager.authenticate("admin@rhm-kanzlei.de", "admin123")
                if user:
                    session_token = user_manager.create_session(user['id'])
                    st.session_state.session_token = session_token
                    st.session_state.current_user = user
                    st.success(f"✅ Willkommen, {user['name']}!")
                    st.rerun()
                else:
                    st.error("❌ Admin-Login fehlgeschlagen. Bitte Demo-Benutzer zurücksetzen.")

        with col_q2:
            if st.button("📬 Als Empfang anmelden", key="quick_login_empfang", type="secondary"):
                user = user_manager.authenticate("empfang@rhm-kanzlei.de", "empfang123")
                if user:
                    session_token = user_manager.create_session(user['id'])
                    st.session_state.session_token = session_token
                    st.session_state.current_user = user
                    st.success(f"✅ Willkommen, {user['name']}!")
                    st.rerun()
                else:
                    st.error("❌ Empfang-Login fehlgeschlagen. Bitte Demo-Benutzer zurücksetzen.")

        with col_q3:
            # Erstelle Demo-Rechtsanwalt falls nicht vorhanden
            if st.button("⚖️ Als Anwalt anmelden", key="quick_login_anwalt", type="secondary"):
                # Prüfe ob Demo-Anwalt existiert
                demo_anwalt = user_manager.get_user_by_email("anwalt@rhm-kanzlei.de")
                if not demo_anwalt:
                    # Erstelle Demo-Anwalt
                    user_manager.create_user(
                        email="anwalt@rhm-kanzlei.de",
                        password="anwalt123",
                        role="Rechtsanwalt",
                        name="Demo Rechtsanwalt",
                        kuerzel="SQ"
                    )

                user = user_manager.authenticate("anwalt@rhm-kanzlei.de", "anwalt123")
                if user:
                    session_token = user_manager.create_session(user['id'])
                    st.session_state.session_token = session_token
                    st.session_state.current_user = user
                    st.success(f"✅ Willkommen, {user['name']}!")
                    st.rerun()
                else:
                    st.error("❌ Anwalt-Login fehlgeschlagen.")

    with tab2:
        st.subheader("✉️ Registrierung mit Einladung")

        inv_token = st.text_input("Einladungs-Token:", key="inv_token")

        if inv_token:
            invitation = user_manager.validate_invitation(inv_token)

            if invitation:
                st.success(f"✅ Gültige Einladung für: {invitation['email']}")
                st.info(f"**Rolle**: {invitation['role']}")

                col1, col2 = st.columns(2)

                with col1:
                    reg_name = st.text_input("Ihr Name:", value=invitation.get('name', ''))
                    reg_kuerzel = st.text_input("Kürzel:", value=invitation.get('kuerzel', ''))

                with col2:
                    reg_password = st.text_input("Passwort wählen:", type="password", key="reg_pass1")
                    reg_password2 = st.text_input("Passwort wiederholen:", type="password", key="reg_pass2")

                if st.button("✅ Registrierung abschließen", type="primary"):
                    if not all([reg_name, reg_kuerzel, reg_password, reg_password2]):
                        st.error("❌ Bitte alle Felder ausfüllen")
                    elif reg_password != reg_password2:
                        st.error("❌ Passwörter stimmen nicht überein")
                    elif len(reg_password) < 6:
                        st.error("❌ Passwort muss mindestens 6 Zeichen lang sein")
                    else:
                        # Update Einladung mit Namen/Kürzel
                        invitation['name'] = reg_name
                        invitation['kuerzel'] = reg_kuerzel

                        # Akzeptiere Einladung
                        if user_manager.accept_invitation(inv_token, reg_password):
                            st.success("✅ Registrierung erfolgreich! Bitte jetzt einloggen.")
                            st.balloons()
                        else:
                            st.error("❌ Fehler bei der Registrierung")
            else:
                st.error("❌ Ungültiger oder abgelaufener Einladungs-Token")

    with tab3:
        st.subheader("🔑 Passwort vergessen")

        reset_email = st.text_input("Ihre Email:", key="reset_email")

        if st.button("📧 Passwort-Reset anfordern"):
            if reset_email:
                token = user_manager.request_password_reset(reset_email)

                if token:
                    st.success("✅ Passwort-Reset wurde angefordert!")
                    st.info("**Info**: Der Administrator wurde per Email benachrichtigt und wird Ihnen ein neues Passwort zusenden.")

                    # Benachrichtige Admins
                    admins = user_manager.get_users_by_role("Administrator")
                    for admin in admins:
                        # Sende Email-Benachrichtigung an Admin
                        if admin.get('email'):
                            subject = "Passwort-Reset angefordert"
                            message = f"""
Ein Benutzer hat einen Passwort-Reset angefordert:

Email: {reset_email}
Zeitpunkt: {datetime.now().strftime('%d.%m.%Y %H:%M')}
Reset-Token: {token}

Bitte setzen Sie das Passwort für diesen Benutzer zurück oder kontaktieren Sie ihn.

---
RHM Posteingangsverarbeitung
                            """

                            try:
                                # Verwende EmailSender wenn konfiguriert
                                email_sender = EmailSender()
                                if email_sender.is_configured():
                                    email_sender.send_email(
                                        recipient=admin['email'],
                                        subject=subject,
                                        body=message
                                    )
                                else:
                                    # Fallback: Zeige Admin-Info
                                    st.info(f"📧 Admin {admin['name']} wurde informiert (Email-Versand nicht konfiguriert)")
                            except Exception as e:
                                st.warning(f"⚠️ Email-Versand an Admin fehlgeschlagen: {str(e)}")

                    st.code(f"Reset-Token (für Admin): {token[:16]}...")
                else:
                    st.error("❌ Email nicht gefunden")
            else:
                st.warning("⚠️ Bitte Email eingeben")

    st.stop()  # Stoppe hier wenn nicht eingeloggt

# ============================================================================
# HAUPT-APP (Nur für eingeloggte Benutzer)
# ============================================================================

current_user = st.session_state.current_user

# Header mit Benutzer-Info
col_h1, col_h2, col_h3 = st.columns([3, 1, 1])

with col_h1:
    st.title("📄 RHM | Automatisierter Posteingang")
    st.caption(f"Version {VERSION}")

with col_h2:
    st.metric("Benutzer", current_user['name'])
    st.caption(f"Rolle: {current_user['role']}")

with col_h3:
    st.write("")  # Spacing
    if st.button("🚪 Logout", width="stretch"):
        user_manager.logout(st.session_state.session_token)
        st.session_state.session_token = None
        st.session_state.current_user = None
        st.rerun()

st.markdown("---")

# Browser-Benachrichtigungen aktivieren (beim ersten Login)
if not current_user.get('browser_notifications_enabled'):
    with st.expander("🔔 Browser-Benachrichtigungen aktivieren (empfohlen)", expanded=True):
        st.info("""
        **Aktivieren Sie Browser-Benachrichtigungen**, um bei neuem Posteingang
        sofort informiert zu werden - auch wenn Sie die App nicht geöffnet haben!
        """)

        # JavaScript für Notification-Request
        st.components.v1.html(browser_notif.get_browser_support_script(), height=0)

        if st.button("✅ Benachrichtigungen aktivieren", type="primary"):
            # In Produktion: JavaScript-Callback für Push-Subscription
            user_manager.update_browser_notification_settings(current_user['id'], True)
            current_user['browser_notifications_enabled'] = True
            st.success("✅ Browser-Benachrichtigungen aktiviert!")
            st.rerun()

# Initialisiere Trash-Manager
if 'trash_manager' not in st.session_state:
    st.session_state.trash_manager = TrashManager(storage.storage_dir)
    # Automatisches Cleanup beim Start
    deleted_count = st.session_state.trash_manager.cleanup_expired()
    if deleted_count > 0:
        print(f"Trash: {deleted_count} abgelaufene Dokumente automatisch gelöscht")

trash_manager = st.session_state.trash_manager

# Initialisiere alle neuen Manager
if 'hot_folder_watcher' not in st.session_state:
    st.session_state.hot_folder_watcher = None  # Wird bei Bedarf gestartet

if 'auto_file_storage' not in st.session_state:
    st.session_state.auto_file_storage = AutoFileStorage(storage.storage_dir)

if 'notification_manager' not in st.session_state:
    st.session_state.notification_manager = NotificationManager(storage.storage_dir)

if 'calendar_integration' not in st.session_state:
    st.session_state.calendar_integration = CalendarIntegration(storage.storage_dir)

if 'email_importer' not in st.session_state:
    st.session_state.email_importer = EmailImporter(storage.storage_dir)

if 'fulltext_search' not in st.session_state:
    st.session_state.fulltext_search = FulltextSearch(storage.storage_dir)

if 'wiedervorlage_system' not in st.session_state:
    st.session_state.wiedervorlage_system = WiedervorlageSystem(storage.storage_dir)

if 'backup_manager' not in st.session_state:
    st.session_state.backup_manager = BackupManager(storage.storage_dir)
    # Auto-Backup wenn fällig
    if st.session_state.backup_manager.should_create_backup():
        st.session_state.backup_manager.create_backup()

if 'posteingangs_bestaetigung' not in st.session_state:
    st.session_state.posteingangs_bestaetigung = PosteingangsBestaetigung(storage.storage_dir)

if 'dashboard_manager' not in st.session_state:
    st.session_state.dashboard_manager = DashboardManager(storage.storage_dir)

# Initialisiere Batch-Processing Session State
if 'accumulated_documents' not in st.session_state:
    st.session_state.accumulated_documents = []
if 'batch_count' not in st.session_state:
    st.session_state.batch_count = 0
if 'batch_mode_active' not in st.session_state:
    st.session_state.batch_mode_active = False
if 'sachbearbeiter_stats_accumulated' not in st.session_state:
    st.session_state.sachbearbeiter_stats_accumulated = {"SQ": 0, "TS": 0, "M": 0, "FÜ": 0, "CV": 0, "nicht-zugeordnet": 0}

# Lade gespeicherte API Keys beim ersten Laden
if 'api_keys' not in st.session_state:
    # Initialisiere mit leeren Strings
    st.session_state.api_keys = {
        'openai': '',
        'claude': '',
        'gemini': ''
    }

    # PRIORITÄT 1: Streamlit Secrets (höchste Priorität für Streamlit Cloud)
    try:
        # Option 1: Verschachtelte Struktur
        if 'openai' in st.secrets:
            st.session_state.api_keys['openai'] = st.secrets['openai'].get('api_key', '')

        if 'claude' in st.secrets:
            st.session_state.api_keys['claude'] = st.secrets['claude'].get('api_key', '')

        if 'gemini' in st.secrets:
            st.session_state.api_keys['gemini'] = st.secrets['gemini'].get('api_key', '')

        # Option 2: Flache Struktur
        if 'OPENAI_API_KEY' in st.secrets:
            st.session_state.api_keys['openai'] = st.secrets['OPENAI_API_KEY']

        if 'ANTHROPIC_API_KEY' in st.secrets:
            st.session_state.api_keys['claude'] = st.secrets['ANTHROPIC_API_KEY']

        if 'GOOGLE_API_KEY' in st.secrets:
            st.session_state.api_keys['gemini'] = st.secrets['GOOGLE_API_KEY']

    except Exception as e:
        # Secrets nicht verfügbar (z.B. lokale Entwicklung)
        pass

    # PRIORITÄT 2: Persistente Speicherung (nur als Fallback wenn keine Secrets)
    saved_keys = storage.load_api_keys()
    for provider in ['openai', 'claude', 'gemini']:
        if not st.session_state.api_keys[provider] and saved_keys.get(provider):
            st.session_state.api_keys[provider] = saved_keys[provider]
if 'api_provider' not in st.session_state:
    st.session_state.api_provider = 'OpenAI (ChatGPT)'

# Sidebar für API-Konfiguration
st.sidebar.header("⚙️ Einstellungen")

# API-Anbieter-Auswahl
st.sidebar.subheader("🤖 KI-Anbieter")
api_provider = st.sidebar.selectbox(
    "Wählen Sie den KI-Dienst:",
    options=["OpenAI (ChatGPT)", "Claude (Anthropic)", "Gemini (Google)"],
    index=0,  # OpenAI als Standard
    help="Wählen Sie den KI-Dienst für die Dokumentenanalyse"
)
st.session_state.api_provider = api_provider

# API-Key Eingabe (mit persistenter Speicherung)
provider_key_map = {
    "OpenAI (ChatGPT)": "openai",
    "Claude (Anthropic)": "claude",
    "Gemini (Google)": "gemini"
}
current_provider_key = provider_key_map[api_provider]

# Zeige Status: Key-Quelle anzeigen
has_saved_key = storage.has_api_key(current_provider_key)
stored_key = st.session_state.api_keys.get(current_provider_key, '')

# Prüfe ob Key aus Streamlit Secrets kommt
key_from_secrets = False
try:
    secret_key_names = {
        'openai': ['openai', 'OPENAI_API_KEY'],
        'claude': ['claude', 'ANTHROPIC_API_KEY'],
        'gemini': ['gemini', 'GOOGLE_API_KEY']
    }

    for secret_name in secret_key_names.get(current_provider_key, []):
        if secret_name in st.secrets:
            if isinstance(st.secrets[secret_name], dict):
                if stored_key == st.secrets[secret_name].get('api_key', ''):
                    key_from_secrets = True
                    break
            elif stored_key == st.secrets[secret_name]:
                key_from_secrets = True
                break
except:
    pass

# 🟢 GRÜNES LÄMPCHEN: Zeige prominente API-Key-Status-Anzeige ganz oben
st.sidebar.markdown("---")
if key_from_secrets and stored_key:
    # GRÜNES LÄMPCHEN: Key aus Streamlit Secrets
    st.sidebar.markdown("""
        <div style="
            background: linear-gradient(135deg, #00c853 0%, #00e676 100%);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,200,83,0.4);
            margin-bottom: 20px;
        ">
            <div style="font-size: 48px; margin-bottom: 10px;">🟢</div>
            <div style="color: white; font-weight: bold; font-size: 18px; margin-bottom: 5px;">
                API KEY AKTIV
            </div>
            <div style="color: #e8f5e9; font-size: 14px; margin-bottom: 10px;">
                🔐 Streamlit Cloud Secrets
            </div>
            <div style="background: rgba(255,255,255,0.2); padding: 8px; border-radius: 8px; font-family: monospace; font-size: 12px; color: white;">
                """ + (stored_key[:7] + "..." + stored_key[-4:] if len(stored_key) > 15 else "***") + """
            </div>
        </div>
    """, unsafe_allow_html=True)
elif stored_key:
    # GELBES LÄMPCHEN: Key gespeichert
    st.sidebar.markdown("""
        <div style="
            background: linear-gradient(135deg, #ffa726 0%, #ffb74d 100%);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(255,167,38,0.4);
            margin-bottom: 20px;
        ">
            <div style="font-size: 48px; margin-bottom: 10px;">🟡</div>
            <div style="color: white; font-weight: bold; font-size: 18px; margin-bottom: 5px;">
                API KEY GESPEICHERT
            </div>
            <div style="color: #fff3e0; font-size: 14px;">
                💾 Lokal gespeichert
            </div>
        </div>
    """, unsafe_allow_html=True)
else:
    # ROTES LÄMPCHEN: Kein Key
    st.sidebar.markdown("""
        <div style="
            background: linear-gradient(135deg, #ef5350 0%, #e57373 100%);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(239,83,80,0.4);
            margin-bottom: 20px;
        ">
            <div style="font-size: 48px; margin-bottom: 10px;">🔴</div>
            <div style="color: white; font-weight: bold; font-size: 18px; margin-bottom: 5px;">
                KEIN API KEY
            </div>
            <div style="color: #ffebee; font-size: 14px;">
                ⚠️ Bitte Key eingeben
            </div>
        </div>
    """, unsafe_allow_html=True)
st.sidebar.markdown("---")

# Zeige Status-Meldung und API-Key Eingabefeld
if key_from_secrets:
    # Key aus Streamlit Secrets - Zeige prominente Meldung
    st.sidebar.success(f"✅ **{api_provider} Key aktiv**")
    st.sidebar.info(f"🔐 **Quelle:** Streamlit Secrets (streamlit.io)")

    # Zeige maskierten Key (nur zur Bestätigung)
    masked_key = stored_key[:7] + "..." + stored_key[-4:] if len(stored_key) > 15 else "***"
    st.sidebar.code(masked_key)

    # Eingabefeld deaktiviert mit Hinweis
    api_key_input = st.sidebar.text_input(
        f"{api_provider} API Key (schreibgeschützt)",
        value="Verwendet Key aus Streamlit Secrets",
        type="default",
        disabled=True,
        help="Key wird aus Streamlit Cloud Secrets geladen und kann hier nicht geändert werden",
        key=f"api_key_input_{current_provider_key}_disabled"
    )

elif has_saved_key:
    # Key aus persistenter Speicherung
    timestamp = storage.get_api_key_timestamp(current_provider_key)
    if timestamp:
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp)
        formatted = dt.strftime('%d.%m.%Y %H:%M')
        st.sidebar.success(f"💾 Gespeicherter {api_provider} Key gefunden\n\n*Zuletzt aktualisiert: {formatted}*")
    else:
        st.sidebar.success(f"💾 Gespeicherter {api_provider} Key gefunden")

    # Normales Eingabefeld
    stored_key = st.session_state.api_keys.get(current_provider_key, '')
    api_key_input = st.sidebar.text_input(
        f"{api_provider} API Key (neu eingeben zum Ändern)",
        value=stored_key,
        type="password",
        help=f"Neuer Key überschreibt gespeicherten Key",
        key=f"api_key_input_{current_provider_key}"
    )
else:
    # Kein Key vorhanden - Bitte um Eingabe
    st.sidebar.warning(f"⚠️ Bitte {api_provider} API Key eingeben")

    # Normales Eingabefeld
    stored_key = st.session_state.api_keys.get(current_provider_key, '')
    api_key_input = st.sidebar.text_input(
        f"{api_provider} API Key",
        value=stored_key,
        type="password",
        help=f"Geben Sie Ihren {api_provider} API Key ein",
        key=f"api_key_input_{current_provider_key}"
    )

# Speichere Key in Session State und persistentem Storage
if api_key_input and api_key_input != stored_key:
    st.session_state.api_keys[current_provider_key] = api_key_input
    # Speichere persistent (verschlüsselt)
    storage.save_api_key(current_provider_key, api_key_input)
    st.sidebar.success("✅ API-Key gespeichert!")

# Lösch-Button für gespeicherten Key
if has_saved_key:
    if st.sidebar.button(f"🗑️ {api_provider} Key löschen", key=f"delete_{current_provider_key}"):
        storage.delete_api_key(current_provider_key)
        st.session_state.api_keys[current_provider_key] = ''
        st.rerun()

# Hole aktuellen Key
current_api_key = st.session_state.api_keys.get(current_provider_key, '')

# API-Key Verbindungstest
if current_api_key:
    try:
        if api_provider == "OpenAI (ChatGPT)":
            from openai import OpenAI
            test_client = OpenAI(api_key=current_api_key)
            test_client.models.list()
            st.sidebar.markdown("🟢 **Verbindung erfolgreich**")

        elif api_provider == "Claude (Anthropic)":
            import anthropic
            test_client = anthropic.Anthropic(api_key=current_api_key)
            # Test mit einfachem API-Aufruf
            test_client.models.list()
            st.sidebar.markdown("🟢 **Verbindung erfolgreich**")

        elif api_provider == "Gemini (Google)":
            import google.generativeai as genai
            genai.configure(api_key=current_api_key)
            # Test: Liste verfügbare Modelle
            list(genai.list_models())
            st.sidebar.markdown("🟢 **Verbindung erfolgreich**")

    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower() or "api_key" in error_msg.lower():
            st.sidebar.markdown("🔴 **Ungültiger API-Key**")
        else:
            st.sidebar.markdown(f"🟡 **Verbindungsfehler**: {error_msg[:100]}")
else:
    st.sidebar.markdown("⚪ **Kein API-Key eingegeben**")

st.sidebar.markdown("---")

# Dokumententrennung (fest: nur "Trennseite"-Text)
st.sidebar.subheader("📑 Dokumententrennung")
st.sidebar.info("Dokumente werden durch Seiten mit dem Text **'Trennseite'** getrennt.")

st.sidebar.markdown("---")
st.sidebar.info("""
**Sachbearbeiter:**
- SQ: Rechtsanwalt und Notar Sven-Bryde Meier
- TS: Rechtsanwältin Tamara Meyer
- M/MQ: Rechtsanwältin Ann-Kathrin Marquardsen
- FÜ: Rechtsanwalt Dr. Fürsen
- CV: Rechtsanwalt Christian Ostertun
""")

# Papierkorb-Einstellungen
st.sidebar.markdown("---")
st.sidebar.subheader("🗑️ Papierkorb")

# Statistiken
trash_stats = trash_manager.get_statistics()
if trash_stats['total_items'] > 0:
    st.sidebar.warning(f"📦 {trash_stats['total_items']} Dokument(e) im Papierkorb")

    # Zeige abgelaufene Dokumente
    if trash_stats['expired_items'] > 0:
        st.sidebar.error(f"⚠️ {trash_stats['expired_items']} abgelaufen")
else:
    st.sidebar.success("✅ Papierkorb leer")

# Aufbewahrungszeit einstellen
with st.sidebar.expander("⚙️ Einstellungen"):
    current_hours = trash_manager.get_retention_hours()

    retention_hours = st.number_input(
        "Aufbewahrungszeit (Stunden):",
        min_value=1,
        max_value=720,  # 30 Tage
        value=current_hours,
        step=1,
        help="Dokumente werden nach dieser Zeit automatisch gelöscht"
    )

    if retention_hours != current_hours:
        trash_manager.set_retention_hours(retention_hours)
        st.success(f"✅ Aufbewahrungszeit auf {retention_hours}h gesetzt")

    # Schnell-Auswahl
    col1, col2 = st.columns(2)
    with col1:
        if st.button("24h", width="stretch"):
            trash_manager.set_retention_hours(24)
            st.rerun()
    with col2:
        if st.button("48h", width="stretch"):
            trash_manager.set_retention_hours(48)
            st.rerun()

    col3, col4 = st.columns(2)
    with col3:
        if st.button("7 Tage", width="stretch"):
            trash_manager.set_retention_hours(168)
            st.rerun()
    with col4:
        if st.button("30 Tage", width="stretch"):
            trash_manager.set_retention_hours(720)
            st.rerun()

# Hot Folder Status
st.sidebar.markdown("---")
st.sidebar.subheader("📁 Hot Folder")
if st.session_state.hot_folder_watcher and st.session_state.hot_folder_watcher.is_running():
    st.sidebar.success("✅ Aktiv")
    stats = st.session_state.hot_folder_watcher.get_statistics()
    st.sidebar.metric("Verarbeitet", stats['processed'])
else:
    st.sidebar.info("⏸️ Nicht aktiv")

# Auto-Ablage Status
st.sidebar.markdown("---")
st.sidebar.subheader("☁️ Auto-Ablage")
auto_storage = st.session_state.auto_file_storage
if auto_storage.is_enabled():
    st.sidebar.success("✅ Aktiviert")
    storage_stats = auto_storage.get_statistics()
    st.sidebar.metric("Gespeichert", storage_stats['total_stored'])
else:
    st.sidebar.info("⏸️ Deaktiviert")

# Backup Status
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Backup")
backup_mgr = st.session_state.backup_manager
backup_stats = backup_mgr.get_statistics()
if backup_stats['enabled']:
    st.sidebar.success(f"✅ {backup_stats['frequency']}")
    st.sidebar.metric("Backups", backup_stats['total_backups'])
else:
    st.sidebar.info("⏸️ Deaktiviert")

# Wiedervorlagen
st.sidebar.markdown("---")
st.sidebar.subheader("📌 Wiedervorlagen")
wv_system = st.session_state.wiedervorlage_system
wv_stats = wv_system.get_statistics()
if wv_stats['aktiv'] > 0:
    st.sidebar.warning(f"⚠️ {wv_stats['aktiv']} aktiv")
    if wv_stats['ueberfaellig'] > 0:
        st.sidebar.error(f"🔴 {wv_stats['ueberfaellig']} überfällig")
    if wv_stats['heute'] > 0:
        st.sidebar.warning(f"🟠 {wv_stats['heute']} heute fällig")
else:
    st.sidebar.success("✅ Keine Wiedervorlagen")

# Admin/Empfang-Bereich
if current_user['role'] in ['Administrator', 'Empfang']:
    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Benutzerverwaltung")

    with st.sidebar.expander("➕ Benutzer einladen"):
        inv_email = st.text_input("Email:", key="sidebar_inv_email")
        inv_role = st.selectbox("Rolle:", [
            "Sachbearbeiter",
            "Rechtsanwalt",
            "Empfang",
            "Administrator"
        ])
        inv_name = st.text_input("Name:", key="sidebar_inv_name")
        inv_kuerzel = st.text_input("Kürzel (z.B. SQ):", key="sidebar_inv_kuerzel")

        if st.button("📧 Einladung versenden", key="sidebar_send_inv"):
            if inv_email and inv_name and inv_kuerzel:
                token = user_manager.create_invitation(
                    email=inv_email,
                    role=inv_role,
                    created_by=current_user['email'],
                    name=inv_name,
                    kuerzel=inv_kuerzel
                )

                invitation_link = f"?invitation={token}"
                st.success("✅ Einladung erstellt!")
                st.code(f"Token: {token[:32]}...")
                st.caption("Link an Benutzer senden")
            else:
                st.warning("⚠️ Alle Felder ausfüllen")

    # Kürzel-Verwaltung
    with st.sidebar.expander("🏷️ Kürzel verwalten"):
        st.caption("Kürzel für neue Mitarbeiter, Rechtsanwälte oder Notare hinzufügen")

        # Bestehende Kürzel anzeigen
        custom_kuerzel = storage.get_all_kuerzel_with_names()

        if custom_kuerzel:
            st.markdown("**Gespeicherte Kürzel:**")
            for kuerzel, data in custom_kuerzel.items():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{kuerzel} → {data['name']} ({data.get('category', 'Mitarbeiter')})")
                with col2:
                    if st.button("❌", key=f"del_kuerzel_{kuerzel}", help=f"{kuerzel} löschen"):
                        if storage.delete_kuerzel(kuerzel):
                            st.success(f"✅ {kuerzel} gelöscht!")
                            st.rerun()
                        else:
                            st.error("❌ Fehler beim Löschen")

        st.markdown("---")
        st.markdown("**Neues Kürzel hinzufügen:**")

        new_kuerzel = st.text_input("Kürzel (z.B. GO):", key="sidebar_new_kuerzel", max_chars=3)
        new_name = st.text_input("Name:", key="sidebar_new_name")
        new_category = st.selectbox("Kategorie:", [
            "Mitarbeiter",
            "Rechtsanwalt",
            "Rechtsanwältin",
            "Notar",
            "Notarin"
        ], key="sidebar_new_category")

        if st.button("➕ Kürzel hinzufügen", key="sidebar_add_kuerzel"):
            if new_kuerzel and new_name:
                if storage.add_kuerzel(new_kuerzel.upper().strip(), new_name.strip(), new_category):
                    st.success(f"✅ Kürzel {new_kuerzel.upper()} hinzugefügt!")
                    st.info("ℹ️ Das neue Kürzel wird beim nächsten Upload verwendet.")
                    st.rerun()
                else:
                    st.error("❌ Fehler beim Hinzufügen (max. 3 Zeichen)")
            else:
                st.warning("⚠️ Beide Felder ausfüllen")

    # Benutzer-Übersicht
    all_users = user_manager.get_all_users()
    active_users = [u for u in all_users if u.get('active', True)]
    st.sidebar.metric("Aktive Benutzer", len(active_users))

# ============================================================================
# PERSONALISIERTES DASHBOARD
# ============================================================================

st.header(f"👋 Willkommen, {current_user['name']}")

# Dashboard-Daten holen
dashboard_data = user_dash.get_dashboard_data(current_user, storage)

# KPIs
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

with col_kpi1:
    st.metric("Meine Dokumente", dashboard_data['total'])

with col_kpi2:
    new_count = dashboard_data['new_count']
    st.metric("Neu (24h)", new_count)
    if new_count > 0:
        # Sende Benachrichtigung wenn noch nicht gesehen
        if dashboard_data['unseen_count'] > 0:
            browser_notif.send_notification_to_user(
                current_user['id'],
                f"📬 Neuer Posteingang",
                f"{new_count} neue Dokument(e) für Sie!"
            )

with col_kpi3:
    st.metric("Ungesehen", dashboard_data['unseen_count'])

with col_kpi4:
    critical = dashboard_data['statistics']['by_priority'].get('CRITICAL', 0)
    st.metric("Kritische Fristen", critical)

st.markdown("---")

# Neue/Ungesehene Dokumente
if dashboard_data['unseen_count'] > 0:
    with st.expander(f"📬 {dashboard_data['unseen_count']} neue Dokument(e)", expanded=True):
        for doc in dashboard_data['unseen_documents'][:5]:
            col_a, col_b, col_c = st.columns([3, 1, 1])

            with col_a:
                st.write(f"**{doc.get('dateiname', 'Unbekannt')}**")
                st.caption(f"AZ: {doc.get('aktenzeichen_info', {}).get('internes_az', '-')}")

            with col_b:
                priority = doc.get('analyse', {}).get('deadline_info', {}).get('priority', 'NORMAL')
                st.caption(f"Priorität: {priority}")

            with col_c:
                if st.button("📥 Details", key=f"view_{doc.get('dateiname')}"):
                    # Zeige Details des Dokuments
                    with st.expander(f"📄 Details: {doc.get('dateiname')}", expanded=True):
                        # Basis-Informationen
                        st.markdown("### 📋 Dokumenten-Information")
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write(f"**Dateiname:** {doc.get('dateiname', '-')}")
                            st.write(f"**Aktenzeichen:** {doc.get('aktenzeichen_info', {}).get('internes_az', '-')}")
                            st.write(f"**Sachbearbeiter:** {doc.get('sachbearbeiter', '-')}")

                        with col2:
                            analyse = doc.get('analyse', {})
                            st.write(f"**Datum:** {analyse.get('datum', '-')}")
                            st.write(f"**Mandant:** {analyse.get('mandant', '-')}")
                            st.write(f"**Gegner:** {analyse.get('gegner', '-')}")

                        # Stichworte
                        if analyse.get('stichworte'):
                            st.write(f"**Stichworte:** {', '.join(analyse.get('stichworte', []))}")

                        # Fristen
                        deadline_info = analyse.get('deadline_info', {})
                        if deadline_info.get('earliest_deadline'):
                            st.markdown("### ⏰ Fristen")
                            earliest = deadline_info['earliest_deadline']
                            st.warning(f"**Frist:** {earliest.get('datum', '-')} - {earliest.get('beschreibung', '-')}")

                        # Text-Vorschau
                        st.markdown("### 📝 Text-Vorschau")
                        doc_text = doc.get('dokument', {}).get('text', '')
                        st.text_area("Dokumententext:", value=doc_text[:1000] + ("..." if len(doc_text) > 1000 else ""), height=200, key=f"text_{doc.get('dateiname')}")

                        # Download-Button für PDF
                        if 'dokument' in doc and 'pdf_bytes' in doc['dokument']:
                            st.download_button(
                                label="📥 PDF herunterladen",
                                data=doc['dokument']['pdf_bytes'],
                                file_name=doc.get('dateiname', 'dokument.pdf'),
                                mime="application/pdf",
                                key=f"download_{doc.get('dateiname')}"
                            )

        # Markiere als gesehen
        if st.button("✅ Alle als gesehen markieren"):
            doc_ids = [d.get('dateiname') for d in dashboard_data['unseen_documents']]
            user_dash.mark_documents_as_seen(current_user['id'], doc_ids)
            st.rerun()

st.markdown("---")

# ============================================================================
# POST-EINGANG (Nur für Empfang/Admin)
# ============================================================================

if current_user['role'] not in ['Administrator', 'Empfang']:
    st.info("ℹ️ **Hinweis**: Der Post-Eingang-Bereich ist nur für Empfang und Administratoren zugänglich.")
    st.markdown("---")

# Dashboard-Auswahl für Empfang/Admin
if current_user['role'] in ['Administrator', 'Empfang']:
    dashboard_auswahl = st.radio(
        "📊 Dashboard auswählen:",
        ["Dashboard Empfang (Einfach)", "Dashboard Renos (Erweitert)"],
        horizontal=True,
        key="dashboard_auswahl"
    )
    st.markdown("---")

# ============================================================================
# DASHBOARD EMPFANG (Einfach) - Nur für Empfang/Admin
# ============================================================================
if current_user['role'] in ['Administrator', 'Empfang'] and dashboard_auswahl == "Dashboard Empfang (Einfach)":
    st.header("📬 Dashboard Empfang")
    st.caption("Einfache Posteingangsverarbeitung: PDF hochladen, verarbeiten, herunterladen oder versenden")

    # 1. API Key Anzeige (bereits in Sidebar konfiguriert)
    if current_api_key:
        st.success(f"✅ {api_provider} API-Key ist konfiguriert")
    else:
        st.warning(f"⚠️ Bitte {api_provider} API-Key in der Sidebar eingeben")
        st.stop()

    col_emp1, col_emp2 = st.columns([1, 1], gap="medium")

    with col_emp1:
        st.subheader("📄 Posteingang hochladen")
        empfang_pdf = st.file_uploader(
            "PDF-Datei mit Tagespost (OCR)",
            type=["pdf"],
            key="empfang_simple_pdf",
            help="Laden Sie eine OCR-PDF-Datei hoch"
        )
        # Speichere Upload-Metadaten
        if empfang_pdf:
            st.session_state.empfang_upload_name = empfang_pdf.name
            st.session_state.empfang_upload_time = datetime.now()

    with col_emp2:
        st.subheader("📊 Aktenregister hochladen")
        if storage.has_aktenregister():
            stats = storage.get_aktenregister_stats()
            dt = datetime.fromtimestamp(stats['last_modified'])
            formatted = dt.strftime('%d.%m.%Y %H:%M')
            st.success(f"💾 Gespeichertes Register: {stats['count']} Akten\n\n*Zuletzt aktualisiert: {formatted}*")

        empfang_excel = st.file_uploader(
            "Aktenregister (.xlsx)",
            type=["xlsx"],
            key="empfang_simple_excel"
        )

    # Verarbeitung
    if empfang_pdf:
        if st.button("🚀 Verarbeitung starten", type="primary", key="empfang_simple_start"):
            # Speichere Excel falls hochgeladen
            if empfang_excel:
                storage.save_aktenregister_upload(empfang_excel.getvalue())

            if not storage.has_aktenregister():
                st.error("❌ Bitte zuerst Aktenregister hochladen!")
                st.stop()

            with st.spinner("📄 Verarbeite Posteingang..."):
                try:
                    import tempfile
                    from pdf_processor import PDFProcessor
                    from document_analyzer import DocumentAnalyzer
                    from excel_generator import ExcelGenerator
                    from training_database import TrainingDatabase

                    pdf_bytes = empfang_pdf.getvalue()

                    # Speichere PDF temporär
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                        tmp.write(pdf_bytes)
                        pdf_path = tmp.name

                    excel_path = storage.aktenregister_file
                    erkenner = AktenzeichenErkenner(excel_path, storage=storage)

                    processor = PDFProcessor(pdf_path, debug=True, trennmodus="Text 'Trennseite'", excel_path=excel_path)
                    dokumente, debug_info = processor.verarbeite_pdf()

                    st.info(f"📄 {len(dokumente)} Dokumente erkannt")

                    training_db = TrainingDatabase(storage.storage_dir)
                    analyzer = DocumentAnalyzer(current_api_key, api_provider=api_provider, training_db=training_db)

                    alle_daten = []
                    sachbearbeiter_stats = {}

                    progress = st.progress(0)
                    for i, doc in enumerate(dokumente):
                        progress.progress((i + 1) / len(dokumente))

                        akt_info = erkenner.erkenne_aktenzeichen(doc['text'])
                        sb_aus_text = erkenner.erkenne_sachbearbeiter_aus_text(doc['text'])
                        analyse = analyzer.analysiere_dokument(doc['text'], akt_info)
                        sb = erkenner.ermittle_sachbearbeiter(akt_info, analyse, sachbearbeiter_aus_text=sb_aus_text)
                        sachbearbeiter_stats[sb] = sachbearbeiter_stats.get(sb, 0) + 1

                        dateiname = erkenner.generiere_dateiname(
                            akt_info.get('internes_az'),
                            analyse.get('mandant'),
                            analyse.get('gegner'),
                            analyse.get('datum'),
                            analyse.get('stichworte', []),
                            aktenkurzbezeichnung=akt_info.get('aktenkurzbezeichnung')
                        )

                        alle_daten.append({
                            'dokument': doc,
                            'aktenzeichen_info': akt_info,
                            'analyse': analyse,
                            'sachbearbeiter': sb,
                            'dateiname': dateiname
                        })

                    # ZIP-Dateien erstellen mit erweitertem Dateinamen
                    scanner_name = _extract_scanner_name(st.session_state.get('empfang_upload_name', ''))
                    scan_datum = st.session_state.get('empfang_upload_time', datetime.now()).strftime('%Y-%m-%d')

                    zip_dateien = {}
                    excel_gen = ExcelGenerator()

                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir)
                        excel_dateien = excel_gen.erstelle_excel_dateien(alle_daten, temp_path)

                        for sb, count in sachbearbeiter_stats.items():
                            if count > 0:
                                zip_buffer = BytesIO()
                                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                    for daten in alle_daten:
                                        if daten['sachbearbeiter'] == sb:
                                            pdf_content = daten['dokument']['pdf_bytes']
                                            zipf.writestr(daten['dateiname'], pdf_content)
                                    if sb in excel_dateien:
                                        zipf.writestr(f"{sb}_Fristen.xlsx", excel_dateien[sb])
                                zip_dateien[sb] = zip_buffer.getvalue()

                    # Speichere Ergebnisse
                    st.session_state.empfang_simple_ergebnisse = {
                        'zip_dateien': zip_dateien,
                        'sachbearbeiter_stats': sachbearbeiter_stats,
                        'scanner_name': scanner_name,
                        'scan_datum': scan_datum
                    }
                    st.session_state.empfang_simple_done = True
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Fehler: {str(e)}")
                    st.exception(e)

    # Ergebnisse anzeigen
    if st.session_state.get('empfang_simple_done', False) and 'empfang_simple_ergebnisse' in st.session_state:
        ergebnisse = st.session_state.empfang_simple_ergebnisse
        st.success("✅ Verarbeitung abgeschlossen!")

        st.subheader("📊 Verteilung")
        cols = st.columns(min(3, len(ergebnisse['sachbearbeiter_stats'])))
        for i, (sb, count) in enumerate(ergebnisse['sachbearbeiter_stats'].items()):
            if count > 0:
                with cols[i % len(cols)]:
                    st.metric(sb, count)

        st.subheader("📥 Downloads")
        scanner_name = ergebnisse.get('scanner_name', '')
        scan_datum = ergebnisse.get('scan_datum', '')

        for sb, zip_bytes in ergebnisse['zip_dateien'].items():
            # Erweiterter Dateiname: SB_ScannerName_Datum.zip
            zip_name = f"{sb}"
            if scanner_name:
                zip_name += f"_{scanner_name}"
            if scan_datum:
                zip_name += f"_{scan_datum}"
            zip_name += ".zip"

            st.download_button(
                label=f"📦 {zip_name}",
                data=zip_bytes,
                file_name=zip_name,
                mime="application/zip",
                key=f"empfang_simple_zip_{sb}"
            )

        # Email-Versand Option
        with st.expander("📧 Per Email versenden"):
            st.info("Konfigurieren Sie den Email-Versand in der Sidebar unter SMTP-Einstellungen")

            smtp_server_simple = st.text_input("SMTP Server", value="smtp.office365.com", key="smtp_simple_server")
            smtp_user_simple = st.text_input("Email-Adresse", key="smtp_simple_user")
            smtp_pass_simple = st.text_input("Passwort", type="password", key="smtp_simple_pass")

            empfaenger = st.text_input("Empfänger (kommagetrennt)", key="empfang_simple_email_to")

            if st.button("📤 Versenden", key="empfang_simple_send"):
                if smtp_user_simple and smtp_pass_simple and empfaenger:
                    try:
                        sender = EmailSender()
                        sender.configure(smtp_server_simple, 587, smtp_user_simple, smtp_pass_simple)

                        for email in [e.strip() for e in empfaenger.split(',')]:
                            for sb, zip_bytes in ergebnisse['zip_dateien'].items():
                                zip_name = f"{sb}"
                                if scanner_name:
                                    zip_name += f"_{scanner_name}"
                                if scan_datum:
                                    zip_name += f"_{scan_datum}"
                                zip_name += ".zip"

                                sender.sende_email(
                                    empfaenger=email,
                                    betreff=f"Posteingang {sb} - {scan_datum}",
                                    text=f"Anbei der Posteingang für {sb}.\n\nScanner: {scanner_name}\nDatum: {scan_datum}",
                                    anhang_bytes=zip_bytes,
                                    anhang_name=zip_name
                                )
                        st.success("✅ Emails versendet!")
                    except Exception as e:
                        st.error(f"❌ Email-Fehler: {str(e)}")
                else:
                    st.warning("⚠️ Bitte alle Felder ausfüllen")

        if st.button("🔄 Neuen Posteingang verarbeiten", key="empfang_simple_reset"):
            for key in ['empfang_simple_ergebnisse', 'empfang_simple_done', 'empfang_upload_name', 'empfang_upload_time']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# ============================================================================
# DASHBOARD RENOS (Erweitert) - Haupt-Upload-Bereich
# ============================================================================
if current_user['role'] in ['Administrator', 'Empfang'] and dashboard_auswahl == "Dashboard Renos (Erweitert)":
    st.header("📬 Dashboard Renos - Post-Eingang scannen")

    col1, col2 = st.columns([1, 1], gap="medium")

    with col1:
        st.subheader("📄 Tagespost-PDF hochladen")
        uploaded_pdfs = st.file_uploader(
            "PDF-Dateien mit Tagespost (OCR) - mehrere Dateien möglich",
            type=["pdf"],
            accept_multiple_files=True,
            help="Laden Sie eine oder mehrere OCR-PDF-Dateien hoch (Drag & Drop mehrerer Dateien möglich)"
        )
        # Speichere Upload-Metadaten für ZIP-Dateinamen
        if uploaded_pdfs:
            # Verwende den ersten Dateinamen für Scanner-Name-Extraktion
            first_pdf_name = uploaded_pdfs[0].name if uploaded_pdfs else ""
            st.session_state.renos_upload_name = first_pdf_name
            st.session_state.renos_upload_time = datetime.now()

    with col2:
        st.subheader("📊 Aktenregister hochladen")

        # Zeige Status: Gespeichertes Register vorhanden?
        if storage.has_aktenregister():
            stats = storage.get_aktenregister_stats()
            # Format timestamp
            from datetime import datetime
            dt = datetime.fromtimestamp(stats['last_modified'])
            formatted = dt.strftime('%d.%m.%Y %H:%M')
            st.success(f"💾 Gespeichertes Register: {stats['count']} Akten\n\n*Zuletzt aktualisiert: {formatted}*")

            # Lösch-Button
            if st.button("🗑️ Gespeichertes Register löschen"):
                storage.delete_aktenregister()
                st.rerun()

        uploaded_excel = st.file_uploader(
            "Neues Aktenregister (wird mit vorhandenem gemergt)" if storage.has_aktenregister() else "aktenregister.xlsx",
            type=["xlsx"],
            help="Neue Daten werden mit gespeicherten Daten zusammengeführt",
            key="excel_uploader"
        )

        # Kanzleisoftware-Integration
        with st.expander("🔄 Kanzleisoftware-Import (RA-MICRO / DATEV)"):
            st.info("**Importieren Sie Ihr Aktenregister direkt aus RA-MICRO oder DATEV**")

            sync_manager = KanzleiSoftwareSync(storage.storage_dir)

            # Template Download
            if st.button("📥 Mapping-Template herunterladen"):
                template_bytes = sync_manager.create_mapping_template()
                st.download_button(
                    label="💾 Template speichern",
                    data=template_bytes,
                    file_name="kanzleisoftware_mapping_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            # Import aus Kanzleisoftware
            kanzlei_import = st.file_uploader(
                "Excel-Export aus RA-MICRO/DATEV",
                type=["xlsx"],
                help="Automatische Format-Erkennung",
                key="kanzlei_import"
            )

            if kanzlei_import:
                try:
                    # Automatischer Import mit Format-Erkennung
                    rhm_df, detected_format = sync_manager.import_auto(BytesIO(kanzlei_import.read()))

                    st.success(f"✅ Format erkannt: **{detected_format}**")
                    st.info(f"📊 {len(rhm_df)} Akten importiert")

                    # Validierung
                    validation = sync_manager.validate_import(rhm_df)

                    if validation['warnings']:
                        for warning in validation['warnings']:
                            st.warning(f"⚠️ {warning}")

                    if validation['errors']:
                        for error in validation['errors']:
                            st.error(f"❌ {error}")

                    # Vorschau
                    with st.expander("👁️ Daten-Vorschau"):
                        st.dataframe(rhm_df.head(10))

                    # Import-Button
                    if st.button("✅ Als Aktenregister übernehmen", type="primary"):
                        # Speichere als Aktenregister
                        merged_df = storage.save_aktenregister(rhm_df, merge=storage.has_aktenregister())
                        st.success(f"✅ {len(merged_df)} Akten im Register gespeichert!")
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Import-Fehler: {str(e)}")

st.markdown("---")

# Zeige Batch-Status wenn im Batch-Modus
if st.session_state.batch_mode_active and st.session_state.batch_count > 0:
    st.info(f"📦 **Batch-Modus aktiv** | {st.session_state.batch_count} Batch(es) verarbeitet | "
            f"{len(st.session_state.accumulated_documents)} Dokumente gesammelt")

    # Zeige akkumulierte Statistiken
    stats_with_count = [(sb, count) for sb, count in st.session_state.sachbearbeiter_stats_accumulated.items() if count > 0]
    if stats_with_count:
        num_cols = min(len(stats_with_count), 6)  # Max 6 Spalten
        col_stats = st.columns(num_cols)
        for idx, (sb, count) in enumerate(stats_with_count[:6]):  # Max 6 anzeigen
            with col_stats[idx]:
                st.metric(sb, count, delta=None)

# Verarbeitungsbutton (Excel ist optional wenn gespeichert)
can_process = uploaded_pdfs and current_api_key and (uploaded_excel or storage.has_aktenregister())
if st.button("🚀 Verarbeitung starten" if st.session_state.batch_count == 0 else "📄 Weiteren Batch verarbeiten",
             type="primary", disabled=not can_process):
    if not current_api_key:
        st.error(f"❌ Bitte geben Sie Ihren {api_provider} API-Key ein!")
    elif not uploaded_pdfs:
        st.error("❌ Bitte laden Sie mindestens eine PDF-Datei hoch!")
    else:
        # Behandle uploaded_pdfs als Liste (auch wenn nur 1 Datei)
        pdf_files = uploaded_pdfs if isinstance(uploaded_pdfs, list) else [uploaded_pdfs]
        total_files = len(pdf_files)

        # Zeige Info über Anzahl der Dateien
        if total_files > 1:
            st.info(f"📦 **{total_files} PDF-Dateien werden nacheinander verarbeitet**")

        # Aktenregister EINMALIG vorbereiten (VOR der PDF-Schleife)
        if uploaded_excel:
            # Neues Excel hochgeladen: Merge mit gespeichertem
            import pandas as pd

            # Automatische Engine-Erkennung basierend auf Dateiendung
            filename = uploaded_excel.name.lower()
            if filename.endswith('.xlsx'):
                engine = 'openpyxl'
            elif filename.endswith('.xls'):
                engine = 'xlrd'
            else:
                # Fallback: Versuche openpyxl (häufigster Fall)
                engine = 'openpyxl'

            new_df = pd.read_excel(
                BytesIO(uploaded_excel.read()),
                sheet_name='akten',
                header=1,
                engine=engine
            )

            # Speichere und merge mit vorhandenem
            merged_df = storage.save_aktenregister(new_df, merge=storage.has_aktenregister())
            st.success(f"✅ Aktenregister aktualisiert: {len(merged_df)} Akten")

        # Verarbeite jede PDF-Datei nacheinander
        for file_index, uploaded_pdf in enumerate(pdf_files, start=1):
            # Zeige aktuellen Datei-Fortschritt
            if total_files > 1:
                st.markdown(f"---")
                st.subheader(f"📄 Datei {file_index} von {total_files}: {uploaded_pdf.name}")

            # Temporäres Verzeichnis für die Verarbeitung
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Dateien speichern
                pdf_path = temp_path / "tagespost.pdf"
                excel_path = temp_path / "aktenregister.xlsx"

                # Lese PDF-Bytes einmalig
                pdf_bytes = uploaded_pdf.read()
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)

                # Duplikate-Prüfung
                duplicate_detector = DuplicateDetector(storage.storage_dir)

                # Extrahiere kurzen Text-Preview für Duplikate-Check
                import fitz
                try:
                    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                        preview_text = ""
                        for page_num in range(min(3, len(doc))):  # Erste 3 Seiten
                            preview_text += doc[page_num].get_text()

                    is_duplicate, duplicate_info = duplicate_detector.check_duplicate(pdf_bytes, preview_text)

                    if is_duplicate:
                        st.warning(f"⚠️ **Duplikat erkannt!**")
                        st.info(f"""
                        Dieses Dokument wurde bereits verarbeitet:
                        - **Datum**: {duplicate_info.get('timestamp', 'Unbekannt')[:19]}
                        - **Größe**: {duplicate_info.get('size_bytes', 0) / 1024:.1f} KB
                        - **Ähnlichkeit**: {duplicate_info.get('similarity', 1.0) * 100:.0f}%
                        """)

                        if not st.checkbox("Trotzdem verarbeiten?", key=f"process_duplicate_{file_index}"):
                            continue  # Skip this file and continue with next
                except Exception as e:
                    st.warning(f"⚠️ Duplikate-Check fehlgeschlagen: {e}")

                # Progress-Container
                progress_container = st.container()
                with progress_container:
                    st.info("⏳ Verarbeitung läuft...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        # 1. Aktenregister vorbereiten
                        status_text.text("📊 Lade Aktenregister...")
                        progress_bar.progress(10)

                        # Verwende gespeichertes Register (wurde bereits vor der Schleife verarbeitet)
                        excel_path = storage.aktenregister_file
                        df = storage.load_aktenregister()
                        if file_index == 1:  # Nur bei erster PDF anzeigen
                            st.info(f"📂 Verwende Aktenregister: {len(df)} Akten")

                        erkenner = AktenzeichenErkenner(excel_path, storage=storage)

                        # 2. PDF verarbeiten
                        status_text.text("📄 Analysiere PDF und trenne Dokumente...")
                        progress_bar.progress(20)

                        # Live-Logging-Container
                        log_container = st.empty()

                        processor = PDFProcessor(pdf_path, debug=True, trennmodus="Text 'Trennseite'", excel_path=excel_path)
                        dokumente, debug_info = processor.verarbeite_pdf()

                        st.success(f"✅ {len(dokumente)} Einzeldokumente erkannt")

                        # Zeige wichtige Statistiken
                        st.info(f"""
                        **Verarbeitungs-Statistik:**
                        - Erkannte Dokumente: {len(dokumente)}
                        - Trennblätter gefunden: {debug_info.count('TRENNBLATT')}
                        - Leerseiten übersprungen: {debug_info.count('LEERSEITE')}
                        """)

                        # Debug-Informationen anzeigen
                        with st.expander("🔍 Debug-Informationen zur PDF-Verarbeitung", expanded=True):
                            for info in debug_info:
                                st.text(info)

                        # 3. Dokumente analysieren mit KI
                        status_text.text(f"🤖 Analysiere Dokumente mit {api_provider}...")
                        progress_bar.progress(40)

                        # Initialisiere Training-Database für KI-gestützte Erkennung
                        from training_database import TrainingDatabase
                        training_db = TrainingDatabase(storage.storage_dir)
                        analyzer = DocumentAnalyzer(current_api_key, api_provider=api_provider, training_db=training_db)

                        alle_daten = []
                        sachbearbeiter_stats = {"SQ": 0, "TS": 0, "M": 0, "FÜ": 0, "CV": 0, "nicht-zugeordnet": 0}

                        for i, doc in enumerate(dokumente):
                            status_text.text(f"🔍 Verarbeite Dokument {i+1}/{len(dokumente)}...")
                            progress_bar.progress(40 + int(40 * (i+1) / len(dokumente)))

                            # Aktenzeichen erkennen
                            akt_info = erkenner.erkenne_aktenzeichen(doc['text'])

                            # Sachbearbeiter aus Text erkennen (Anrede/Anschrift)
                            sb_aus_text = erkenner.erkenne_sachbearbeiter_aus_text(doc['text'])

                            # Dokumenteninhalt analysieren (inkl. Training-DB Vorschläge)
                            analyse = analyzer.analysiere_dokument(doc['text'], akt_info)

                            # Prüfe Training-Suggestion als zusätzliche Priorität
                            training_sb = None
                            if 'training_suggestion' in analyse and not sb_aus_text and not akt_info.get('kuerzel'):
                                # Training-Vorschlag nur nutzen wenn keine anderen Quellen vorhanden
                                suggestion = analyse['training_suggestion']
                                if suggestion['haeufigkeit'] >= 2:  # Min. 2x zuvor gesehen
                                    training_sb = suggestion['sachbearbeiter']

                            # Sachbearbeiter zuordnen (mit Priorität für Text-Erkennung)
                            sb = erkenner.ermittle_sachbearbeiter(akt_info, analyse, sachbearbeiter_aus_text=sb_aus_text or training_sb)
                            sachbearbeiter_stats[sb] = sachbearbeiter_stats.get(sb, 0) + 1

                            # Dateiname generieren
                            dateiname = erkenner.generiere_dateiname(
                                akt_info.get('internes_az'),
                                analyse.get('mandant'),
                                analyse.get('gegner'),
                                analyse.get('datum'),
                                analyse.get('stichworte', []),
                                aktenkurzbezeichnung=akt_info.get('aktenkurzbezeichnung')
                            )

                            alle_daten.append({
                                'dokument': doc,
                                'aktenzeichen_info': akt_info,
                                'analyse': analyse,
                                'sachbearbeiter': sb,
                                'sachbearbeiter_aus_text': sb_aus_text,  # Debug-Info speichern
                                'dateiname': dateiname
                            })

                            # Zeige erweiterte Debug-Info mit Aktenzeichen und Quelle
                            debug_parts = [f"📄 Dok {i+1}/{len(dokumente)}"]

                            # Aktenzeichen-Info
                            if akt_info.get('internes_az'):
                                az_quelle = akt_info.get('quelle', 'unbekannt')
                                az_text = f"AZ: {akt_info['internes_az']} ({az_quelle})"

                                # Zeige Kurzbezeichnung aus Register, falls vorhanden
                                if akt_info.get('aktenkurzbezeichnung'):
                                    kurzbez = akt_info['aktenkurzbezeichnung']
                                    # Kürze sehr lange Kurzbezeichnungen
                                    if len(kurzbez) > 40:
                                        kurzbez = kurzbez[:37] + "..."
                                    az_text += f" [{kurzbez}]"

                                debug_parts.append(az_text)
                            elif akt_info.get('az_vorschlaege'):
                                # Mehrere AZ-Vorschläge basierend auf Beteiligten
                                vorschlaege = akt_info['az_vorschlaege']
                                debug_parts.append(f"⚠️ AZ: {len(vorschlaege)} Vorschläge gefunden")

                                # Zeige Top-3 Vorschläge inline
                                for idx, v in enumerate(vorschlaege[:3], 1):
                                    matched = ", ".join(v['matched_beteiligte'])
                                    kurzbez = v.get('aktenkurzbezeichnung', 'keine Bez.')
                                    if len(kurzbez) > 30:
                                        kurzbez = kurzbez[:27] + "..."
                                    st.text(f"   {idx}. {v['internes_az']} [{kurzbez}] - Treffer: {matched}")
                            else:
                                debug_parts.append("AZ: nicht erkannt")

                            # Sachbearbeiter-Zuordnung
                            if training_sb:
                                suggestion = analyse.get('training_suggestion', {})
                                fuzzy = " (ähnlich)" if suggestion.get('fuzzy_match') else ""
                                debug_parts.append(f"SB: {sb} (aus Training-DB{fuzzy}, {suggestion.get('haeufigkeit', 0)}x)")
                            elif sb_aus_text:
                                debug_parts.append(f"SB: {sb} (aus Anrede/Anschrift)")
                            elif akt_info.get('kuerzel'):
                                debug_parts.append(f"SB: {sb} (aus AZ-Kürzel)")
                            elif 'register_data' in akt_info:
                                debug_parts.append(f"SB: {sb} (aus Register)")
                            else:
                                # Zeige Training-Suggestion wenn vorhanden, aber nicht genutzt
                                if 'training_suggestion' in analyse:
                                    suggestion = analyse['training_suggestion']
                                    debug_parts.append(f"SB: {sb} (nicht zugeordnet, Training-Vorschlag: {suggestion['sachbearbeiter']} ({suggestion['haeufigkeit']}x))")
                                else:
                                    debug_parts.append(f"SB: {sb} (nicht zugeordnet)")

                            # Dateiname
                            debug_parts.append(f"→ {dateiname}")

                            st.text(" | ".join(debug_parts))

                        progress_bar.progress(100)
                        status_text.text("✅ Batch-Verarbeitung abgeschlossen!")

                        # Füge Dokumente zu akkumulierten Daten hinzu
                        st.session_state.accumulated_documents.extend(alle_daten)

                        # Aktualisiere akkumulierte Statistiken
                        for sb, count in sachbearbeiter_stats.items():
                            st.session_state.sachbearbeiter_stats_accumulated[sb] = \
                                st.session_state.sachbearbeiter_stats_accumulated.get(sb, 0) + count

                        # Batch-Counter erhöhen
                        st.session_state.batch_count += 1
                        st.session_state.batch_mode_active = True

                        # Speichere alle Daten für Zugriff
                        st.session_state.alle_daten = list(st.session_state.accumulated_documents)

                        # Zeige Batch-Info
                        if total_files > 1:
                            st.success(f"✅ Datei {file_index}/{total_files} verarbeitet: {len(alle_daten)} Dokumente")
                        else:
                            st.success(f"✅ Batch #{st.session_state.batch_count} verarbeitet: {len(alle_daten)} Dokumente")
                        st.info(f"📊 **Gesamt akkumuliert**: {len(st.session_state.accumulated_documents)} Dokumente aus {st.session_state.batch_count} Batch(es)")

                        # Setze Flag dass Batch verarbeitet wurde (NICHT finale Verarbeitung)
                        st.session_state.batch_verarbeitet = True

                    except Exception as e:
                        st.error(f"❌ Fehler bei der Verarbeitung von Datei {file_index}/{total_files}: {str(e)}")
                        st.exception(e)

        # Zusammenfassung nach allen Dateien
        if total_files > 1:
            st.markdown("---")
            st.success(f"🎉 **Alle {total_files} PDF-Dateien erfolgreich verarbeitet!**")
            st.info(f"📊 Gesamt: {len(st.session_state.accumulated_documents)} Dokumente aus {total_files} Dateien")

# Zeige Batch-Aktionen wenn Batch verarbeitet wurde
if st.session_state.get('batch_verarbeitet', False):
    st.markdown("---")
    st.subheader("📦 Nächster Schritt")

    col_btn1, col_btn2 = st.columns(2, gap="medium")

    with col_btn1:
        if st.button("📄 Weitere Datei einlesen und hinzufügen", type="secondary", width="stretch"):
            # Lösche nur Upload-bezogene Session States, behalte akkumulierte Daten
            st.session_state.batch_verarbeitet = False
            # File uploader wird automatisch zurückgesetzt durch rerun
            st.rerun()

    with col_btn2:
        if st.button("📦 Postscan beenden und ZIP-Dateien erstellen", type="primary", width="stretch"):
            # Starte finale Verarbeitung
            with st.spinner("📦 Erstelle finale ZIP-Dateien aus allen Batches..."):
                try:
                    # Verwende akkumulierte Dokumente
                    alle_daten = st.session_state.accumulated_documents

                    # Erstelle temporäres Verzeichnis für Excel-Generierung
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir)

                        # Excel-Dateien generieren
                        excel_gen = ExcelGenerator()
                        excel_dateien = excel_gen.erstelle_excel_dateien(alle_daten, temp_path)

                        # ZIP-Dateien erstellen
                        zip_dateien = {}

                        for sb in ["SQ", "TS", "M", "FÜ", "CV", "nicht-zugeordnet"]:
                            if st.session_state.sachbearbeiter_stats_accumulated.get(sb, 0) > 0:
                                zip_buffer = BytesIO()
                                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                    # PDFs hinzufügen
                                    for daten in alle_daten:
                                        if daten['sachbearbeiter'] == sb:
                                            pdf_content = daten['dokument']['pdf_bytes']
                                            zipf.writestr(daten['dateiname'], pdf_content)

                                    # Excel hinzufügen
                                    if sb in excel_dateien:
                                        excel_bytes = excel_dateien[sb]
                                        zipf.writestr(f"{sb}_Fristen.xlsx", excel_bytes)

                                zip_dateien[sb] = zip_buffer.getvalue()

                        # Gesamt-Excel
                        gesamt_excel = excel_gen.erstelle_gesamt_excel(alle_daten)

                        # Extrahiere Scanner-Name und Scan-Datum
                        scanner_name = _extract_scanner_name(st.session_state.get('renos_upload_name', ''))
                        scan_datum = st.session_state.get('renos_upload_time', datetime.now()).strftime('%Y-%m-%d')

                        # Speichere Ergebnisse
                        st.session_state.verarbeitung_ergebnisse = {
                            'zip_dateien': dict(zip_dateien),
                            'gesamt_excel': bytes(gesamt_excel),
                            'sachbearbeiter_stats': dict(st.session_state.sachbearbeiter_stats_accumulated),
                            'scanner_name': scanner_name,
                            'scan_datum': scan_datum
                        }
                        st.session_state.verarbeitung_abgeschlossen = True
                        st.session_state.batch_verarbeitet = False

                        st.success(f"✅ {st.session_state.batch_count} Batch(es) mit {len(alle_daten)} Dokumenten finalisiert!")
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Fehler beim Erstellen der ZIP-Dateien: {str(e)}")
                    st.exception(e)

# Zeige Download-Buttons außerhalb des Processing-Blocks (persistent)
# Prüfe ob Verarbeitung abgeschlossen und Ergebnisse vorhanden
if (st.session_state.get('verarbeitung_abgeschlossen', False) and
    'verarbeitung_ergebnisse' in st.session_state):

    ergebnisse = st.session_state.verarbeitung_ergebnisse

    # Validiere dass alle erforderlichen Daten vorhanden sind
    if not all(key in ergebnisse for key in ['zip_dateien', 'gesamt_excel', 'sachbearbeiter_stats']):
        st.error("⚠️ Fehler: Verarbeitungsergebnisse unvollständig. Bitte erneut verarbeiten.")
        if st.button("Ergebnisse zurücksetzen"):
            if 'verarbeitung_ergebnisse' in st.session_state:
                del st.session_state.verarbeitung_ergebnisse
            if 'verarbeitung_abgeschlossen' in st.session_state:
                del st.session_state.verarbeitung_abgeschlossen
            st.rerun()
    else:
        # Ergebnisse sind vollständig - zeige Downloads
        st.markdown("---")
        st.success("🎉 Verarbeitung erfolgreich abgeschlossen!")

        # Statistik (responsive: max 3 Spalten für bessere Mobile-Darstellung)
        st.subheader("📊 Verteilung")
        stats_items = [(sb, count) for sb, count in ergebnisse['sachbearbeiter_stats'].items() if count > 0]

        # Dynamische Spaltenanzahl: max 3 Spalten für Mobile-Kompatibilität
        num_stats = len(stats_items)
        num_cols = min(3, num_stats)

        if num_stats > 0:
            cols = st.columns(num_cols)
            for i, (sb, count) in enumerate(stats_items):
                with cols[i % num_cols]:
                    st.metric(sb, count)

        # Downloads
        st.subheader("📥 Downloads")

        # Hole Scanner-Name und Scan-Datum
        scanner_name = ergebnisse.get('scanner_name', '')
        scan_datum = ergebnisse.get('scan_datum', '')

        # ZIP-Dateien - Responsive Layout (2 Spalten für bessere Mobile-UX)
        zip_liste = list(ergebnisse['zip_dateien'].items())

        # 2 Spalten statt 3 für bessere Mobile-Darstellung
        num_cols = 2
        cols = st.columns(num_cols, gap="small")

        for idx, (sb, zip_bytes) in enumerate(zip_liste):
            col_index = idx % num_cols
            with cols[col_index]:
                # Erweiterter Dateiname: SB_ScannerName_Datum.zip
                zip_name = f"{sb}"
                if scanner_name:
                    zip_name += f"_{scanner_name}"
                if scan_datum:
                    zip_name += f"_{scan_datum}"
                zip_name += ".zip"

                st.download_button(
                    label=f"📦 {zip_name}",
                    data=zip_bytes,
                    file_name=zip_name,
                    mime="application/zip",
                    key=f"download_zip_{sb}",
                    width="stretch",
                    help=f"{ergebnisse['sachbearbeiter_stats'][sb]} Dokumente"
                )

        # Gesamt-Excel - mit eigenem Container
        st.markdown("")  # Abstand
        st.download_button(
            label="📊 Gesamt-Excel: Fristen & Akten",
            data=ergebnisse['gesamt_excel'],
            file_name="Fristen_und_Akten_Gesamt.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_gesamt_excel",
            width="content"
        )

        # Kanzleisoftware-Export
        st.markdown("---")
        st.subheader("🔄 Export für Kanzleisoftware")

        with st.expander("📤 Export für RA-MICRO / DATEV", expanded=False):
            st.info("**Exportieren Sie die verarbeiteten Dokumente für Re-Import in Ihre Kanzleisoftware**")

            sync_manager = KanzleiSoftwareSync(storage.storage_dir)

            # Export-Format wählen
            export_format = st.radio(
                "Export-Format:",
                ["RA-MICRO", "DATEV"],
                horizontal=True
            )

            col_exp1, col_exp2 = st.columns(2)

            with col_exp1:
                if st.button("📥 Export erstellen", type="primary"):
                    try:
                        # Hole verarbeitete Dokumente
                        alle_daten = st.session_state.get('alle_daten', [])

                        if export_format == "RA-MICRO":
                            export_bytes = sync_manager.export_for_ramicro_import(alle_daten)
                            filename = f"RHM_Export_RA-MICRO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        else:  # DATEV
                            export_bytes = sync_manager.export_for_datev_import(alle_daten)
                            filename = f"RHM_Export_DATEV_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

                        # Speichere in Session State für Download
                        st.session_state.kanzlei_export = {
                            'data': export_bytes,
                            'filename': filename
                        }

                        st.success(f"✅ Export für {export_format} erstellt!")

                    except Exception as e:
                        st.error(f"❌ Export-Fehler: {str(e)}")

            with col_exp2:
                # Download-Button nur zeigen wenn Export vorhanden
                if 'kanzlei_export' in st.session_state:
                    export_data = st.session_state.kanzlei_export
                    st.download_button(
                        label="💾 Export herunterladen",
                        data=export_data['data'],
                        file_name=export_data['filename'],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="download_kanzlei_export"
                    )

            # Info-Box mit Spalten-Beschreibung
            with st.expander("ℹ️ Export-Spalten"):
                if export_format == "RA-MICRO":
                    st.markdown("""
                    **RA-MICRO Export enthält:**
                    - AktenNr
                    - Dokumenttyp (Posteingang)
                    - Datum
                    - Absender
                    - Empfänger
                    - Sachbearbeiter
                    - Dateiname
                    - Betreff (Stichworte)
                    - Frist
                    - Priorität
                    - Verarbeitet (Timestamp)
                    """)
                else:
                    st.markdown("""
                    **DATEV Export enthält:**
                    - Akten-Nr.
                    - Belegart (Posteingang)
                    - Belegdatum
                    - Absender
                    - Empfänger
                    - Bearbeiter
                    - Dokumentname
                    - Beschreibung (Stichworte)
                    - Wiedervorlagedatum (Frist)
                    - Priorität
                    - Erfassungsdatum
                    """)

        # Email-Versand an RENOs
        st.markdown("---")
        st.subheader("📧 Email-Versand an RENOs")

        with st.expander("📮 ZIP-Dateien per Email versenden", expanded=False):
            st.info("📝 Wählen Sie für jeden Sachbearbeiter die RENOs aus, die die Dokumente per Email erhalten sollen.")

            # SMTP-Konfiguration (responsive: stacked auf Mobile)
            col_smtp1, col_smtp2 = st.columns([1, 1], gap="medium")
            with col_smtp1:
                smtp_server = st.text_input(
                    "SMTP Server",
                    value="smtp.office365.com",
                    help="z.B. smtp.gmail.com, smtp.office365.com, smtp.ionos.de"
                )
                smtp_user = st.text_input(
                    "Email-Adresse (Absender)",
                    help="Ihre Email-Adresse für den Versand"
                )
            with col_smtp2:
                smtp_port = st.number_input(
                    "SMTP Port",
                    value=587,
                    min_value=1,
                    max_value=65535,
                    help="Standard: 587 (TLS)"
                )
                smtp_password = st.text_input(
                    "SMTP Passwort",
                    type="password",
                    help="Passwort für Email-Account"
                )

            st.markdown("---")

            # RENO-Auswahl für jeden Sachbearbeiter
            reno_auswahl = {}
            for sb, zip_bytes in ergebnisse['zip_dateien'].items():
                anzahl = ergebnisse['sachbearbeiter_stats'][sb]
                st.markdown(f"**{sb}** ({anzahl} Dokumente)")

                # Hole verfügbare RENOs für diesen Sachbearbeiter
                verfuegbare_renos = EmailSender.get_renos_fuer_sachbearbeiter(sb)

                if verfuegbare_renos:
                    # Multiselect für RENO-Auswahl
                    ausgewaehlte_renos = st.multiselect(
                        f"RENOs für {sb} auswählen:",
                        options=[f"{reno['name']} ({reno['email']})" for reno in verfuegbare_renos],
                        key=f"reno_select_{sb}"
                    )

                    # Extrahiere Email-Adressen
                    if ausgewaehlte_renos:
                        emails = []
                        for auswahl in ausgewaehlte_renos:
                            # Extrahiere Email aus "Name (email@domain.de)"
                            email = auswahl.split('(')[1].split(')')[0]
                            emails.append(email)
                        reno_auswahl[sb] = emails
                else:
                    st.warning(f"Keine RENOs für {sb} verfügbar")

                st.markdown("")  # Abstand

            # Versand-Button
            if st.button("📧 Emails versenden", type="primary"):
                if not smtp_server or not smtp_user or not smtp_password:
                    st.error("❌ Bitte SMTP-Konfiguration vollständig ausfüllen!")
                elif not reno_auswahl:
                    st.error("❌ Bitte mindestens einen RENO auswählen!")
                else:
                    # Email-Sender initialisieren
                    try:
                        sender = EmailSender(
                            smtp_server=smtp_server,
                            smtp_port=int(smtp_port),
                            smtp_user=smtp_user,
                            smtp_password=smtp_password
                        )

                        # Emails versenden
                        with st.spinner("📤 Sende Emails..."):
                            results = sender.sende_mehrere_zips(
                                reno_auswahl=reno_auswahl,
                                zip_dateien=ergebnisse['zip_dateien'],
                                sachbearbeiter_stats=ergebnisse['sachbearbeiter_stats'],
                                datum=datetime.now().strftime('%d.%m.%Y'),
                                scanner_name=ergebnisse.get('scanner_name', ''),
                                scan_datum=ergebnisse.get('scan_datum', '')
                            )

                        # Ergebnisse anzeigen
                        erfolge = sum(1 for success in results.values() if success)
                        gesamt = len(results)

                        if erfolge == gesamt:
                            st.success(f"✅ Alle {gesamt} Emails erfolgreich versendet!")
                        elif erfolge > 0:
                            st.warning(f"⚠️ {erfolge}/{gesamt} Emails erfolgreich versendet")
                        else:
                            st.error(f"❌ Keine Emails erfolgreich versendet")

                        # Details anzeigen
                        with st.expander("📊 Versand-Details"):
                            for versand, success in results.items():
                                status = "✅" if success else "❌"
                                st.text(f"{status} {versand}")

                    except Exception as e:
                        st.error(f"❌ Fehler beim Email-Versand: {str(e)}")

        # === MANUELLE NACHBEARBEITUNG ===
        st.markdown("---")
        st.subheader("🔍 Manuelle Nachbearbeitung")

        # Prüfe ob nicht-zugeordnete Dokumente vorhanden
        if 'alle_daten' in st.session_state and st.session_state.get('alle_daten'):
            alle_daten = st.session_state.alle_daten

            # Filtere nicht-zugeordnete Dokumente ODER Dokumente mit AZ-Vorschlägen
            nicht_zugeordnet = [
                d for d in alle_daten
                if d['sachbearbeiter'] == 'nicht-zugeordnet'
                or d.get('aktenzeichen_info', {}).get('az_vorschlaege')  # AZ-Vorschläge vorhanden
            ]

            if nicht_zugeordnet:
                # Zähle Dokumente mit Vorschlägen separat
                mit_vorschlaegen = sum(1 for d in nicht_zugeordnet if d.get('aktenzeichen_info', {}).get('az_vorschlaege'))
                ohne_az = len(nicht_zugeordnet) - mit_vorschlaegen

                if mit_vorschlaegen > 0 and ohne_az > 0:
                    st.warning(f"⚠️ {len(nicht_zugeordnet)} Dokument(e) zur manuellen Zuordnung: "
                              f"{mit_vorschlaegen} mit AZ-Vorschlägen, {ohne_az} ohne erkanntes AZ")
                elif mit_vorschlaegen > 0:
                    st.warning(f"📋 {mit_vorschlaegen} Dokument(e) mit AZ-Vorschlägen zur Auswahl")
                else:
                    st.warning(f"⚠️ {ohne_az} Dokument(e) konnten nicht automatisch zugeordnet werden.")
                st.info("👉 Sie können diese Dokumente jetzt manuell zuordnen. Das System lernt aus Ihren Zuordnungen!")

                with st.expander(f"📋 {len(nicht_zugeordnet)} nicht-zugeordnete Dokumente bearbeiten", expanded=False):
                    # Initialisiere Training-Database
                    from training_database import TrainingDatabase
                    training_db = TrainingDatabase(storage.storage_dir)

                    # Zeige Statistiken
                    stats = training_db.get_statistics()
                    if stats['total_training_entries'] > 0:
                        st.info(f"📚 **Training-Datenbank**: {stats['total_training_entries']} Einträge | "
                                f"{stats['unique_absender']} eindeutige Absender")

                    # Session State für aktuelles Dokument
                    if 'current_manual_doc_index' not in st.session_state:
                        st.session_state.current_manual_doc_index = 0

                    current_index = st.session_state.current_manual_doc_index

                    if current_index < len(nicht_zugeordnet):
                        current_doc = nicht_zugeordnet[current_index]

                        st.markdown(f"### Dokument {current_index + 1} von {len(nicht_zugeordnet)}")

                        # Zwei Spalten: PDF-Viewer links, Zuordnung rechts
                        col_pdf, col_assign = st.columns([2, 1], gap="large")

                        with col_pdf:
                            st.markdown("#### 📄 Dokument-Vorschau")

                            # PDF als Base64 in iframe
                            import base64
                            pdf_bytes = current_doc['dokument']['pdf_bytes']
                            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                            pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_base64}" width="100%" height="600px" type="application/pdf"></iframe>'
                            st.markdown(pdf_display, unsafe_allow_html=True)

                            # Textauszug
                            with st.expander("📝 Text-Auszug (erste 500 Zeichen)"):
                                text = current_doc['dokument']['text']
                                st.text(text[:500] + "..." if len(text) > 500 else text)

                        with col_assign:
                            st.markdown("#### ✏️ Manuelle Zuordnung")

                            # Extrahiere Absender aus Analyse
                            absender = current_doc['analyse'].get('gegner', 'Unbekannt')
                            st.info(f"**Absender**: {absender}")

                            # PRIORITÄT 0: AZ-Vorschläge aus Beteiligten-Abgleich anzeigen
                            az_vorschlaege = current_doc['aktenzeichen_info'].get('az_vorschlaege', [])
                            if az_vorschlaege:
                                st.warning(f"📋 **{len(az_vorschlaege)} AZ-Vorschläge** basierend auf erkannten Beteiligten:")

                                for v_idx, vorschlag in enumerate(az_vorschlaege[:5]):  # Max 5 Vorschläge
                                    matched = ", ".join(vorschlag.get('matched_beteiligte', []))
                                    kurzbez = vorschlag.get('aktenkurzbezeichnung', 'keine Bez.')
                                    if len(kurzbez) > 35:
                                        kurzbez = kurzbez[:32] + "..."

                                    col_v1, col_v2 = st.columns([3, 1])
                                    with col_v1:
                                        st.text(f"{v_idx+1}. {vorschlag['internes_az']} [{kurzbez}]")
                                        st.caption(f"   Treffer: {matched} (Score: {vorschlag.get('score', 0)})")
                                    with col_v2:
                                        if st.button("Übernehmen", key=f"az_vorschlag_{current_index}_{v_idx}"):
                                            # AZ-Vorschlag übernehmen
                                            current_doc['aktenzeichen_info'] = vorschlag
                                            current_doc['sachbearbeiter'] = vorschlag['kuerzel']

                                            # Dateiname neu generieren
                                            from aktenzeichen_erkennung import AktenzeichenErkenner
                                            if storage.has_aktenregister():
                                                excel_path = storage.aktenregister_file
                                                erkenner = AktenzeichenErkenner(excel_path, storage=storage)
                                                neuer_dateiname = erkenner.generiere_dateiname(
                                                    vorschlag.get('internes_az'),
                                                    current_doc['analyse'].get('mandant'),
                                                    current_doc['analyse'].get('gegner'),
                                                    current_doc['analyse'].get('datum'),
                                                    current_doc['analyse'].get('stichworte', []),
                                                    aktenkurzbezeichnung=vorschlag.get('aktenkurzbezeichnung')
                                                )
                                                current_doc['dateiname'] = neuer_dateiname

                                            # Training speichern
                                            training_db.save_training_entry(
                                                absender=absender,
                                                aktenzeichen=vorschlag['internes_az'],
                                                sachbearbeiter=vorschlag['kuerzel']
                                            )

                                            st.success(f"AZ {vorschlag['internes_az']} übernommen!")
                                            st.session_state.current_manual_doc_index += 1
                                            st.rerun()

                                st.markdown("---")

                            # Prüfe ob Training-Daten vorhanden
                            pattern = training_db.find_matching_pattern(absender)
                            if pattern:
                                fuzzy = " (ähnlich)" if pattern.get('fuzzy_match') else ""
                                st.success(f"✨ **KI-Vorschlag{fuzzy}**:\n\n"
                                          f"Sachbearbeiter: **{pattern['sachbearbeiter']}**\n\n"
                                          f"Basiert auf {pattern['haeufigkeit']} früheren Zuordnung(en)")

                                # Vorschlag übernehmen?
                                if st.button("✅ Vorschlag übernehmen", key=f"accept_suggestion_{current_index}"):
                                    # Zuordnung durchführen
                                    current_doc['sachbearbeiter'] = pattern['sachbearbeiter']
                                    # Training speichern
                                    training_db.save_training_entry(
                                        absender=absender,
                                        aktenzeichen=current_doc['aktenzeichen_info'].get('internes_az', 'unbekannt'),
                                        sachbearbeiter=pattern['sachbearbeiter']
                                    )
                                    st.success(f"✅ Dokument zu {pattern['sachbearbeiter']} zugeordnet!")
                                    # Nächstes Dokument
                                    st.session_state.current_manual_doc_index += 1
                                    st.rerun()

                                st.markdown("---")

                            # Option 1: Aktenzeichen manuell eingeben
                            st.markdown("**Option 1: Aktenzeichen eingeben**")
                            manual_az = st.text_input(
                                "Aktenzeichen:",
                                placeholder="z.B. 12345/01",
                                key=f"manual_az_{current_index}",
                                help="Geben Sie das Aktenzeichen aus dem Dokument ein"
                            )

                            if manual_az:
                                # Prüfe gegen Register
                                from aktenzeichen_erkennung import AktenzeichenErkenner
                                # Lade Register
                                if storage.has_aktenregister():
                                    excel_path = storage.aktenregister_file
                                    erkenner = AktenzeichenErkenner(excel_path, storage=storage)
                                    register_info = erkenner._pruefe_register(manual_az)

                                    if register_info:
                                        st.success(f"✅ Im Register gefunden: **{register_info['kuerzel']}**")

                                        if st.button("💾 Zuordnung speichern", key=f"save_manual_{current_index}"):
                                            # Aktualisiere Dokument
                                            current_doc['sachbearbeiter'] = register_info['kuerzel']
                                            current_doc['aktenzeichen_info'] = register_info

                                            # Training speichern
                                            training_db.save_training_entry(
                                                absender=absender,
                                                aktenzeichen=manual_az,
                                                sachbearbeiter=register_info['kuerzel']
                                            )

                                            st.success(f"✅ Zugeordnet zu {register_info['kuerzel']}!")
                                            st.session_state.current_manual_doc_index += 1
                                            st.rerun()
                                    else:
                                        st.warning("⚠️ Aktenzeichen nicht im Register gefunden")

                                        # Manuelle Sachbearbeiter-Auswahl
                                        sb_manual = st.selectbox(
                                            "Sachbearbeiter auswählen:",
                                            options=['SQ', 'TS', 'M', 'CV', 'FÜ'],
                                            key=f"sb_manual_{current_index}"
                                        )

                                        if st.button("💾 Zuordnung speichern", key=f"save_manual_no_reg_{current_index}"):
                                            current_doc['sachbearbeiter'] = sb_manual
                                            current_doc['aktenzeichen_info']['internes_az'] = f"{manual_az}{sb_manual}"

                                            training_db.save_training_entry(
                                                absender=absender,
                                                aktenzeichen=manual_az,
                                                sachbearbeiter=sb_manual
                                            )

                                            st.success(f"✅ Zugeordnet zu {sb_manual}!")
                                            st.session_state.current_manual_doc_index += 1
                                            st.rerun()

                            st.markdown("---")

                            # Option 2: Nur Sachbearbeiter auswählen
                            st.markdown("**Option 2: Direkte Sachbearbeiter-Zuordnung**")
                            sb_direct = st.selectbox(
                                "Sachbearbeiter:",
                                options=['SQ', 'TS', 'M', 'CV', 'FÜ'],
                                key=f"sb_direct_{current_index}"
                            )

                            if st.button("💾 Nur Sachbearbeiter zuordnen", key=f"save_direct_{current_index}"):
                                current_doc['sachbearbeiter'] = sb_direct

                                training_db.save_training_entry(
                                    absender=absender,
                                    aktenzeichen=current_doc['aktenzeichen_info'].get('internes_az', 'unbekannt'),
                                    sachbearbeiter=sb_direct
                                )

                                st.success(f"✅ Zugeordnet zu {sb_direct}!")
                                st.session_state.current_manual_doc_index += 1
                                st.rerun()

                            # Dokument überspringen
                            st.markdown("---")
                            if st.button("⏭️ Überspringen", key=f"skip_{current_index}"):
                                st.session_state.current_manual_doc_index += 1
                                st.rerun()

                    else:
                        st.success("🎉 Alle Dokumente bearbeitet!")
                        if st.button("🔄 Neu starten"):
                            st.session_state.current_manual_doc_index = 0
                            st.rerun()

            else:
                st.success("✅ Alle Dokumente wurden automatisch zugeordnet!")

        # Button zum Neu-Generieren der ZIP-Dateien nach manuellen Änderungen
        st.markdown("---")
        if st.button("🔄 ZIP-Dateien mit manuellen Zuordnungen neu generieren", type="secondary"):
            with st.spinner("📦 Generiere ZIP-Dateien neu..."):
                try:
                    # Verwende aktualisierte alle_daten (mit manuellen Zuordnungen)
                    alle_daten = st.session_state.alle_daten

                    # Aktualisiere Sachbearbeiter-Statistiken
                    sachbearbeiter_stats_neu = {"SQ": 0, "TS": 0, "M": 0, "FÜ": 0, "CV": 0, "nicht-zugeordnet": 0}
                    for daten in alle_daten:
                        sb = daten['sachbearbeiter']
                        sachbearbeiter_stats_neu[sb] = sachbearbeiter_stats_neu.get(sb, 0) + 1

                    # Erstelle temporäres Verzeichnis für Excel-Generierung
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir)

                        # Excel-Dateien generieren
                        excel_gen = ExcelGenerator()
                        excel_dateien = excel_gen.erstelle_excel_dateien(alle_daten, temp_path)

                        # ZIP-Dateien erstellen
                        zip_dateien = {}

                        for sb in ["SQ", "TS", "M", "FÜ", "CV", "nicht-zugeordnet"]:
                            if sachbearbeiter_stats_neu.get(sb, 0) > 0:
                                zip_buffer = BytesIO()
                                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                    # PDFs hinzufügen
                                    for daten in alle_daten:
                                        if daten['sachbearbeiter'] == sb:
                                            pdf_content = daten['dokument']['pdf_bytes']
                                            zipf.writestr(daten['dateiname'], pdf_content)

                                    # Excel hinzufügen
                                    if sb in excel_dateien:
                                        excel_bytes = excel_dateien[sb]
                                        zipf.writestr(f"{sb}_Fristen.xlsx", excel_bytes)

                                zip_dateien[sb] = zip_buffer.getvalue()

                        # Gesamt-Excel
                        gesamt_excel = excel_gen.erstelle_gesamt_excel(alle_daten)

                        # Behalte Scanner-Name und Scan-Datum aus vorherigen Ergebnissen
                        prev_results = st.session_state.get('verarbeitung_ergebnisse', {})
                        scanner_name = prev_results.get('scanner_name', _extract_scanner_name(st.session_state.get('renos_upload_name', '')))
                        scan_datum = prev_results.get('scan_datum', st.session_state.get('renos_upload_time', datetime.now()).strftime('%Y-%m-%d'))

                        # Update Ergebnisse
                        st.session_state.verarbeitung_ergebnisse = {
                            'zip_dateien': dict(zip_dateien),
                            'gesamt_excel': bytes(gesamt_excel),
                            'sachbearbeiter_stats': dict(sachbearbeiter_stats_neu),
                            'scanner_name': scanner_name,
                            'scan_datum': scan_datum
                        }

                        st.success("✅ ZIP-Dateien erfolgreich neu generiert! Bitte scrollen Sie nach oben zu den Downloads.")
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Fehler beim Neu-Generieren: {str(e)}")
                    st.exception(e)

        # Button zum Löschen der Ergebnisse und Neustart
        if st.button("🔄 Neue Verarbeitung starten (alle Daten löschen)"):
            # Lösche alle Verarbeitungs- und Batch-Daten
            keys_to_delete = [
                'verarbeitung_ergebnisse',
                'verarbeitung_abgeschlossen',
                'accumulated_documents',
                'batch_count',
                'batch_mode_active',
                'sachbearbeiter_stats_accumulated',
                'batch_verarbeitet',
                'alle_daten',
                'current_manual_doc_index'
            ]
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]

            # Initialisiere Batch-Variablen neu
            st.session_state.accumulated_documents = []
            st.session_state.batch_count = 0
            st.session_state.batch_mode_active = False
            st.session_state.sachbearbeiter_stats_accumulated = {"SQ": 0, "TS": 0, "M": 0, "FÜ": 0, "CV": 0, "nicht-zugeordnet": 0}

            st.rerun()

# === PAPIERKORB-VERWALTUNG ===
st.markdown("---")
st.subheader("🗑️ Papierkorb")

trash_items = trash_manager.get_trash_items()

if trash_items:
    st.warning(f"📦 {len(trash_items)} Dokument(e) im Papierkorb")

    # Warnung bei bald ablaufenden Dokumenten
    expiring_soon = trash_manager.get_expiring_soon(hours=6)
    if expiring_soon:
        st.error(f"⚠️ {len(expiring_soon)} Dokument(e) werden in den nächsten 6 Stunden gelöscht!")

    with st.expander("📋 Papierkorb anzeigen", expanded=False):
        # Statistiken
        col_stat1, col_stat2, col_stat3 = st.columns(3)

        with col_stat1:
            st.metric("Dokumente", len(trash_items))
        with col_stat2:
            st.metric("Größe", f"{trash_stats['total_size_mb']:.2f} MB")
        with col_stat3:
            st.metric("Aufbewahrung", f"{trash_stats['retention_hours']}h")

        # Such-Funktion
        search_query = st.text_input("🔍 Suche im Papierkorb", placeholder="Dateiname...")

        if search_query:
            trash_items = trash_manager.search_trash(search_query)
            st.info(f"📊 {len(trash_items)} Ergebnis(se) gefunden")

        # Liste der Dokumente
        for item in trash_items:
            with st.container():
                col_info, col_actions = st.columns([3, 1])

                with col_info:
                    # Status-Icon
                    if item['is_expired']:
                        status_icon = "🔴"
                        status_text = "Abgelaufen"
                    elif item['hours_remaining'] <= 6:
                        status_icon = "🟠"
                        status_text = f"Noch {item['hours_remaining']:.1f}h"
                    else:
                        status_icon = "🟢"
                        status_text = f"Noch {item['hours_remaining']:.1f}h"

                    st.markdown(f"""
                    {status_icon} **{item['name']}**
                    Gelöscht: {item['deleted_at']} | Läuft ab: {item['expires_at']} | {item['size_kb']:.1f} KB
                    Original: `{item['original_path']}`
                    {status_text}
                    """)

                with col_actions:
                    # Wiederherstellen
                    if st.button("♻️ Wiederherstellen", key=f"restore_{item['trash_id']}", width="stretch"):
                        try:
                            trash_manager.restore_from_trash(item['trash_id'])
                            st.success(f"✅ '{item['name']}' wiederhergestellt!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Fehler: {e}")

                    # Endgültig löschen
                    if st.button("🗑️ Löschen", key=f"delete_{item['trash_id']}", width="stretch"):
                        if trash_manager.permanent_delete(item['trash_id']):
                            st.success(f"✅ '{item['name']}' endgültig gelöscht!")
                            st.rerun()

                    # Verlängern
                    if st.button("⏰ +24h", key=f"extend_{item['trash_id']}", width="stretch"):
                        if trash_manager.extend_retention(item['trash_id'], 24):
                            st.success(f"✅ Aufbewahrung verlängert!")
                            st.rerun()

                st.markdown("---")

        # Massen-Aktionen
        st.markdown("### 🔧 Massen-Aktionen")

        col_mass1, col_mass2, col_mass3 = st.columns(3)

        with col_mass1:
            if st.button("♻️ Alles wiederherstellen", type="secondary", width="stretch"):
                restored_count = 0
                for item in trash_items:
                    try:
                        trash_manager.restore_from_trash(item['trash_id'])
                        restored_count += 1
                    except:
                        pass
                st.success(f"✅ {restored_count} Dokument(e) wiederhergestellt!")
                st.rerun()

        with col_mass2:
            if st.button("🗑️ Papierkorb leeren", type="secondary", width="stretch"):
                deleted_count = trash_manager.empty_trash()
                st.success(f"✅ {deleted_count} Dokument(e) endgültig gelöscht!")
                st.rerun()

        with col_mass3:
            if st.button("🧹 Nur Abgelaufene löschen", type="secondary", width="stretch"):
                deleted_count = trash_manager.cleanup_expired()
                st.success(f"✅ {deleted_count} abgelaufene Dokument(e) gelöscht!")
                st.rerun()

        # Export-Funktion
        st.markdown("### 📥 Export")
        if st.button("📊 Papierkorb-Liste als Excel exportieren"):
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                trash_manager.export_trash_list(Path(tmp.name))

                with open(tmp.name, 'rb') as f:
                    excel_bytes = f.read()

                st.download_button(
                    label="💾 Excel herunterladen",
                    data=excel_bytes,
                    file_name=f"Papierkorb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

else:
    st.success("✅ Papierkorb ist leer")

# Erweiterte Features in Tabs
st.markdown("---")
st.header("🚀 Erweiterte Features")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Dashboard",
    "🔍 Volltext-Suche",
    "📌 Wiedervorlagen",
    "📧 Email-Import",
    "📁 Hot Folder & Ablage",
    "🔔 Benachrichtigungen",
    "⚙️ System & Backup"
])

with tab1:
    st.subheader("📊 Dashboard & Statistiken")

    try:
        import plotly.graph_objects as go
        import plotly.express as px

        dashboard_mgr = st.session_state.dashboard_manager

        # KPIs
        col1, col2, col3, col4 = st.columns(4)

        timeline_data = dashboard_mgr.get_documents_timeline(days=30)
        sb_data = dashboard_mgr.get_sachbearbeiter_distribution()
        deadline_data = dashboard_mgr.get_deadline_summary(storage)

        with col1:
            st.metric("Dokumente (30 Tage)", timeline_data['total'])
        with col2:
            st.metric("Kritische Fristen", deadline_data['critical'])
        with col3:
            st.metric("Sachbearbeiter", len(sb_data['sachbearbeiter']))
        with col4:
            st.metric("Überfällig", deadline_data['overdue'])

        st.markdown("---")

        # Timeline Chart
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Dokumente-Zeitverlauf")
            if timeline_data['dates']:
                fig_timeline = go.Figure()
                fig_timeline.add_trace(go.Scatter(
                    x=timeline_data['dates'],
                    y=timeline_data['counts'],
                    mode='lines+markers',
                    name='Dokumente',
                    line=dict(color='#1f77b4', width=2),
                    marker=dict(size=8)
                ))
                fig_timeline.update_layout(
                    xaxis_title="Datum",
                    yaxis_title="Anzahl Dokumente",
                    height=300
                )
                st.plotly_chart(fig_timeline, width="stretch")

        with col_b:
            st.subheader("Verteilung Sachbearbeiter")
            if sb_data['sachbearbeiter']:
                fig_sb = px.pie(
                    values=sb_data['counts'],
                    names=sb_data['sachbearbeiter'],
                    title="Dokumente pro Sachbearbeiter"
                )
                fig_sb.update_layout(height=300)
                st.plotly_chart(fig_sb, width="stretch")

        # Prioritäten
        st.markdown("---")
        st.subheader("Fristen-Übersicht")

        col_c, col_d = st.columns(2)

        with col_c:
            # Fristen-Status
            fig_deadlines = go.Figure()
            fig_deadlines.add_trace(go.Bar(
                x=['Kritisch', 'Hoch', 'Mittel', 'Normal', 'Überfällig'],
                y=[
                    deadline_data['critical'],
                    deadline_data['high'],
                    deadline_data['medium'],
                    deadline_data['normal'],
                    deadline_data['overdue']
                ],
                marker_color=['red', 'orange', 'yellow', 'green', 'darkred']
            ))
            fig_deadlines.update_layout(
                title="Fristen nach Priorität",
                xaxis_title="Priorität",
                yaxis_title="Anzahl",
                height=300
            )
            st.plotly_chart(fig_deadlines, width="stretch")

        with col_d:
            # API-Nutzung
            api_data = dashboard_mgr.get_api_usage_stats()
            if api_data['providers']:
                fig_api = px.bar(
                    x=api_data['providers'],
                    y=api_data['counts'],
                    title="API-Nutzung",
                    labels={'x': 'Provider', 'y': 'Anzahl Aufrufe'}
                )
                fig_api.update_layout(height=300)
                st.plotly_chart(fig_api, width="stretch")

    except ImportError:
        st.warning("⚠️ Plotly nicht installiert. Installieren Sie mit: pip install plotly")

        # Fallback: Einfache Statistiken
        st.write("**Statistiken verfügbar - Plotly für Charts benötigt**")

with tab2:
    st.subheader("🔍 Volltext-Suche")

    search = st.session_state.fulltext_search

    if not search.is_available():
        st.error("⚠️ Whoosh nicht installiert. Installieren Sie mit: pip install whoosh")
    else:
        col1, col2 = st.columns([3, 1])

        with col1:
            query = st.text_input("Suchbegriff:", placeholder="Aktenzeichen, Mandant, Text...")

        with col2:
            fuzzy = st.checkbox("Fuzzy-Suche", value=False)

        if st.button("🔍 Suchen", type="primary"):
            if query:
                results = search.search(query, limit=50, fuzzy=fuzzy)

                st.write(f"**{len(results)} Ergebnisse gefunden**")

                for result in results:
                    with st.expander(f"📄 {result['dateiname']} ({result['aktenzeichen']})"):
                        st.write(f"**Sachbearbeiter:** {result['sachbearbeiter']}")
                        st.write(f"**Datum:** {result['datum']}")
                        st.write(f"**Priorität:** {result['priority']}")

                        if result['excerpt']:
                            st.markdown("**Textauszug:**")
                            st.markdown(result['excerpt'], unsafe_allow_html=True)

        # Statistiken
        st.markdown("---")
        search_stats = search.get_statistics()
        if search_stats['available']:
            st.metric("Indexierte Dokumente", search_stats['total_documents'])

            if st.button("🔄 Index neu aufbauen"):
                with st.spinner("Index wird neu aufgebaut..."):
                    count = search.rebuild_index(storage)
                    st.success(f"✅ {count} Dokumente indexiert")

with tab3:
    st.subheader("📌 Wiedervorlage-System")

    wv = st.session_state.wiedervorlage_system

    # Neue Wiedervorlage
    with st.expander("➕ Neue Wiedervorlage erstellen"):
        col1, col2 = st.columns(2)

        with col1:
            wv_titel = st.text_input("Titel:")
            wv_aktenzeichen = st.text_input("Aktenzeichen (optional):")
            wv_sb = st.text_input("Sachbearbeiter (optional):")

        with col2:
            wv_datum = st.date_input("Wiedervorlage-Datum:")
            wv_priority = st.selectbox("Priorität:", ["NORMAL", "MEDIUM", "HIGH", "CRITICAL"])
            wv_notiz = st.text_area("Notiz:")

        if st.button("💾 Wiedervorlage anlegen", type="primary"):
            from datetime import datetime
            wv_id = wv.create_wiedervorlage(
                titel=wv_titel,
                datum=datetime.combine(wv_datum, datetime.min.time()),
                aktenzeichen=wv_aktenzeichen if wv_aktenzeichen else None,
                sachbearbeiter=wv_sb if wv_sb else None,
                notiz=wv_notiz,
                priority=wv_priority
            )
            st.success(f"✅ Wiedervorlage erstellt (ID: {wv_id[:8]}...)")

    # Fällige Wiedervorlagen
    st.markdown("---")
    st.subheader("⚠️ Fällige Wiedervorlagen")

    faellig = wv.get_faellige_wiedervorlagen(tage_vorher=7)

    if faellig:
        for item in faellig:
            color = "🔴" if item['is_overdue'] else ("🟠" if item['days_remaining'] <= 3 else "🟡")

            with st.expander(f"{color} {item['titel']} ({item['datum'][:10]})"):
                st.write(f"**Aktenzeichen:** {item['aktenzeichen']}")
                st.write(f"**Sachbearbeiter:** {item['sachbearbeiter']}")
                st.write(f"**Priorität:** {item['priority']}")
                st.write(f"**Verbleibende Tage:** {item['days_remaining']}")
                st.write(f"**Notiz:** {item['notiz']}")

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("✅ Erledigt", key=f"done_{item['id']}"):
                        wv.mark_erledigt(item['id'])
                        st.rerun()

                with col2:
                    if st.button("📅 Verschieben", key=f"move_{item['id']}"):
                        # Session-State für Modal-Dialog
                        st.session_state[f"move_dialog_{item['id']}"] = True

                # Verschieben-Dialog (außerhalb der Spalten)
                if st.session_state.get(f"move_dialog_{item['id']}", False):
                    with st.form(key=f"move_form_{item['id']}"):
                        st.markdown("#### 📅 Wiedervorlage verschieben")
                        from datetime import datetime, timedelta

                        # Aktuelles Datum
                        current_date = datetime.fromisoformat(item['datum'][:10])

                        # Neues Datum
                        new_date = st.date_input(
                            "Neues Datum:",
                            value=current_date + timedelta(days=7),
                            min_value=datetime.now().date()
                        )

                        # Notiz hinzufügen
                        move_note = st.text_area("Grund für Verschiebung (optional):", key=f"note_{item['id']}")

                        col_btn1, col_btn2 = st.columns(2)

                        with col_btn1:
                            if st.form_submit_button("✅ Verschieben", type="primary"):
                                # Aktualisiere Datum
                                wv.update_wiedervorlage(item['id'], {'datum': datetime.combine(new_date, datetime.min.time()).isoformat()})

                                # Füge Notiz hinzu wenn vorhanden
                                if move_note:
                                    current_notiz = item.get('notiz', '')
                                    updated_notiz = f"{current_notiz}\n\n[Verschoben am {datetime.now().strftime('%Y-%m-%d')}]: {move_note}"
                                    wv.update_wiedervorlage(item['id'], {'notiz': updated_notiz})

                                st.session_state[f"move_dialog_{item['id']}"] = False
                                st.success(f"✅ Wiedervorlage auf {new_date} verschoben!")
                                st.rerun()

                        with col_btn2:
                            if st.form_submit_button("❌ Abbrechen"):
                                st.session_state[f"move_dialog_{item['id']}"] = False
                                st.rerun()

                with col3:
                    if st.button("🗑️ Löschen", key=f"del_{item['id']}"):
                        wv.delete(item['id'])
                        st.rerun()
    else:
        st.success("✅ Keine fälligen Wiedervorlagen")

with tab4:
    st.subheader("📧 Email-Import (IMAP)")

    email_imp = st.session_state.email_importer

    # Konfiguration
    with st.expander("⚙️ IMAP-Konfiguration"):
        col1, col2 = st.columns(2)

        with col1:
            imap_server = st.text_input("IMAP-Server:", value="imap.gmail.com", key="email_import_imap_server")
            imap_username = st.text_input("Email:", key="email_import_username")

        with col2:
            imap_port = st.number_input("Port:", value=993, key="email_import_port")
            imap_password = st.text_input("Passwort:", type="password", key="email_import_password")

        if st.button("💾 IMAP Konfigurieren"):
            email_imp.configure(imap_server, imap_username, imap_password, imap_port)
            st.success("✅ IMAP konfiguriert")

        # Test
        if email_imp.is_enabled():
            if st.button("🔌 Verbindung testen"):
                success, message = email_imp.test_connection()
                if success:
                    st.success(message)
                else:
                    st.error(message)

    # Import
    st.markdown("---")

    if email_imp.is_enabled():
        if st.button("📥 PDFs aus Emails importieren", type="primary"):
            with st.spinner("Rufe Emails ab..."):
                emails = email_imp.fetch_emails_with_pdfs()

                if emails:
                    st.success(f"✅ {len(emails)} Email(s) mit PDFs gefunden")

                    for email_data in emails:
                        with st.expander(f"📧 {email_data['subject']} ({len(email_data['pdfs'])} PDF(s))"):
                            st.write(f"**Von:** {email_data['from']}")
                            st.write(f"**Datum:** {email_data['date']}")

                            for pdf in email_data['pdfs']:
                                st.write(f"- {pdf['filename']} ({pdf['size'] / 1024:.1f} KB)")

                            if st.button(f"✅ Verarbeiten", key=f"process_{email_data['email_id']}"):
                                # Speichere PDFs zur Session für Verarbeitung
                                import tempfile
                                from pathlib import Path

                                # Erstelle temporäre Dateien für PDFs
                                if 'email_import_pdfs' not in st.session_state:
                                    st.session_state.email_import_pdfs = []

                                for pdf in email_data['pdfs']:
                                    st.session_state.email_import_pdfs.append({
                                        'name': pdf['filename'],
                                        'bytes': pdf['data'],
                                        'from': email_data['from'],
                                        'subject': email_data['subject']
                                    })

                                # Markiere Email als verarbeitet
                                email_imp.mark_email_as_processed(email_data['email_id'])

                                st.success(f"✅ {len(email_data['pdfs'])} PDF(s) importiert und zur Verarbeitung bereitgestellt!")
                                st.info("📋 **Hinweis:** Die importierten PDFs stehen jetzt im Post-Eingang zur Verarbeitung bereit.")
                                st.info("💡 **Tipp:** Wechseln Sie zum Tab 'Post-Eingang' und laden Sie die PDFs dort hoch.")
                else:
                    st.info("Keine neuen Emails mit PDFs gefunden")
    else:
        st.warning("⚠️ IMAP noch nicht konfiguriert")

with tab5:
    st.subheader("📁 Hot Folder & Automatische Ablage")

    # Hot Folder
    st.markdown("### 🔥 Hot Folder Überwachung")

    with st.expander("⚙️ Hot Folder konfigurieren"):
        hot_folder_path = st.text_input("Überwachtes Verzeichnis:", value="./hot_folder")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("▶️ Hot Folder starten", type="primary"):
                from pathlib import Path

                watcher = HotFolderWatcher(Path(hot_folder_path))
                watcher.start()
                st.session_state.hot_folder_watcher = watcher
                st.success(f"✅ Hot Folder gestartet: {hot_folder_path}")

        with col2:
            if st.session_state.hot_folder_watcher:
                if st.button("⏸️ Hot Folder stoppen"):
                    st.session_state.hot_folder_watcher.stop()
                    st.session_state.hot_folder_watcher = None
                    st.success("✅ Hot Folder gestoppt")

    # Auto-Ablage
    st.markdown("---")
    st.markdown("### ☁️ Automatische Ablage")

    auto_storage = st.session_state.auto_file_storage

    with st.expander("⚙️ Auto-Ablage konfigurieren"):
        storage_type = st.selectbox("Storage-Typ:", ["Lokal", "Netzlaufwerk", "Dropbox", "Google Drive"])
        base_path = st.text_input("Basis-Pfad:", value="./ablage")

        if st.button("💾 Auto-Ablage aktivieren"):
            auto_storage.enable(base_path, storage_type)
            st.success("✅ Auto-Ablage aktiviert")

        # Test
        if auto_storage.is_enabled():
            if st.button("🔌 Verbindung testen"):
                success, message = auto_storage.test_connection()
                if success:
                    st.success(message)
                else:
                    st.error(message)

with tab6:
    st.subheader("🔔 Benachrichtigungen & Kalender")

    notif_mgr = st.session_state.notification_manager
    cal_int = st.session_state.calendar_integration

    # Benachrichtigungen
    st.markdown("### 📧 Email-Benachrichtigungen")

    with st.expander("⚙️ Email konfigurieren"):
        col1, col2 = st.columns(2)

        with col1:
            smtp_server = st.text_input("SMTP-Server:", value="smtp.gmail.com", key="notif_smtp_server")
            smtp_port = st.number_input("SMTP-Port:", value=587, key="notif_smtp_port")
            smtp_user = st.text_input("Benutzername:", key="notif_smtp_user")

        with col2:
            smtp_pass = st.text_input("Passwort:", type="password", key="notif_smtp_pass")
            email_from = st.text_input("Absender-Email:", key="notif_email_from")
            recipients = st.text_input("Empfänger (kommagetrennt):", key="notif_recipients")

        if st.button("💾 Email-Benachrichtigungen konfigurieren"):
            recipient_list = [r.strip() for r in recipients.split(',')]
            notif_mgr.configure_email(smtp_server, smtp_port, smtp_user, smtp_pass, email_from, recipient_list)
            st.success("✅ Email-Benachrichtigungen konfiguriert")

        if notif_mgr.config.get('email_enabled'):
            if st.button("🔌 Email-Verbindung testen"):
                success, message = notif_mgr.test_email_connection()
                if success:
                    st.success(message)
                else:
                    st.error(message)

    # Kalender
    st.markdown("---")
    st.markdown("### 📅 Kalender-Integration")

    with st.expander("⚙️ Kalender konfigurieren"):
        cal_type = st.selectbox("Kalender-Typ:", ["Outlook/Exchange", "Google Calendar"])

        if cal_type == "Outlook/Exchange":
            client_id = st.text_input("Client ID:")
            client_secret = st.text_input("Client Secret:", type="password")
            tenant_id = st.text_input("Tenant ID:")

            if st.button("💾 Outlook konfigurieren"):
                cal_int.configure_outlook(client_id, client_secret, tenant_id)
                st.success("✅ Outlook konfiguriert")

        else:  # Google Calendar
            creds_path = st.text_input("Credentials JSON Pfad:")

            if st.button("💾 Google Calendar konfigurieren"):
                cal_int.configure_google(creds_path)
                st.success("✅ Google Calendar konfiguriert")

        if cal_int.is_enabled():
            if st.button("🔌 Kalender-Verbindung testen"):
                success, message = cal_int.test_connection()
                if success:
                    st.success(message)
                else:
                    st.error(message)

with tab7:
    st.subheader("⚙️ System & Backup")

    backup_mgr = st.session_state.backup_manager

    # Backup-Einstellungen
    st.markdown("### 💾 Backup-Verwaltung")

    col1, col2 = st.columns(2)

    with col1:
        backup_enabled = st.checkbox("Automatische Backups aktivieren", value=backup_mgr.is_enabled())

        if backup_enabled != backup_mgr.is_enabled():
            if backup_enabled:
                backup_mgr.enable()
                st.success("✅ Backups aktiviert")
            else:
                backup_mgr.disable()
                st.info("⏸️ Backups deaktiviert")

    with col2:
        if st.button("💾 Backup jetzt erstellen", type="primary"):
            with st.spinner("Erstelle Backup..."):
                backup_path = backup_mgr.create_backup()
                if backup_path:
                    st.success(f"✅ Backup erstellt: {backup_path.name}")
                else:
                    st.error("❌ Backup fehlgeschlagen")

    # Backup-Liste
    st.markdown("---")
    st.subheader("📦 Vorhandene Backups")

    backups = backup_mgr.list_backups()

    if backups:
        for backup in backups:
            with st.expander(f"📦 {backup['name']} ({backup['size_mb']:.1f} MB)"):
                st.write(f"**Erstellt:** {backup['created']}")
                st.write(f"**Alter:** {backup['age_days']} Tage")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("🔄 Wiederherstellen", key=f"restore_{backup['name']}"):
                        if backup_mgr.restore_backup(Path(backup['path'])):
                            st.success("✅ Wiederhergestellt")
                        else:
                            st.error("❌ Fehler")

                with col2:
                    if st.button("🗑️ Löschen", key=f"del_backup_{backup['name']}"):
                        if backup_mgr.delete_backup(backup['name']):
                            st.success("✅ Gelöscht")
                            st.rerun()
    else:
        st.info("Noch keine Backups vorhanden")

    # Statistiken
    st.markdown("---")
    st.subheader("📊 System-Statistiken")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Backups", backup_stats['total_backups'])

    with col2:
        storage_stats = dashboard_mgr.get_storage_stats()
        st.metric("Storage (MB)", f"{storage_stats['total_size_mb']:.1f}")

    with col3:
        st.metric("PDF-Dateien", storage_stats['pdf_count'])

# Info-Box
st.markdown("---")
with st.expander("ℹ️ Anleitung"):
    st.markdown("""
    ### So funktioniert die App:

    1. **API Key eingeben** (OpenAI, Claude oder Gemini)
    2. **Tagespost-PDF hochladen** (OCR-Version)
    3. **Aktenregister-Excel hochladen** (aktenregister.xlsx)
    4. **"Verarbeitung starten" klicken**
    5. **Batch-Modus nutzen** (optional):
       - **"Weitere Datei einlesen"** → Nächstes PDF-Paket hinzufügen
       - **"Postscan beenden"** → Alle Batches zu ZIP-Dateien packen
    6. **ZIP-Dateien herunterladen** (eine pro Sachbearbeiter)

    ### Batch-Processing (NEU):
    Sie können mehrere Post-Pakete nacheinander einscannen:
    - 1. PDF hochladen und verarbeiten
    - **"Weitere Datei einlesen"** klicken
    - 2. PDF hochladen und verarbeiten
    - Beliebig wiederholen...
    - **"Postscan beenden"** → Alle Dokumente werden zusammen gepackt

    ### Die App erstellt:
    - ZIP-Dateien pro Sachbearbeiter (SQ, TS, M, FÜ, CV, nicht-zugeordnet)
    - Einzelne PDFs mit erkannten Aktenzeichen im Dateinamen
    - Excel-Dateien mit Fristen und Metadaten
    - Gesamt-Excel mit allen Dokumenten

    ### Aktenzeichen-Erkennung:
    - Interne Kanzlei-Aktenzeichen (z.B. 151/25M, 1179/24TS)
    - "Ihr Zeichen" / "Unser Zeichen" - Felder haben höchste Priorität
    - Externe Aktenzeichen (Gerichte, Versicherungen)
    - Automatische Zuordnung über Aktenregister
    - **KI-gestütztes Lernen** aus manuellen Zuordnungen
    """)
