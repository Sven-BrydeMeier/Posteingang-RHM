#!/usr/bin/env python3
"""
Test-Skript für Gerichts-Aktenzeichen-Filterung
Stellt sicher, dass Gerichts-AZ nicht mit Kanzlei-AZ verwechselt werden
"""

from pathlib import Path
import sys
import pandas as pd
import tempfile

# Simuliertes Aktenregister
MOCK_REGISTER_DATA = {
    'Akte': ['739/25', '151/25', '1234/01', '500/24', '42/25', '456/24'],
    'SB': ['SQ', 'M', 'TS', 'CV', 'FÜ', 'GO'],
    'Kurzbezeichnung': [
        'Müller ./. Stadtwerke Hamburg',
        'Schmidt gegen Versicherung AG',
        'Meier GmbH ./. Schulze',
        'Nachlass Weber',
        'Testament Hoffmann',
        'Test ./. Test'
    ]
}

def create_mock_erkenner():
    """Erstellt AktenzeichenErkenner mit Mock-Register"""
    from aktenzeichen_erkennung import AktenzeichenErkenner

    df = pd.DataFrame(MOCK_REGISTER_DATA)

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        with pd.ExcelWriter(f.name, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='akten', index=False)
        return AktenzeichenErkenner(Path(f.name))


def test_gerichts_az_erkennung():
    """
    Testet, dass Gerichts-Aktenzeichen korrekt gefiltert werden
    """
    print("=" * 70)
    print("TEST: Gerichts-Aktenzeichen-Filterung")
    print("=" * 70)

    erkenner = create_mock_erkenner()

    testfaelle = [
        # (Text, erwartetes_internes_az, erwartetes_externes_az, beschreibung)
        (
            "Das Amtsgericht Hamburg hat im Verfahren 12 C 456/24 entschieden...",
            None,  # Kein internes AZ, da "456/24" Teil eines Gerichts-AZ ist
            ["456/24"],
            "Amtsgericht Zivilsache (12 C 456/24)"
        ),
        (
            "Im Insolvenzverfahren 23 IN 100/24 wurde...",
            None,
            ["100/24"],
            "Insolvenzverfahren (23 IN 100/24)"
        ),
        (
            "Az: 5 IK 200/24 - Verbraucherinsolvenz",
            None,
            ["200/24"],
            "Verbraucherinsolvenz (5 IK 200/24)"
        ),
        (
            "Landgericht Berlin 10 O 500/24...",
            None,  # 500/24 ist im Register, aber hier Teil eines Gerichts-AZ!
            ["500/24"],
            "LG Zivilsache - Konflikt mit Register-AZ"
        ),
        (
            "Ihr Zeichen: 739/25\nAz beim Gericht: 5 O 100/24",
            "739/25",  # Internes AZ aus "Ihr Zeichen"
            [],
            "Kombination: Internes AZ + Gerichts-AZ"
        ),
        (
            "BGH 1 ZR 50/24 - Revision",
            None,
            ["50/24"],
            "BGH Zivilrevision"
        ),
        (
            "BVerfG 2 BvR 123/24 - Verfassungsbeschwerde",
            None,
            ["123/24"],
            "BVerfG Verfassungsbeschwerde"
        ),
        (
            "Strafsache 10 Ds 300/24",
            None,
            ["300/24"],
            "Strafsache Schöffengericht"
        ),
        (
            "Familiensache 3 F 150/24",
            None,
            ["150/24"],
            "Familiensache"
        ),
        (
            "Ihr Zeichen: 151/25M\nGerichts-Az: 8 C 999/24",
            "151/25",  # Internes AZ erkannt via "Ihr Zeichen"
            [],
            "Kanzlei-AZ mit Kürzel + Gerichts-AZ"
        ),
        (
            "Bitte beziehen Sie sich auf 739/25SQ",
            "739/25",  # Im Register + mit Kürzel
            [],
            "Kanzlei-AZ mit Kürzel (im Register)"
        ),
        (
            "Aktenzeichen 1547/25TS",
            "1547/25",  # Stamm wird erkannt, Kürzel wird separat behandelt
            [],
            "Kanzlei-AZ mit Kürzel (nicht im Register)"
        ),
    ]

    erfolge = 0
    fehler = 0

    for text, erwartetes_az, erwartete_externe, beschreibung in testfaelle:
        result = erkenner.erkenne_aktenzeichen(text)

        # Normalisiere für Vergleich
        internes_az = result.get('stamm') or result.get('internes_az')
        if internes_az and internes_az.endswith('?'):
            internes_az = internes_az[:-1]

        externe_az = result.get('externe_az', [])

        # Prüfung
        az_ok = (internes_az == erwartetes_az) or (erwartetes_az is None and internes_az is None)

        print(f"\n📋 {beschreibung}")
        print(f"   Text: {text[:60]}...")
        print(f"   Erwartet intern: {erwartetes_az}")
        print(f"   Gefunden intern: {internes_az}")
        print(f"   Quelle: {result.get('quelle')}")
        print(f"   Konfidenz: {result.get('confidence')}")
        print(f"   Externe AZ: {externe_az}")

        if az_ok:
            print(f"   ✅ ERFOLG")
            erfolge += 1
        else:
            print(f"   ❌ FEHLER")
            fehler += 1

    print("\n" + "=" * 70)
    print(f"ERGEBNIS: {erfolge}/{erfolge + fehler} Tests bestanden")
    print("=" * 70)

    return fehler == 0


def test_validierungsfunktionen():
    """Testet die internen Validierungsfunktionen direkt"""
    print("\n" + "=" * 70)
    print("TEST: Interne Validierungsfunktionen")
    print("=" * 70)

    erkenner = create_mock_erkenner()

    # Test _ist_gerichts_aktenzeichen
    print("\n1. Test _ist_gerichts_aktenzeichen:")

    gerichts_tests = [
        ("12 C 456/24", "456/24", True, "Amtsgericht Zivilsache"),
        ("23 IN 100/24", "100/24", True, "Insolvenzverfahren"),
        ("5 IK 200/24", "200/24", True, "Verbraucherinsolvenz"),
        ("10 O 500/24", "500/24", True, "Landgericht Zivilsache"),
        ("1 ZR 50/24", "50/24", True, "BGH Revision"),
        ("2 BvR 123/24", "123/24", True, "BVerfG"),
        ("Ihr Zeichen: 739/25", "739/25", False, "Kanzlei-AZ"),
        ("AZ: 151/25M", "151/25", False, "Kanzlei-AZ mit Kürzel"),
    ]

    for text, stamm, erwartung, beschreibung in gerichts_tests:
        result = erkenner._ist_gerichts_aktenzeichen(text, 0, stamm)
        status = "✅" if result == erwartung else "❌"
        print(f"   {status} {beschreibung}: ist_gerichts={result} (erwartet: {erwartung})")

    # Test _ist_valides_internes_aktenzeichen
    print("\n2. Test _ist_valides_internes_aktenzeichen:")

    valid_tests = [
        ("739/25", "Bitte Ihr Zeichen 739/25", True, "Im Register"),
        ("151/25", "AZ: 151/25", True, "Im Register"),
        ("999/25SQ", "AZ: 999/25SQ", True, "Mit gültigem Kürzel"),
        ("888/25TS", "AZ: 888/25TS", True, "Mit gültigem Kürzel"),
        ("456/24", "12 C 456/24", False, "Gerichts-AZ"),
        ("100/24", "23 IN 100/24", False, "Insolvenz-AZ"),
        ("777/25", "AZ: 777/25", False, "Weder Register noch Kürzel"),
    ]

    for stamm, text, erwartung, beschreibung in valid_tests:
        ist_valid, grund = erkenner._ist_valides_internes_aktenzeichen(stamm, text)
        status = "✅" if ist_valid == erwartung else "❌"
        print(f"   {status} {beschreibung}: valid={ist_valid}, grund={grund}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🔍 GERICHTS-AKTENZEICHEN FILTER TEST")
    print("=" * 70)

    test_validierungsfunktionen()
    success = test_gerichts_az_erkennung()

    sys.exit(0 if success else 1)
