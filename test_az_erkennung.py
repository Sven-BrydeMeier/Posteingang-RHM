#!/usr/bin/env python3
"""
Test-Skript für Aktenzeichen-Erkennung
Zeigt die verschiedenen Erkennungsmethoden
"""

from pathlib import Path
import sys

# Test ohne echtes Aktenregister (simuliert)
import pandas as pd
import io

# Simuliertes Aktenregister (mit korrektem Header)
MOCK_REGISTER_DATA = {
    'Akte': ['739/25', '151/25', '1234/01', '500/24', '42/25'],
    'SB': ['SQ', 'M', 'TS', 'CV', 'FÜ'],
    'Kurzbezeichnung': [
        'Müller ./. Stadtwerke Hamburg',
        'Schmidt gegen Versicherung AG',
        'Meier GmbH ./. Schulze',
        'Nachlass Weber',
        'Testament Hoffmann'
    ]
}

def create_mock_erkenner():
    """Erstellt AktenzeichenErkenner mit Mock-Register"""
    from aktenzeichen_erkennung import AktenzeichenErkenner

    # Temporäre Excel-Datei erstellen
    import tempfile

    df = pd.DataFrame(MOCK_REGISTER_DATA)

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        # Erstelle Excel mit Sheet "akten"
        with pd.ExcelWriter(f.name, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='akten', index=False)
        return AktenzeichenErkenner(Path(f.name))

def test_erkennung():
    """Testet verschiedene Erkennungsszenarien"""

    print("=" * 70)
    print("🔍 AKTENZEICHEN-ERKENNUNGS-TEST")
    print("=" * 70)

    erkenner = create_mock_erkenner()

    # Testfälle
    testfaelle = [
        {
            "name": "1️⃣ Zeichen-Feld (Priorität 1)",
            "text": """
                Radtke, Heigener und Meier
                Rechtsanwälte

                Ihr Zeichen: 739/25SQ
                Unser Zeichen: 123 C 456/24

                Sehr geehrte Damen und Herren...
            """,
            "erwartet": "739/25SQ (zeichen_feld)"
        },
        {
            "name": "2️⃣ Vollmuster (Priorität 2)",
            "text": """
                Amtsgericht Hamburg

                In der Sache 739/25SQ08TÖ

                wird folgendes Urteil verkündet...
            """,
            "erwartet": "739/25SQ (vollmuster)"
        },
        {
            "name": "3️⃣ Stamm + Register (Priorität 3)",
            "text": """
                Betreff: Akte 739/25

                Hiermit teilen wir mit...
            """,
            "erwartet": "739/25SQ (register)"
        },
        {
            "name": "4️⃣ Kurzbezeichnung (Priorität 4)",
            "text": """
                Sehr geehrter Herr Kollege,

                in der Sache Müller ./. Stadtwerke Hamburg
                übersenden wir Ihnen...
            """,
            "erwartet": "739/25SQ (kurzbezeichnung_im_text)"
        },
        {
            "name": "5️⃣ Parteien (Priorität 5)",
            "text": """
                Betreff: Sache Müller / Stadtwerke

                Anliegend erhalten Sie...
            """,
            "erwartet": "739/25SQ (parteien_...)"
        },
        {
            "name": "6️⃣ Erweitertes Format mit Bereich+ReNo",
            "text": """
                Gz.: 739/25SQ08TÖ

                Kostenfestsetzungsbeschluss
            """,
            "erwartet": "739/25SQ (zeichen_feld) + Bereich=08, ReNo=TÖ"
        },
        {
            "name": "7️⃣ OCR-Fehler tolerant",
            "text": """
                lhr Zeichen: 739/25SQ

                (OCR hat 'I' als 'l' erkannt)
            """,
            "erwartet": "739/25SQ (zeichen_feld)"
        },
    ]

    for i, test in enumerate(testfaelle):
        print(f"\n{'─' * 70}")
        print(f"TEST: {test['name']}")
        print(f"{'─' * 70}")
        print(f"📄 Text-Auszug: {test['text'][:100].strip()}...")
        print(f"🎯 Erwartet: {test['erwartet']}")

        try:
            result = erkenner.erkenne_aktenzeichen(test['text'])

            az = result.get('internes_az', 'NICHT ERKANNT')
            quelle = result.get('quelle', 'keine')
            bereich = result.get('bereich', '')
            reno = result.get('reno', '')
            kurzbez = result.get('aktenkurzbezeichnung', '')

            print(f"✅ Ergebnis: {az} (Quelle: {quelle})")
            if bereich:
                print(f"   Bereich: {bereich}")
            if reno:
                print(f"   ReNo: {reno}")
            if kurzbez:
                print(f"   Kurzbezeichnung: {kurzbez}")

        except Exception as e:
            print(f"❌ Fehler: {e}")

    print(f"\n{'=' * 70}")
    print("✅ TEST ABGESCHLOSSEN")
    print("=" * 70)

if __name__ == "__main__":
    test_erkennung()
