"""LLM integration for extracting document layout rules from plain-text specifications.

Supports OpenAI chat-completion models.  When no API key is available the module
falls back to a sensible default LayoutConfig so the rest of the system remains
usable for testing / demo purposes.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from .models import (
    AlignmentEnum,
    FontConfig,
    HeaderFooterConfig,
    LayoutConfig,
    MarginConfig,
    PageConfig,
    ParagraphConfig,
    StyleConfig,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt fed to the LLM
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a document formatting expert who specialises in academic
and scientific journals. Your task is to analyse document formatting requirements
written in natural language and extract a structured layout configuration.

Return a JSON object that strictly follows this schema (all fields optional except
where noted):

{
  "title": "<template name>",
  "page": {
    "width": <float, inches>,
    "height": <float, inches>,
    "margins": {
      "top": <float, inches>,
      "bottom": <float, inches>,
      "left": <float, inches>,
      "right": <float, inches>
    },
    "orientation": "portrait" | "landscape",
    "columns": <int 1-4>,
    "column_spacing": <float, inches>
  },
  "header": {
    "text": "<static text or null>",
    "include_page_number": <bool>,
    "font": {"name": "<family>", "size": <pt>, "bold": <bool>, "italic": <bool>},
    "alignment": "left" | "center" | "right" | "justify"
  },
  "footer": { <same shape as header> },
  "styles": [
    {
      "name": "<style name>",
      "based_on": "<built-in style name or null>",
      "font": {"name": "<family>", "size": <pt>, "bold": <bool>, "italic": <bool>, "color": "<hex without #>"},
      "paragraph": {
        "alignment": "left" | "center" | "right" | "justify",
        "space_before": <pt>,
        "space_after": <pt>,
        "line_spacing": <multiplier>,
        "first_line_indent": <inches>,
        "left_indent": <inches>,
        "right_indent": <inches>
      }
    }
  ]
}

Style names should follow Microsoft Word conventions where applicable:
  "Normal", "Title", "Subtitle", "Abstract", "Heading 1", "Heading 2",
  "Heading 3", "Body Text", "Caption", "References".

Return ONLY the JSON object with no surrounding markdown, no code fences, and no
additional text.
"""


# ---------------------------------------------------------------------------
# Default / mock layout used when LLM is unavailable
# ---------------------------------------------------------------------------


def _default_layout(hint: str = "") -> LayoutConfig:
    """Return a sensible default LayoutConfig, optionally shaped by simple
    keyword matching when no LLM is available."""
    columns = 2 if any(w in hint.lower() for w in ("two column", "double column", "two-column")) else 1
    font_name = "Times New Roman"
    if any(w in hint.lower() for w in ("arial", "helvetica", "sans")):
        font_name = "Arial"
    elif "calibri" in hint.lower():
        font_name = "Calibri"

    body_size = 12.0
    for token in hint.split():
        try:
            v = float(token.rstrip("pt"))
            if 8 <= v <= 14:
                body_size = v
                break
        except ValueError:
            pass

    return LayoutConfig(
        title="Auto-generated Template",
        page=PageConfig(
            columns=columns,
            column_spacing=0.5,
            margins=MarginConfig(top=1.0, bottom=1.0, left=1.0, right=1.0),
        ),
        header=HeaderFooterConfig(
            text=None,
            include_page_number=True,
            alignment=AlignmentEnum.CENTER,
        ),
        footer=HeaderFooterConfig(
            text=None,
            include_page_number=True,
            alignment=AlignmentEnum.CENTER,
        ),
        styles=[
            StyleConfig(
                name="Title",
                font=FontConfig(name=font_name, size=16.0, bold=True),
                paragraph=ParagraphConfig(
                    alignment=AlignmentEnum.CENTER,
                    space_before=0,
                    space_after=12,
                ),
            ),
            StyleConfig(
                name="Subtitle",
                font=FontConfig(name=font_name, size=13.0, italic=True),
                paragraph=ParagraphConfig(
                    alignment=AlignmentEnum.CENTER,
                    space_before=0,
                    space_after=10,
                ),
            ),
            StyleConfig(
                name="Abstract",
                font=FontConfig(name=font_name, size=body_size - 1),
                paragraph=ParagraphConfig(
                    alignment=AlignmentEnum.JUSTIFY,
                    left_indent=0.5,
                    right_indent=0.5,
                    space_after=10,
                ),
            ),
            StyleConfig(
                name="Heading 1",
                font=FontConfig(name=font_name, size=body_size + 1, bold=True),
                paragraph=ParagraphConfig(
                    alignment=AlignmentEnum.LEFT,
                    space_before=12,
                    space_after=6,
                ),
            ),
            StyleConfig(
                name="Heading 2",
                font=FontConfig(name=font_name, size=body_size, bold=True, italic=True),
                paragraph=ParagraphConfig(
                    alignment=AlignmentEnum.LEFT,
                    space_before=10,
                    space_after=4,
                ),
            ),
            StyleConfig(
                name="Heading 3",
                font=FontConfig(name=font_name, size=body_size, italic=True),
                paragraph=ParagraphConfig(
                    alignment=AlignmentEnum.LEFT,
                    space_before=8,
                    space_after=4,
                ),
            ),
            StyleConfig(
                name="Normal",
                font=FontConfig(name=font_name, size=body_size),
                paragraph=ParagraphConfig(
                    alignment=AlignmentEnum.JUSTIFY,
                    first_line_indent=0.5,
                    line_spacing=1.5,
                    space_after=0,
                ),
            ),
            StyleConfig(
                name="Caption",
                font=FontConfig(name=font_name, size=body_size - 1, italic=True),
                paragraph=ParagraphConfig(
                    alignment=AlignmentEnum.CENTER,
                    space_before=4,
                    space_after=8,
                ),
            ),
            StyleConfig(
                name="References",
                font=FontConfig(name=font_name, size=body_size - 1),
                paragraph=ParagraphConfig(
                    alignment=AlignmentEnum.JUSTIFY,
                    left_indent=0.3,
                    first_line_indent=0.0,
                    space_after=4,
                ),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_requirements(text: str, api_key: Optional[str] = None) -> LayoutConfig:
    """Parse plain-text formatting requirements and return a :class:`LayoutConfig`.

    If *api_key* is not supplied the function checks the ``OPENAI_API_KEY``
    environment variable.  When no key is available it falls back to
    :func:`_default_layout` so the application remains functional without
    a live LLM.

    Parameters
    ----------
    text:
        The plain-text formatting specification provided by the user.
    api_key:
        Optional OpenAI API key; overrides the environment variable.

    Returns
    -------
    LayoutConfig
        Validated layout configuration.
    """
    resolved_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()

    if not resolved_key:
        logger.warning(
            "No OPENAI_API_KEY found – using heuristic default layout."
        )
        return _default_layout(text)

    try:
        from openai import OpenAI  # local import so the module is importable without openai

        client = OpenAI(api_key=resolved_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        return LayoutConfig.model_validate(data)

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("LLM call failed (%s) – falling back to default layout.", exc)
        return _default_layout(text)
