"""
Volltext-Suche über alle verarbeiteten Dokumente

Features:
- Whoosh-basierte Volltext-Indexierung
- Suche über Text, Aktenzeichen, Sachbearbeiter, etc.
- Fuzzy-Suche
- Filter nach Datum, Priorität, etc.
- Highlighting von Suchtreffern
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import shutil


class FulltextSearch:
    """Volltext-Suche über Dokumente"""

    def __init__(self, storage_dir: Path):
        """
        Initialisiert Volltext-Suche

        Args:
            storage_dir: Storage-Verzeichnis
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.index_dir = self.storage_dir / "search_index"
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.whoosh_available = False
        self.ix = None
        self.schema = None

        # Versuche Whoosh zu importieren
        try:
            from whoosh.fields import Schema, TEXT, ID, DATETIME, KEYWORD
            from whoosh.index import create_in, open_dir, exists_in
            from whoosh.qparser import QueryParser, MultifieldParser
            from whoosh.query import FuzzyTerm

            self.whoosh_available = True

            # Definiere Schema
            self.schema = Schema(
                doc_id=ID(stored=True, unique=True),
                dateiname=TEXT(stored=True),
                text=TEXT(stored=True),
                aktenzeichen=TEXT(stored=True),
                sachbearbeiter=KEYWORD(stored=True),
                mandant=TEXT(stored=True),
                gegner=TEXT(stored=True),
                absender=TEXT(stored=True),
                datum=DATETIME(stored=True),
                priority=KEYWORD(stored=True),
                stichworte=KEYWORD(stored=True, commas=True),
                verarbeitet_am=DATETIME(stored=True)
            )

            # Erstelle oder öffne Index
            if exists_in(str(self.index_dir)):
                self.ix = open_dir(str(self.index_dir))
            else:
                self.ix = create_in(str(self.index_dir), self.schema)

        except ImportError:
            print("Whoosh nicht installiert. Installiere mit: pip install whoosh")
            self.whoosh_available = False

    def is_available(self) -> bool:
        """Prüft ob Whoosh verfügbar ist"""
        return self.whoosh_available

    def index_document(self, document_info: Dict, text: str) -> bool:
        """
        Indexiert Dokument für Suche

        Args:
            document_info: Dokument-Informationen
            text: Volltext des Dokuments

        Returns:
            True bei Erfolg
        """
        if not self.whoosh_available:
            return False

        try:
            from whoosh.writing import AsyncWriter

            # Extrahiere Informationen
            doc_id = document_info.get('dateiname', str(datetime.now().timestamp()))
            dateiname = document_info.get('dateiname', '')
            aktenzeichen = document_info.get('aktenzeichen_info', {}).get('internes_az', '')
            sachbearbeiter = document_info.get('sachbearbeiter', '')

            analyse = document_info.get('analyse', {})
            mandant = analyse.get('mandant', '')
            gegner = analyse.get('gegner', '')
            absender = analyse.get('absender', '')
            stichworte = ', '.join(analyse.get('stichworte', []))

            # Datum parsen
            datum_str = analyse.get('datum', '')
            try:
                for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d.%m.%y']:
                    try:
                        datum = datetime.strptime(datum_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    datum = datetime.now()
            except:
                datum = datetime.now()

            # Priorität
            deadline_info = analyse.get('deadline_info', {})
            priority = deadline_info.get('priority', 'NORMAL')

            # Indexiere
            writer = AsyncWriter(self.ix)

            writer.update_document(
                doc_id=doc_id,
                dateiname=dateiname,
                text=text[:50000],  # Limitiere Text-Länge
                aktenzeichen=aktenzeichen,
                sachbearbeiter=sachbearbeiter,
                mandant=mandant,
                gegner=gegner,
                absender=absender,
                datum=datum,
                priority=priority,
                stichworte=stichworte,
                verarbeitet_am=datetime.now()
            )

            writer.commit()

            return True

        except Exception as e:
            print(f"Fehler beim Indexieren: {e}")
            return False

    def search(
        self,
        query_string: str,
        limit: int = 50,
        fuzzy: bool = False,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Durchsucht Dokumente

        Args:
            query_string: Suchbegriff
            limit: Maximale Anzahl Ergebnisse
            fuzzy: Fuzzy-Suche aktivieren
            filters: Optional Filter (sachbearbeiter, priority, etc.)

        Returns:
            Liste von Suchergebnissen
        """
        if not self.whoosh_available:
            return []

        try:
            from whoosh.qparser import QueryParser, MultifieldParser
            from whoosh import scoring

            results = []

            with self.ix.searcher(weighting=scoring.BM25F()) as searcher:
                # Multi-Field-Suche
                fields = ['text', 'dateiname', 'aktenzeichen', 'mandant', 'gegner', 'absender', 'stichworte']
                parser = MultifieldParser(fields, schema=self.schema)

                # Parse Query
                if fuzzy:
                    query_string = ' '.join([f"{term}~" for term in query_string.split()])

                query = parser.parse(query_string)

                # Suche
                hits = searcher.search(query, limit=limit)

                for hit in hits:
                    result = {
                        'doc_id': hit['doc_id'],
                        'dateiname': hit['dateiname'],
                        'aktenzeichen': hit['aktenzeichen'],
                        'sachbearbeiter': hit['sachbearbeiter'],
                        'mandant': hit['mandant'],
                        'gegner': hit['gegner'],
                        'absender': hit['absender'],
                        'datum': hit['datum'].strftime('%d.%m.%Y') if hit['datum'] else '',
                        'priority': hit['priority'],
                        'stichworte': hit['stichworte'],
                        'score': hit.score,
                        'excerpt': hit.highlights('text', top=3)  # Text-Auszug mit Highlighting
                    }

                    # Prüfe Filter
                    if filters:
                        if 'sachbearbeiter' in filters and result['sachbearbeiter'] != filters['sachbearbeiter']:
                            continue
                        if 'priority' in filters and result['priority'] != filters['priority']:
                            continue
                        # Weitere Filter können hier hinzugefügt werden

                    results.append(result)

            return results

        except Exception as e:
            print(f"Fehler bei Suche: {e}")
            return []

    def search_by_aktenzeichen(self, aktenzeichen: str) -> List[Dict]:
        """
        Sucht alle Dokumente zu einem Aktenzeichen

        Args:
            aktenzeichen: Aktenzeichen

        Returns:
            Liste von Dokumenten
        """
        if not self.whoosh_available:
            return []

        try:
            from whoosh.qparser import QueryParser

            results = []

            with self.ix.searcher() as searcher:
                parser = QueryParser("aktenzeichen", schema=self.schema)
                query = parser.parse(aktenzeichen)

                hits = searcher.search(query, limit=None)

                for hit in hits:
                    results.append({
                        'doc_id': hit['doc_id'],
                        'dateiname': hit['dateiname'],
                        'datum': hit['datum'].strftime('%d.%m.%Y') if hit['datum'] else '',
                        'sachbearbeiter': hit['sachbearbeiter'],
                        'priority': hit['priority']
                    })

            # Sortiere nach Datum (neueste zuerst)
            results.sort(key=lambda x: x['datum'], reverse=True)

            return results

        except Exception as e:
            print(f"Fehler bei Suche: {e}")
            return []

    def search_by_sachbearbeiter(self, sachbearbeiter: str) -> List[Dict]:
        """
        Sucht alle Dokumente eines Sachbearbeiters

        Args:
            sachbearbeiter: Sachbearbeiter-Kürzel

        Returns:
            Liste von Dokumenten
        """
        if not self.whoosh_available:
            return []

        try:
            from whoosh.qparser import QueryParser

            results = []

            with self.ix.searcher() as searcher:
                parser = QueryParser("sachbearbeiter", schema=self.schema)
                query = parser.parse(sachbearbeiter)

                hits = searcher.search(query, limit=None)

                for hit in hits:
                    results.append({
                        'doc_id': hit['doc_id'],
                        'dateiname': hit['dateiname'],
                        'aktenzeichen': hit['aktenzeichen'],
                        'datum': hit['datum'].strftime('%d.%m.%Y') if hit['datum'] else '',
                        'priority': hit['priority']
                    })

            # Sortiere nach Datum (neueste zuerst)
            results.sort(key=lambda x: x['datum'], reverse=True)

            return results

        except Exception as e:
            print(f"Fehler bei Suche: {e}")
            return []

    def search_by_priority(self, priority: str) -> List[Dict]:
        """
        Sucht alle Dokumente mit bestimmter Priorität

        Args:
            priority: Priorität (CRITICAL, HIGH, MEDIUM, NORMAL)

        Returns:
            Liste von Dokumenten
        """
        if not self.whoosh_available:
            return []

        try:
            from whoosh.qparser import QueryParser

            results = []

            with self.ix.searcher() as searcher:
                parser = QueryParser("priority", schema=self.schema)
                query = parser.parse(priority)

                hits = searcher.search(query, limit=None)

                for hit in hits:
                    results.append({
                        'doc_id': hit['doc_id'],
                        'dateiname': hit['dateiname'],
                        'aktenzeichen': hit['aktenzeichen'],
                        'sachbearbeiter': hit['sachbearbeiter'],
                        'datum': hit['datum'].strftime('%d.%m.%Y') if hit['datum'] else ''
                    })

            # Sortiere nach Datum (neueste zuerst)
            results.sort(key=lambda x: x['datum'], reverse=True)

            return results

        except Exception as e:
            print(f"Fehler bei Suche: {e}")
            return []

    def search_by_date_range(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Sucht Dokumente in Datumsbereich

        Args:
            start_date: Start-Datum (inklusiv)
            end_date: End-Datum (inklusiv)

        Returns:
            Liste von Dokumenten
        """
        if not self.whoosh_available:
            return []

        try:
            from whoosh import query

            results = []

            with self.ix.searcher() as searcher:
                # Erstelle Datums-Query
                q = query.Every('datum')

                if start_date and end_date:
                    q = query.DateRange("datum", start_date, end_date)
                elif start_date:
                    q = query.DateRange("datum", start_date, None)
                elif end_date:
                    q = query.DateRange("datum", None, end_date)

                hits = searcher.search(q, limit=None)

                for hit in hits:
                    results.append({
                        'doc_id': hit['doc_id'],
                        'dateiname': hit['dateiname'],
                        'aktenzeichen': hit['aktenzeichen'],
                        'sachbearbeiter': hit['sachbearbeiter'],
                        'datum': hit['datum'].strftime('%d.%m.%Y') if hit['datum'] else '',
                        'priority': hit['priority']
                    })

            # Sortiere nach Datum (neueste zuerst)
            results.sort(key=lambda x: x['datum'], reverse=True)

            return results

        except Exception as e:
            print(f"Fehler bei Suche: {e}")
            return []

    def get_statistics(self) -> Dict:
        """
        Liefert Statistiken

        Returns:
            Dict mit Statistiken
        """
        if not self.whoosh_available:
            return {
                'available': False,
                'total_documents': 0
            }

        try:
            with self.ix.searcher() as searcher:
                total_docs = searcher.doc_count_all()

                # Gruppiere nach Sachbearbeiter
                by_sachbearbeiter = {}
                by_priority = {}

                from whoosh import query

                # Alle Dokumente
                hits = searcher.search(query.Every('doc_id'), limit=None)

                for hit in hits:
                    sb = hit['sachbearbeiter']
                    if sb:
                        by_sachbearbeiter[sb] = by_sachbearbeiter.get(sb, 0) + 1

                    prio = hit['priority']
                    if prio:
                        by_priority[prio] = by_priority.get(prio, 0) + 1

                return {
                    'available': True,
                    'total_documents': total_docs,
                    'by_sachbearbeiter': by_sachbearbeiter,
                    'by_priority': by_priority
                }

        except Exception as e:
            print(f"Fehler beim Abrufen der Statistiken: {e}")
            return {
                'available': False,
                'total_documents': 0
            }

    def rebuild_index(self, document_storage) -> int:
        """
        Baut Index komplett neu auf

        Args:
            document_storage: DocumentStorage-Instanz

        Returns:
            Anzahl indexierter Dokumente
        """
        if not self.whoosh_available:
            return 0

        # Lösche alten Index
        if self.index_dir.exists():
            shutil.rmtree(self.index_dir)
            self.index_dir.mkdir(parents=True, exist_ok=True)

        # Erstelle neuen Index
        from whoosh.index import create_in
        self.ix = create_in(str(self.index_dir), self.schema)

        # Indexiere alle Dokumente
        indexed_count = 0

        try:
            all_docs = document_storage.get_all_documents()

            for doc in all_docs:
                # Lade Text
                text = ""
                if 'text_path' in doc and Path(doc['text_path']).exists():
                    with open(doc['text_path'], 'r', encoding='utf-8') as f:
                        text = f.read()

                if self.index_document(doc, text):
                    indexed_count += 1

        except Exception as e:
            print(f"Fehler beim Neuaufbau des Index: {e}")

        return indexed_count

    def optimize_index(self):
        """Optimiert Index (defragmentiert)"""
        if not self.whoosh_available:
            return

        try:
            from whoosh.writing import AsyncWriter

            writer = AsyncWriter(self.ix)
            writer.commit(optimize=True)

        except Exception as e:
            print(f"Fehler beim Optimieren: {e}")

    def delete_document(self, doc_id: str) -> bool:
        """
        Löscht Dokument aus Index

        Args:
            doc_id: Dokument-ID

        Returns:
            True bei Erfolg
        """
        if not self.whoosh_available:
            return False

        try:
            from whoosh.writing import AsyncWriter

            writer = AsyncWriter(self.ix)
            writer.delete_by_term('doc_id', doc_id)
            writer.commit()

            return True

        except Exception as e:
            print(f"Fehler beim Löschen: {e}")
            return False

    def get_suggestions(self, partial_query: str, field: str = 'aktenzeichen', limit: int = 10) -> List[str]:
        """
        Liefert Vorschläge basierend auf partieller Eingabe

        Args:
            partial_query: Partielle Sucheingabe
            field: Feld für Vorschläge
            limit: Maximale Anzahl

        Returns:
            Liste von Vorschlägen
        """
        if not self.whoosh_available:
            return []

        try:
            suggestions = []

            with self.ix.searcher() as searcher:
                # Hole alle eindeutigen Werte für das Feld
                from whoosh import query

                hits = searcher.search(query.Every(field), limit=None)

                values = set()
                for hit in hits:
                    value = hit[field]
                    if value and partial_query.lower() in value.lower():
                        values.add(value)

                suggestions = sorted(list(values))[:limit]

            return suggestions

        except Exception as e:
            print(f"Fehler bei Vorschlägen: {e}")
            return []
