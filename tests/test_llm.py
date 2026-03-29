"""Unit tests for app.llm (LLM parsing & default layout fallback)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.llm import _default_layout, parse_requirements
from app.models import LayoutConfig


# ---------------------------------------------------------------------------
# _default_layout heuristics
# ---------------------------------------------------------------------------


class TestDefaultLayout:
    def test_returns_layout_config(self):
        result = _default_layout()
        assert isinstance(result, LayoutConfig)

    def test_default_is_single_column(self):
        result = _default_layout("standard paper")
        assert result.page.columns == 1

    def test_two_column_hint(self):
        result = _default_layout("two column layout")
        assert result.page.columns == 2

    def test_double_column_hint(self):
        result = _default_layout("double column format")
        assert result.page.columns == 2

    def test_hyphenated_two_column_hint(self):
        result = _default_layout("two-column template")
        assert result.page.columns == 2

    def test_arial_font_hint(self):
        result = _default_layout("use arial font throughout")
        title_style = result.get_style("Title")
        assert title_style is not None
        assert title_style.font.name == "Arial"

    def test_calibri_font_hint(self):
        result = _default_layout("calibri 12pt body")
        normal = result.get_style("Normal")
        assert normal is not None
        assert normal.font.name == "Calibri"

    def test_body_size_hint(self):
        result = _default_layout("body text 10pt")
        normal = result.get_style("Normal")
        assert normal is not None
        assert normal.font.size == 10.0

    def test_has_required_styles(self):
        result = _default_layout()
        style_names = {s.name for s in result.styles}
        for name in ("Title", "Heading 1", "Normal", "Abstract", "References"):
            assert name in style_names, f"Missing style: {name}"

    def test_has_header_and_footer(self):
        result = _default_layout()
        assert result.header is not None
        assert result.footer is not None
        assert result.header.include_page_number is True
        assert result.footer.include_page_number is True


# ---------------------------------------------------------------------------
# parse_requirements – no API key (fallback)
# ---------------------------------------------------------------------------


class TestParseRequirementsNoKey:
    def test_returns_default_when_no_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = parse_requirements("A4 page, 12pt Times New Roman")
        assert isinstance(result, LayoutConfig)

    def test_two_column_fallback(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = parse_requirements("two column journal paper")
        assert result.page.columns == 2


# ---------------------------------------------------------------------------
# parse_requirements – mock OpenAI response
# ---------------------------------------------------------------------------


class TestParseRequirementsWithMockLLM:
    def _mock_response(self, payload: dict):
        """Build a mock OpenAI response object."""
        msg = MagicMock()
        msg.content = str(payload).replace("'", '"')  # rough JSON
        import json
        msg.content = json.dumps(payload)
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        return response

    def test_valid_llm_response_parsed(self, monkeypatch):
        payload = {
            "title": "LLM Template",
            "page": {
                "width": 8.5,
                "height": 11.0,
                "margins": {"top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0},
                "orientation": "portrait",
                "columns": 1,
                "column_spacing": 0.5,
            },
            "header": None,
            "footer": None,
            "styles": [],
        }

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = self._mock_response(payload)

        with patch("openai.OpenAI", return_value=mock_client):
            result = parse_requirements("Some requirements", api_key="sk-fake")

        assert isinstance(result, LayoutConfig)
        assert result.title == "LLM Template"

    def test_llm_error_falls_back_to_default(self, monkeypatch):
        """When the LLM call raises, fallback default is returned."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API error")

        with patch("openai.OpenAI", return_value=mock_client):
            result = parse_requirements("Some requirements", api_key="sk-fake")

        assert isinstance(result, LayoutConfig)

    def test_llm_invalid_json_falls_back(self, monkeypatch):
        """When the LLM returns invalid JSON, fallback default is returned."""
        msg = MagicMock()
        msg.content = "not valid json {{{"
        choice = MagicMock()
        choice.message = msg
        mock_response = MagicMock()
        mock_response.choices = [choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            result = parse_requirements("Some requirements", api_key="sk-fake")

        assert isinstance(result, LayoutConfig)
