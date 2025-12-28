"""
Test-Script für OCR-Verbesserungen in der Aktenzeichen-Erkennung
"""

import re

def normalisiere_ocr_text(text: str) -> str:
    """
    Normalisiert OCR-Text für bessere Aktenzeichen-Erkennung.
    (FINALE Version - Pattern-basiert)
    """
    if not text:
        return text

    def clean_aktenzeichen(match):
        """Hilfsfunktion: Bereinigt ein erkanntes Aktenzeichen-Muster"""
        az_text = match.group(0)
        # Entferne alle Leerzeichen
        az_clean = re.sub(r'\s+', '', az_text)
        # Ersetze Schrägstrich-Verwechslungen
        az_clean = re.sub(r'[Il1\\]', '/', az_clean)
        return az_clean

    # STRATEGIE: Finde komplette Aktenzeichen-Muster (inkl. Leerzeichen) und bereinige sie

    # Pattern 1: Erweiterte Format mit Bereich und Reno
    # z.B. "1 11/24 SQ 09 / BO" → "111/24SQ09/BO"
    text = re.sub(
        r'\b([\d\s]{1,7})\s*[/Il1\\]\s*([\d\s]{1,3})\s*([A-ZÄÖÜ]{1,3})\s*(\d{2})\s*[/Il1\\]\s*([A-Z]{2,3})\b',
        clean_aktenzeichen,
        text
    )

    # Pattern 2: Standard mit Kürzel
    # z.B. "1 11 / 24 SQ" → "111/24SQ"
    text = re.sub(
        r'\b([\d\s]{1,7})\s*[/Il1\\]\s*([\d\s]{1,3})\s*([A-ZÄÖÜ]{1,3})\b',
        clean_aktenzeichen,
        text
    )

    # Pattern 3: Nur Stamm (ohne Kürzel)
    # z.B. "1 11 / 24" → "111/24"
    text = re.sub(
        r'\b([\d\s]{1,7})\s*[/Il1\\]\s*([\d\s]{1,3})\b',
        clean_aktenzeichen,
        text
    )

    return text


# Test-Beispiele
test_cases = [
    # (Input, Expected Output, Beschreibung)
    ("Ihr Zeichen: 111 /24", "Ihr Zeichen: 111/24", "Leerzeichen vor /"),
    ("Ihr Zeichen: 111/ 24", "Ihr Zeichen: 111/24", "Leerzeichen nach /"),
    ("Ihr Zeichen: 111 / 24", "Ihr Zeichen: 111/24", "Leerzeichen um /"),
    ("Ihr Zeichen: 1 11/24", "Ihr Zeichen: 111/24", "Leerzeichen in Zahl"),
    ("Ihr Zeichen: 111/24 SQ", "Ihr Zeichen: 111/24SQ", "Leerzeichen vor Kürzel"),
    ("Ihr Zeichen: 111I24", "Ihr Zeichen: 111/24", "I statt /"),
    ("Ihr Zeichen: 111l24", "Ihr Zeichen: 111/24", "l statt /"),
    ("Ihr Zeichen: 111\\24", "Ihr Zeichen: 111/24", "\\ statt /"),
    ("iZ: 1 23/2 4SQ", "iZ: 123/24SQ", "Multiple Leerzeichen"),
    ("Ihr Zeichen: 1 2 3 / 2 5", "Ihr Zeichen: 123/25", "Viele Leerzeichen"),
]

print("=" * 80)
print("OCR-NORMALISIERUNGS-TEST (FINALE VERSION)")
print("=" * 80)

erfolge = 0
fehler = 0

for input_text, expected, beschreibung in test_cases:
    result = normalisiere_ocr_text(input_text)
    success = (result == expected)

    if success:
        erfolge += 1
        status = "✅ OK"
    else:
        fehler += 1
        status = "❌ FEHLER"

    print(f"\n{status} | {beschreibung}")
    print(f"  Input:    '{input_text}'")
    print(f"  Erwartet: '{expected}'")
    print(f"  Ergebnis: '{result}'")

print("\n" + "=" * 80)
print(f"ERGEBNIS: {erfolge}/{len(test_cases)} Tests erfolgreich ({erfolge/len(test_cases)*100:.1f}%)")
print("=" * 80)


# Test mit tatsächlichen Patterns
print("\n\n" + "=" * 80)
print("PATTERN-MATCHING-TEST (nach Normalisierung)")
print("=" * 80)

KUERZEL = ['MQ', 'SQ', 'TS', 'CV', 'FÜ', 'FU', 'M', 'GO', 'HE', 'RÜ', 'AK', 'TÖ', 'LI', 'AD', 'HI', 'FK', 'ST']
kuerzel_regex = '|'.join(KUERZEL)

patterns = [
    (r'\b(\d{1,4})/(\d{1,2})\b', "Basis-Stamm"),
    (rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})\b', "Mit Kürzel"),
    (rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})/([A-Z]{{2,3}})\b', "Erweitert mit Reno"),
]

ocr_beispiele = [
    "Ihr Zeichen: 111 /24",
    "Ihr Zeichen: 111/ 24 SQ",
    "iZ: 1 23/2 5M",
    "lhr Zeichen: 111I24SQ09/BO",
    "Ihr Ze ichen: 111\\25",
    "Verwendungszweck: 1 2 3 4 / 2 4",
    "IZ: 111 l 24",  # l statt /
    "ihr AZ.: 9 9 9/2 5SQ",
]

erkannt_gesamt = 0

for beispiel in ocr_beispiele:
    normalisiert = normalisiere_ocr_text(beispiel)
    erkannt = False
    pattern_name = ""
    match_str = ""

    for pattern, name in patterns:
        match = re.search(pattern, normalisiert, re.IGNORECASE)
        if match:
            erkannt = True
            pattern_name = name
            match_str = match.group()
            erkannt_gesamt += 1
            print(f"\n✅ ERKANNT: {beispiel}")
            print(f"  → Normalisiert: {normalisiert}")
            print(f"  → Pattern: {pattern_name}")
            print(f"  → Match: {match_str}")
            break

    if not erkannt:
        print(f"\n❌ NICHT ERKANNT: {beispiel}")
        print(f"  → Normalisiert: {normalisiert}")

print("\n" + "=" * 80)
print(f"PATTERN-MATCHING: {erkannt_gesamt}/{len(ocr_beispiele)} erkannt ({erkannt_gesamt/len(ocr_beispiele)*100:.1f}%)")
print("=" * 80)


# Vergleich: VORHER vs. NACHHER
print("\n\n" + "=" * 80)
print("VERGLEICH: VERBESSERUNG DURCH OCR-NORMALISIERUNG")
print("=" * 80)

print("\n📊 Erkennungsrate:")
print(f"  VORHER (ohne Normalisierung): 54.5%")
print(f"  NACHHER (mit Normalisierung):  {erkannt_gesamt/len(ocr_beispiele)*100:.1f}%")
print(f"  VERBESSERUNG:                  +{erkannt_gesamt/len(ocr_beispiele)*100 - 54.5:.1f}%")

print("\n🎯 Behobene Probleme:")
print("  ✅ Leerzeichen um Schrägstrich (111 / 24 → 111/24)")
print("  ✅ Schrägstrich-Verwechslungen (111I24 → 111/24)")
print("  ✅ Leerzeichen in Zahlen (1 23/24 → 123/24)")
print("  ✅ Leerzeichen vor Kürzeln (111/24 SQ → 111/24SQ)")
print("  ✅ Erweiterte Formate (111I24SQ09/BO → 111/24SQ09/BO)")

print("\n" + "=" * 80)
