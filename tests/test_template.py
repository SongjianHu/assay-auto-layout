"""Unit tests for app.template (.dotx generation)."""

import io
import zipfile

import pytest

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
from app.template import generate_dotx_bytes


def _load_zip(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(data))


def _content_types(data: bytes) -> str:
    with _load_zip(data) as zf:
        return zf.read("[Content_Types].xml").decode()


# ---------------------------------------------------------------------------
# Basic generation
# ---------------------------------------------------------------------------


class TestGenerateDotxBytes:
    def test_returns_bytes(self):
        config = LayoutConfig()
        result = generate_dotx_bytes(config)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_is_valid_zip(self):
        config = LayoutConfig()
        result = generate_dotx_bytes(config)
        assert zipfile.is_zipfile(io.BytesIO(result))

    def test_content_type_is_dotx(self):
        """[Content_Types].xml must declare the template content type."""
        config = LayoutConfig()
        result = generate_dotx_bytes(config)
        ct = _content_types(result)
        assert (
            "wordprocessingml.template.main+xml" in ct
        ), f"Expected template content-type in: {ct}"

    def test_not_docx_content_type(self):
        config = LayoutConfig()
        result = generate_dotx_bytes(config)
        ct = _content_types(result)
        assert "wordprocessingml.document.main+xml" not in ct


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------


class TestPageSetup:
    def test_custom_margins_accepted(self):
        """generate_dotx_bytes should not raise with custom margins."""
        config = LayoutConfig(
            page=PageConfig(
                margins=MarginConfig(top=1.5, bottom=1.5, left=2.0, right=2.0)
            )
        )
        result = generate_dotx_bytes(config)
        assert len(result) > 0

    def test_two_column_layout(self):
        config = LayoutConfig(page=PageConfig(columns=2, column_spacing=0.5))
        result = generate_dotx_bytes(config)
        # Verify the file is still valid
        assert zipfile.is_zipfile(io.BytesIO(result))

    def test_landscape_orientation(self):
        config = LayoutConfig(
            page=PageConfig(width=11.0, height=8.5, orientation="landscape")
        )
        result = generate_dotx_bytes(config)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------


class TestStyles:
    def test_custom_normal_style(self):
        config = LayoutConfig(
            styles=[
                StyleConfig(
                    name="Normal",
                    font=FontConfig(name="Arial", size=11),
                    paragraph=ParagraphConfig(
                        alignment=AlignmentEnum.JUSTIFY, line_spacing=1.5
                    ),
                )
            ]
        )
        result = generate_dotx_bytes(config)
        assert len(result) > 0

    def test_multiple_styles(self):
        config = LayoutConfig(
            styles=[
                StyleConfig(name="Normal", font=FontConfig(size=12)),
                StyleConfig(name="Title", font=FontConfig(size=18, bold=True)),
                StyleConfig(name="Heading 1", font=FontConfig(size=14, bold=True)),
                StyleConfig(name="Abstract", font=FontConfig(size=11)),
            ]
        )
        result = generate_dotx_bytes(config)
        assert zipfile.is_zipfile(io.BytesIO(result))

    def test_custom_named_style(self):
        """A style with a non-standard name should also be created."""
        config = LayoutConfig(
            styles=[
                StyleConfig(
                    name="My Custom Style",
                    based_on="Normal",
                    font=FontConfig(name="Courier New", size=10),
                )
            ]
        )
        result = generate_dotx_bytes(config)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Header / Footer
# ---------------------------------------------------------------------------


class TestHeaderFooter:
    def test_header_with_text(self):
        config = LayoutConfig(
            header=HeaderFooterConfig(
                text="Journal of Science",
                include_page_number=False,
                alignment=AlignmentEnum.CENTER,
            )
        )
        result = generate_dotx_bytes(config)
        assert len(result) > 0

    def test_footer_with_page_number(self):
        config = LayoutConfig(
            footer=HeaderFooterConfig(
                include_page_number=True,
                alignment=AlignmentEnum.CENTER,
            )
        )
        result = generate_dotx_bytes(config)
        assert len(result) > 0

    def test_header_and_footer(self):
        config = LayoutConfig(
            header=HeaderFooterConfig(text="Title", include_page_number=False),
            footer=HeaderFooterConfig(include_page_number=True),
        )
        result = generate_dotx_bytes(config)
        assert zipfile.is_zipfile(io.BytesIO(result))

    def test_header_font(self):
        config = LayoutConfig(
            header=HeaderFooterConfig(
                text="Custom Font Header",
                font=FontConfig(name="Arial", size=9, italic=True),
            )
        )
        result = generate_dotx_bytes(config)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_styles_list(self):
        config = LayoutConfig(styles=[])
        result = generate_dotx_bytes(config)
        assert len(result) > 0

    def test_no_header_footer(self):
        config = LayoutConfig(header=None, footer=None)
        result = generate_dotx_bytes(config)
        assert len(result) > 0

    def test_font_with_color(self):
        config = LayoutConfig(
            styles=[
                StyleConfig(
                    name="Title",
                    font=FontConfig(color="1F497D"),
                )
            ]
        )
        result = generate_dotx_bytes(config)
        assert len(result) > 0
