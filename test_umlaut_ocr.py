"""
Test: Umlaut-OCR-Fehler in Reno-Kürzeln
"132/25TS04T6" (OCR) → "132/25TS04Tö" (korrigiert)
"""

import re

class UmlautOCRTester:
    KUERZEL = ['TS', 'SQ', 'M', 'BO']
    KUERZEL_NORMALISIERT = {'TS': 'TS', 'SQ': 'SQ', 'M': 'M', 'BO': 'BO'}

    def get_all_kuerzel_regex(self):
        return '|'.join(self.KUERZEL)

    def _normalisiere_ocr_text(self, text: str) -> str:
        if not text:
            return text

        # Korrigiere Umlaut-OCR-Fehler in Reno-Kürzeln
        def fix_umlaut_ocr_in_reno(match):
            full_match = match.group(0)
            reno = match.group(5)

            reno_fixed = reno
            reno_fixed = re.sub(r'([A-Z])6\b', r'\1ö', reno_fixed)  # T6 → Tö
            reno_fixed = re.sub(r'([A-Z])0\b', r'\1ö', reno_fixed)  # T0 → Tö
            reno_fixed = re.sub(r'([A-Z])ii\b', r'\1ü', reno_fixed, flags=re.IGNORECASE)
            reno_fixed = re.sub(r'([A-Z])u([A-Z])\b', r'\1ü\2', reno_fixed)

            if reno != reno_fixed:
                return full_match.replace(reno, reno_fixed)
            return full_match

        text = re.sub(
            r'\b(\d{1,4})/(\d{1,2})([A-Z]{2,3})(\d{2})([A-Z0-9]{2,3})\b',
            fix_umlaut_ocr_in_reno,
            text,
            flags=re.IGNORECASE
        )
        return text

    def erkenne_aktenzeichen(self, text: str):
        text = self._normalisiere_ocr_text(text)

        kuerzel_regex = self.get_all_kuerzel_regex()

        # Erweiterte Patterns (mit Umlaut-Unterstützung und Ziffern-Fallback)
        patterns = [
            (rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})/([A-ZÄÖÜß]{{2,3}})\b', "Erweitert mit Slash"),
            (rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})([A-ZÄÖÜß]{{2,3}})\b', "Erweitert ohne Slash"),
            (rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})/([A-Z0-9]{{2,3}})\b', "OCR-tolerant mit Slash"),
            (rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})(\d{{2}})([A-Z0-9]{{2,3}})\b', "OCR-tolerant ohne Slash"),
        ]

        for pattern, name in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 5:
                    laufnr, jahr, kuerzel, bereich, reno = match.groups()
                    stamm = f"{laufnr}/{jahr.zfill(2)}"
                    return {
                        'internes_az': f"{stamm}{kuerzel}",
                        'stamm': stamm,
                        'kuerzel': kuerzel,
                        'bereich': bereich,
                        'reno': reno,
                        'vollformat': match.group(0),
                        'pattern': name
                    }
        return None

# Tests
tester = UmlautOCRTester()

test_cases = [
    ("Ihr Zeichen: 132/25TS04T6", "132/25TS", "Tö"),     # T6 → Tö
    ("Ihr Zeichen: 111/24SQ09B0", "111/24SQ", "Bö"),     # B0 → Bö
    ("Ihr Zeichen: 999/25M05BO", "999/25M", "BO"),       # BO bleibt BO
]

print("=" * 80)
print("TEST: Umlaut-OCR-Korrektur in Reno-Kürzeln")
print("=" * 80)

erfolge = 0

for test_input, expected_az, expected_reno in test_cases:
    print(f"\nTest: {test_input}")

    # Zeige Normalisierung
    normalized = tester._normalisiere_ocr_text(test_input)
    print(f"  Nach Normalisierung: {normalized}")

    # Erkenne Aktenzeichen
    result = tester.erkenne_aktenzeichen(test_input)

    if result:
        success = (result['internes_az'] == expected_az)
        reno_correct = (result['reno'] == expected_reno)

        if success and reno_correct:
            print(f"  ✅ ERFOLG")
            print(f"     Aktenzeichen: {result['internes_az']}")
            print(f"     Vollformat:   {result['vollformat']}")
            print(f"     Reno:         {result['reno']} (erwartet: {expected_reno})")
            print(f"     Pattern:      {result['pattern']}")
            erfolge += 1
        else:
            print(f"  ⚠️  TEILWEISE")
            print(f"     Aktenzeichen: {result['internes_az']} (erwartet: {expected_az})")
            print(f"     Reno:         {result['reno']} (erwartet: {expected_reno})")
    else:
        print(f"  ❌ FEHLER: Nicht erkannt")

print(f"\n{'=' * 80}")
print(f"ERGEBNIS: {erfolge}/{len(test_cases)} Tests erfolgreich")
print("=" * 80)
