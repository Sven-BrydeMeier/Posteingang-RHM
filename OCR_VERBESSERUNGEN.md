# 🔍 OCR-Verbesserungen für Aktenzeichen-Erkennung

## ❌ Das Problem

Die Aktenzeichen-Erkennung funktionierte **schlecht bei OCR-Texten** aus gescannten PDFs:

### Erkennungsrate VORHER: **54,5%** ❌

Typische OCR-Fehler, die NICHT erkannt wurden:
- ❌ `"Ihr Zeichen: 111 / 24"` → Leerzeichen um Schrägstrich
- ❌ `"Ihr Zeichen: 111I24"` → "I" statt "/"
- ❌ `"Ihr Zeichen: 111l24"` → "l" (kleines L) statt "/"
- ❌ `"Ihr Zeichen: 1 11/24"` → Leerzeichen in der Zahl
- ❌ `"Ihr Zeichen: 111/24 SQ"` → Leerzeichen vor Kürzel

### Warum passiert das?

**PyMuPDF (fitz)** extrahiert nur eingebetteten Text aus PDFs:
- Bei **gescannten Dokumenten** ohne vorheriges OCR: **Kein Text**
- Bei **extern OCR-verarbeiteten PDFs**: Schlechte Qualität durch:
  - Falsche Zeichenerkennung ("/" wird zu "I", "l", "\")
  - Fehlerhafte Leerzeichen-Einfügung
  - Zeilenumbrüche an falschen Stellen

---

## ✅ Die Lösung

### 1. **OCR-Normalisierungsfunktion**

Neue Funktion: `_normalisiere_ocr_text()` in `aktenzeichen_erkennung.py`

```python
def _normalisiere_ocr_text(self, text: str) -> str:
    """
    Normalisiert OCR-Text für bessere Aktenzeichen-Erkennung.

    Behebt:
    - Leerzeichen um Schrägstrich: "111 / 24" → "111/24"
    - Leerzeichen in Zahlen: "1 11/24" → "111/24"
    - Schrägstrich-Verwechslungen: "111I24" → "111/24"
    - Leerzeichen vor Kürzeln: "111/24 SQ" → "111/24SQ"
    """
```

**Wie es funktioniert:**
1. **Pattern-basierte Erkennung**: Findet Aktenzeichen-Muster trotz OCR-Fehler
2. **Intelligente Bereinigung**: Entfernt nur relevante Leerzeichen
3. **Schrägstrich-Normalisierung**: Ersetzt I, l, L, \ durch /

### 2. **Erweiterte Keyword-Erkennung**

Neue OCR-tolerante Keywords in `ZEICHEN_KEYWORDS`:
```python
# OCR-Varianten (häufige Verwechslungen)
'lhr zeichen',      # I statt h
'lz',               # I statt h in iZ
'ihr ze ichen',     # Leerzeichen im Wort
```

### 3. **Integration in alle Suchmethoden**

Die Normalisierung wird **automatisch** angewendet in:
- ✅ `_suche_in_zeichen_feldern()` - Suche bei "Ihr Zeichen" etc.
- ✅ `_suche_vollmuster()` - Vollmuster-Suche
- ✅ `_suche_stamm_mit_register()` - Register-basierte Suche

---

## 📊 Verbesserung

### Erkennungsrate jetzt deutlich höher! ✅

**Beispiele - VORHER vs. NACHHER:**

| OCR-Text | VORHER | NACHHER |
|----------|--------|---------|
| `"Ihr Zeichen: 111 / 24"` | ❌ Nicht erkannt | ✅ **111/24** |
| `"Ihr Zeichen: 111I24"` | ❌ Nicht erkannt | ✅ **111/24** |
| `"Ihr Zeichen: 111l24"` | ❌ Nicht erkannt | ✅ **111/24** |
| `"Ihr Zeichen: 1 11/24"` | ❌ Nicht erkannt | ✅ **111/24** |
| `"iZ: 111/24 SQ"` | ❌ Nicht erkannt | ✅ **111/24SQ** |
| `"111\\24"` | ❌ Nicht erkannt | ✅ **111/24** |
| `"lhr Zeichen: 111/24"` | ❌ Nicht erkannt | ✅ **111/24** |
| `"1 2 3 / 2 5"` | ❌ Nicht erkannt | ✅ **123/25** |

---

## 🔧 Test-Tools

### 1. **OCR-Fehler-Analyse** (`ocr_test_analysis.py`)

Zeigt welche OCR-Probleme mit aktuellen Patterns erkannt werden:
```bash
python ocr_test_analysis.py
```

**Output:**
- Kategorisierte OCR-Fehler-Beispiele
- Erkennungsrate pro Kategorie
- Empfohlene Fixes mit Priorität (⭐⭐⭐⭐⭐)

### 2. **OCR-Verbesserungs-Test** (`test_ocr_improvements.py`)

Testet die Normalisierungsfunktion:
```bash
python test_ocr_improvements.py
```

**Output:**
- Unit-Tests für alle OCR-Fehlertypen
- Pattern-Matching-Tests
- Vorher/Nachher-Vergleich

---

## 🎯 Behobene OCR-Probleme

### ✅ **Problem 1: Leerzeichen um Schrägstrich** (⭐⭐⭐⭐⭐ sehr häufig)
- **Beispiel:** `"111 / 24"`, `"111 /24"`, `"111/ 24"`
- **Lösung:** Pattern erkennt Aktenzeichen mit optionalen Leerzeichen
- **Ergebnis:** `"111/24"`

### ✅ **Problem 2: Schrägstrich-Verwechslungen** (⭐⭐⭐ häufig)
- **Beispiel:** `"111I24"`, `"111l24"`, `"111\\24"`
- **Lösung:** Separator-Pattern `[/IlL\\]` akzeptiert alle Varianten
- **Ergebnis:** `"111/24"`

### ✅ **Problem 3: Leerzeichen in Zahlen** (⭐⭐⭐⭐ häufig)
- **Beispiel:** `"1 11/24"`, `"1 2 3/25"`
- **Lösung:** Zahlengruppen `[\d\s]{1,7}` erfassen Ziffern mit Spaces
- **Ergebnis:** `"111/24"`, `"123/25"`

### ✅ **Problem 4: Leerzeichen vor Kürzeln** (⭐⭐⭐⭐ häufig)
- **Beispiel:** `"111/24 SQ"`, `"123/25 M"`
- **Lösung:** Pattern berücksichtigt optionale Spaces vor Kürzel
- **Ergebnis:** `"111/24SQ"`, `"123/25M"`

### ✅ **Problem 5: Keyword-Variationen** (⭐⭐ gelegentlich)
- **Beispiel:** `"lhr Zeichen"`, `"lZ"` (h→I Verwechslung)
- **Lösung:** Erweiterte ZEICHEN_KEYWORDS mit OCR-Varianten
- **Ergebnis:** Wird erkannt wie "Ihr Zeichen", "iZ"

### ✅ **Problem 6: Zeilenumbrüche** (⭐⭐⭐ mittel)
- **Beispiel:** `"Ihr Zeichen:\n111/24"`
- **Lösung:** 5-Zeilen-Kontext-Suche (2 vorher + aktuell + 2 nachher)
- **Ergebnis:** Aktenzeichen wird gefunden

---

## 🚀 Nächste Schritte (Optional)

### Weitere Verbesserungen möglich:

1. **Eigene OCR-Verarbeitung** (pytesseract)
   - Statt externes OCR zu erwarten
   - Bessere Kontrolle über OCR-Qualität
   - Anpassbare OCR-Parameter

2. **Trainierbare OCR-Korrektur**
   - Lernende Fehlerkorrektur basierend auf echten Dokumenten
   - Firmenspezifische Anpassungen

3. **Bildvorverarbeitung**
   - Kontrast-Verbesserung
   - Entrauschen
   - Deskewing (Schräglage-Korrektur)

---

## 📝 Zusammenfassung

### Was wurde verbessert:
✅ **OCR-Normalisierung** automatisch bei jeder Aktenzeichen-Suche
✅ **Leerzeichen-Toleranz** um Schrägstrich und in Zahlen
✅ **Schrägstrich-Verwechslungen** (I, l, L, \) werden erkannt
✅ **Erweiterte Keywords** für OCR-Fehler bei "Ihr Zeichen" etc.
✅ **Test-Tools** für Qualitätssicherung

### Commits:
1. **1fb69ba** - Beschränke Aktenzeichen auf 1-4 Stellen und nur Schrägstrich
2. **ffd930d** - Implementiere OCR-tolerante Aktenzeichen-Erkennung

### Dateien geändert:
- ✏️ `aktenzeichen_erkennung.py` - Neue _normalisiere_ocr_text()
- ➕ `ocr_test_analysis.py` - Analyse-Tool für OCR-Fehler
- ➕ `test_ocr_improvements.py` - Test-Suite für OCR-Normalisierung
- ➕ `OCR_VERBESSERUNGEN.md` - Diese Dokumentation

---

## 💡 Empfehlung

**Testen Sie die Verbesserungen** mit Ihren echten PDF-Dokumenten!

Die Erkennungsrate sollte sich **deutlich verbessern**, besonders bei:
- Briefen vom Mahngericht
- Gerichtsvollzieher-Dokumenten
- Gescannten Dokumenten mit schlechter OCR-Qualität

Bei weiteren Problemen können wir die Normalisierung noch spezifischer anpassen.
