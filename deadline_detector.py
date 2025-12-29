"""
Fristen-Erkennung für juristische Dokumente

Erkennt:
- Fristen mit Datums-Angaben
- Dringlichkeits-Marker (Eilig, Dringend)
- Berechnet Priorität basierend auf verbleibender Zeit
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class Priority(Enum):
    """Prioritäts-Stufen"""
    CRITICAL = "🔴 Kritisch"  # < 3 Tage
    HIGH = "🟠 Hoch"  # 3-7 Tage
    MEDIUM = "🟡 Mittel"  # 7-14 Tage
    NORMAL = "🟢 Normal"  # > 14 Tage
    NONE = "⚪ Keine Frist"


@dataclass
class Deadline:
    """Repräsentiert eine erkannte Frist"""
    date: datetime
    text_context: str
    priority: Priority
    days_remaining: int
    is_urgent: bool = False


class DeadlineDetector:
    """Erkennt Fristen und Dringlichkeit in Dokumenten"""

    # Frist-Keywords
    DEADLINE_KEYWORDS = [
        r'frist\s+bis',
        r'frist\s+zum',
        r'frist\s+am',
        r'bis\s+zum',
        r'bis\s+sp[aä]testens',
        r'sp[aä]testens\s+bis',
        r'bis\s+einschlie[sß]lich',
        r'termin\s+am',
        r'verhandlung\s+am',
        r'hauptverhandlung\s+am',
        r'gerichtstermin',
        r'fristende',
        r'ablauf\s+der\s+frist'
    ]

    # Dringlichkeits-Keywords
    URGENCY_KEYWORDS = [
        r'eilig',
        r'dringend',
        r'sofort',
        r'unverzüglich',
        r'umgehend',
        r'eilt',
        r'einstweilige\s+verfügung',
        r'arrest',
        r'vorläufig',
        r'binnen\s+\d+\s+tag',
        r'express',
        r'priorität'
    ]

    # Datums-Pattern
    DATE_PATTERNS = [
        # 31.12.2024, 31.12.24
        (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', 'de_long'),
        (r'(\d{1,2})\.(\d{1,2})\.(\d{2})', 'de_short'),
        # 2024-12-31
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'iso'),
        # 31. Dezember 2024
        (r'(\d{1,2})\.\s*(januar|februar|m[aä]rz|april|mai|juni|juli|august|september|oktober|november|dezember)\s+(\d{4})', 'de_text'),
    ]

    MONTH_MAP = {
        'januar': 1, 'februar': 2, 'märz': 3, 'maerz': 3, 'april': 4,
        'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12
    }

    def __init__(self):
        """Initialisiert Fristen-Detektor"""
        pass

    def parse_date(self, date_str: str, pattern_type: str) -> Optional[datetime]:
        """
        Parst Datumsstring zu datetime

        Args:
            date_str: Datums-String
            pattern_type: Typ des Patterns

        Returns:
            datetime oder None
        """
        try:
            if pattern_type == 'de_long':
                match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', date_str)
                if match:
                    day, month, year = map(int, match.groups())
                    return datetime(year, month, day)

            elif pattern_type == 'de_short':
                match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{2})', date_str)
                if match:
                    day, month, year = map(int, match.groups())
                    year += 2000  # 24 -> 2024
                    return datetime(year, month, day)

            elif pattern_type == 'iso':
                match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
                if match:
                    year, month, day = map(int, match.groups())
                    return datetime(year, month, day)

            elif pattern_type == 'de_text':
                match = re.search(r'(\d{1,2})\.\s*(januar|februar|m[aä]rz|april|mai|juni|juli|august|september|oktober|november|dezember)\s+(\d{4})', date_str.lower())
                if match:
                    day = int(match.group(1))
                    month_name = match.group(2).replace('ä', 'ae')
                    month = self.MONTH_MAP.get(month_name)
                    year = int(match.group(3))
                    if month:
                        return datetime(year, month, day)

        except (ValueError, AttributeError):
            return None

        return None

    def find_deadlines(self, text: str) -> List[Deadline]:
        """
        Findet alle Fristen im Text

        Args:
            text: Dokument-Text

        Returns:
            Liste von Deadlines
        """
        deadlines = []
        text_lower = text.lower()

        # Suche nach Frist-Keywords mit nachfolgendem Datum
        for keyword_pattern in self.DEADLINE_KEYWORDS:
            matches = re.finditer(keyword_pattern, text_lower)

            for match in matches:
                start_pos = match.end()
                # Suche Datum in den nächsten 100 Zeichen
                context = text[match.start():min(match.end() + 100, len(text))]
                context_lower = context.lower()

                for date_pattern, pattern_type in self.DATE_PATTERNS:
                    date_matches = re.finditer(date_pattern, context_lower)

                    for date_match in date_matches:
                        parsed_date = self.parse_date(date_match.group(), pattern_type)

                        if parsed_date:
                            # Berechne Priorität
                            days_remaining = (parsed_date - datetime.now()).days
                            priority = self._calculate_priority(days_remaining)

                            deadline = Deadline(
                                date=parsed_date,
                                text_context=context[:80].strip(),
                                priority=priority,
                                days_remaining=days_remaining
                            )

                            deadlines.append(deadline)

        # Prüfe auf Dringlichkeits-Keywords
        for urgency_pattern in self.URGENCY_KEYWORDS:
            if re.search(urgency_pattern, text_lower):
                for deadline in deadlines:
                    deadline.is_urgent = True

        return deadlines

    def _calculate_priority(self, days_remaining: int) -> Priority:
        """
        Berechnet Priorität basierend auf verbleibenden Tagen

        Args:
            days_remaining: Tage bis Frist

        Returns:
            Priority
        """
        if days_remaining < 0:
            return Priority.CRITICAL  # Überfällig
        elif days_remaining <= 3:
            return Priority.CRITICAL
        elif days_remaining <= 7:
            return Priority.HIGH
        elif days_remaining <= 14:
            return Priority.MEDIUM
        else:
            return Priority.NORMAL

    def check_urgency(self, text: str) -> bool:
        """
        Prüft ob Dokument als dringend markiert ist

        Args:
            text: Dokument-Text

        Returns:
            True wenn dringend
        """
        text_lower = text.lower()

        for pattern in self.URGENCY_KEYWORDS:
            if re.search(pattern, text_lower):
                return True

        return False

    def get_earliest_deadline(self, deadlines: List[Deadline]) -> Optional[Deadline]:
        """
        Liefert früheste Frist

        Args:
            deadlines: Liste von Fristen

        Returns:
            Früheste Deadline oder None
        """
        if not deadlines:
            return None

        return min(deadlines, key=lambda d: d.date)

    def format_deadline_info(self, deadline: Deadline) -> Dict[str, any]:
        """
        Formatiert Deadline für Ausgabe

        Args:
            deadline: Deadline-Objekt

        Returns:
            Dict mit formatierten Informationen
        """
        return {
            'datum': deadline.date.strftime('%d.%m.%Y'),
            'prioritaet': deadline.priority.value,
            'tage_verbleibend': deadline.days_remaining,
            'ist_dringend': deadline.is_urgent,
            'kontext': deadline.text_context,
            'warning_level': self._get_warning_level(deadline)
        }

    def _get_warning_level(self, deadline: Deadline) -> str:
        """Liefert Warn-Level für UI"""
        if deadline.priority == Priority.CRITICAL:
            return 'error'
        elif deadline.priority == Priority.HIGH:
            return 'warning'
        elif deadline.priority == Priority.MEDIUM:
            return 'info'
        else:
            return 'success'

    def analyze_document(self, text: str) -> Dict:
        """
        Analysiert Dokument auf Fristen und Dringlichkeit

        Args:
            text: Dokument-Text

        Returns:
            Analyse-Ergebnis
        """
        deadlines = self.find_deadlines(text)
        is_urgent = self.check_urgency(text)
        earliest = self.get_earliest_deadline(deadlines)

        result = {
            'has_deadlines': len(deadlines) > 0,
            'deadline_count': len(deadlines),
            'is_urgent': is_urgent,
            'deadlines': [self.format_deadline_info(d) for d in deadlines]
        }

        if earliest:
            result['earliest_deadline'] = self.format_deadline_info(earliest)
            result['priority'] = earliest.priority.value
        else:
            result['priority'] = Priority.NONE.value

        return result
