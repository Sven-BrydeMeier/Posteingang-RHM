"""
Wiedervorlage-System (Tickler System)

Features:
- Wiedervorlagen für Dokumente/Akten
- Automatische Erinnerungen
- Wiederkehrende Wiedervorlagen
- Integration mit Kalender & Benachrichtigungen
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum


class WiedervorlageType(Enum):
    """Wiedervorlage-Typen"""
    EINMALIG = "Einmalig"
    TAEGLICH = "Täglich"
    WOECHENTLICH = "Wöchentlich"
    MONATLICH = "Monatlich"


class WiedervorlageStatus(Enum):
    """Status"""
    AKTIV = "Aktiv"
    ERLEDIGT = "Erledigt"
    VERSCHOBEN = "Verschoben"
    ABGEBROCHEN = "Abgebrochen"


class WiedervorlageSystem:
    """Verwaltet Wiedervorlagen"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Wiedervorlage-System

        Args:
            storage_dir: Storage-Verzeichnis
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.data_file = self.storage_dir / "wiedervorlagen.json"
        self.wiedervorlagen = self._load_data()

    def _load_data(self) -> Dict:
        """Lädt Wiedervorlagen"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_data(self):
        """Speichert Wiedervorlagen"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.wiedervorlagen, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")

    def create_wiedervorlage(
        self,
        titel: str,
        datum: datetime,
        aktenzeichen: Optional[str] = None,
        sachbearbeiter: Optional[str] = None,
        notiz: str = "",
        wiedervorlage_type: WiedervorlageType = WiedervorlageType.EINMALIG,
        priority: str = "NORMAL"
    ) -> str:
        """
        Erstellt Wiedervorlage

        Args:
            titel: Titel
            datum: Wiedervorlage-Datum
            aktenzeichen: Optional Aktenzeichen
            sachbearbeiter: Optional Sachbearbeiter
            notiz: Notiz
            wiedervorlage_type: Typ
            priority: Priorität

        Returns:
            Wiedervorlage-ID
        """
        import hashlib

        # Generiere ID
        wv_id = hashlib.md5(f"{titel}_{datetime.now().isoformat()}".encode()).hexdigest()

        self.wiedervorlagen[wv_id] = {
            'id': wv_id,
            'titel': titel,
            'datum': datum.isoformat(),
            'aktenzeichen': aktenzeichen,
            'sachbearbeiter': sachbearbeiter,
            'notiz': notiz,
            'type': wiedervorlage_type.value,
            'priority': priority,
            'status': WiedervorlageStatus.AKTIV.value,
            'erstellt_am': datetime.now().isoformat(),
            'erledigt_am': None
        }

        self._save_data()
        return wv_id

    def get_faellige_wiedervorlagen(self, tage_vorher: int = 0) -> List[Dict]:
        """
        Liefert fällige Wiedervorlagen

        Args:
            tage_vorher: Berücksichtige auch X Tage im Voraus

        Returns:
            Liste von Wiedervorlagen
        """
        now = datetime.now()
        threshold = now + timedelta(days=tage_vorher)

        faellig = []

        for wv_id, wv in self.wiedervorlagen.items():
            if wv['status'] != WiedervorlageStatus.AKTIV.value:
                continue

            wv_datum = datetime.fromisoformat(wv['datum'])

            if wv_datum <= threshold:
                wv_copy = wv.copy()
                wv_copy['days_remaining'] = (wv_datum - now).days
                wv_copy['is_overdue'] = wv_datum < now
                faellig.append(wv_copy)

        # Sortiere nach Datum
        faellig.sort(key=lambda x: x['datum'])

        return faellig

    def get_wiedervorlagen_by_sachbearbeiter(self, sachbearbeiter: str) -> List[Dict]:
        """Liefert Wiedervorlagen eines Sachbearbeiters"""
        return [
            wv for wv in self.wiedervorlagen.values()
            if wv['sachbearbeiter'] == sachbearbeiter and wv['status'] == WiedervorlageStatus.AKTIV.value
        ]

    def get_wiedervorlagen_by_aktenzeichen(self, aktenzeichen: str) -> List[Dict]:
        """Liefert Wiedervorlagen zu einem Aktenzeichen"""
        return [
            wv for wv in self.wiedervorlagen.values()
            if wv['aktenzeichen'] == aktenzeichen
        ]

    def mark_erledigt(self, wv_id: str) -> bool:
        """Markiert Wiedervorlage als erledigt"""
        if wv_id in self.wiedervorlagen:
            self.wiedervorlagen[wv_id]['status'] = WiedervorlageStatus.ERLEDIGT.value
            self.wiedervorlagen[wv_id]['erledigt_am'] = datetime.now().isoformat()
            self._save_data()
            return True
        return False

    def verschieben(self, wv_id: str, neues_datum: datetime) -> bool:
        """Verschiebt Wiedervorlage"""
        if wv_id in self.wiedervorlagen:
            self.wiedervorlagen[wv_id]['datum'] = neues_datum.isoformat()
            self.wiedervorlagen[wv_id]['status'] = WiedervorlageStatus.VERSCHOBEN.value
            self._save_data()
            return True
        return False

    def delete(self, wv_id: str) -> bool:
        """Löscht Wiedervorlage"""
        if wv_id in self.wiedervorlagen:
            del self.wiedervorlagen[wv_id]
            self._save_data()
            return True
        return False

    def get_statistics(self) -> Dict:
        """Liefert Statistiken"""
        stats = {
            'total': len(self.wiedervorlagen),
            'aktiv': 0,
            'erledigt': 0,
            'ueberfaellig': 0,
            'heute': 0,
            'diese_woche': 0
        }

        now = datetime.now()
        today_end = now.replace(hour=23, minute=59, second=59)
        week_end = now + timedelta(days=7)

        for wv in self.wiedervorlagen.values():
            if wv['status'] == WiedervorlageStatus.AKTIV.value:
                stats['aktiv'] += 1

                wv_datum = datetime.fromisoformat(wv['datum'])

                if wv_datum < now:
                    stats['ueberfaellig'] += 1
                elif wv_datum <= today_end:
                    stats['heute'] += 1
                elif wv_datum <= week_end:
                    stats['diese_woche'] += 1

            elif wv['status'] == WiedervorlageStatus.ERLEDIGT.value:
                stats['erledigt'] += 1

        return stats
