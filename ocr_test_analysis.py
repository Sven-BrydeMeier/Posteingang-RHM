"""
OCR-Fehler-Analyse für Aktenzeichen-Erkennung

Zeigt typische OCR-Probleme und testet aktuelle Patterns
"""

import re

# Aktuelle Patterns (1-4 Stellen, nur /)
CURRENT_PATTERNS = [
    r'\b(\d{1,4})[/](\d{1,2})\b',  # Basis-Stamm
    r'\b(\d{1,4})/(\d{1,2})(MQ|SQ|TS|CV|FÜ|FU|M|GO|HE|RÜ|AK|TÖ|LI|AD|HI|FK|ST)\b',  # Mit Kürzel
]

# OCR-Problem-Beispiele aus realen PDFs
OCR_BEISPIELE = {
    "Perfekt (sollte erkannt werden)": [
        "Ihr Zeichen: 111/24",
        "Ihr Zeichen: 1234/24SQ",
        "iZ: 123/25M",
        "111/24SQ09/BO",
    ],

    "Leerzeichen-Probleme (häufigster OCR-Fehler)": [
        "Ihr Zeichen: 111 /24",      # Leerzeichen vor /
        "Ihr Zeichen: 111/ 24",      # Leerzeichen nach /
        "Ihr Zeichen: 111 / 24",     # Leerzeichen um /
        "Ihr Zeichen: 1 11/24",      # Leerzeichen in Zahl
        "Ihr Zeichen: 111/24 SQ",    # Leerzeichen vor Kürzel
        "Ihr Zeichen:111/24",        # Kein Leerzeichen nach :
    ],

    "Zeilenumbruch-Probleme": [
        "Ihr Zeichen:\n111/24",      # Zeilenumbruch nach Keyword
        "Ihr Zeichen: 111/\n24",     # Zeilenumbruch im Zeichen
        "Ihr Zeichen:\n111/24SQ",    # Beides
    ],

    "Zeichen-Verwechslungen": [
        "Ihr Zeichen: 111I24",       # / wird zu I
        "Ihr Zeichen: 111l24",       # / wird zu l (kleines L)
        "Ihr Zeichen: 111\\24",      # / wird zu \
        "Ihr Zeichen: O11/24",       # 0 wird zu O
        "Ihr Zeichen: 111/Z4",       # 2 wird zu Z
    ],

    "Keyword-Variationen": [
        "lhr Zeichen: 111/24",       # I statt h
        "lZ: 111/24",                # I statt h in iZ
        "Ihr Ze ichen: 111/24",      # Leerzeichen im Wort
        "lhrZeichen: 111/24",        # Zusammengeschrieben + I
    ]
}


def teste_pattern(pattern: str, text: str) -> bool:
    """Testet ob ein Pattern im Text matched"""
    match = re.search(pattern, text, re.IGNORECASE)
    return match is not None


def analysiere_ocr_probleme():
    """Analysiert welche OCR-Probleme mit aktuellen Patterns erkannt werden"""
    print("=" * 80)
    print("OCR-FEHLER-ANALYSE: Aktenzeichen-Erkennung")
    print("=" * 80)
    print("\nAKTUELLE PATTERNS:")
    for p in CURRENT_PATTERNS:
        print(f"  - {p}")
    print()

    gesamt_tests = 0
    erfolgreiche = 0

    for kategorie, beispiele in OCR_BEISPIELE.items():
        print(f"\n{'=' * 80}")
        print(f"KATEGORIE: {kategorie}")
        print(f"{'=' * 80}")

        for beispiel in beispiele:
            gesamt_tests += 1
            erkannt = False

            for pattern in CURRENT_PATTERNS:
                if teste_pattern(pattern, beispiel):
                    erkannt = True
                    erfolgreiche += 1
                    break

            status = "✅ ERKANNT" if erkannt else "❌ NICHT ERKANNT"
            print(f"{status:20} | {beispiel}")

    print(f"\n{'=' * 80}")
    print(f"ERGEBNIS: {erfolgreiche}/{gesamt_tests} Beispiele erkannt ({erfolgreiche/gesamt_tests*100:.1f}%)")
    print(f"{'=' * 80}\n")


def empfohlene_fixes():
    """Zeigt empfohlene Verbesserungen"""
    print("\n" + "=" * 80)
    print("EMPFOHLENE FIXES FÜR OCR-PROBLEME")
    print("=" * 80)

    fixes = [
        {
            "Problem": "Leerzeichen um Schrägstrich",
            "Häufigkeit": "⭐⭐⭐⭐⭐ (sehr häufig)",
            "Beispiel": "'111 / 24' statt '111/24'",
            "Lösung": r"Pattern: (\d{1,4})\s*/\s*(\d{1,2})",
            "Erklärung": r"\s* erlaubt 0 oder mehr Leerzeichen"
        },
        {
            "Problem": "Leerzeichen in Zahlen",
            "Häufigkeit": "⭐⭐⭐⭐ (häufig)",
            "Beispiel": "'1 23/24' statt '123/24'",
            "Lösung": "Text-Normalisierung VOR Pattern-Matching",
            "Erklärung": "Entferne Leerzeichen zwischen Ziffern im Aktenzeichen-Kontext"
        },
        {
            "Problem": "Leerzeichen vor Kürzel",
            "Häufigkeit": "⭐⭐⭐⭐ (häufig)",
            "Beispiel": "'111/24 SQ' statt '111/24SQ'",
            "Lösung": r"Pattern: (\d{1,4})\s*/\s*(\d{1,2})\s*(KUERZEL)",
            "Erklärung": r"\s* vor Kürzel erlaubt optionale Leerzeichen"
        },
        {
            "Problem": "Zeilenumbrüche",
            "Häufigkeit": "⭐⭐⭐ (mittel)",
            "Beispiel": "'Ihr Zeichen:\\n111/24'",
            "Lösung": "Text-Normalisierung: Ersetze \\n mit Leerzeichen in Keyword-Kontext",
            "Erklärung": "Bereits teilweise implementiert (5-Zeilen-Kontext-Suche)"
        },
        {
            "Problem": "Zeichen-Verwechslungen (/, I, l, 1)",
            "Häufigkeit": "⭐⭐ (gelegentlich)",
            "Beispiel": "'111I24' oder '111l24' statt '111/24'",
            "Lösung": r"Pattern: (\d{1,4})[/Il1\\](\d{1,2})",
            "Erklärung": "Erlaube I, l, 1, \\ als Schrägstrich-Ersatz"
        },
        {
            "Problem": "Keyword-Variationen",
            "Häufigkeit": "⭐⭐ (gelegentlich)",
            "Beispiel": "'lhr Zeichen' statt 'Ihr Zeichen'",
            "Lösung": "Erweitere ZEICHEN_KEYWORDS um OCR-Varianten",
            "Erklärung": "Füge 'lhr zeichen', 'lZ' etc. hinzu"
        },
    ]

    for i, fix in enumerate(fixes, 1):
        print(f"\n{i}. {fix['Problem']}")
        print(f"   Häufigkeit: {fix['Häufigkeit']}")
        print(f"   Beispiel:   {fix['Beispiel']}")
        print(f"   Lösung:     {fix['Lösung']}")
        print(f"   Erklärung:  {fix['Erklärung']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    analysiere_ocr_probleme()
    empfohlene_fixes()
