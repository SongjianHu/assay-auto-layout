"""Unit tests for app.models (Pydantic schemas)."""

import pytest
from pydantic import ValidationError

from app.models import (
    AlignmentEnum,
    FontConfig,
    HeaderFooterConfig,
    LayoutConfig,
    MarginConfig,
    PageConfig,
    ParagraphConfig,
    StyleConfig,
)


# ---------------------------------------------------------------------------
# FontConfig
# ---------------------------------------------------------------------------


class TestFontConfig:
    def test_defaults(self):
        fc = FontConfig()
        assert fc.name == "Times New Roman"
        assert fc.size == 12.0
        assert fc.bold is False
        assert fc.italic is False
        assert fc.color is None

    def test_custom_values(self):
        fc = FontConfig(name="Arial", size=10.0, bold=True, italic=True, color="FF0000")
        assert fc.name == "Arial"
        assert fc.size == 10.0
        assert fc.bold is True
        assert fc.italic is True
        assert fc.color == "FF0000"

    def test_invalid_size(self):
        with pytest.raises(ValidationError):
            FontConfig(size=0)  # must be > 0

    def test_negative_size(self):
        with pytest.raises(ValidationError):
            FontConfig(size=-1)


# ---------------------------------------------------------------------------
# ParagraphConfig
# ---------------------------------------------------------------------------


class TestParagraphConfig:
    def test_defaults(self):
        pc = ParagraphConfig()
        assert pc.alignment == AlignmentEnum.LEFT
        assert pc.space_before == 0.0
        assert pc.space_after == 6.0
        assert pc.line_spacing == 1.0

    def test_alignment_enum(self):
        pc = ParagraphConfig(alignment="justify")
        assert pc.alignment == AlignmentEnum.JUSTIFY

    def test_invalid_alignment(self):
        with pytest.raises(ValidationError):
            ParagraphConfig(alignment="diagonal")

    def test_negative_spacing_rejected(self):
        with pytest.raises(ValidationError):
            ParagraphConfig(space_before=-1)

    def test_zero_line_spacing_rejected(self):
        with pytest.raises(ValidationError):
            ParagraphConfig(line_spacing=0)


# ---------------------------------------------------------------------------
# StyleConfig
# ---------------------------------------------------------------------------


class TestStyleConfig:
    def test_minimal(self):
        sc = StyleConfig(name="Normal")
        assert sc.name == "Normal"
        assert isinstance(sc.font, FontConfig)
        assert isinstance(sc.paragraph, ParagraphConfig)

    def test_based_on(self):
        sc = StyleConfig(name="My Style", based_on="Normal")
        assert sc.based_on == "Normal"

    def test_name_required(self):
        with pytest.raises(ValidationError):
            StyleConfig()


# ---------------------------------------------------------------------------
# MarginConfig
# ---------------------------------------------------------------------------


class TestMarginConfig:
    def test_defaults(self):
        m = MarginConfig()
        assert m.top == 1.0
        assert m.bottom == 1.0
        assert m.left == 1.25
        assert m.right == 1.25

    def test_zero_margin_rejected(self):
        with pytest.raises(ValidationError):
            MarginConfig(top=0)


# ---------------------------------------------------------------------------
# PageConfig
# ---------------------------------------------------------------------------


class TestPageConfig:
    def test_defaults(self):
        p = PageConfig()
        assert p.width == 8.5
        assert p.height == 11.0
        assert p.columns == 1
        assert p.orientation == "portrait"

    def test_columns_range(self):
        with pytest.raises(ValidationError):
            PageConfig(columns=0)
        with pytest.raises(ValidationError):
            PageConfig(columns=5)

    def test_two_column(self):
        p = PageConfig(columns=2, column_spacing=0.4)
        assert p.columns == 2
        assert p.column_spacing == 0.4


# ---------------------------------------------------------------------------
# HeaderFooterConfig
# ---------------------------------------------------------------------------


class TestHeaderFooterConfig:
    def test_defaults(self):
        hf = HeaderFooterConfig()
        assert hf.text is None
        assert hf.include_page_number is False
        assert hf.alignment == AlignmentEnum.CENTER

    def test_with_text(self):
        hf = HeaderFooterConfig(text="Journal Name", include_page_number=True)
        assert hf.text == "Journal Name"
        assert hf.include_page_number is True


# ---------------------------------------------------------------------------
# LayoutConfig
# ---------------------------------------------------------------------------


class TestLayoutConfig:
    def test_defaults(self):
        lc = LayoutConfig()
        assert lc.title == "Document Template"
        assert isinstance(lc.page, PageConfig)
        assert lc.header is None
        assert lc.footer is None
        assert lc.styles == []

    def test_get_style_found(self):
        lc = LayoutConfig(styles=[StyleConfig(name="Normal"), StyleConfig(name="Title")])
        s = lc.get_style("Title")
        assert s is not None
        assert s.name == "Title"

    def test_get_style_not_found(self):
        lc = LayoutConfig()
        assert lc.get_style("NonExistent") is None

    def test_full_config_roundtrip(self):
        """JSON serialise then deserialise a complete LayoutConfig."""
        original = LayoutConfig(
            title="IEEE Template",
            page=PageConfig(
                columns=2,
                column_spacing=0.4,
                margins=MarginConfig(top=1, bottom=1, left=1, right=1),
            ),
            header=HeaderFooterConfig(text="IEEE Trans.", include_page_number=True),
            footer=HeaderFooterConfig(include_page_number=True),
            styles=[
                StyleConfig(
                    name="Normal",
                    font=FontConfig(name="Times New Roman", size=10),
                    paragraph=ParagraphConfig(
                        alignment=AlignmentEnum.JUSTIFY, line_spacing=1.15
                    ),
                )
            ],
        )
        data = original.model_dump()
        reconstructed = LayoutConfig.model_validate(data)
        assert reconstructed.title == original.title
        assert reconstructed.page.columns == 2
        assert reconstructed.styles[0].font.size == 10
