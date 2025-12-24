"""
Presentation Type Management System

This module provides a convenient way to manage presentation types in SlideGuard.
It allows for type-specific criteria evaluation and slide type filtering.
"""

from enum import Enum
from typing import Dict, List, Optional


class PresentationType(str, Enum):
    """Enum for presentation types to provide type safety and better IDE support"""
    SCIENTIFIC = "scientific"
    INDUSTRIAL = "industrial"
    COLLABORATIVE = "collaborative"
    TECHNOLOGICAL = "technological"

    def get_display_name(self, lang: str = "en") -> str:
        """Get localized display name for the presentation type"""
        names = {
            "en": {
                PresentationType.SCIENTIFIC: "Scientific",
                PresentationType.INDUSTRIAL: "Industrial",
                PresentationType.COLLABORATIVE: "Collaborative",
                PresentationType.TECHNOLOGICAL: "Technological",
            },
            "ru": {
                PresentationType.SCIENTIFIC: "Научный",
                PresentationType.INDUSTRIAL: "Индустриальный",
                PresentationType.COLLABORATIVE: "Коллаборативный",
                PresentationType.TECHNOLOGICAL: "Технологический",
            }
        }
        return names.get(lang, names["en"]).get(self, self.value)

    @classmethod
    def from_string(cls, value: str) -> Optional["PresentationType"]:
        """Create PresentationType from string value"""
        try:
            return cls(value.lower())
        except ValueError:
            return None

    @classmethod
    def get_all_types(cls) -> List["PresentationType"]:
        """Get all available presentation types"""
        return list(cls)

    @classmethod
    def get_all_values(cls) -> List[str]:
        """Get all available presentation type values"""
        return [pt.value for pt in cls]

