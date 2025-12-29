"""
Test: Zusammengeklebte Aktenzeichen-Erkennung
Zeigt wie "1342/2450089 / Li" → "1342/24Li" wird
"""

import re

class AktenzeichenNormalisierer:
    KUERZEL = ['MQ', 'SQ', 'TS', 'CV', 'FÜ', 'FU', 'M', 'GO', 'HE', 'RÜ', 'AK', 'TÖ', 'LI', 'AD', 'HI', 'FK', 'ST', 'BO']

    def get_all_kuerzel_regex(self):
        return '|'.join(self.KUERZEL)

    def _normalisiere_ocr_text(self, text: str, verbose=False) -> str:
        if not text:
            return text

        if verbose:
            print(f"  0. Input: '{text}'")

        # SCHRITT 1: Trenne zusammengeklebte Zahlen
        def split_concatenated_numbers(match):
            laufnr = match.group(1)
            jahr_plus = match.group(2)
            rest = match.group(3) if match.lastindex >= 3 else ""

            if len(jahr_plus) > 2:
                jahr = jahr_plus[:2]
                extra_nummern = jahr_plus[2:]
                result = f"{laufnr}/{jahr} {extra_nummern}{rest}"
                if verbose:
                    print(f"    SPLIT: '{match.group()}' → '{result}'")
                return result
            else:
                return match.group(0)

        text = re.sub(
            r'\b(\d{1,4})\s*[/IlL\\]\s*(\d{3,})(\s|[/IlL\\]|$)',
            split_concatenated_numbers,
            text
        )

        if verbose:
            print(f"  1. Nach Split: '{text}'")

        # SCHRITT 2: Bereinige Aktenzeichen
        def clean_aktenzeichen_mit_kuerzel(match):
            full_match = match.group(0)
            g1, g2, g3 = match.groups()
            num1 = re.sub(r'\s+', '', g1)
            num2 = re.sub(r'\s+', '', g2)

            if not num2 or len(num2) > 2:
                return full_match

            kuerzel = g3
            trailing_space = " " if full_match.endswith(" ") else ""
            result = f"{num1}/{num2}{kuerzel}{trailing_space}"
            if verbose:
                print(f"    KÜRZEL: '{match.group()}' → '{result}'")
            return result

        def clean_aktenzeichen_stamm(match):
            full_match = match.group(0)
            g1, g2 = match.groups()
            num1 = re.sub(r'\s+', '', g1)
            num2 = re.sub(r'\s+', '', g2)

            if not num1 or not num2 or len(num1) > 4 or len(num2) > 2:
                return full_match

            trailing_space = " " if full_match.endswith(" ") else ""
            result = f"{num1}/{num2}{trailing_space}"
            if verbose:
                print(f"    STAMM: '{match.group()}' → '{result}'")
            return result

        text = re.sub(
            r'\b([\d\s]{1,7})\s*[/IlL\\]\s*([\d\s]{1,3})\s*([A-ZÄÖÜ]{1,3})\b',
            clean_aktenzeichen_mit_kuerzel,
            text
        )

        if verbose:
            print(f"  2. Nach Kürzel: '{text}'")

        text = re.sub(
            r'\b([\d\s]{1,7})\s*[/IlL\\]\s*([\d\s]{1,3})\b',
            clean_aktenzeichen_stamm,
            text
        )

        if verbose:
            print(f"  3. Nach Stamm: '{text}'")

        return text

# Tests
normalisierer = AktenzeichenNormalisierer()

test_cases = [
    ("Ihr Zeichen: 1342/2450089 / Li", "1342/24LI"),
    ("Ihr Zeichen: 111/2450089 / BO", "111/24BO"),
    ("Ihr Zeichen: 999/25M", "999/25M"),
]

print("=" * 80)
print("TEST: Zusammengeklebte Aktenzeichen-Erkennung")
print("=" * 80)

erfolge = 0

for test_input, expected_az in test_cases:
    print(f"\n{'='*80}")
    print(f"Test: {test_input}")
    print(f"Erwartetes AZ: {expected_az}")
    print(f"{'='*80}")

    result = normalisierer._normalisiere_ocr_text(test_input, verbose=True)

    # Check pattern match
    kuerzel_regex = normalisierer.get_all_kuerzel_regex()
    pattern = rf'\b(\d{{1,4}})/(\d{{1,2}})({kuerzel_regex})\b'
    match = re.search(pattern, result, re.IGNORECASE)

    if match and match.group() == expected_az:
        print(f"✅ SUCCESS: Erkannt als '{match.group()}'")
        erfolge += 1
    elif match:
        print(f"⚠️  TEILWEISE: Erkannt als '{match.group()}' (erwartet: {expected_az})")
    else:
        print(f"❌ FEHLER: Nicht erkannt")

print(f"\n{'='*80}")
print(f"ERGEBNIS: {erfolge}/{len(test_cases)} Tests erfolgreich")
print(f"{'='*80}")
