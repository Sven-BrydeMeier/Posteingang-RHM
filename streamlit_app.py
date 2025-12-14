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

# Versionsnummer: Zähler.JJ.MM.TT.HH.MM
VERSION = "5.25.12.13.02.00"  # Version 5, 13. Dezember 2025, Kanzleisoftware-Integration

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

st.title("📄 RHM | Automatisierter Posteingang")
st.caption(f"Version {VERSION}")
st.markdown("---")

# Initialisiere Persistent Storage
if 'storage' not in st.session_state:
    st.session_state.storage = PersistentStorage()

storage = st.session_state.storage

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

# Haupt-Upload-Bereich (responsive: 1 Spalte auf Mobile, 2 auf Desktop)
col1, col2 = st.columns([1, 1], gap="medium")

with col1:
    st.subheader("📄 Tagespost-PDF hochladen")
    uploaded_pdf = st.file_uploader(
        "PDF-Datei mit Tagespost (OCR)",
        type=["pdf"],
        help="Laden Sie die OCR-PDF-Datei mit der Tagespost hoch"
    )

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
    col_stats = st.columns(6)
    for idx, (sb, count) in enumerate(st.session_state.sachbearbeiter_stats_accumulated.items()):
        if count > 0:
            with col_stats[idx]:
                st.metric(sb, count, delta=None)

# Verarbeitungsbutton (Excel ist optional wenn gespeichert)
can_process = uploaded_pdf and current_api_key and (uploaded_excel or storage.has_aktenregister())
if st.button("🚀 Verarbeitung starten" if st.session_state.batch_count == 0 else "📄 Weiteren Batch verarbeiten",
             type="primary", disabled=not can_process):
    if not current_api_key:
        st.error(f"❌ Bitte geben Sie Ihren {api_provider} API-Key ein!")
    elif not uploaded_pdf:
        st.error("❌ Bitte laden Sie eine PDF-Datei hoch!")
    else:
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

                    if not st.checkbox("Trotzdem verarbeiten?", key="process_duplicate"):
                        st.stop()
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

                    if uploaded_excel:
                        # Neues Excel hochgeladen: Merge mit gespeichertem
                        import pandas as pd
                        new_df = pd.read_excel(BytesIO(uploaded_excel.read()), sheet_name='akten', header=1)

                        # Speichere und merge mit vorhandenem
                        merged_df = storage.save_aktenregister(new_df, merge=storage.has_aktenregister())
                        st.success(f"✅ Aktenregister aktualisiert: {len(merged_df)} Akten")

                        # Verwende gespeicherte Version
                        excel_path = storage.aktenregister_file
                    else:
                        # Verwende nur gespeichertes Register
                        excel_path = storage.aktenregister_file
                        df = storage.load_aktenregister()
                        st.info(f"📂 Verwende gespeichertes Register: {len(df)} Akten")

                    erkenner = AktenzeichenErkenner(excel_path)

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
                            analyse.get('stichworte', [])
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
                            debug_parts.append(f"AZ: {akt_info['internes_az']} ({az_quelle})")
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
                    st.success(f"✅ Batch #{st.session_state.batch_count} verarbeitet: {len(alle_daten)} Dokumente")
                    st.info(f"📊 **Gesamt akkumuliert**: {len(st.session_state.accumulated_documents)} Dokumente aus {st.session_state.batch_count} Batch(es)")

                    # Setze Flag dass Batch verarbeitet wurde (NICHT finale Verarbeitung)
                    st.session_state.batch_verarbeitet = True

                except Exception as e:
                    st.error(f"❌ Fehler bei der Verarbeitung: {str(e)}")
                    st.exception(e)

# Zeige Batch-Aktionen wenn Batch verarbeitet wurde
if st.session_state.get('batch_verarbeitet', False):
    st.markdown("---")
    st.subheader("📦 Nächster Schritt")

    col_btn1, col_btn2 = st.columns(2, gap="medium")

    with col_btn1:
        if st.button("📄 Weitere Datei einlesen und hinzufügen", type="secondary", use_container_width=True):
            # Lösche nur Upload-bezogene Session States, behalte akkumulierte Daten
            st.session_state.batch_verarbeitet = False
            # File uploader wird automatisch zurückgesetzt durch rerun
            st.rerun()

    with col_btn2:
        if st.button("📦 Postscan beenden und ZIP-Dateien erstellen", type="primary", use_container_width=True):
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

                        # Speichere Ergebnisse
                        st.session_state.verarbeitung_ergebnisse = {
                            'zip_dateien': dict(zip_dateien),
                            'gesamt_excel': bytes(gesamt_excel),
                            'sachbearbeiter_stats': dict(st.session_state.sachbearbeiter_stats_accumulated)
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

        # ZIP-Dateien - Responsive Layout (2 Spalten für bessere Mobile-UX)
        zip_liste = list(ergebnisse['zip_dateien'].items())

        # 2 Spalten statt 3 für bessere Mobile-Darstellung
        num_cols = 2
        cols = st.columns(num_cols, gap="small")

        for idx, (sb, zip_bytes) in enumerate(zip_liste):
            col_index = idx % num_cols
            with cols[col_index]:
                st.download_button(
                    label=f"📦 {sb}.zip",
                    data=zip_bytes,
                    file_name=f"{sb}.zip",
                    mime="application/zip",
                    key=f"download_zip_{sb}",
                    use_container_width=True,
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
            use_container_width=False
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
                                datum=datetime.now().strftime('%d.%m.%Y')
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

            # Filtere nicht-zugeordnete Dokumente
            nicht_zugeordnet = [d for d in alle_daten if d['sachbearbeiter'] == 'nicht-zugeordnet']

            if nicht_zugeordnet:
                st.warning(f"⚠️ {len(nicht_zugeordnet)} Dokument(e) konnten nicht automatisch zugeordnet werden.")
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
                                    erkenner = AktenzeichenErkenner(excel_path)
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

                        # Update Ergebnisse
                        st.session_state.verarbeitung_ergebnisse = {
                            'zip_dateien': dict(zip_dateien),
                            'gesamt_excel': bytes(gesamt_excel),
                            'sachbearbeiter_stats': dict(sachbearbeiter_stats_neu)
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
