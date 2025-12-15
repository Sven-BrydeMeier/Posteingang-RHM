"""
Browser-Benachrichtigungen (Web Push API)

Features:
- Browser-Detection (Chrome, Firefox, Safari, Edge)
- Push-Benachrichtigungen
- Subscription-Management
- Benachrichtigung bei Post-Eingang
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class BrowserNotificationManager:
    """Verwaltet Browser-Benachrichtigungen"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Browser-Notification-Manager

        Args:
            storage_dir: Storage-Verzeichnis
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.subscriptions_file = self.storage_dir / "push_subscriptions.json"
        self.subscriptions = self._load_subscriptions()

    def _load_subscriptions(self) -> Dict:
        """Lädt Push-Subscriptions"""
        if self.subscriptions_file.exists():
            try:
                with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_subscriptions(self):
        """Speichert Subscriptions"""
        try:
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump(self.subscriptions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")

    def get_browser_support_script(self) -> str:
        """
        Liefert JavaScript für Browser-Detection und Push-Setup

        Returns:
            JavaScript-Code
        """
        return """
<script>
// Browser-Detection
function detectBrowser() {
    const userAgent = navigator.userAgent;

    if (userAgent.includes('Chrome') && !userAgent.includes('Edg')) {
        return 'Chrome';
    } else if (userAgent.includes('Firefox')) {
        return 'Firefox';
    } else if (userAgent.includes('Safari') && !userAgent.includes('Chrome')) {
        return 'Safari';
    } else if (userAgent.includes('Edg')) {
        return 'Edge';
    }
    return 'Unknown';
}

// Prüfe ob Push-Notifications unterstützt werden
function isPushSupported() {
    return 'Notification' in window &&
           'serviceWorker' in navigator &&
           'PushManager' in window;
}

// Request Permission
async function requestNotificationPermission() {
    if (!isPushSupported()) {
        console.log('Push-Benachrichtigungen nicht unterstützt');
        return false;
    }

    try {
        const permission = await Notification.requestPermission();

        if (permission === 'granted') {
            console.log('Benachrichtigungen aktiviert');

            // Zeige Test-Benachrichtigung
            new Notification('RHM Posteingang', {
                body: 'Benachrichtigungen wurden aktiviert!',
                icon: '/favicon.ico',
                badge: '/favicon.ico'
            });

            return true;
        } else {
            console.log('Benachrichtigungen abgelehnt');
            return false;
        }
    } catch (error) {
        console.error('Fehler beim Aktivieren:', error);
        return false;
    }
}

// Sende Benachrichtigung
function sendBrowserNotification(title, body, data = {}) {
    if (!isPushSupported()) {
        return;
    }

    if (Notification.permission === 'granted') {
        const notification = new Notification(title, {
            body: body,
            icon: '/favicon.ico',
            badge: '/favicon.ico',
            tag: 'rhm-post',
            requireInteraction: true,
            data: data
        });

        notification.onclick = function(event) {
            event.preventDefault();
            window.focus();
            notification.close();
        };
    }
}

// Speichere Browser-Info
function getBrowserInfo() {
    return {
        browser: detectBrowser(),
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
        supported: isPushSupported(),
        permission: Notification.permission
    };
}

// Export für Streamlit
window.RHM = {
    detectBrowser: detectBrowser,
    isPushSupported: isPushSupported,
    requestNotificationPermission: requestNotificationPermission,
    sendBrowserNotification: sendBrowserNotification,
    getBrowserInfo: getBrowserInfo
};

console.log('RHM Browser-Notifications geladen');
console.log('Browser:', detectBrowser());
console.log('Push unterstützt:', isPushSupported());
</script>
"""

    def register_subscription(self, user_id: str, subscription_data: Dict):
        """
        Registriert Push-Subscription

        Args:
            user_id: Benutzer-ID
            subscription_data: Subscription-Daten
        """
        self.subscriptions[user_id] = {
            'user_id': user_id,
            'subscription': subscription_data,
            'created_at': datetime.now().isoformat(),
            'browser': subscription_data.get('browser', 'Unknown'),
            'active': True
        }

        self._save_subscriptions()

    def unregister_subscription(self, user_id: str):
        """Deaktiviert Subscription"""
        if user_id in self.subscriptions:
            self.subscriptions[user_id]['active'] = False
            self._save_subscriptions()

    def get_active_subscriptions(self) -> List[Dict]:
        """Liefert alle aktiven Subscriptions"""
        return [s for s in self.subscriptions.values() if s.get('active', False)]

    def get_user_subscription(self, user_id: str) -> Optional[Dict]:
        """Liefert Subscription eines Benutzers"""
        return self.subscriptions.get(user_id)

    def send_notification_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> bool:
        """
        Sendet Benachrichtigung an Benutzer

        Args:
            user_id: Benutzer-ID
            title: Titel
            body: Nachricht
            data: Zusätzliche Daten

        Returns:
            True bei Erfolg
        """
        subscription = self.get_user_subscription(user_id)

        if not subscription or not subscription.get('active'):
            return False

        # Für Web-Push würde man hier pywebpush verwenden
        # Vereinfachte Implementierung - speichere Benachrichtigung
        notification = {
            'user_id': user_id,
            'title': title,
            'body': body,
            'data': data or {},
            'sent_at': datetime.now().isoformat(),
            'read': False
        }

        # In Produktion: Web Push API verwenden
        # from pywebpush import webpush
        # webpush(subscription['subscription'], ...)

        print(f"📧 Benachrichtigung an {user_id}: {title}")
        return True

    def send_notification_to_role(
        self,
        role: str,
        title: str,
        body: str,
        user_manager,
        data: Optional[Dict] = None
    ):
        """
        Sendet Benachrichtigung an alle Benutzer einer Rolle

        Args:
            role: Rolle
            title: Titel
            body: Nachricht
            user_manager: UserManager-Instanz
            data: Zusätzliche Daten
        """
        users = user_manager.get_users_by_role(role)

        for user in users:
            if user.get('browser_notifications_enabled'):
                self.send_notification_to_user(
                    user['id'],
                    title,
                    body,
                    data
                )

    def get_notification_stats(self) -> Dict:
        """Liefert Statistiken"""
        active = len([s for s in self.subscriptions.values() if s.get('active')])

        browsers = {}
        for sub in self.subscriptions.values():
            if sub.get('active'):
                browser = sub.get('browser', 'Unknown')
                browsers[browser] = browsers.get(browser, 0) + 1

        return {
            'total_subscriptions': len(self.subscriptions),
            'active_subscriptions': active,
            'by_browser': browsers
        }
