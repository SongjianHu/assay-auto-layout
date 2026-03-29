"""FastAPI web application for assay-auto-layout.

Endpoints
---------
GET  /                        Serve the single-page web UI.
POST /api/parse               Parse plain-text requirements → LayoutConfig JSON.
POST /api/generate-template   LayoutConfig JSON → .dotx bytes download.
POST /api/export              Content text + LayoutConfig JSON → .docx bytes download.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .llm import parse_requirements
from .models import LayoutConfig
from .template import generate_dotx_bytes
from .export import export_docx_bytes

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Assay Auto-Layout",
    description="AI-powered academic paper template generator",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

_STATIC_DIR = Path(__file__).parent.parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ParseRequest(BaseModel):
    """Request body for /api/parse."""

    requirements: str
    api_key: str | None = None


class GenerateTemplateRequest(BaseModel):
    """Request body for /api/generate-template."""

    config: LayoutConfig


class ExportRequest(BaseModel):
    """Request body for /api/export."""

    content: str
    config: LayoutConfig


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the single-page web UI."""
    html_path = _STATIC_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/parse")
async def api_parse(req: ParseRequest) -> LayoutConfig:
    """Parse plain-text formatting requirements and return a LayoutConfig.

    The API key is optional; when absent the server uses ``OPENAI_API_KEY``
    from the environment.  If neither is available a sensible default layout
    is returned.
    """
    try:
        config = parse_requirements(req.requirements, api_key=req.api_key)
    except Exception as exc:
        logger.exception("Error during parse_requirements")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return config


@app.post("/api/generate-template")
async def api_generate_template(req: GenerateTemplateRequest) -> Response:
    """Generate a ``.dotx`` template from the supplied LayoutConfig."""
    try:
        dotx_bytes = generate_dotx_bytes(req.config)
    except Exception as exc:
        logger.exception("Error during generate_dotx_bytes")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"{req.config.title.replace(' ', '_')}.dotx"
    return Response(
        content=dotx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.template"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export")
async def api_export(req: ExportRequest) -> Response:
    """Export a styled ``.docx`` from plain-text content and a LayoutConfig."""
    try:
        docx_bytes = export_docx_bytes(req.content, req.config)
    except Exception as exc:
        logger.exception("Error during export_docx_bytes")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"{req.config.title.replace(' ', '_')}_paper.docx"
    return Response(
        content=docx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
