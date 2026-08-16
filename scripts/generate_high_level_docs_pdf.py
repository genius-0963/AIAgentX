#!/usr/bin/env python3
"""Build the AIAgentX high-level architecture PDF from the validated draft."""

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT = Path("output/pdf/AIAgentX_High_Level_Documentation.pdf")

NAVY = colors.HexColor("#18243A")
BLUE = colors.HexColor("#2563EB")
MID = colors.HexColor("#52627D")
PALE_BLUE = colors.HexColor("#EEF4FF")
PALE_GRAY = colors.HexColor("#F5F7FA")
BORDER = colors.HexColor("#D7DFEA")
GREEN = colors.HexColor("#0F766E")


class ArchitectureDiagram(Flowable):
    """A simple vector diagram that remains crisp in the PDF."""

    def __init__(self, width=468, height=190):
        super().__init__()
        self.width = width
        self.height = height

    def _box(self, canvas, x, y, w, h, title, subtitle, fill, stroke=colors.white):
        canvas.setFillColor(fill)
        canvas.setStrokeColor(stroke)
        canvas.roundRect(x, y, w, h, 8, fill=1, stroke=1)
        canvas.setFillColor(colors.white if fill == NAVY else NAVY)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawCentredString(x + w / 2, y + h - 18, title)
        canvas.setFont("Helvetica", 7.6)
        lines = subtitle.split("\n")
        for index, line in enumerate(lines):
            canvas.drawCentredString(x + w / 2, y + h - 32 - (index * 10), line)

    def _arrow(self, canvas, x1, y1, x2, y2, dashed=False):
        canvas.setStrokeColor(BLUE)
        canvas.setFillColor(BLUE)
        canvas.setLineWidth(1.4)
        if dashed:
            canvas.setDash(3, 3)
        canvas.line(x1, y1, x2, y2)
        canvas.setDash()
        if x2 >= x1:
            points = [(x2, y2), (x2 - 6, y2 + 3), (x2 - 6, y2 - 3)]
        else:
            points = [(x2, y2), (x2 + 6, y2 + 3), (x2 + 6, y2 - 3)]
        path = canvas.beginPath()
        path.moveTo(*points[0])
        path.lineTo(*points[1])
        path.lineTo(*points[2])
        path.close()
        canvas.drawPath(path, fill=1, stroke=0)

    def draw(self):
        c = self.canv
        self._box(c, 4, 119, 112, 48, "Application", "Developer or host", PALE_GRAY, BORDER)
        self._box(c, 170, 119, 128, 48, "Agent factory", "spawn_agent", NAVY)
        self._box(c, 352, 119, 112, 48, "Agent runtime", "role, context, tools", PALE_GRAY, BORDER)
        self._box(c, 170, 25, 128, 50, "Memory kernel", "ephemeral session\nlocal persistent", PALE_BLUE, BORDER)
        self._box(c, 352, 25, 112, 50, "Resilience", "retry, fallback\nerror handling", PALE_BLUE, BORDER)
        self._box(c, 4, 25, 112, 50, "Telemetry", "optional, non-blocking\nconsent unverified", PALE_BLUE, BORDER)
        self._arrow(c, 116, 143, 170, 143)
        self._arrow(c, 298, 143, 352, 143)
        self._arrow(c, 408, 119, 408, 75)
        self._arrow(c, 298, 50, 352, 50)
        self._arrow(c, 234, 119, 234, 75)
        self._arrow(c, 170, 50, 116, 50, dashed=True)
        c.setFont("Helvetica", 7.6)
        c.setFillColor(MID)
        c.drawString(0, 178, "Conceptual architecture - reference-defined behavior; implementation details require validation.")


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=30,
            leading=35, textColor=NAVY, spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=13,
            leading=19, textColor=MID, spaceAfter=22,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=18,
            leading=23, textColor=NAVY, spaceBefore=17, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.4,
            leading=16, textColor=BLUE, spaceBefore=11, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.7,
            leading=14.2, textColor=colors.HexColor("#334155"), spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="Helvetica", fontSize=8.3,
            leading=11.2, textColor=MID, spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"], fontName="Helvetica", fontSize=9.5,
            leading=13.5, textColor=colors.HexColor("#334155"), leftIndent=14,
            firstLineIndent=-9, spaceAfter=3,
        ),
        "cell": ParagraphStyle(
            "Cell", parent=base["BodyText"], fontName="Helvetica", fontSize=8.25,
            leading=10.5, textColor=colors.HexColor("#334155"),
        ),
        "cell_header": ParagraphStyle(
            "CellHeader", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8.15,
            leading=10, textColor=colors.white,
        ),
        "code": ParagraphStyle(
            "Code", parent=base["Code"], fontName="Courier", fontSize=8.5,
            leading=12, textColor=NAVY, leftIndent=8, rightIndent=8,
        ),
    }


def para(text, style):
    return Paragraph(text, style)


def bullets(items, style):
    return [para("- " + item, style) for item in items]


def table(rows, widths, style_map):
    converted = []
    for row_index, row in enumerate(rows):
        key = "cell_header" if row_index == 0 else "cell"
        converted.append([para(cell, style_map[key]) for cell in row])
    result = Table(converted, colWidths=widths, hAlign="LEFT", repeatRows=1)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_GRAY]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return result


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 0.56 * inch, letter[0] - doc.rightMargin, 0.56 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MID)
    canvas.drawString(doc.leftMargin, 0.35 * inch, "AIAgentX High-Level Technical Documentation")
    canvas.drawRightString(letter[0] - doc.rightMargin, 0.35 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build(output: Path):
    s = styles()
    doc = SimpleDocTemplate(
        str(output), pagesize=letter, rightMargin=0.78 * inch, leftMargin=0.78 * inch,
        topMargin=0.72 * inch, bottomMargin=0.82 * inch,
        title="AIAgentX High-Level Technical Documentation",
        author="AIAgentX Open-Source Core Team",
    )
    story = []
    story += [
        Spacer(1, 0.42 * inch),
        para("AIAgentX", s["title"]),
        para("High-Level Technical Documentation", s["title"]),
        HRFlowable(width="100%", thickness=2, color=BLUE, spaceBefore=8, spaceAfter=18),
        para("Conceptual architecture draft", s["subtitle"]),
        para("<b>Document status:</b> Reference-defined design intent. The supplied repository contains no application source files or commits, so implementation-level behavior has not been verified.", s["body"]),
        Spacer(1, 0.24 * inch),
        para("Purpose", s["h1"]),
        para("AIAgentX is described in the supplied reference as a configuration-light multi-agent runtime. The intended experience is a small public API that creates agents, binds approved tools, selects a memory mode, and executes work through a managed runtime context.", s["body"]),
        para("This document preserves that product direction while clearly separating the stated design from behavior that must be verified when the implementation is available.", s["body"]),
        Spacer(1, 0.14 * inch),
        para("How to read this document", s["h2"]),
        *bullets([
            "<b>Reference-defined:</b> described in the supplied high-level PDF.",
            "<b>Illustrative:</b> a communication aid, not an executable contract.",
            "<b>Validation required:</b> cannot be confirmed from the current repository checkout.",
        ], s["bullet"]),
        Spacer(1, 0.13 * inch),
        para("Design intent", s["h1"]),
        *bullets([
            "A semantic agent factory that minimizes application configuration.",
            "Role, context, and tool binding in a managed agent runtime.",
            "Ephemeral or local memory modes for session state.",
            "Resilience controls for transient provider and network failures.",
        ], s["bullet"]),
        PageBreak(),
        para("1. Conceptual Architecture", s["h1"]),
        para("The following diagram is a high-level view of the system described by the supplied reference. Solid paths represent the primary runtime path; the dotted path represents an optional telemetry integration.", s["body"]),
        ArchitectureDiagram(),
        Spacer(1, 0.13 * inch),
        table([
            ["Component", "Responsibility", "Evidence status"],
            ["Agent factory", "Creates a runtime from role, tools, memory, and model inputs.", "Reference-defined concept"],
            ["Agent runtime", "Holds instruction context, invokes tools, and coordinates a model interaction.", "Reference-defined concept"],
            ["Memory kernel", "Provides ephemeral and local memory modes.", "Storage technology and lifecycle unverified"],
            ["Resilience layer", "Handles transient failures and may select a fallback provider.", "Exact policy and error taxonomy unverified"],
            ["Telemetry hook", "Emits operational metadata outside the main request path.", "Integration and privacy model unverified"],
        ], [1.05 * inch, 2.77 * inch, 2.25 * inch], s),
        para("2. Intended Runtime Flow", s["h1"]),
        *bullets([
            "The host application requests an agent with a role and optional tool, memory, and model preferences.",
            "The factory validates inputs, assembles context, and binds permitted tools.",
            "The runtime invokes a model provider and exchanges relevant context with the selected memory mode.",
            "The resilience layer evaluates transient failures for retries or provider fallback when policy permits.",
            "If configured, approved events are emitted asynchronously to telemetry before a result or structured failure is returned.",
        ], s["bullet"]),
        PageBreak(),
        para("3. Proposed Public Interface", s["h1"]),
        para("The supplied reference presents <b>spawn_agent</b> as the primary entry point. This signature is illustrative; it is not verified against an implementation.", s["body"]),
        Table([[para("from ai_agent_x import spawn_agent<br/><br/>agent = spawn_agent(<br/>    role=\"researcher\",<br/>    tools=[\"web_search\"],<br/>    memory=\"local\",<br/>    model=\"gpt-4o\",<br/>)<br/><br/>response = agent.ask(\"Analyze market gaps in AI infrastructure.\")", s["code"])]], colWidths=[6.08 * inch], style=[
            ("BACKGROUND", (0, 0), (-1, -1), PALE_GRAY),
            ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]),
        Spacer(1, 0.14 * inch),
        table([
            ["Parameter", "Intended meaning", "Reference default", "Validation needed"],
            ["role", "Persona, operating boundary, or instruction set.", "Required", "Schema and safety rules"],
            ["tools", "Approved runtime utilities.", "[]", "Registration, authorization, isolation"],
            ["memory", "Session-state selection.", "ephemeral", "Durability, encryption, retention"],
            ["model", "Preferred model or route.", "gpt-4o", "Provider mapping and fallback behavior"],
        ], [0.75 * inch, 2.05 * inch, 1.0 * inch, 2.28 * inch], s),
        para("4. Operational and Security Considerations", s["h1"]),
        para("Before production use, the implementation should document and test the controls below.", s["body"]),
        *bullets([
            "Authentication, authorization, and least-privilege tool execution.",
            "Secret management for providers, tools, and telemetry.",
            "Input and output safety controls, including approval gates for sensitive tool actions.",
            "Memory classification, encryption, retention, deletion, and tenant isolation.",
            "Timeouts, retry limits, idempotency, circuit breaking, and fallback criteria.",
            "Telemetry schema, consent, redaction, opt-out behavior, logging, and incident response.",
        ], s["bullet"]),
        PageBreak(),
        para("5. Implementation Validation Checklist", s["h1"]),
        para("Use this checklist to turn the conceptual draft into authoritative developer documentation when source is available.", s["body"]),
        table([
            ["#", "Verification activity", "Expected documentation outcome"],
            ["1", "Locate package entry points, supported runtimes, and released version.", "Accurate installation and API overview"],
            ["2", "Trace agent creation through tool binding, model invocation, error handling, and result return.", "Verified runtime sequence diagram"],
            ["3", "Record memory providers, schema, persistence boundaries, and cleanup behavior.", "Data lifecycle and retention section"],
            ["4", "Verify provider adapters, backoff policy, rate-limit handling, and fallback semantics.", "Resilience and reliability contract"],
            ["5", "Inspect telemetry payloads, transport, privacy controls, and async behavior.", "Observability and privacy reference"],
            ["6", "Add deployment topology, configuration reference, test strategy, and onboarding steps.", "Production-ready operator guide"],
        ], [0.35 * inch, 3.15 * inch, 2.58 * inch], s),
        para("Document maintenance", s["h1"]),
        para("Maintain this document alongside public-interface or runtime-architecture changes. Each statement should be labeled implementation-verified, proposal, or deprecated design intent. Replace illustrative material with links to authoritative modules and tests once the codebase is populated.", s["body"]),
        Spacer(1, 0.14 * inch),
        Table([[para("<b>Current evidence boundary</b><br/>This document is based on the supplied AIAgentX high-level reference PDF. The checked-out repository had no application files and no Git commits at authoring time.", s["body"])]], colWidths=[6.08 * inch], style=[
            ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
            ("BOX", (0, 0), (-1, -1), 0.7, BLUE),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]),
    ]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    build(target)
    print(target)
