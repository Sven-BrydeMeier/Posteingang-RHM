"""
Hot Folder / Ordner-Überwachung für automatische PDF-Verarbeitung

Features:
- Überwacht Verzeichnis auf neue PDF-Dateien
- Automatische Verarbeitung bei Änderungen
- Verschiebung in processed/error Ordner
- Parallele Verarbeitung mehrerer Dateien
- Status-Logging
"""

import time
import shutil
from pathlib import Path
from typing import Callable, Optional, Dict, List
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
import threading
import queue


class PDFFileHandler(FileSystemEventHandler):
    """Handler für PDF-Datei-Events"""

    def __init__(self, processing_queue: queue.Queue):
        """
        Initialisiert Handler

        Args:
            processing_queue: Queue für zu verarbeitende Dateien
        """
        super().__init__()
        self.processing_queue = processing_queue
        self.processing_files = set()  # Verhindere Doppel-Verarbeitung

    def on_created(self, event):
        """Wird aufgerufen wenn neue Datei erstellt wird"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Nur PDF-Dateien
        if file_path.suffix.lower() != '.pdf':
            return

        # Verhindere Doppel-Verarbeitung
        if str(file_path) in self.processing_files:
            return

        # Warte kurz um sicherzustellen dass Datei vollständig kopiert wurde
        time.sleep(1)

        # Prüfe ob Datei noch existiert und nicht leer ist
        if file_path.exists() and file_path.stat().st_size > 0:
            self.processing_files.add(str(file_path))
            self.processing_queue.put(file_path)

    def on_modified(self, event):
        """Wird aufgerufen wenn Datei geändert wird"""
        # Behandle wie created (für manche Kopiervorgänge)
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix.lower() == '.pdf' and str(file_path) not in self.processing_files:
                time.sleep(0.5)
                if file_path.exists() and file_path.stat().st_size > 0:
                    self.processing_files.add(str(file_path))
                    self.processing_queue.put(file_path)


class HotFolderWatcher:
    """Überwacht Hot Folder und verarbeitet PDFs automatisch"""

    def __init__(
        self,
        watch_folder: Path,
        processed_folder: Optional[Path] = None,
        error_folder: Optional[Path] = None,
        storage_dir: Optional[Path] = None
    ):
        """
        Initialisiert Hot Folder Watcher

        Args:
            watch_folder: Zu überwachendes Verzeichnis
            processed_folder: Ziel für verarbeitete Dateien
            error_folder: Ziel für fehlerhafte Dateien
            storage_dir: Storage-Verzeichnis für Logs
        """
        self.watch_folder = Path(watch_folder)
        self.watch_folder.mkdir(parents=True, exist_ok=True)

        # Standard-Unterordner
        self.processed_folder = Path(processed_folder) if processed_folder else (self.watch_folder / "processed")
        self.error_folder = Path(error_folder) if error_folder else (self.watch_folder / "error")

        self.processed_folder.mkdir(parents=True, exist_ok=True)
        self.error_folder.mkdir(parents=True, exist_ok=True)

        # Storage für Logs
        self.storage_dir = Path(storage_dir) if storage_dir else Path(".")
        self.log_file = self.storage_dir / "hot_folder_log.jsonl"

        # Queue für Verarbeitung
        self.processing_queue = queue.Queue()

        # Watchdog Observer
        self.observer = None
        self.event_handler = None

        # Processing callback
        self.process_callback = None

        # Worker Thread
        self.worker_thread = None
        self.running = False

        # Statistiken
        self.stats = {
            'processed': 0,
            'errors': 0,
            'started_at': None
        }

    def set_process_callback(self, callback: Callable[[Path], Dict]):
        """
        Setzt Callback-Funktion für PDF-Verarbeitung

        Args:
            callback: Funktion die PDF verarbeitet und Dict zurückgibt
                     Format: {'success': bool, 'message': str, 'data': dict}
        """
        self.process_callback = callback

    def _log_event(self, event_type: str, file_path: Path, status: str, message: str = ""):
        """Loggt Event in JSONL-Datei"""
        import json

        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'file': str(file_path.name),
            'status': status,
            'message': message
        }

        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"Fehler beim Loggen: {e}")

    def _worker(self):
        """Worker Thread für Datei-Verarbeitung"""
        while self.running:
            try:
                # Hole Datei aus Queue (mit Timeout)
                try:
                    file_path = self.processing_queue.get(timeout=1)
                except queue.Empty:
                    continue

                print(f"[Hot Folder] Verarbeite: {file_path.name}")
                self._log_event('processing', file_path, 'started')

                # Verarbeite Datei
                success = False
                message = ""

                try:
                    if self.process_callback:
                        result = self.process_callback(file_path)
                        success = result.get('success', False)
                        message = result.get('message', '')
                    else:
                        # Fallback: Nur verschieben ohne Verarbeitung
                        success = True
                        message = "Keine Verarbeitungs-Callback definiert"

                except Exception as e:
                    success = False
                    message = f"Fehler bei Verarbeitung: {str(e)}"

                # Verschiebe Datei
                try:
                    if success:
                        target_folder = self.processed_folder
                        self.stats['processed'] += 1
                        status = 'success'
                    else:
                        target_folder = self.error_folder
                        self.stats['errors'] += 1
                        status = 'error'

                    # Erstelle Zieldatei mit Timestamp
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    target_name = f"{timestamp}_{file_path.name}"
                    target_path = target_folder / target_name

                    # Verschiebe
                    shutil.move(str(file_path), str(target_path))

                    self._log_event('processing', file_path, status, message)
                    print(f"[Hot Folder] ✓ {file_path.name} → {target_folder.name}/")

                except Exception as e:
                    self._log_event('processing', file_path, 'error', f"Fehler beim Verschieben: {str(e)}")
                    print(f"[Hot Folder] ✗ Fehler: {str(e)}")

                finally:
                    self.processing_queue.task_done()

            except Exception as e:
                print(f"[Hot Folder] Worker-Fehler: {str(e)}")

    def start(self):
        """Startet Überwachung"""
        if self.running:
            return False

        print(f"[Hot Folder] Starte Überwachung: {self.watch_folder}")

        self.running = True
        self.stats['started_at'] = datetime.now().isoformat()

        # Starte Worker Thread
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

        # Starte Watchdog Observer
        self.event_handler = PDFFileHandler(self.processing_queue)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.watch_folder), recursive=False)
        self.observer.start()

        self._log_event('watcher', self.watch_folder, 'started')

        return True

    def stop(self):
        """Stoppt Überwachung"""
        if not self.running:
            return False

        print(f"[Hot Folder] Stoppe Überwachung...")

        self.running = False

        # Stoppe Observer
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)

        # Warte auf Worker Thread
        if self.worker_thread:
            self.worker_thread.join(timeout=5)

        self._log_event('watcher', self.watch_folder, 'stopped')

        print(f"[Hot Folder] Gestoppt. Verarbeitet: {self.stats['processed']}, Fehler: {self.stats['errors']}")

        return True

    def is_running(self) -> bool:
        """Prüft ob Watcher läuft"""
        return self.running

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken

        Returns:
            Dict mit Statistiken
        """
        stats = self.stats.copy()
        stats['is_running'] = self.running
        stats['queue_size'] = self.processing_queue.qsize()
        stats['watch_folder'] = str(self.watch_folder)
        stats['processed_folder'] = str(self.processed_folder)
        stats['error_folder'] = str(self.error_folder)

        return stats

    def get_recent_logs(self, count: int = 50) -> List[Dict]:
        """
        Liefert letzte Log-Einträge

        Args:
            count: Anzahl Einträge

        Returns:
            Liste von Log-Events
        """
        import json

        logs = []

        if not self.log_file.exists():
            return logs

        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Letzte N Zeilen
            for line in lines[-count:]:
                try:
                    logs.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            print(f"Fehler beim Lesen der Logs: {e}")

        return logs

    def process_existing_files(self):
        """
        Verarbeitet bereits vorhandene PDF-Dateien im Watch-Folder

        Returns:
            Anzahl gefundener Dateien
        """
        pdf_files = list(self.watch_folder.glob("*.pdf"))

        for pdf_file in pdf_files:
            if str(pdf_file) not in self.event_handler.processing_files:
                self.event_handler.processing_files.add(str(pdf_file))
                self.processing_queue.put(pdf_file)

        return len(pdf_files)

    def clear_processed_folder(self, days_old: int = 30):
        """
        Löscht alte Dateien aus processed-Ordner

        Args:
            days_old: Dateien älter als X Tage

        Returns:
            Anzahl gelöschter Dateien
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted_count = 0

        for file_path in self.processed_folder.glob("*.pdf"):
            try:
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_date:
                    file_path.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"Fehler beim Löschen von {file_path}: {e}")

        return deleted_count
