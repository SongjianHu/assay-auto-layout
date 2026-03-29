"""Content matching and style application.

Takes plain text with lightweight Markdown-like markup and a
:class:`~app.models.LayoutConfig`, then produces a fully-styled ``.docx``
document.

Markup conventions
------------------
``# Title text``        → *Title* style
``## Heading text``     → *Heading 1* style
``### Sub-heading``     → *Heading 2* style
``#### Sub-sub``        → *Heading 3* style
``**Abstract**``        → marks the next paragraph as *Abstract* style
``---``                 → horizontal section separator (page break is NOT inserted;
                          the separator is skipped silently to maintain flow)
``[ref] …``  or
``1. …`` inside a
``References`` section  → *References* style
Everything else         → *Normal* / *Body Text* style
"""

from __future__ import annotations

import io
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from .models import AlignmentEnum, FontConfig, LayoutConfig, ParagraphConfig

# Alignment mapping (reused from template module)
_ALIGNMENT_MAP = {
    AlignmentEnum.LEFT: WD_ALIGN_PARAGRAPH.LEFT,
    AlignmentEnum.CENTER: WD_ALIGN_PARAGRAPH.CENTER,
    AlignmentEnum.RIGHT: WD_ALIGN_PARAGRAPH.RIGHT,
    AlignmentEnum.JUSTIFY: WD_ALIGN_PARAGRAPH.JUSTIFY,
}

# Regex patterns for markup detection
_RE_H1 = re.compile(r"^#{1}\s+(.+)$")          # # Title
_RE_H2 = re.compile(r"^#{2}\s+(.+)$")           # ## Heading 1
_RE_H3 = re.compile(r"^#{3}\s+(.+)$")           # ### Heading 2
_RE_H4 = re.compile(r"^#{4}\s+(.+)$")           # #### Heading 3
_RE_ABSTRACT = re.compile(r"^\*?\*?abstract\*?\*?:?\s*$", re.IGNORECASE)
_RE_REFERENCES = re.compile(r"^\*?\*?references\*?\*?:?\s*$", re.IGNORECASE)
_RE_SEPARATOR = re.compile(r"^-{3,}$")
_RE_REF_ITEM = re.compile(r"^(\[\d+\]|\d+\.)\s+")  # [1] … or 1. …


def _apply_font_to_run(run, fc: FontConfig) -> None:
    run.font.name = fc.name
    run.font.size = Pt(fc.size)
    run.font.bold = fc.bold
    run.font.italic = fc.italic
    if fc.color:
        hex_str = fc.color.lstrip("#")
        r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
        run.font.color.rgb = RGBColor(r, g, b)


def _apply_paragraph_format(pf, pc: ParagraphConfig) -> None:
    pf.alignment = _ALIGNMENT_MAP.get(pc.alignment, WD_ALIGN_PARAGRAPH.LEFT)
    pf.space_before = Pt(pc.space_before)
    pf.space_after = Pt(pc.space_after)
    pf.line_spacing = Pt(pc.line_spacing * 12)
    if pc.first_line_indent > 0:
        pf.first_line_indent = Inches(pc.first_line_indent)
    pf.left_indent = Inches(pc.left_indent)
    pf.right_indent = Inches(pc.right_indent)


def _set_para_style(doc: Document, config: LayoutConfig, para, style_name: str) -> None:
    """Apply a named style to *para*, falling back to inline formatting when the
    style is not registered in the document."""
    try:
        para.style = doc.styles[style_name]
        return
    except KeyError:
        pass

    # Style not found – apply inline formatting from the LayoutConfig
    sc = config.get_style(style_name)
    if sc is None:
        return
    run = para.runs[0] if para.runs else None
    if run:
        _apply_font_to_run(run, sc.font)
    _apply_paragraph_format(para.paragraph_format, sc.paragraph)


def _add_page_number_field(para) -> None:
    """Insert an auto-updating PAGE field into *para*."""
    run = para.add_run()
    for tag, text in [
        ("w:fldChar", None),
        ("w:instrText", " PAGE "),
        ("w:fldChar", None),
    ]:
        el = OxmlElement(tag)
        if tag == "w:fldChar":
            el.set(
                qn("w:fldCharType"),
                "begin" if not run._r.findall(qn("w:instrText")) else "end",
            )
        else:
            el.text = text
        run._r.append(el)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_docx_bytes(content: str, config: LayoutConfig) -> bytes:
    """Apply *config* styles to *content* and return raw ``.docx`` bytes.

    Parameters
    ----------
    content:
        Plain text with optional Markdown-like markup.
    config:
        Layout configuration (produced by the LLM parser or constructed
        manually).

    Returns
    -------
    bytes
        Raw bytes of a styled ``.docx`` document.
    """
    doc = Document()

    # ---- Page setup --------------------------------------------------------
    for section in doc.sections:
        m = config.page.margins
        section.top_margin = Inches(m.top)
        section.bottom_margin = Inches(m.bottom)
        section.left_margin = Inches(m.left)
        section.right_margin = Inches(m.right)
        section.page_width = Inches(config.page.width)
        section.page_height = Inches(config.page.height)

        if config.page.columns > 1:
            from .template import _add_columns
            _add_columns(section, config.page.columns, config.page.column_spacing)

        if config.header is not None:
            from .template import _add_header_footer_text
            _add_header_footer_text(
                section,
                is_header=True,
                text=config.header.text,
                include_page_number=config.header.include_page_number,
                fc=config.header.font,
                alignment=config.header.alignment,
            )

        if config.footer is not None:
            from .template import _add_header_footer_text
            _add_header_footer_text(
                section,
                is_header=False,
                text=config.footer.text,
                include_page_number=config.footer.include_page_number,
                fc=config.footer.font,
                alignment=config.footer.alignment,
            )

    # ---- Register custom styles --------------------------------------------
    from .template import _apply_style_config
    for sc in config.styles:
        _apply_style_config(doc, sc)

    # ---- Parse and render content ------------------------------------------
    lines = content.splitlines()
    in_abstract = False
    in_references = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        i += 1

        if not stripped:
            in_abstract = False  # blank line ends abstract block
            continue

        if _RE_SEPARATOR.match(stripped):
            continue  # skip horizontal rules

        # Detect section transitions
        if _RE_ABSTRACT.match(stripped):
            in_abstract = True
            para = doc.add_paragraph("Abstract")
            _set_para_style(doc, config, para, "Heading 1")
            continue

        if _RE_REFERENCES.match(stripped):
            in_references = True
            in_abstract = False
            para = doc.add_paragraph("References")
            _set_para_style(doc, config, para, "Heading 1")
            continue

        # Headings
        m = _RE_H1.match(stripped)
        if m:
            para = doc.add_paragraph(m.group(1))
            _set_para_style(doc, config, para, "Title")
            continue

        m = _RE_H2.match(stripped)
        if m:
            in_abstract = False
            para = doc.add_paragraph(m.group(1))
            _set_para_style(doc, config, para, "Heading 1")
            continue

        m = _RE_H3.match(stripped)
        if m:
            in_abstract = False
            para = doc.add_paragraph(m.group(1))
            _set_para_style(doc, config, para, "Heading 2")
            continue

        m = _RE_H4.match(stripped)
        if m:
            in_abstract = False
            para = doc.add_paragraph(m.group(1))
            _set_para_style(doc, config, para, "Heading 3")
            continue

        # Body text
        if in_abstract:
            para = doc.add_paragraph(stripped)
            _set_para_style(doc, config, para, "Abstract")
        elif in_references or _RE_REF_ITEM.match(stripped):
            para = doc.add_paragraph(stripped)
            _set_para_style(doc, config, para, "References")
        else:
            para = doc.add_paragraph(stripped)
            _set_para_style(doc, config, para, "Normal")

    # ---- Serialise --------------------------------------------------------
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
