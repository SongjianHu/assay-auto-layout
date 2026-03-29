"""Generate a .dotx Word template from a :class:`~app.models.LayoutConfig`.

The public entry-point is :func:`generate_dotx_bytes`.  It returns the raw
bytes of a ``.dotx`` file ready to be streamed to the client.

A ``.dotx`` file is identical to a ``.docx`` ZIP archive except that the
``[Content_Types].xml`` entry names the document part as a *template* rather
than a *document*.  python-docx has no native template-save API, so we post-
process the ZIP ourselves.
"""

from __future__ import annotations

import io
import zipfile
from typing import Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from .models import AlignmentEnum, FontConfig, LayoutConfig, ParagraphConfig, StyleConfig

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ALIGNMENT_MAP = {
    AlignmentEnum.LEFT: WD_ALIGN_PARAGRAPH.LEFT,
    AlignmentEnum.CENTER: WD_ALIGN_PARAGRAPH.CENTER,
    AlignmentEnum.RIGHT: WD_ALIGN_PARAGRAPH.RIGHT,
    AlignmentEnum.JUSTIFY: WD_ALIGN_PARAGRAPH.JUSTIFY,
}

# Built-in style names that python-docx knows how to find / create.
_BUILTIN_STYLES = {
    "Normal",
    "Title",
    "Subtitle",
    "Heading 1",
    "Heading 2",
    "Heading 3",
    "Heading 4",
    "Body Text",
    "Caption",
    "Header",
    "Footer",
    "Footnote Text",
    "Default Paragraph Font",
}


def _apply_font(run_font, fc: FontConfig) -> None:
    """Apply a :class:`FontConfig` to a *run_font* object (paragraph or run)."""
    run_font.name = fc.name
    run_font.size = Pt(fc.size)
    run_font.bold = fc.bold
    run_font.italic = fc.italic
    if fc.color:
        hex_str = fc.color.lstrip("#")
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        run_font.color.rgb = RGBColor(r, g, b)


def _apply_paragraph_format(pf, pc: ParagraphConfig) -> None:
    """Apply a :class:`ParagraphConfig` to a *paragraph_format* object."""
    pf.alignment = _ALIGNMENT_MAP.get(pc.alignment, WD_ALIGN_PARAGRAPH.LEFT)
    pf.space_before = Pt(pc.space_before)
    pf.space_after = Pt(pc.space_after)
    # line_spacing: use a multiplier value
    from docx.shared import Length  # noqa: F401
    pf.line_spacing = Pt(pc.line_spacing * 12)  # 12pt × multiplier
    if pc.first_line_indent > 0:
        pf.first_line_indent = Inches(pc.first_line_indent)
    pf.left_indent = Inches(pc.left_indent)
    pf.right_indent = Inches(pc.right_indent)


def _apply_style_config(doc: Document, sc: StyleConfig) -> None:
    """Create or update a Word style from a :class:`StyleConfig`."""
    styles = doc.styles

    # Determine the style type (paragraph vs character)
    from docx.enum.style import WD_STYLE_TYPE

    # Try to get existing style; create if missing
    try:
        style = styles[sc.name]
    except KeyError:
        # Derive base style
        base_name = sc.based_on or ("Normal" if sc.name not in _BUILTIN_STYLES else None)
        style = styles.add_style(sc.name, WD_STYLE_TYPE.PARAGRAPH)
        if base_name:
            try:
                style.base_style = styles[base_name]
            except KeyError:
                pass  # base not found – leave unset

    _apply_font(style.font, sc.font)
    _apply_paragraph_format(style.paragraph_format, sc.paragraph)


def _add_header_footer_text(
    section,
    is_header: bool,
    text: Optional[str],
    include_page_number: bool,
    fc: Optional[FontConfig],
    alignment: AlignmentEnum,
) -> None:
    """Populate a section header or footer."""
    hf = section.header if is_header else section.footer
    hf.is_linked_to_previous = False

    # Clear default paragraph
    para = hf.paragraphs[0] if hf.paragraphs else hf.add_paragraph()
    para.clear()
    para.alignment = _ALIGNMENT_MAP.get(alignment, WD_ALIGN_PARAGRAPH.CENTER)

    if text:
        run = para.add_run(text)
        if fc:
            _apply_font(run.font, fc)

    if include_page_number:
        if text:
            para.add_run("  ")
        _add_page_number(para, fc)


def _add_page_number(para, fc: Optional[FontConfig] = None) -> None:
    """Insert an auto-updating PAGE field into *para*."""
    run = para.add_run()
    if fc:
        _apply_font(run.font, fc)

    fldChar_begin = OxmlElement("w:fldChar")
    fldChar_begin.set(qn("w:fldCharType"), "begin")
    run._r.append(fldChar_begin)

    instrText = OxmlElement("w:instrText")
    instrText.text = " PAGE "
    run._r.append(instrText)

    fldChar_end = OxmlElement("w:fldChar")
    fldChar_end.set(qn("w:fldCharType"), "end")
    run._r.append(fldChar_end)


def _add_columns(section, num_columns: int, spacing_inches: float) -> None:
    """Set the number of text columns on *section*."""
    if num_columns <= 1:
        return
    sectPr = section._sectPr
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), str(num_columns))
    cols.set(qn("w:space"), str(int(spacing_inches * 1440)))  # twips (1 inch = 1440 twips)


def _docx_to_dotx(docx_bytes: bytes) -> bytes:
    """Convert raw .docx bytes to .dotx by changing the content-type declaration."""
    buf_in = io.BytesIO(docx_bytes)
    buf_out = io.BytesIO()

    _DOCX_CT = (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document.main+xml"
    )
    _DOTX_CT = (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.template.main+xml"
    )

    with zipfile.ZipFile(buf_in, "r") as zin, zipfile.ZipFile(
        buf_out, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = data.replace(
                    _DOCX_CT.encode(), _DOTX_CT.encode()
                )
            zout.writestr(item, data)

    return buf_out.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_dotx_bytes(config: LayoutConfig) -> bytes:
    """Generate a ``.dotx`` template file and return its raw bytes.

    Parameters
    ----------
    config:
        A validated :class:`~app.models.LayoutConfig` describing the template.

    Returns
    -------
    bytes
        Raw bytes of a ``.dotx`` Word template.
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
            _add_columns(section, config.page.columns, config.page.column_spacing)

        # Header
        if config.header is not None:
            _add_header_footer_text(
                section,
                is_header=True,
                text=config.header.text,
                include_page_number=config.header.include_page_number,
                fc=config.header.font,
                alignment=config.header.alignment,
            )

        # Footer
        if config.footer is not None:
            _add_header_footer_text(
                section,
                is_header=False,
                text=config.footer.text,
                include_page_number=config.footer.include_page_number,
                fc=config.footer.font,
                alignment=config.footer.alignment,
            )

    # ---- Styles ------------------------------------------------------------
    for style_config in config.styles:
        _apply_style_config(doc, style_config)

    # ---- Placeholder paragraph (templates typically have one) --------------
    if not doc.paragraphs:
        doc.add_paragraph()

    # ---- Serialise to bytes then convert to .dotx --------------------------
    buf = io.BytesIO()
    doc.save(buf)
    return _docx_to_dotx(buf.getvalue())
