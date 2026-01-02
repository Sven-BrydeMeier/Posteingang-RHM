# posteingang_trenner.py
# Upload: aktenregister.xlsx + Posteingang.pdf
# Output: getrennte PDFs (an "TRENNSEITE") + Dateinamen nach:
#   Akte-SB-Kurzbez__<2-Wort-Kurzbez aus Inhalt>__<Absender>__<Datum>.pdf
#
# Aktenzeichen-Format Kanzlei: 739/25SQ08TÖ
#   AZ=739/25, SB=SQ, Bereich=08 (optional), ReNo=TÖ (optional)
#
# Dependencies:
#   pip install streamlit pandas pymupdf openpyxl
# Optional OCR fallback (falls gescannt):
#   pip install pytesseract pillow  (und tesseract-ocr OS-Paket)

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st

import fitz  # PyMuPDF


# ----------------------------
# Ausgeschlossene Begriffe (Kanzlei-Namen, Mitarbeiter)
# Diese dürfen NICHT für Akten-Matching verwendet werden
# ----------------------------
AUSGESCHLOSSENE_BEGRIFFE = {
    # Kanzleiname und Varianten
    'radtke, heigener und meier',
    'radtke heigener und meier',
    'radtke heigener meier',
    'radtke, heigener & meier',
    'rhm',
    'rhm kanzlei',
    'rhm-kanzlei',

    # Kanzlei-Mitarbeiter Nachnamen (einzeln)
    'meier',           # Sven-Bryde Meier
    'meyer',           # Tamara Meyer
    'marquardsen',     # Ann-Kathrin Marquardsen
    'ostertun',        # Christian Ostertun
    'osterthun',       # Schreibvariante
    'vollbrecht',      # Christian Vollbrecht
    'fürsen',          # Dr. Ernst Joachim Fürsen
    'fuersen',
    'fuersten',
    'goeser',
    'göser',
    'herberg',
    'rückborn',
    'rueckborn',
    'akkoc',
    'tönjes',
    'toenjes',
    'litzenroth',
    'hingst',
    'kaya',
    'stöcken',
    'stoecken',
    'radtke',
    'heigener',

    # Volle Namen der Kanzlei-Mitarbeiter
    'sven-bryde meier',
    'sven bryde meier',
    'tamara meyer',
    'ann-kathrin marquardsen',
    'christian ostertun',
    'christian vollbrecht',
    'ernst joachim fürsen',
    'dr. fürsen',
    'dr fürsen',
    'korinna rückborn',

    # Typische Anrede-/Grußformel-Wörter
    'kollege',
    'kollegin',
    'rechtsanwalt',
    'rechtsanwältin',
    'notar',
}


def _ist_ausgeschlossener_begriff(text: str) -> bool:
    """
    Prüft ob ein Text einen ausgeschlossenen Begriff enthält.
    Wird verwendet um falsche Akten-Matches zu vermeiden.
    """
    if not text:
        return False
    text_lower = text.lower().strip()

    # Exakter Match
    if text_lower in AUSGESCHLOSSENE_BEGRIFFE:
        return True

    # Prüfe ob ein ausgeschlossener Begriff im Text enthalten ist
    for begriff in AUSGESCHLOSSENE_BEGRIFFE:
        if len(begriff) >= 4:  # Nur längere Begriffe für Teilmatch
            if re.search(rf'\b{re.escape(begriff)}\b', text_lower):
                return True

    return False


# ----------------------------
# Helpers: Normalisierung
# ----------------------------
def _norm_col(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _safe_filename(s: str, max_len: int = 160) -> str:
    s = str(s).strip().replace("\n", " ")
    # Windows-unfreundliche Zeichen
    s = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def _date_to_iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def _parse_date(dstr: str) -> Optional[datetime]:
    m = re.match(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*$", dstr)
    if not m:
        return None
    day, month, year = map(int, m.groups())
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


# ----------------------------
# Aktenregister laden
# ----------------------------
def load_aktenregister(xlsx_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(xlsx_bytes), dtype=str)
    df.columns = [str(c) for c in df.columns]

    # flexible Spaltenzuordnung
    colmap = {_norm_col(c): c for c in df.columns}
    required = {"akte": None, "sb": None, "kurzbez": None}

    for k in list(required.keys()):
        if k in colmap:
            required[k] = colmap[k]
        else:
            for nc, orig in colmap.items():
                if k in nc:
                    required[k] = orig
                    break

    missing = [k for k, v in required.items() if v is None]
    if missing:
        raise ValueError(
            f"Aktenregister: Spalten nicht gefunden: {missing}. "
            f"Gefunden: {list(df.columns)}. Erwartet mindestens: Akte, SB, Kurzbez."
        )

    df = df.rename(columns={required["akte"]: "Akte", required["sb"]: "SB", required["kurzbez"]: "Kurzbez"})
    df["Akte"] = df["Akte"].astype(str).str.strip()
    df["SB"] = df["SB"].astype(str).str.strip()
    df["Kurzbez"] = df["Kurzbez"].astype(str).str.strip()
    df = df.dropna(subset=["Akte"]).copy()
    df = df[df["Akte"].str.len() > 0].copy()

    # Normalisierte Hilfsspalten für Matching
    df["Akte_norm"] = df["Akte"].str.lower()
    df["SB_norm"] = df["SB"].str.upper()

    return df


# ----------------------------
# PDF Split: Trennseiten
# ----------------------------
def page_text(doc: fitz.Document, page_index: int) -> str:
    page = doc[page_index]
    return page.get_text("text") or ""


def is_trennseite(text: str) -> bool:
    return bool(re.search(r"\btrennseite\b", text, flags=re.IGNORECASE))


def split_pdf_by_trennseite(pdf_bytes: bytes) -> Tuple[fitz.Document, List[List[int]]]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chunks: List[List[int]] = []
    cur: List[int] = []

    for i in range(len(doc)):
        t = page_text(doc, i)
        if is_trennseite(t):
            if cur:
                chunks.append(cur)
                cur = []
            continue  # Trennseite selbst nicht übernehmen
        cur.append(i)

    if cur:
        chunks.append(cur)

    return doc, chunks


def extract_chunk_text(doc: fitz.Document, pages: List[int], max_pages: int = 3) -> str:
    out = []
    for i in pages[:max_pages]:
        out.append(page_text(doc, i))
    return "\n".join(out)


def write_chunk_pdf(doc: fitz.Document, pages: List[int]) -> bytes:
    out = fitz.open()
    out.insert_pdf(doc, from_page=min(pages), to_page=max(pages), pages=pages)
    b = out.tobytes(deflate=True)
    out.close()
    return b


# ----------------------------
# Extraktion: Kanzlei-Aktenzeichen / Absender / Datum / Kurzbez (2 Wörter)
# ----------------------------

# Kanzlei-Aktenzeichen: 739/25SQ08TÖ
# Gruppe 1 = AZ (739/25), Gruppe 2 = SB (SQ), Gruppe 3 = Bereich (optional), Gruppe 4 = ReNo (optional)
KANZLEI_AZ_RE = re.compile(
    r"\b([0-9]{1,6}/[0-9]{2})\s*([A-ZÄÖÜ]{1,3})\s*([0-9]{2})?\s*([A-ZÄÖÜ]{1,3})?\b"
)

# Wenn ein Label davor steht (Gz./Az./Aktenzeichen), matchen wir gern "kompakt"
KANZLEI_AZ_COMPACT_RE = re.compile(
    r"(?:\bGz\.?\b|\bAz\.?\b|\bAktenzeichen\b)\s*[:\-]?\s*([0-9]{1,6}/[0-9]{2}[A-ZÄÖÜ]{1,3}[0-9]{0,2}[A-ZÄÖÜ]{0,3})",
    flags=re.IGNORECASE,
)

DATE_RULES = [
    r"\bVerk[üu]ndet\s+am\s+(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\bBeschlossen\s+am\s+(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\bAufgenommen\s+am\s+(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\bDatum\s*[:\-]?\s*(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\bvom\s+(\d{1,2}\.\d{1,2}\.\d{4})\b",
]
GENERIC_DATE = r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b"


def extract_az_sb(text: str) -> Tuple[Optional[str], Optional[str]]:
    # 1) Mit Label (Gz/Az/Aktenzeichen)
    m0 = KANZLEI_AZ_COMPACT_RE.search(text)
    if m0:
        raw = m0.group(1)
        m = KANZLEI_AZ_RE.search(raw)
        if m:
            return m.group(1), m.group(2)

    # 2) Fallback: irgendwo im Text
    m = KANZLEI_AZ_RE.search(text)
    if m:
        return m.group(1), m.group(2)

    return None, None


def extract_date(text: str) -> Optional[datetime]:
    for pat in DATE_RULES:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            d = _parse_date(m.group(1))
            if d:
                return d
    m = re.search(GENERIC_DATE, text)
    if m:
        return _parse_date(m.group(1))
    return None


def extract_sender(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    head = lines[:12]

    # Kanzlei-Zeilen ausschließen (eigene Adresse, Anrede etc.)
    kanzlei_indicators = [
        'radtke',
        'heigener',
        'rhm',
        'sehr geehrte',
        'mit freundlichen',
        'mit kollegialen',
        'hochachtungsvoll',
    ]

    def ist_kanzlei_zeile(line: str) -> bool:
        line_l = line.lower()
        return any(ind in line_l for ind in kanzlei_indicators)

    # Filtere Kanzlei-Zeilen aus
    head_filtered = [ln for ln in head if not ist_kanzlei_zeile(ln)]

    court_keywords = [
        "Bundesgerichtshof",
        "Oberlandesgericht",
        "Landgericht",
        "Amtsgericht",
        "Arbeitsgericht",
        "Sozialgericht",
        "Verwaltungsgericht",
        "Finanzgericht",
        "Staatsanwaltschaft",
        "Kreis",
        "Stadt",
        "Gemeinde",
        "Jobcenter",
        "Agentur für Arbeit",
    ]

    for ln in head_filtered:
        for kw in court_keywords:
            if kw.lower() in ln.lower():
                return " ".join(ln.split()[:4])

    if head_filtered:
        return " ".join(head_filtered[0].split()[:4])

    return "Unbekannt"


def two_word_kurzbez_from_content(text: str) -> str:
    rules = [
        (r"\bvers[äa]umnisurteil\b", "Versäumnisurteil"),
        (r"\burteil\b", "Urteil"),
        (r"\bkostenfestsetz", "Kostenfestsetzung"),
        (r"\bbeschluss\b", "Beschluss"),
        (r"\bmahnung\b", "Mahnung"),
        (r"\bklage\b", "Klage"),
        (r"\bk[üu]ndigung\b", "Kündigung"),
        (r"\bvollmacht\b", "Vollmacht"),
        (r"\btestament\b", "Testament"),
        (r"\bnachlass\b", "Nachlass"),
        (r"\brechnung\b", "Rechnung"),
        (r"\bzahlungsaufforder", "Zahlungsaufforderung"),
    ]
    t = text.lower()
    hits: List[str] = []
    for pat, label in rules:
        if re.search(pat, t):
            hits.append(label)
        if len(hits) >= 2:
            break

    if not hits:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for ln in lines[:20]:
            if len(ln) < 6:
                continue
            w = re.findall(r"[A-Za-zÄÖÜäöüß\-]+", ln)
            w = [x for x in w if len(x) > 2]
            if len(w) >= 2:
                hits = [w[0], w[1]]
                break
        if not hits:
            hits = ["Dokument"]

    return " ".join(hits[:2])


def match_register_row(df_reg: pd.DataFrame, az: Optional[str], sb: Optional[str], text: str) -> Optional[pd.Series]:
    if az:
        m = df_reg[df_reg["Akte_norm"] == az.strip().lower()]
        if sb:
            m2 = m[m["SB_norm"] == sb.strip().upper()]
            if len(m2) >= 1:
                return m2.iloc[0]
        if len(m) >= 1:
            return m.iloc[0]

    # Bereinige Text von Kanzlei-Adressen für Kurzbez-Matching
    # Entferne typische Kanzlei-Adresszeilen um falsche Matches zu vermeiden
    text_bereinigt = text
    kanzlei_patterns = [
        r'Radtke,?\s*Heigener\s+und\s+Meier[^\n]*',
        r'Radtke,?\s*Heigener\s*&\s*Meier[^\n]*',
        r'RHM[- ]?Kanzlei[^\n]*',
        r'(?:Rechtsanwalt|RA|Notar)[^\n]*(?:Meier|Meyer|Marquardsen|Ostertun|Vollbrecht)[^\n]*',
        r'Sehr\s+geehrte[r]?\s+(?:Herr|Frau)\s+(?:Kollege?|Kollegin)?[^\n]*(?:Meier|Meyer)[^\n]*',
        r'Mit\s+(?:freundlichen|kollegialen)\s+Grüßen[^\n]*',
    ]
    for pat in kanzlei_patterns:
        text_bereinigt = re.sub(pat, '', text_bereinigt, flags=re.IGNORECASE)

    # fallback: Kurzbez im Text finden (schwach, aber mit Ausschluss-Prüfung)
    text_l = text_bereinigt.lower()
    df2 = df_reg.copy()
    df2["kb_len"] = df2["Kurzbez"].fillna("").astype(str).str.len()
    df2 = df2.sort_values("kb_len", ascending=False)
    for _, row in df2.head(50).iterrows():
        kb = str(row["Kurzbez"]).strip()
        if not kb:
            continue

        # WICHTIG: Überspringe Kurzbez, die ausgeschlossene Begriffe sind
        # (z.B. wenn Kurzbez "Meier" ist und "Meier" in der Kanzlei-Adresse steht)
        if _ist_ausgeschlossener_begriff(kb):
            continue

        # Prüfe auch einzelne Wörter der Kurzbezeichnung
        kb_words = kb.lower().split()
        if any(word in AUSGESCHLOSSENE_BEGRIFFE for word in kb_words if len(word) >= 4):
            continue

        if kb.lower() in text_l:
            return row

    return None


@dataclass
class Proposed:
    idx: int
    akte: str
    sb: str
    kurzbez_register: str
    kurzbez_content_2w: str
    sender: str
    date_iso: str
    filename: str
    pages: str


def build_proposals(doc: fitz.Document, chunks: List[List[int]], df_reg: pd.DataFrame) -> Tuple[List[Proposed], List[bytes]]:
    proposals: List[Proposed] = []
    chunk_pdfs: List[bytes] = []

    for i, pages in enumerate(chunks, start=1):
        t = extract_chunk_text(doc, pages, max_pages=3)

        az, sb_found = extract_az_sb(t)
        dt = extract_date(t)
        sender = extract_sender(t)
        kurz2 = two_word_kurzbez_from_content(t)

        row = match_register_row(df_reg, az, sb_found, t)

        if row is not None:
            akte_out = str(row["Akte"]).strip()
            sb_out = str(row["SB"]).strip()
            kb_out = str(row["Kurzbez"]).strip()
        else:
            akte_out = az.strip() if az else "Unbekannt"
            sb_out = sb_found.strip() if sb_found else "Unbekannt"
            kb_out = "Unbekannt"

        date_iso = _date_to_iso(dt) if dt else "Unbekanntes-Datum"

        base = f"{akte_out}-{sb_out}-{kb_out}"
        fname = f"{base}__{kurz2}__{sender}__{date_iso}.pdf"
        fname = _safe_filename(fname)

        pdf_bytes = write_chunk_pdf(doc, pages)

        proposals.append(
            Proposed(
                idx=i,
                akte=akte_out,
                sb=sb_out,
                kurzbez_register=kb_out,
                kurzbez_content_2w=kurz2,
                sender=sender,
                date_iso=date_iso,
                filename=fname,
                pages=f"{pages[0]+1}-{pages[-1]+1}",
            )
        )
        chunk_pdfs.append(pdf_bytes)

    return proposals, chunk_pdfs


def proposals_to_df(props: List[Proposed]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Dok#": p.idx,
                "Seiten": p.pages,
                "Akte": p.akte,
                "SB": p.sb,
                "Kurzbez (Register)": p.kurzbez_register,
                "Kurzbez (Inhalt, 2W)": p.kurzbez_content_2w,
                "Absender": p.sender,
                "Datum (ISO)": p.date_iso,
                "Dateiname": p.filename,
            }
            for p in props
        ]
    )


def build_zip(df_final: pd.DataFrame, chunk_pdfs: List[bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("summary.csv", df_final.to_csv(index=False).encode("utf-8-sig"))
        for i, pdf_b in enumerate(chunk_pdfs):
            fname = str(df_final.loc[i, "Dateiname"])
            if not fname.lower().endswith(".pdf"):
                fname = f"{fname}.pdf"
            z.writestr(fname, pdf_b)
    return buf.getvalue()


# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="Posteingang trennen & benennen", layout="wide")
st.title("Posteingang trennen & benennen (TRENNSEITE)")

with st.sidebar:
    st.markdown("### Upload")
    reg_file = st.file_uploader("Aktenregister (.xlsx)", type=["xlsx"])
    pdf_file = st.file_uploader("Posteingang (.pdf)", type=["pdf"])

    st.markdown("---")
    st.markdown("### Hinweise")
    st.markdown("- Trennung erfolgt an Seiten mit **TRENNSEITE** (Trennseiten werden entfernt).")
    st.markdown("- Dateinamen werden vorgeschlagen und können unten bearbeitet werden.")
    st.markdown("- Keine Secrets/API-Keys in Code/Logs eintragen (nutze `st.secrets`).")

if not reg_file or not pdf_file:
    st.info("Bitte Aktenregister.xlsx und Posteingang.pdf hochladen.")
    st.stop()

try:
    df_reg = load_aktenregister(reg_file.getvalue())
except Exception as e:
    st.error("Aktenregister konnte nicht geladen werden.")
    st.exception(e)
    st.stop()

pdf_bytes = pdf_file.getvalue()

try:
    doc, chunks = split_pdf_by_trennseite(pdf_bytes)
except Exception as e:
    st.error("PDF konnte nicht geöffnet/analysiert werden.")
    st.exception(e)
    st.stop()

if not chunks:
    st.warning("Keine Dokumente gefunden (evtl. nur Trennseiten?).")
    st.stop()

st.success(f"Gefunden: {len(chunks)} Dokument(e) nach Trennung an 'TRENNSEITE'.")

props, chunk_pdfs = build_proposals(doc, chunks, df_reg)
df_props = proposals_to_df(props)

st.markdown("## Vorschläge (bearbeitbar)")
st.caption("Du kannst Absender/Datum/Kurzbez/Dateiname überschreiben, bevor du exportierst.")
edited = st.data_editor(
    df_props,
    use_container_width=True,
    num_rows="fixed",
    hide_index=True,
    column_config={
        "Dok#": st.column_config.NumberColumn(disabled=True),
        "Seiten": st.column_config.TextColumn(disabled=True),
    },
)

st.markdown("### Export")
col1, col2 = st.columns([1, 2], vertical_alignment="center")

with col1:
    auto_rebuild = st.checkbox("Dateiname aus Feldern neu zusammensetzen", value=False)

df_final = edited.copy()
if auto_rebuild:
    new_names = []
    for _, r in df_final.iterrows():
        base = f"{r['Akte']}-{r['SB']}-{r['Kurzbez (Register)']}"
        fname = f"{base}__{r['Kurzbez (Inhalt, 2W)']}__{r['Absender']}__{r['Datum (ISO)']}.pdf"
        new_names.append(_safe_filename(fname))
    df_final["Dateiname"] = new_names

zip_bytes = build_zip(df_final, chunk_pdfs)

with col2:
    st.download_button(
        label="ZIP herunterladen (getrennte PDFs + summary.csv)",
        data=zip_bytes,
        file_name="posteingang_getrennt_und_benannt.zip",
        mime="application/zip",
    )

doc.close()
