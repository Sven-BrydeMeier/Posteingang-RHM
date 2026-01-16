"""
Persistentes Speichersystem für RHM Posteingang
- Verschlüsselte API-Key-Speicherung
- Aktenregister-Speicherung mit Merge-Funktion
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from cryptography.fernet import Fernet
import base64
import hashlib


class PersistentStorage:
    def __init__(self, storage_dir: Path = None):
        """
        Initialisiert persistenten Speicher.

        Args:
            storage_dir: Verzeichnis für Speicherung (default: .streamlit/storage)
        """
        if storage_dir is None:
            storage_dir = Path.home() / '.streamlit' / 'rhm_storage'

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Dateipfade
        self.api_keys_file = self.storage_dir / 'api_keys.enc'
        self.aktenregister_file = self.storage_dir / 'aktenregister.xlsx'
        self.key_file = self.storage_dir / '.key'

        # Verschlüsselungsschlüssel laden oder erstellen
        self.cipher = self._get_cipher()

    def _get_cipher(self) -> Fernet:
        """Lädt oder erstellt Verschlüsselungsschlüssel"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            # Generiere neuen Schlüssel
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # Setze Dateiberechtigungen (nur Owner kann lesen)
            self.key_file.chmod(0o600)

        return Fernet(key)

    # ==================== API-KEYS ====================

    def save_api_key(self, provider: str, api_key: str) -> None:
        """
        Speichert API-Key verschlüsselt mit Zeitstempel.
        Überschreibt vorhandenen Key für diesen Provider.

        Args:
            provider: 'openai', 'claude', oder 'gemini'
            api_key: Der API-Schlüssel
        """
        # Lade vorhandene Keys
        keys_data = self._load_api_keys_data()

        # Aktualisiere/Füge hinzu mit Zeitstempel
        from datetime import datetime
        keys_data[provider] = {
            'key': api_key,
            'updated_at': datetime.now().isoformat()
        }

        # Verschlüssele und speichere
        json_data = json.dumps(keys_data)
        encrypted = self.cipher.encrypt(json_data.encode())

        with open(self.api_keys_file, 'wb') as f:
            f.write(encrypted)

        # Setze Dateiberechtigungen
        self.api_keys_file.chmod(0o600)

    def _load_api_keys_data(self) -> Dict:
        """Lädt vollständige Key-Daten (inkl. Timestamps)"""
        if not self.api_keys_file.exists():
            return {}

        try:
            with open(self.api_keys_file, 'rb') as f:
                encrypted = f.read()

            decrypted = self.cipher.decrypt(encrypted)
            keys_data = json.loads(decrypted.decode())

            # Konvertiere altes Format (nur Strings) zu neuem Format (Dict mit Timestamp)
            for provider, value in keys_data.items():
                if isinstance(value, str):
                    # Altes Format: nur Key als String
                    from datetime import datetime
                    keys_data[provider] = {
                        'key': value,
                        'updated_at': datetime.now().isoformat()  # Zeitstempel für alte Keys
                    }

            return keys_data
        except Exception as e:
            return {}

    def load_api_keys(self) -> Dict[str, str]:
        """
        Lädt gespeicherte API-Keys (ohne Timestamps).

        Returns:
            Dict mit provider -> api_key
        """
        keys_data = self._load_api_keys_data()
        return {provider: data['key'] for provider, data in keys_data.items() if 'key' in data}

    def get_api_key_timestamp(self, provider: str) -> Optional[str]:
        """
        Gibt Zeitstempel der letzten Aktualisierung zurück.

        Returns:
            ISO-Format Zeitstempel oder None
        """
        keys_data = self._load_api_keys_data()
        if provider in keys_data and 'updated_at' in keys_data[provider]:
            return keys_data[provider]['updated_at']
        return None

    def delete_api_key(self, provider: str) -> None:
        """Löscht API-Key für einen Provider"""
        keys_data = self._load_api_keys_data()
        if provider in keys_data:
            del keys_data[provider]

            if keys_data:
                # Speichere verbleibende Keys
                json_data = json.dumps(keys_data)
                encrypted = self.cipher.encrypt(json_data.encode())
                with open(self.api_keys_file, 'wb') as f:
                    f.write(encrypted)
            else:
                # Keine Keys mehr: Lösche Datei
                self.api_keys_file.unlink(missing_ok=True)

    def has_api_key(self, provider: str) -> bool:
        """Prüft ob API-Key für Provider existiert"""
        keys = self.load_api_keys()
        return provider in keys and bool(keys[provider])

    # ==================== AKTENREGISTER ====================

    def _detect_excel_header(self, excel_path: Path, sheet_name: str = 'akten') -> int:
        """
        Erkennt automatisch die Header-Zeile in einer Excel-Datei.

        Returns:
            Header-Zeile (0, 1, oder 2)
        """
        # Versuche verschiedene Header-Zeilen (1, 0, 2) - wie in aktenzeichen_erkennung.py
        for header_row in [1, 0, 2]:
            try:
                df = pd.read_excel(
                    excel_path,
                    sheet_name=sheet_name,
                    header=header_row,
                    engine='openpyxl'
                )

                # Prüfe ob Spalten sinnvoll sind (nicht nur "Unnamed")
                unnamed_count = sum(1 for col in df.columns if str(col).startswith('Unnamed'))
                total_cols = len(df.columns)

                # Wenn weniger als 50% "Unnamed" Spalten, ist es wahrscheinlich der richtige Header
                if total_cols > 0 and unnamed_count < total_cols * 0.5:
                    return header_row
            except Exception:
                continue

        # Fallback: Verwende header=1
        return 1

    def save_aktenregister(self, new_df: pd.DataFrame, merge: bool = True) -> pd.DataFrame:
        """
        Speichert Aktenregister.

        Args:
            new_df: Neues DataFrame
            merge: True = Merge mit vorhandenen Daten, False = Ersetze

        Returns:
            Gespeichertes (ggf. gemergtes) DataFrame
        """
        if merge and self.aktenregister_file.exists():
            # Lade vorhandene Daten mit automatischer Header-Erkennung
            header_row = self._detect_excel_header(self.aktenregister_file)
            existing_df = pd.read_excel(
                self.aktenregister_file,
                sheet_name='akten',
                header=header_row,
                engine='openpyxl'
            )

            # Merge: Neue Zeilen hinzufügen, existierende aktualisieren
            # Annahme: 'Akte' ist der eindeutige Identifier
            if 'Akte' in existing_df.columns and 'Akte' in new_df.columns:
                # Aktualisiere existierende Einträge
                merged_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['Akte'], keep='last')
                merged_df = merged_df.reset_index(drop=True)
            else:
                # Kein Akte-Spalte: Einfach zusammenfügen
                merged_df = pd.concat([existing_df, new_df]).drop_duplicates()
                merged_df = merged_df.reset_index(drop=True)

            result_df = merged_df
        else:
            result_df = new_df

        # Speichere als Excel mit korrektem Format
        with pd.ExcelWriter(self.aktenregister_file, engine='openpyxl') as writer:
            # Leere Zeile als Header (wie Original)
            header_df = pd.DataFrame([[''] * len(result_df.columns)], columns=result_df.columns)
            combined = pd.concat([header_df, result_df], ignore_index=True)
            combined.to_excel(writer, sheet_name='akten', index=False, header=True)

        return result_df

    def load_aktenregister(self) -> Optional[pd.DataFrame]:
        """
        Lädt gespeichertes Aktenregister mit automatischer Header-Erkennung.

        Returns:
            DataFrame oder None wenn nicht vorhanden
        """
        if not self.aktenregister_file.exists():
            return None

        try:
            # Automatische Header-Erkennung
            header_row = self._detect_excel_header(self.aktenregister_file)
            df = pd.read_excel(
                self.aktenregister_file,
                sheet_name='akten',
                header=header_row,
                engine='openpyxl'
            )

            # Prüfe ob Ergebnis sinnvoll ist
            if df.empty:
                return None

            # Entferne "Unnamed" Spalten die komplett leer sind
            unnamed_cols = [col for col in df.columns if str(col).startswith('Unnamed')]
            for col in unnamed_cols:
                if df[col].isna().all():
                    df = df.drop(columns=[col])

            return df
        except Exception as e:
            return None

    def has_aktenregister(self) -> bool:
        """Prüft ob Aktenregister existiert"""
        return self.aktenregister_file.exists()

    def delete_aktenregister(self) -> None:
        """Löscht gespeichertes Aktenregister"""
        self.aktenregister_file.unlink(missing_ok=True)

    def get_aktenregister_stats(self) -> Dict:
        """Gibt Statistiken zum Aktenregister zurück"""
        if not self.has_aktenregister():
            return {'exists': False}

        df = self.load_aktenregister()
        if df is None:
            return {'exists': False}

        return {
            'exists': True,
            'count': len(df),
            'last_modified': self.aktenregister_file.stat().st_mtime
        }

    # ==================== DOKUMENTE ====================

    def save_document(self, document_data: Dict) -> None:
        """
        Speichert Dokument-Metadaten

        Args:
            document_data: Dict mit Dokument-Informationen
        """
        documents_file = self.storage_dir / 'documents.json'

        # Lade vorhandene Dokumente
        documents = []
        if documents_file.exists():
            try:
                with open(documents_file, 'r', encoding='utf-8') as f:
                    documents = json.load(f)
            except:
                documents = []

        # Füge neues Dokument hinzu
        documents.append(document_data)

        # Speichere
        with open(documents_file, 'w', encoding='utf-8') as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)

    def get_all_documents(self) -> list:
        """
        Liefert alle gespeicherten Dokumente

        Returns:
            Liste von Dokument-Dicts
        """
        documents_file = self.storage_dir / 'documents.json'

        if not documents_file.exists():
            return []

        try:
            with open(documents_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def clear_documents(self) -> None:
        """Löscht alle Dokumente"""
        documents_file = self.storage_dir / 'documents.json'
        documents_file.unlink(missing_ok=True)

    # ===== Kürzel-Verwaltung =====

    def get_custom_kuerzel(self) -> Dict[str, str]:
        """
        Lädt benutzerdefinierte Kürzel aus der Datei.

        Returns:
            Dict mit Kürzel -> Name Mapping
        """
        kuerzel_file = self.storage_dir / 'custom_kuerzel.json'
        if not kuerzel_file.exists():
            return {}

        try:
            with open(kuerzel_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def save_custom_kuerzel(self, kuerzel_dict: Dict[str, str]) -> None:
        """
        Speichert benutzerdefinierte Kürzel.

        Args:
            kuerzel_dict: Dict mit Kürzel -> Name Mapping
        """
        kuerzel_file = self.storage_dir / 'custom_kuerzel.json'
        with open(kuerzel_file, 'w', encoding='utf-8') as f:
            json.dump(kuerzel_dict, f, ensure_ascii=False, indent=2)

    def add_kuerzel(self, kuerzel: str, name: str, category: str = "Mitarbeiter") -> bool:
        """
        Fügt ein neues Kürzel hinzu.

        Args:
            kuerzel: Das Kürzel (z.B. "GO")
            name: Der Name (z.B. "Goeser")
            category: Kategorie (z.B. "Mitarbeiter", "Rechtsanwalt", "Notar")

        Returns:
            True bei Erfolg
        """
        kuerzel = kuerzel.upper().strip()
        name = name.strip()

        # Validierung
        if not kuerzel or not name:
            return False

        if len(kuerzel) > 3:
            return False

        # Lade bestehende Kürzel
        kuerzel_dict = self.get_custom_kuerzel()

        # Füge neues Kürzel hinzu
        kuerzel_dict[kuerzel] = {
            'name': name,
            'category': category,
            'created_at': pd.Timestamp.now().isoformat()
        }

        # Speichern
        self.save_custom_kuerzel(kuerzel_dict)
        return True

    def update_kuerzel(self, kuerzel: str, name: str, category: str) -> bool:
        """
        Aktualisiert ein bestehendes Kürzel.

        Args:
            kuerzel: Das Kürzel (z.B. "GO")
            name: Der neue Name
            category: Die neue Kategorie

        Returns:
            True bei Erfolg
        """
        kuerzel = kuerzel.upper().strip()
        kuerzel_dict = self.get_custom_kuerzel()

        if kuerzel not in kuerzel_dict:
            return False

        kuerzel_dict[kuerzel]['name'] = name.strip()
        kuerzel_dict[kuerzel]['category'] = category
        kuerzel_dict[kuerzel]['updated_at'] = pd.Timestamp.now().isoformat()

        self.save_custom_kuerzel(kuerzel_dict)
        return True

    def delete_kuerzel(self, kuerzel: str) -> bool:
        """
        Löscht ein Kürzel.

        Args:
            kuerzel: Das zu löschende Kürzel

        Returns:
            True bei Erfolg
        """
        kuerzel = kuerzel.upper().strip()
        kuerzel_dict = self.get_custom_kuerzel()

        if kuerzel not in kuerzel_dict:
            return False

        del kuerzel_dict[kuerzel]
        self.save_custom_kuerzel(kuerzel_dict)
        return True

    def get_all_kuerzel_with_names(self) -> Dict[str, Dict[str, str]]:
        """
        Gibt alle Kürzel mit Namen und Kategorien zurück.

        Returns:
            Dict mit Kürzel -> {name, category} Mapping
        """
        return self.get_custom_kuerzel()

    # ==================== RENO-ZUORDNUNGEN ====================

    def get_reno_zuordnungen(self) -> Dict[str, list]:
        """
        Lädt RENO-Zuordnungen (Empfänger für Sachbearbeiter).
        Falls keine gespeichert, werden Standardwerte aus EmailSender verwendet.

        Returns:
            Dict mit Sachbearbeiter-Kürzel -> Liste von {name, email}
        """
        reno_file = self.storage_dir / 'reno_zuordnungen.json'

        if reno_file.exists():
            try:
                with open(reno_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        # Fallback: Standardwerte aus email_sender
        from email_sender import EmailSender
        return EmailSender.RENO_ZUORDNUNGEN.copy()

    def save_reno_zuordnungen(self, zuordnungen: Dict[str, list]) -> None:
        """
        Speichert RENO-Zuordnungen.

        Args:
            zuordnungen: Dict mit Sachbearbeiter-Kürzel -> Liste von {name, email}
        """
        reno_file = self.storage_dir / 'reno_zuordnungen.json'

        with open(reno_file, 'w', encoding='utf-8') as f:
            json.dump(zuordnungen, f, ensure_ascii=False, indent=2)

    def add_reno_zu_sachbearbeiter(self, sachbearbeiter: str, name: str, email: str) -> bool:
        """
        Fügt einen RENO zu einem Sachbearbeiter hinzu.

        Args:
            sachbearbeiter: Kürzel des Sachbearbeiters (z.B. 'SQ')
            name: Name des RENo
            email: Email-Adresse des RENO

        Returns:
            True bei Erfolg, False wenn bereits vorhanden
        """
        zuordnungen = self.get_reno_zuordnungen()

        if sachbearbeiter not in zuordnungen:
            zuordnungen[sachbearbeiter] = []

        # Prüfe ob Email bereits vorhanden
        for reno in zuordnungen[sachbearbeiter]:
            if reno['email'].lower() == email.lower():
                return False

        zuordnungen[sachbearbeiter].append({'name': name, 'email': email})
        self.save_reno_zuordnungen(zuordnungen)
        return True

    def remove_reno_von_sachbearbeiter(self, sachbearbeiter: str, email: str) -> bool:
        """
        Entfernt einen RENO von einem Sachbearbeiter.

        Args:
            sachbearbeiter: Kürzel des Sachbearbeiters
            email: Email-Adresse des zu entfernenden RENO

        Returns:
            True bei Erfolg, False wenn nicht gefunden
        """
        zuordnungen = self.get_reno_zuordnungen()

        if sachbearbeiter not in zuordnungen:
            return False

        original_length = len(zuordnungen[sachbearbeiter])
        zuordnungen[sachbearbeiter] = [
            reno for reno in zuordnungen[sachbearbeiter]
            if reno['email'].lower() != email.lower()
        ]

        if len(zuordnungen[sachbearbeiter]) == original_length:
            return False

        self.save_reno_zuordnungen(zuordnungen)
        return True

    def get_alle_renos(self) -> list:
        """
        Gibt eine deduplizierte Liste aller RENOs zurück.

        Returns:
            Liste von {name, email} Dicts
        """
        zuordnungen = self.get_reno_zuordnungen()
        seen_emails = set()
        alle_renos = []

        for renos in zuordnungen.values():
            for reno in renos:
                if reno['email'].lower() not in seen_emails:
                    seen_emails.add(reno['email'].lower())
                    alle_renos.append(reno)

        return sorted(alle_renos, key=lambda x: x['name'])
