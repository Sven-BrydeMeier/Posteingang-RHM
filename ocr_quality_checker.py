"""
OCR-Qualitäts-Check für PDF-Dokumente

Prüft:
- Text-Dichte (Wörter pro Seite)
- Zeichen-Verteilung
- Ungewöhnliche Zeichen/Artefakte
- Lesbarkeit
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import fitz  # PyMuPDF


class QualityLevel(Enum):
    """OCR-Qualitäts-Stufen"""
    EXCELLENT = "🟢 Ausgezeichnet"
    GOOD = "🟡 Gut"
    POOR = "🟠 Mangelhaft"
    VERY_POOR = "🔴 Sehr schlecht"
    NO_TEXT = "⚫ Kein Text"


@dataclass
class QualityReport:
    """OCR-Qualitäts-Bericht"""
    quality_level: QualityLevel
    score: float  # 0-100
    total_pages: int
    avg_words_per_page: float
    text_density: float
    special_char_ratio: float
    warnings: List[str]
    recommendations: List[str]


class OCRQualityChecker:
    """Prüft OCR-Qualität von PDF-Dokumenten"""

    # Schwellwerte
    MIN_WORDS_PER_PAGE = 50
    MIN_TEXT_DENSITY = 0.1  # Prozent der Seite mit Text
    MAX_SPECIAL_CHAR_RATIO = 0.3  # Max 30% Sonderzeichen

    def __init__(self):
        """Initialisiert OCR-Quality-Checker"""
        pass

    def check_pdf_quality(self, pdf_path_or_bytes) -> QualityReport:
        """
        Prüft OCR-Qualität einer PDF

        Args:
            pdf_path_or_bytes: Pfad zur PDF oder PDF-Bytes

        Returns:
            QualityReport
        """
        warnings = []
        recommendations = []

        try:
            # Öffne PDF
            if isinstance(pdf_path_or_bytes, bytes):
                doc = fitz.open(stream=pdf_path_or_bytes, filetype="pdf")
            else:
                doc = fitz.open(pdf_path_or_bytes)

            total_pages = len(doc)
            total_words = 0
            total_chars = 0
            total_special_chars = 0
            total_text_area = 0
            total_page_area = 0

            # Analysiere jede Seite
            for page_num in range(total_pages):
                page = doc[page_num]

                # Extrahiere Text
                text = page.get_text()
                words = text.split()
                total_words += len(words)

                # Zähle Zeichen
                chars = len(text)
                total_chars += chars

                # Zähle Sonderzeichen (nicht alphanumerisch, nicht Whitespace)
                special_chars = len(re.findall(r'[^\w\s]', text))
                total_special_chars += special_chars

                # Schätze Text-Bereich (vereinfacht)
                page_rect = page.rect
                page_area = page_rect.width * page_rect.height
                total_page_area += page_area

                # Wörter auf dieser Seite
                page_words = len(words)

                # Warnungen für einzelne Seiten
                if page_words < 10:
                    warnings.append(f"Seite {page_num + 1}: Sehr wenig Text ({page_words} Wörter)")

            doc.close()

            # Berechne Metriken
            avg_words_per_page = total_words / total_pages if total_pages > 0 else 0
            special_char_ratio = total_special_chars / total_chars if total_chars > 0 else 0
            text_density = total_chars / total_page_area if total_page_area > 0 else 0

            # Bewerte Qualität
            score = self._calculate_quality_score(
                avg_words_per_page,
                text_density,
                special_char_ratio
            )

            quality_level = self._determine_quality_level(score)

            # Generiere Empfehlungen
            if avg_words_per_page < self.MIN_WORDS_PER_PAGE:
                warnings.append(f"Niedrige Wort-Dichte: {avg_words_per_page:.1f} Wörter/Seite")
                recommendations.append("PDF erneut mit höherer Auflösung scannen")

            if special_char_ratio > self.MAX_SPECIAL_CHAR_RATIO:
                warnings.append(f"Hohe Sonderzeichen-Rate: {special_char_ratio*100:.1f}%")
                recommendations.append("OCR-Software-Einstellungen überprüfen")

            if total_words == 0:
                warnings.append("Kein Text gefunden - PDF möglicherweise nicht OCR-verarbeitet")
                recommendations.append("PDF mit OCR-Software verarbeiten (z.B. Adobe Acrobat, ABBYY)")

            return QualityReport(
                quality_level=quality_level,
                score=score,
                total_pages=total_pages,
                avg_words_per_page=avg_words_per_page,
                text_density=text_density,
                special_char_ratio=special_char_ratio,
                warnings=warnings,
                recommendations=recommendations
            )

        except Exception as e:
            return QualityReport(
                quality_level=QualityLevel.VERY_POOR,
                score=0,
                total_pages=0,
                avg_words_per_page=0,
                text_density=0,
                special_char_ratio=0,
                warnings=[f"Fehler beim Analysieren: {str(e)}"],
                recommendations=["PDF-Datei überprüfen"]
            )

    def _calculate_quality_score(
        self,
        avg_words_per_page: float,
        text_density: float,
        special_char_ratio: float
    ) -> float:
        """
        Berechnet Qualitäts-Score (0-100)

        Args:
            avg_words_per_page: Durchschnittliche Wörter pro Seite
            text_density: Text-Dichte
            special_char_ratio: Sonderzeichen-Verhältnis

        Returns:
            Score 0-100
        """
        score = 0

        # Wörter pro Seite (max 40 Punkte)
        if avg_words_per_page >= 200:
            score += 40
        elif avg_words_per_page >= 100:
            score += 30
        elif avg_words_per_page >= 50:
            score += 20
        elif avg_words_per_page >= 20:
            score += 10

        # Text-Dichte (max 30 Punkte)
        if text_density >= 0.5:
            score += 30
        elif text_density >= 0.2:
            score += 20
        elif text_density >= 0.1:
            score += 10

        # Sonderzeichen-Verhältnis (max 30 Punkte)
        if special_char_ratio <= 0.1:
            score += 30
        elif special_char_ratio <= 0.2:
            score += 20
        elif special_char_ratio <= 0.3:
            score += 10

        return min(100, score)

    def _determine_quality_level(self, score: float) -> QualityLevel:
        """
        Bestimmt Qualitäts-Level basierend auf Score

        Args:
            score: Qualitäts-Score

        Returns:
            QualityLevel
        """
        if score == 0:
            return QualityLevel.NO_TEXT
        elif score >= 80:
            return QualityLevel.EXCELLENT
        elif score >= 60:
            return QualityLevel.GOOD
        elif score >= 30:
            return QualityLevel.POOR
        else:
            return QualityLevel.VERY_POOR

    def format_report(self, report: QualityReport) -> str:
        """
        Formatiert Bericht für Ausgabe

        Args:
            report: QualityReport

        Returns:
            Formatierter String
        """
        lines = []
        lines.append(f"**OCR-Qualität**: {report.quality_level.value} ({report.score:.0f}/100)")
        lines.append(f"- **Seiten**: {report.total_pages}")
        lines.append(f"- **Wörter/Seite**: {report.avg_words_per_page:.1f}")
        lines.append(f"- **Text-Dichte**: {report.text_density*100:.2f}%")
        lines.append(f"- **Sonderzeichen**: {report.special_char_ratio*100:.1f}%")

        if report.warnings:
            lines.append("\n**Warnungen**:")
            for warning in report.warnings:
                lines.append(f"- ⚠️ {warning}")

        if report.recommendations:
            lines.append("\n**Empfehlungen**:")
            for rec in report.recommendations:
                lines.append(f"- 💡 {rec}")

        return "\n".join(lines)
