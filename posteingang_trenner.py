# posteingang_trenner.py
# Upload: aktenregister.xlsx + Posteingang.pdf
# Output: getrennte PDFs (an "TRENNSEITE") + Dateinamen
#
# Aktenzeichen-Erkennung:
#   1) "Ihr Zeichen" (OCR-Varianten: thrZeichen, lhrZeichen)
#   2) "Gz.:" (Geschäftszeichen)
#   3) Fallback: Muster d{1,4}/d{2} die im Register existieren
#
# Dependencies:
#   pip install streamlit pandas pymupdf openpyxl

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import streamlit as st

import fitz  # PyMuPDF


# ----------------------------
# Helpers: Normalisierung
# ----------------------------
def _norm(s: str) -> str:
    """Normalize strings (remove whitespace + non-breaking spaces)."""
    if s is None:
        return ""
    return re.sub(r"\s+", "", str(s).replace("\xa0", "")).strip()


def _safe_filename(s: str, max_len: int = 140) -> str:
    """Create safe filename for Windows/Linux."""
    s = str(s).strip().replace("\n", " ")
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s or "unbenannt"


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
def load_aktenregister(xlsx_bytes: bytes) -> Tuple[pd.DataFrame, Set[str]]:
    """
    Load Aktenregister Excel.
    Returns DataFrame and set of normalized Akte numbers for quick lookup.
    """
    df = pd.read_excel(io.BytesIO(xlsx_bytes), dtype=str)
    df.columns = [str(c) for c in df.columns]

    # Flexible Spaltenzuordnung
    colmap = {re.sub(r"[^a-z0-9]+", "", str(c).lower()): c for c in df.columns}

    # Finde Akte-Spalte
    akte_col = None
    for key in ["akte", "aktenzeichen", "az"]:
        if key in colmap:
            akte_col = colmap[key]
            break

    if not akte_col:
        raise ValueError(f"Spalte 'Akte' nicht gefunden. Vorhanden: {list(df.columns)}")

    # Finde SB-Spalte
    sb_col = None
    for key in ["sb", "sachbearbeiter"]:
        if key in colmap:
            sb_col = colmap[key]
            break

    # Finde Kurzbez-Spalte
    kurzbez_col = None
    for key in ["kurzbez", "kurzbezeichnung", "bezeichnung", "bez"]:
        if key in colmap:
            kurzbez_col = colmap[key]
            break

    # Normalisiere
    df["akte_norm"] = df[akte_col].apply(_norm)
    df["Akte"] = df[akte_col]

    if sb_col:
        df["SB"] = df[sb_col].fillna("").astype(str).str.strip().str.upper()
    else:
        df["SB"] = ""

    if kurzbez_col:
        df["Kurzbez"] = df[kurzbez_col].fillna("").astype(str).str.strip()
    else:
        df["Kurzbez"] = ""

    # Entferne leere Zeilen
    df = df[df["akte_norm"].str.len() > 0].copy()

    # Set für schnelles Lookup
    reg_set = set(df["akte_norm"].dropna())

    return df, reg_set


# ----------------------------
# PDF Split: Trennseiten
# ----------------------------
def page_text(doc: fitz.Document, page_index: int) -> str:
    page = doc[page_index]
    return page.get_text("text") or ""


def is_trennseite(text: str) -> bool:
    if not text:
        return False
    t = re.sub(r"\s+", "", text).upper()
    return t == "TRENNSEITE"


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
    for p in pages:
        out.insert_pdf(doc, from_page=p, to_page=p)
    b = out.tobytes(deflate=True)
    out.close()
    return b


# ----------------------------
# AKTENZEICHEN-ERKENNUNG (robust, OCR-tolerant)
# ----------------------------
def detect_akte(text: str, reg_set: Set[str], df_reg: pd.DataFrame = None) -> Tuple[Optional[str], float, str, bool]:
    """
    Detect internal Akte (e.g. '1547/21') from OCR-ish page text.

    Strategy:
    1) Look for 'Ihr Zeichen' (OCR variants like 'thrZeichen') nearby
    2) Look for 'Gz.:' (often appears in judgments)
    3) Fallback: take all occurrences of d{1,4}/d{2} and pick one that exists in register
    4) Alternative Format: 1079-25 (mit Bindestrich)
    5) Mandanten-Suche im Text

    Returns: (akte_norm, confidence, reason, unsicher)
    """
    if not text:
        return None, 0.0, "no_text", False

    # Remove whitespace to survive OCR that loses spacing
    t_no_ws = re.sub(r"\s+", "", text.replace("\xa0", " "))

    # 1) Ihr Zeichen (OCR variations: Ihr / thr / lhr => *hrZeichen)
    m = re.search(r"[A-Za-z]?hrZeichen[^0-9]{0,60}([0-9]{1,4}/[0-9]{2})", t_no_ws, flags=re.IGNORECASE)
    if m:
        akte_norm = _norm(m.group(1))
        if akte_norm in reg_set:
            return akte_norm, 0.95, "context:hrZeichen", False
        return akte_norm, 0.70, "context:hrZeichen_not_in_register", False

    # 2) Gz.: (Geschäftszeichen der Kanzlei im Urteil/Schriftsatz)
    m = re.search(r"Gz\.?:[^0-9]{0,20}([0-9]{1,4}/[0-9]{2})", t_no_ws, flags=re.IGNORECASE)
    if m:
        akte_norm = _norm(m.group(1))
        if akte_norm in reg_set:
            return akte_norm, 0.95, "context:Gz", False
        return akte_norm, 0.70, "context:Gz_not_in_register", False

    # 3) Fallback: all patterns like 1547/21
    candidates = re.findall(r"(?<!\d)(\d{1,4}/\d{2})", t_no_ws)
    candidates_norm = [_norm(c) for c in candidates]
    candidates_in = [c for c in candidates_norm if c in reg_set]

    if len(set(candidates_in)) == 1:
        return candidates_in[0], 0.80, "fallback:unique_in_register", False

    if len(candidates_in) > 1:
        # Nimm das erste im Text vorkommende
        earliest = min(set(candidates_in), key=lambda c: t_no_ws.find(c))
        return earliest, 0.60, f"fallback:multiple_in_register({sorted(set(candidates_in))[:5]})", False

    if candidates_norm:
        return candidates_norm[0], 0.40, "fallback:pattern_not_in_register", False

    # 4) Alternative AZ-Formate: 1079-25 (mit Bindestrich statt Schrägstrich)
    alt_candidates = re.findall(r"(?<!\d)(\d{1,4})-(\d{2})(?!\d)", t_no_ws)
    for num, year in alt_candidates:
        # Konvertiere zu Standard-Format
        stamm_alt = f"{num}/{year}"
        if stamm_alt in reg_set:
            return stamm_alt, 0.50, "alt_format:bindestrich", True  # unsicher=True

    # 5) Mandanten-Suche: Suche Mandantennamen im Text
    if df_reg is not None and not df_reg.empty:
        mandant_result = _suche_mandant_im_text(text, df_reg)
        if mandant_result:
            return mandant_result, 0.35, "mandant_match", True  # unsicher=True

    return None, 0.0, "no_match", False


def _suche_mandant_im_text(text: str, df_reg: pd.DataFrame) -> Optional[str]:
    """
    Sucht Mandantennamen im Text und vergleicht mit dem Aktenregister.
    Letzte Fallback-Methode.
    """
    # Mögliche Spalten für Mandanten/Kurzbezeichnung
    mandant_spalten = ['Mandant', 'Kurzbez', 'Kurzbezeichnung']

    text_lower = text.lower()

    # Kanzlei-Namen ausschließen
    ausschluss = {
        'meier', 'meyer', 'radtke', 'heigener', 'marquardsen', 'ostertun',
        'vollbrecht', 'fürsen', 'goeser', 'herberg', 'rückborn', 'akkoc',
        'tönjes', 'litzenroth', 'hingst', 'kaya', 'stöcken'
    }

    for spalte in mandant_spalten:
        if spalte not in df_reg.columns:
            continue

        for idx, row in df_reg.iterrows():
            wert = row.get(spalte)
            if pd.isna(wert) or not str(wert).strip():
                continue

            mandant = str(wert).strip()

            # Extrahiere einzelne Namen aus der Kurzbezeichnung
            # Format oft: "Müller ./. Schmidt" oder "Firma GmbH"
            namen = re.split(r'\s*[./]+\s*|\s+', mandant)
            namen = [n.strip() for n in namen if len(n.strip()) >= 4]

            for name in namen:
                name_lower = name.lower()

                # Überspringe ausgeschlossene Namen
                if name_lower in ausschluss:
                    continue

                # Suche Name im Text (als ganzes Wort)
                if re.search(rf'\b{re.escape(name_lower)}\b', text_lower):
                    akte = row.get('Akte')
                    if pd.notna(akte) and str(akte).strip():
                        return _norm(str(akte))

    return None


def lookup_akte(df_reg: pd.DataFrame, akte_norm: str) -> Optional[Dict]:
    """Lookup Akte in register, return row as dict or None."""
    if not akte_norm:
        return None
    hit = df_reg[df_reg["akte_norm"] == akte_norm]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


# ----------------------------
# Datum / Absender Extraktion
# ----------------------------
DATE_RULES = [
    r"\bVerk[üu]ndet\s+am\s+(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\bBeschlossen\s+am\s+(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\bAufgenommen\s+am\s+(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\bDatum\s*[:\-]?\s*(\d{1,2}\.\d{1,2}\.\d{4})\b",
    r"\bvom\s+(\d{1,2}\.\d{1,2}\.\d{4})\b",
]
GENERIC_DATE = r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b"


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

    # Kanzlei-Zeilen ausschließen
    kanzlei_indicators = [
        'radtke', 'heigener', 'rhm',
        'sehr geehrte', 'mit freundlichen', 'mit kollegialen', 'hochachtungsvoll',
    ]

    def ist_kanzlei_zeile(line: str) -> bool:
        line_l = line.lower()
        return any(ind in line_l for ind in kanzlei_indicators)

    head_filtered = [ln for ln in head if not ist_kanzlei_zeile(ln)]

    court_keywords = [
        "Bundesgerichtshof", "Oberlandesgericht", "Landgericht", "Amtsgericht",
        "Arbeitsgericht", "Sozialgericht", "Verwaltungsgericht", "Finanzgericht",
        "Staatsanwaltschaft", "Kreis", "Stadt", "Gemeinde", "Jobcenter", "Agentur für Arbeit",
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


# ----------------------------
# Dokument-Vorschläge erstellen
# ----------------------------
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
    confidence: float
    reason: str


def build_proposals(doc: fitz.Document, chunks: List[List[int]], df_reg: pd.DataFrame, reg_set: Set[str]) -> Tuple[List[Proposed], List[bytes]]:
    proposals: List[Proposed] = []
    chunk_pdfs: List[bytes] = []

    for i, pages in enumerate(chunks, start=1):
        t = extract_chunk_text(doc, pages, max_pages=3)

        # AKTENZEICHEN-ERKENNUNG (neue robuste Methode)
        akte_norm, confidence, reason, unsicher = detect_akte(t, reg_set, df_reg)

        dt = extract_date(t)
        sender = extract_sender(t)
        kurz2 = two_word_kurzbez_from_content(t)

        # Lookup im Register
        info = lookup_akte(df_reg, akte_norm) if akte_norm else None

        if info:
            akte_out = str(info.get("Akte", akte_norm)).strip()
            sb_out = str(info.get("SB", "")).strip()
            kb_out = str(info.get("Kurzbez", "")).strip()
        else:
            akte_out = akte_norm if akte_norm else "Unbekannt"
            sb_out = ""
            kb_out = ""

        # Bei unsicherer Erkennung (Bindestrich-Format oder Mandanten-Match) -> "?" anhängen
        if unsicher and akte_out and akte_out != "Unbekannt":
            akte_out = akte_out + "?"

        date_iso = _date_to_iso(dt) if dt else "Unbekanntes-Datum"

        # Dateiname zusammenbauen
        if kb_out:
            base = f"{akte_out}-{sb_out}-{kb_out}" if sb_out else f"{akte_out}-{kb_out}"
        elif sb_out:
            base = f"{akte_out}-{sb_out}"
        else:
            base = akte_out

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
                confidence=confidence,
                reason=reason,
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
                "Confidence": f"{p.confidence:.0%}",
                "Erkennung": p.reason,
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
    st.markdown("### Aktenzeichen-Erkennung")
    st.markdown("""
    **Strategie (Priorität):**
    1. `Ihr Zeichen: 1547/21...` (OCR-tolerant)
    2. `Gz.: 1547/21` (Geschäftszeichen)
    3. Fallback: Muster `dddd/dd` im Register

    **Keine** Erkennung über Kurzbezeichnungen!
    """)

if not reg_file or not pdf_file:
    st.info("Bitte Aktenregister.xlsx und Posteingang.pdf hochladen.")
    st.stop()

try:
    df_reg, reg_set = load_aktenregister(reg_file.getvalue())
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

props, chunk_pdfs = build_proposals(doc, chunks, df_reg, reg_set)
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
        "Confidence": st.column_config.TextColumn(disabled=True),
        "Erkennung": st.column_config.TextColumn(disabled=True),
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
        parts = [r['Akte']]
        if r['SB']:
            parts.append(r['SB'])
        if r['Kurzbez (Register)']:
            parts.append(r['Kurzbez (Register)'])
        base = "-".join(parts)
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
