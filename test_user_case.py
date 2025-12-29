"""
Test: Spezifischer User-Case
"Ihr Zeichen: 1342/2450089 / Li" muss als "1342/24Li" erkannt werden
"""

import re

# Simuliere die komplette Erkennungslogik
class MiniErkenner:
    KUERZEL = ['LI', 'BO', 'SQ', 'M']
    KUERZEL_NORMALISIERT = {'LI': 'LI', 'BO': 'BO', 'SQ': 'SQ', 'M': 'M'}
    ZEICHEN_KEYWORDS = ['ihr zeichen', 'ihr zeichen:']

    def _normalisiere_ocr_text(self, text):
        # Schritt 1: Split concatenated numbers
        def split_concat(match):
            laufnr, jahr_plus, rest = match.group(1), match.group(2), match.group(3) if match.lastindex >= 3 else ""
            if len(jahr_plus) > 2:
                jahr = jahr_plus[:2]
                extra = jahr_plus[2:]
                return f"{laufnr}/{jahr} {extra}{rest}"
            return match.group(0)

        text = re.sub(r'\b(\d{1,4})\s*[/IlL\\]\s*(\d{3,})(\s|[/IlL\\]|$)', split_concat, text)
        return text

    def _finde_kuerzel_im_text(self, text, position_sensitive=False):
        text_upper = text.upper()
        if position_sensitive:
            for k in self.KUERZEL:
                if text_upper[:5].find(k) in [0, 1, 2]:
                    return k
        return None

    def _suche_in_zeichen_feldern(self, text):
        text = self._normalisiere_ocr_text(text)
        lines = text.split('\n')

        for line in lines:
            if any(kw in line.lower() for kw in self.ZEICHEN_KEYWORDS):
                # Suche Stamm
                stamm_match = re.search(r'\b(\d{1,4})[/](\d{1,2})\b', line)
                if stamm_match:
                    zahl1, zahl2 = stamm_match.groups()
                    stamm = f"{zahl1}/{zahl2.zfill(2)}"

                    # Suche Kürzel im Suffix
                    suffix = line[stamm_match.end():stamm_match.end() + 50]

                    # 1. Direkt nach Stamm
                    kuerzel = self._finde_kuerzel_im_text(suffix, position_sensitive=True)

                    # 2. Suche "/ KÜRZEL" Pattern
                    if not kuerzel:
                        slash_match = re.search(r'[/IlL\\]\s*([A-ZÄÖÜ]{1,3})\b', suffix, re.IGNORECASE)
                        if slash_match:
                            kuerzel_text = slash_match.group(1).upper()
                            if kuerzel_text in self.KUERZEL:
                                kuerzel = kuerzel_text

                    if kuerzel:
                        return {
                            'internes_az': f"{stamm}{kuerzel}",
                            'stamm': stamm,
                            'kuerzel': kuerzel
                        }
        return None

# TEST
erkenner = MiniErkenner()

test_cases = [
    ("Ihr Zeichen: 1342/2450089 / Li", "1342/24LI"),
    ("Ihr Zeichen: 111/2450089 / BO", "111/24BO"),
]

print("=" * 80)
print("USER-CASE TEST: Zusammengeklebte Aktenzeichen")
print("=" * 80)

for test_input, expected in test_cases:
    result = erkenner._suche_in_zeichen_feldern(test_input)

    if result and result['internes_az'] == expected:
        print(f"\n✅ SUCCESS")
        print(f"   Input:    {test_input}")
        print(f"   Erwartet: {expected}")
        print(f"   Erkannt:  {result['internes_az']}")
    elif result:
        print(f"\n⚠️  TEILWEISE")
        print(f"   Input:    {test_input}")
        print(f"   Erwartet: {expected}")
        print(f"   Erkannt:  {result['internes_az']}")
    else:
        print(f"\n❌ FEHLER")
        print(f"   Input:    {test_input}")
        print(f"   Erwartet: {expected}")
        print(f"   Erkannt:  (nichts)")

print(f"\n{'='*80}\n")
