"""
Benutzer-Management System

Features:
- Benutzerrollen: Admin, Empfang, Rechtsanwalt, Sachbearbeiter
- Benutzerverwaltung (CRUD)
- Passwort-Hashing (bcrypt)
- Einladungs-Token
- Session-Management
"""

import json
import hashlib
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

# bcrypt optional - Fallback auf SHA256 wenn nicht verfügbar
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    print("⚠️ bcrypt nicht installiert - verwende SHA256 (weniger sicher!)")
    print("   Installiere mit: pip install bcrypt")


class UserRole(Enum):
    """Benutzer-Rollen"""
    ADMIN = "Administrator"
    EMPFANG = "Empfang"
    RECHTSANWALT = "Rechtsanwalt"
    SACHBEARBEITER = "Sachbearbeiter"


class UserManager:
    """Verwaltet Benutzer und Authentifizierung"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert User-Manager

        Args:
            storage_dir: Storage-Verzeichnis
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.users_file = self.storage_dir / "users.json"
        self.invitations_file = self.storage_dir / "invitations.json"
        self.sessions_file = self.storage_dir / "sessions.json"
        self.password_reset_file = self.storage_dir / "password_resets.json"

        # Lade Daten
        self.users = self._load_users()
        self.invitations = self._load_invitations()
        self.sessions = self._load_sessions()
        self.password_resets = self._load_password_resets()

        # Erstelle Default-Benutzer (Admin + Empfang) wenn keine Benutzer vorhanden
        if not self.users:
            self._create_default_users()

    def _load_users(self) -> Dict:
        """Lädt Benutzer"""
        if self.users_file.exists():
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_users(self):
        """Speichert Benutzer"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Benutzer: {e}")

    def _load_invitations(self) -> Dict:
        """Lädt Einladungen"""
        if self.invitations_file.exists():
            try:
                with open(self.invitations_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_invitations(self):
        """Speichert Einladungen"""
        try:
            with open(self.invitations_file, 'w', encoding='utf-8') as f:
                json.dump(self.invitations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Einladungen: {e}")

    def _load_sessions(self) -> Dict:
        """Lädt Sessions"""
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_sessions(self):
        """Speichert Sessions"""
        try:
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Sessions: {e}")

    def _load_password_resets(self) -> Dict:
        """Lädt Passwort-Reset-Anfragen"""
        if self.password_reset_file.exists():
            try:
                with open(self.password_reset_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_password_resets(self):
        """Speichert Passwort-Reset-Anfragen"""
        try:
            with open(self.password_reset_file, 'w', encoding='utf-8') as f:
                json.dump(self.password_resets, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")

    def _create_default_users(self):
        """Erstellt Default-Benutzer (Admin + Empfang)"""

        # Admin-Benutzer
        admin_password = "admin123"
        self.create_user(
            email="admin@rhm-kanzlei.de",
            password=admin_password,
            role=UserRole.ADMIN.value,
            name="Administrator",
            kuerzel="ADMIN"
        )

        # Empfang-Benutzer (Demo-Zugang)
        empfang_password = "empfang123"
        self.create_user(
            email="empfang@rhm-kanzlei.de",
            password=empfang_password,
            role=UserRole.EMPFANG.value,
            name="Empfang",
            kuerzel="EMPFANG"
        )

        print("⚠️ Default-Benutzer erstellt:")
        print("")
        print("   👤 ADMIN:")
        print("      Email: admin@rhm-kanzlei.de")
        print("      Passwort: admin123")
        print("")
        print("   📬 EMPFANG (Demo):")
        print("      Email: empfang@rhm-kanzlei.de")
        print("      Passwort: empfang123")
        print("")
        print("   ⚠️ BITTE BEIDE PASSWÖRTER SOFORT ÄNDERN!")

    def _hash_password(self, password: str) -> str:
        """Hasht Passwort mit bcrypt (oder SHA256 als Fallback)"""
        if BCRYPT_AVAILABLE:
            # bcrypt (sicher)
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        else:
            # Fallback: SHA256 (NICHT SICHER für Produktion!)
            return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verifiziert Passwort"""
        if BCRYPT_AVAILABLE and hashed.startswith('$2'):
            # bcrypt hash (erkennbar an $2a/$2b/$2y prefix)
            try:
                return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
            except:
                return False
        else:
            # SHA256 Fallback
            return hashlib.sha256(password.encode()).hexdigest() == hashed

    def create_user(
        self,
        email: str,
        password: str,
        role: str,
        name: str,
        kuerzel: str,
        created_by: Optional[str] = None
    ) -> bool:
        """
        Erstellt neuen Benutzer

        Args:
            email: Email-Adresse
            password: Passwort
            role: Rolle
            name: Vollständiger Name
            kuerzel: Kürzel (z.B. SQ, TS)
            created_by: Email des Erstellers

        Returns:
            True bei Erfolg
        """
        # Prüfe ob Email bereits existiert
        if email.lower() in [u['email'].lower() for u in self.users.values()]:
            return False

        user_id = hashlib.md5(f"{email}_{datetime.now().isoformat()}".encode()).hexdigest()

        self.users[user_id] = {
            'id': user_id,
            'email': email.lower(),
            'password_hash': self._hash_password(password),
            'role': role,
            'name': name,
            'kuerzel': kuerzel.upper(),
            'created_at': datetime.now().isoformat(),
            'created_by': created_by,
            'last_login': None,
            'active': True,
            'browser_notifications_enabled': False,
            'notification_token': None
        }

        self._save_users()
        return True

    def authenticate(self, email: str, password: str) -> Optional[Dict]:
        """
        Authentifiziert Benutzer

        Args:
            email: Email
            password: Passwort

        Returns:
            Benutzer-Dict bei Erfolg, None bei Fehler
        """
        for user in self.users.values():
            if user['email'].lower() == email.lower():
                if user['active'] and self._verify_password(password, user['password_hash']):
                    # Update last_login
                    user['last_login'] = datetime.now().isoformat()
                    self._save_users()
                    return user

        return None

    def create_session(self, user_id: str) -> str:
        """
        Erstellt Session für Benutzer

        Args:
            user_id: Benutzer-ID

        Returns:
            Session-Token
        """
        session_token = secrets.token_urlsafe(32)

        self.sessions[session_token] = {
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=7)).isoformat()
        }

        self._save_sessions()
        return session_token

    def validate_session(self, session_token: str) -> Optional[Dict]:
        """
        Validiert Session

        Args:
            session_token: Session-Token

        Returns:
            Benutzer-Dict bei gültiger Session, None sonst
        """
        if session_token not in self.sessions:
            return None

        session = self.sessions[session_token]
        expires_at = datetime.fromisoformat(session['expires_at'])

        # Prüfe ob abgelaufen
        if datetime.now() > expires_at:
            del self.sessions[session_token]
            self._save_sessions()
            return None

        # Hole Benutzer
        user_id = session['user_id']
        user = self.users.get(user_id)

        if user and user['active']:
            return user

        return None

    def logout(self, session_token: str):
        """Löscht Session"""
        if session_token in self.sessions:
            del self.sessions[session_token]
            self._save_sessions()

    def create_invitation(
        self,
        email: str,
        role: str,
        created_by: str,
        name: str = "",
        kuerzel: str = ""
    ) -> str:
        """
        Erstellt Einladungs-Link

        Args:
            email: Email des einzuladenden Benutzers
            role: Rolle
            created_by: Email des Erstellers
            name: Name (optional)
            kuerzel: Kürzel (optional)

        Returns:
            Einladungs-Token
        """
        invitation_token = secrets.token_urlsafe(32)

        self.invitations[invitation_token] = {
            'token': invitation_token,
            'email': email.lower(),
            'role': role,
            'name': name,
            'kuerzel': kuerzel,
            'created_by': created_by,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=7)).isoformat(),
            'used': False
        }

        self._save_invitations()
        return invitation_token

    def validate_invitation(self, token: str) -> Optional[Dict]:
        """
        Validiert Einladungs-Token

        Args:
            token: Einladungs-Token

        Returns:
            Einladungs-Dict bei gültigkeit, None sonst
        """
        if token not in self.invitations:
            return None

        invitation = self.invitations[token]

        # Prüfe ob bereits verwendet
        if invitation['used']:
            return None

        # Prüfe Ablaufdatum
        expires_at = datetime.fromisoformat(invitation['expires_at'])
        if datetime.now() > expires_at:
            return None

        return invitation

    def accept_invitation(self, token: str, password: str) -> bool:
        """
        Akzeptiert Einladung und erstellt Benutzer

        Args:
            token: Einladungs-Token
            password: Gewähltes Passwort

        Returns:
            True bei Erfolg
        """
        invitation = self.validate_invitation(token)
        if not invitation:
            return False

        # Erstelle Benutzer
        success = self.create_user(
            email=invitation['email'],
            password=password,
            role=invitation['role'],
            name=invitation['name'],
            kuerzel=invitation['kuerzel'],
            created_by=invitation['created_by']
        )

        if success:
            # Markiere Einladung als verwendet
            invitation['used'] = True
            invitation['used_at'] = datetime.now().isoformat()
            self._save_invitations()

        return success

    def request_password_reset(self, email: str) -> str:
        """
        Erstellt Passwort-Reset-Anfrage

        Args:
            email: Email des Benutzers

        Returns:
            Reset-Token
        """
        # Prüfe ob Benutzer existiert
        user = None
        for u in self.users.values():
            if u['email'].lower() == email.lower():
                user = u
                break

        if not user:
            return ""

        reset_token = secrets.token_urlsafe(32)

        self.password_resets[reset_token] = {
            'token': reset_token,
            'user_id': user['id'],
            'email': email.lower(),
            'requested_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=24)).isoformat(),
            'used': False
        }

        self._save_password_resets()
        return reset_token

    def reset_password(self, token: str, new_password: str) -> bool:
        """
        Setzt Passwort zurück (nur von Admin)

        Args:
            token: Reset-Token
            new_password: Neues Passwort

        Returns:
            True bei Erfolg
        """
        if token not in self.password_resets:
            return False

        reset = self.password_resets[token]

        # Prüfe ob bereits verwendet
        if reset['used']:
            return False

        # Prüfe Ablauf
        expires_at = datetime.fromisoformat(reset['expires_at'])
        if datetime.now() > expires_at:
            return False

        # Update Passwort
        user_id = reset['user_id']
        if user_id in self.users:
            self.users[user_id]['password_hash'] = self._hash_password(new_password)
            self._save_users()

            # Markiere als verwendet
            reset['used'] = True
            reset['used_at'] = datetime.now().isoformat()
            self._save_password_resets()

            return True

        return False

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Holt Benutzer nach Email"""
        for user in self.users.values():
            if user['email'].lower() == email.lower():
                return user
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Holt Benutzer nach ID"""
        return self.users.get(user_id)

    def get_users_by_role(self, role: str) -> List[Dict]:
        """Holt alle Benutzer einer Rolle"""
        return [u for u in self.users.values() if u['role'] == role and u['active']]

    def get_all_users(self) -> List[Dict]:
        """Holt alle Benutzer"""
        return list(self.users.values())

    def update_browser_notification_settings(self, user_id: str, enabled: bool, token: Optional[str] = None):
        """Aktualisiert Browser-Benachrichtigungs-Einstellungen"""
        if user_id in self.users:
            self.users[user_id]['browser_notifications_enabled'] = enabled
            if token:
                self.users[user_id]['notification_token'] = token
            self._save_users()

    def deactivate_user(self, user_id: str) -> bool:
        """Deaktiviert Benutzer"""
        if user_id in self.users:
            self.users[user_id]['active'] = False
            self._save_users()
            return True
        return False

    def activate_user(self, user_id: str) -> bool:
        """Aktiviert Benutzer"""
        if user_id in self.users:
            self.users[user_id]['active'] = True
            self._save_users()
            return True
        return False

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Ändert Passwort (mit Verifizierung)"""
        if user_id not in self.users:
            return False

        user = self.users[user_id]

        # Verifiziere altes Passwort
        if not self._verify_password(old_password, user['password_hash']):
            return False

        # Setze neues Passwort
        user['password_hash'] = self._hash_password(new_password)
        self._save_users()
        return True

    def get_pending_password_resets(self) -> List[Dict]:
        """Holt offene Passwort-Reset-Anfragen"""
        pending = []
        for reset in self.password_resets.values():
            if not reset['used']:
                expires_at = datetime.fromisoformat(reset['expires_at'])
                if datetime.now() <= expires_at:
                    pending.append(reset)
        return pending
