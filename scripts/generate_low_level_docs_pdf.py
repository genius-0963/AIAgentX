#!/usr/bin/env python3
"""Render the production implementation blueprint to a reviewable PDF."""

from __future__ import annotations

import html
import re
import sys
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

SOURCE = Path("docs/LOW_LEVEL_PRODUCTION_IMPLEMENTATION.md")
OUTPUT = Path("output/pdf/AIAgentX_Low_Level_Production_Implementation.pdf")

NAVY = colors.HexColor("#15243E")
BLUE = colors.HexColor("#2563EB")
TEAL = colors.HexColor("#0F766E")
SLATE = colors.HexColor("#334155")
MID = colors.HexColor("#52627D")
PALE_BLUE = colors.HexColor("#EEF4FF")
PALE_TEAL = colors.HexColor("#ECFDF5")
PALE_GRAY = colors.HexColor("#F6F8FB")
BORDER = colors.HexColor("#D6DEEA")
AMBER = colors.HexColor("#B45309")


class PipelineDiagram(Flowable):
    """Compact vector diagram for the worker execution boundary."""

    def __init__(self, width=468, height=132):
        super().__init__()
        self.width = width
        self.height = height

    def _box(self, c, x, y, w, h, title, body, fill, text_color=SLATE):
        c.setFillColor(fill)
        c.setStrokeColor(BORDER if fill != NAVY else NAVY)
        c.roundRect(x, y, w, h, 7, fill=1, stroke=1)
        c.setFillColor(text_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(x + w / 2, y + h - 17, title)
        c.setFont("Helvetica", 7.3)
        for number, line in enumerate(body.split("\n")):
            c.drawCentredString(x + w / 2, y + h - 31 - (number * 9), line)

    def _arrow(self, c, x1, y1, x2, y2):
        c.setStrokeColor(BLUE)
        c.setFillColor(BLUE)
        c.setLineWidth(1.2)
        c.line(x1, y1, x2, y2)
        p = c.beginPath()
        p.moveTo(x2, y2)
        p.lineTo(x2 - 5, y2 + 3)
        p.lineTo(x2 - 5, y2 - 3)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    def draw(self):
        c = self.canv
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MID)
        c.drawString(0, 121, "Worker execution boundary: persistent state before outbound effect.")
        self._box(c, 2, 42, 88, 48, "Run claim", "lease + cancel\ncheck", PALE_GRAY)
        self._box(c, 111, 42, 95, 48, "Context", "memory + policy\nsnapshot", PALE_BLUE)
        self._box(c, 227, 42, 92, 48, "Model", "provider adapter\nbudget", NAVY, colors.white)
        self._box(c, 340, 42, 125, 48, "Tool gateway", "validate, authorize,\napprove, invoke", PALE_TEAL)
        self._arrow(c, 90, 66, 111, 66)
        self._arrow(c, 206, 66, 227, 66)
        self._arrow(c, 319, 66, 340, 66)
        c.setStrokeColor(TEAL)
        c.setDash(3, 3)
        c.line(402, 42, 402, 17)
        c.setDash()
        c.setFillColor(TEAL)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(402, 6, "audit + outbox")


def make_styles():
    sheet = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "LLTitle", parent=sheet["Title"], fontName="Helvetica-Bold", fontSize=26,
            leading=31, textColor=NAVY, spaceBefore=12, spaceAfter=8,
        ),
        "meta": ParagraphStyle(
            "Meta", parent=sheet["BodyText"], fontName="Helvetica", fontSize=9.5,
            leading=13.5, textColor=MID, spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "LLH1", parent=sheet["Heading1"], fontName="Helvetica-Bold", fontSize=17,
            leading=22, textColor=NAVY, spaceBefore=17, spaceAfter=7, keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "LLH2", parent=sheet["Heading2"], fontName="Helvetica-Bold", fontSize=12.3,
            leading=16, textColor=BLUE, spaceBefore=11, spaceAfter=5, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "LLBody", parent=sheet["BodyText"], fontName="Helvetica", fontSize=9.25,
            leading=13.15, textColor=SLATE, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "LLBullet", parent=sheet["BodyText"], fontName="Helvetica", fontSize=9.15,
            leading=12.9, textColor=SLATE, leftIndent=14, firstLineIndent=-9, spaceAfter=3,
        ),
        "numbered": ParagraphStyle(
            "LLNumbered", parent=sheet["BodyText"], fontName="Helvetica", fontSize=9.15,
            leading=12.9, textColor=SLATE, leftIndent=15, firstLineIndent=-13, spaceAfter=3,
        ),
        "table": ParagraphStyle(
            "LLTable", parent=sheet["BodyText"], fontName="Helvetica", fontSize=7.25,
            leading=9.2, textColor=SLATE,
        ),
        "tablehead": ParagraphStyle(
            "LLTableHead", parent=sheet["BodyText"], fontName="Helvetica-Bold", fontSize=7.25,
            leading=9.0, textColor=colors.white,
        ),
        "code": ParagraphStyle(
            "LLCode", parent=sheet["Code"], fontName="Courier", fontSize=6.65,
            leading=8.5, textColor=NAVY, leftIndent=7, rightIndent=7,
        ),
        "note": ParagraphStyle(
            "LLNote", parent=sheet["BodyText"], fontName="Helvetica", fontSize=9.1,
            leading=13.2, textColor=SLATE,
        ),
    }


def inline_markup(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    return escaped


def paragraph(value: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(inline_markup(value), style)


def table_widths(count: int, available: float) -> list[float]:
    presets = {
        2: [0.34, 0.66],
        3: [0.21, 0.43, 0.36],
        4: [0.16, 0.34, 0.23, 0.27],
        5: [0.14, 0.25, 0.21, 0.20, 0.20],
    }
    fractions = presets.get(count, [1 / count] * count)
    return [available * fraction for fraction in fractions]


def make_table(rows: list[list[str]], width: float, style_map: dict[str, ParagraphStyle]) -> Table:
    data = []
    for row_number, row in enumerate(rows):
        text_style = style_map["tablehead"] if row_number == 0 else style_map["table"]
        data.append([paragraph(cell, text_style) for cell in row])
    result = Table(data, colWidths=table_widths(len(rows[0]), width), repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GRAY]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return result


def hard_wrap_code(lines: list[str]) -> str:
    output: list[str] = []
    for raw_line in lines:
        if len(raw_line) <= 92:
            output.append(raw_line)
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        wrapped = textwrap.wrap(
            raw_line, width=92, subsequent_indent=" " * min(indent + 2, 16),
            break_long_words=False, break_on_hyphens=False,
        )
        output.extend(wrapped or [raw_line])
    return "\n".join(output)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 0.55 * inch, letter[0] - doc.rightMargin, 0.55 * inch)
    canvas.setFillColor(MID)
    canvas.setFont("Helvetica", 7.7)
    canvas.drawString(doc.leftMargin, 0.34 * inch, "AIAgentX Low-Level Production Implementation Blueprint")
    canvas.drawRightString(letter[0] - doc.rightMargin, 0.34 * inch, f"Page {doc.page}")
    canvas.restoreState()


def parse_markdown(source: Path, styles: dict[str, ParagraphStyle], usable_width: float):
    lines = source.read_text(encoding="utf-8").splitlines()
    story = []
    index = 0
    code_mode = False
    code_lines: list[str] = []
    paragraph_lines: list[str] = []
    seen_title = False
    table_rows: list[list[str]] = []

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(part.strip() for part in paragraph_lines)
            story.append(paragraph(text, styles["body"]))
            paragraph_lines = []

    def flush_table():
        nonlocal table_rows
        if table_rows:
            story.append(make_table(table_rows, usable_width, styles))
            story.append(Spacer(1, 6))
            table_rows = []

    def flush_code():
        nonlocal code_lines
        if code_lines:
            story.append(Preformatted(hard_wrap_code(code_lines), styles["code"], maxLineLength=108))
            story.append(Spacer(1, 6))
            code_lines = []

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            flush_table()
            if code_mode:
                flush_code()
                code_mode = False
            else:
                code_mode = True
            index += 1
            continue
        if code_mode:
            code_lines.append(line)
            index += 1
            continue
        if not stripped:
            flush_paragraph()
            flush_table()
            index += 1
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            cells = [cell.strip() for cell in stripped[1:-1].split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
                table_rows.append(cells)
            index += 1
            continue
        flush_table()
        if stripped.startswith("# "):
            flush_paragraph()
            if not seen_title:
                story.extend([
                    Spacer(1, 0.18 * inch),
                    paragraph(stripped[2:], styles["title"]),
                    HRFlowable(width="100%", thickness=2, color=BLUE, spaceBefore=4, spaceAfter=14),
                    Table([[Paragraph("<b>Reference implementation blueprint</b><br/>This is a detailed build specification based on the conceptual AIAgentX documentation. It makes deliberate, replaceable v1 engineering decisions because no application source exists in the repository.", styles["note"])]], colWidths=[usable_width], style=[
                        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                        ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                    ]),
                    Spacer(1, 10),
                ])
                seen_title = True
            index += 1
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            heading = stripped[3:]
            story.append(paragraph(heading, styles["h1"]))
            if heading.startswith("6."):
                story.append(PipelineDiagram())
                story.append(Spacer(1, 5))
            index += 1
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            story.append(paragraph(stripped[4:], styles["h2"]))
            index += 1
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            story.append(paragraph("- " + stripped[2:], styles["bullet"]))
            index += 1
            continue
        match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if match:
            flush_paragraph()
            story.append(paragraph(f"{match.group(1)}. {match.group(2)}", styles["numbered"]))
            index += 1
            continue
        if stripped.startswith("**Status:") or stripped.startswith("**Audience:") or stripped.startswith("**Scope:") or stripped.startswith("**Evidence boundary:"):
            flush_paragraph()
            story.append(paragraph(stripped, styles["meta"]))
            index += 1
            continue
        paragraph_lines.append(stripped)
        index += 1

    flush_paragraph()
    flush_table()
    flush_code()
    return story


def build(output: Path) -> None:
    styles = make_styles()
    doc = SimpleDocTemplate(
        str(output), pagesize=letter, leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.66 * inch, bottomMargin=0.8 * inch,
        title="AIAgentX Low-Level Production Implementation Blueprint",
        author="AIAgentX Engineering",
    )
    story = parse_markdown(SOURCE, styles, letter[0] - doc.leftMargin - doc.rightMargin)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    build(destination)
    print(destination)
