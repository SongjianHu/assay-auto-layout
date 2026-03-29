"""Pydantic models for document layout configuration."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AlignmentEnum(str, Enum):
    """Text alignment options."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class FontConfig(BaseModel):
    """Font configuration."""

    name: str = Field(default="Times New Roman", description="Font family name")
    size: float = Field(default=12.0, description="Font size in points", gt=0)
    bold: bool = Field(default=False)
    italic: bool = Field(default=False)
    color: Optional[str] = Field(
        default=None, description="Hex colour code without '#', e.g. '000000'"
    )


class ParagraphConfig(BaseModel):
    """Paragraph formatting configuration."""

    alignment: AlignmentEnum = Field(default=AlignmentEnum.LEFT)
    space_before: float = Field(
        default=0.0, description="Space before paragraph in points", ge=0
    )
    space_after: float = Field(
        default=6.0, description="Space after paragraph in points", ge=0
    )
    line_spacing: float = Field(
        default=1.0,
        description="Line spacing multiplier (e.g. 1.5 for one-and-a-half lines)",
        gt=0,
    )
    first_line_indent: float = Field(
        default=0.0, description="First-line indent in inches", ge=0
    )
    left_indent: float = Field(default=0.0, description="Left indent in inches", ge=0)
    right_indent: float = Field(default=0.0, description="Right indent in inches", ge=0)


class StyleConfig(BaseModel):
    """A named document style with font and paragraph settings."""

    name: str = Field(description="Style name, e.g. 'Normal', 'Heading 1', 'Title'")
    based_on: Optional[str] = Field(
        default=None, description="Name of the built-in style to base this on"
    )
    font: FontConfig = Field(default_factory=FontConfig)
    paragraph: ParagraphConfig = Field(default_factory=ParagraphConfig)


class MarginConfig(BaseModel):
    """Page margin configuration (all values in inches)."""

    top: float = Field(default=1.0, description="Top margin in inches", gt=0)
    bottom: float = Field(default=1.0, description="Bottom margin in inches", gt=0)
    left: float = Field(default=1.25, description="Left margin in inches", gt=0)
    right: float = Field(default=1.25, description="Right margin in inches", gt=0)


class HeaderFooterConfig(BaseModel):
    """Header or footer configuration."""

    text: Optional[str] = Field(default=None, description="Static header/footer text")
    include_page_number: bool = Field(
        default=False, description="Include automatic page number"
    )
    font: Optional[FontConfig] = Field(default=None, description="Font for the text")
    alignment: AlignmentEnum = Field(default=AlignmentEnum.CENTER)


class PageConfig(BaseModel):
    """Page layout configuration."""

    width: float = Field(default=8.5, description="Page width in inches", gt=0)
    height: float = Field(default=11.0, description="Page height in inches", gt=0)
    margins: MarginConfig = Field(default_factory=MarginConfig)
    orientation: str = Field(
        default="portrait", description="Page orientation: 'portrait' or 'landscape'"
    )
    columns: int = Field(
        default=1, description="Number of text columns", ge=1, le=4
    )
    column_spacing: float = Field(
        default=0.5, description="Spacing between columns in inches", ge=0
    )


class LayoutConfig(BaseModel):
    """Top-level document layout configuration produced by LLM parsing."""

    title: str = Field(default="Document Template", description="Template name")
    page: PageConfig = Field(default_factory=PageConfig)
    header: Optional[HeaderFooterConfig] = Field(default=None)
    footer: Optional[HeaderFooterConfig] = Field(default=None)
    styles: List[StyleConfig] = Field(
        default_factory=list,
        description="Custom style definitions; extend or override built-in styles",
    )

    def get_style(self, name: str) -> Optional[StyleConfig]:
        """Return the StyleConfig with the given name, or None."""
        for s in self.styles:
            if s.name == name:
                return s
        return None
