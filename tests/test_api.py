"""Integration tests for the FastAPI web application."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import LayoutConfig

client = TestClient(app)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


class TestUI:
    def test_index_returns_html(self):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "Assay Auto-Layout" in res.text


# ---------------------------------------------------------------------------
# /api/parse
# ---------------------------------------------------------------------------


class TestApiParse:
    def test_parse_returns_layout_config(self):
        """Without an API key the endpoint returns a valid default LayoutConfig."""
        res = client.post(
            "/api/parse",
            json={"requirements": "A4 page, Times New Roman 12pt body, two columns"},
        )
        assert res.status_code == 200
        data = res.json()
        # Must be a valid LayoutConfig
        config = LayoutConfig.model_validate(data)
        assert config.title != ""

    def test_parse_two_column_hint(self):
        res = client.post(
            "/api/parse",
            json={"requirements": "Two column layout, Arial 11pt"},
        )
        assert res.status_code == 200
        config = LayoutConfig.model_validate(res.json())
        assert config.page.columns == 2

    def test_parse_missing_requirements(self):
        res = client.post("/api/parse", json={})
        assert res.status_code == 422  # Pydantic validation error


# ---------------------------------------------------------------------------
# /api/generate-template
# ---------------------------------------------------------------------------


class TestApiGenerateTemplate:
    def _minimal_config(self):
        return {
            "title": "Test",
            "page": {
                "width": 8.5,
                "height": 11.0,
                "margins": {"top": 1.0, "bottom": 1.0, "left": 1.25, "right": 1.25},
                "orientation": "portrait",
                "columns": 1,
                "column_spacing": 0.5,
            },
            "header": None,
            "footer": None,
            "styles": [],
        }

    def test_returns_dotx_bytes(self):
        res = client.post(
            "/api/generate-template",
            json={"config": self._minimal_config()},
        )
        assert res.status_code == 200
        assert "wordprocessingml.template" in res.headers["content-type"]
        assert len(res.content) > 0

    def test_content_disposition_header(self):
        res = client.post(
            "/api/generate-template",
            json={"config": self._minimal_config()},
        )
        assert "attachment" in res.headers["content-disposition"]
        assert ".dotx" in res.headers["content-disposition"]

    def test_invalid_config_rejected(self):
        res = client.post(
            "/api/generate-template",
            json={"config": {"page": {"columns": 99}}},  # columns > 4
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# /api/export
# ---------------------------------------------------------------------------


class TestApiExport:
    def _minimal_config(self):
        return {
            "title": "My Paper",
            "page": {
                "width": 8.5,
                "height": 11.0,
                "margins": {"top": 1.0, "bottom": 1.0, "left": 1.25, "right": 1.25},
                "orientation": "portrait",
                "columns": 1,
                "column_spacing": 0.5,
            },
            "header": None,
            "footer": None,
            "styles": [],
        }

    def test_returns_docx_bytes(self):
        res = client.post(
            "/api/export",
            json={
                "content": "# Title\n\nBody text here.",
                "config": self._minimal_config(),
            },
        )
        assert res.status_code == 200
        assert "wordprocessingml.document" in res.headers["content-type"]
        assert len(res.content) > 0

    def test_content_disposition_header(self):
        res = client.post(
            "/api/export",
            json={
                "content": "Hello world",
                "config": self._minimal_config(),
            },
        )
        assert "attachment" in res.headers["content-disposition"]
        assert ".docx" in res.headers["content-disposition"]

    def test_missing_content_rejected(self):
        res = client.post(
            "/api/export",
            json={"config": self._minimal_config()},
        )
        assert res.status_code == 422

    def test_missing_config_rejected(self):
        res = client.post(
            "/api/export",
            json={"content": "Some text"},
        )
        assert res.status_code == 422
