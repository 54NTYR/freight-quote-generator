"""Jericho Freight SOP PDF layout. Matches the company ops-manual header style."""
from __future__ import annotations

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = HexColor("#1e3c72")
BLUE = HexColor("#2a5298")
INK = HexColor("#1d1d1f")
MUTED = HexColor("#4a4a4f")
LINE = HexColor("#d8d8de")
PALE = HexColor("#f4f6fb")
FORMULA = HexColor("#eef2f8")

CONTENT_WIDTH = 7 * inch
LABEL_COL_WIDTH = 1.65 * inch
BODY_COL_WIDTH = CONTENT_WIDTH - LABEL_COL_WIDTH
FORMULA_PAD = 10


def _styles():
    return {
        "title": ParagraphStyle(
            "SopTitle",
            fontName="Times-Bold",
            fontSize=18,
            leading=22,
            textColor=NAVY,
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "SopH1",
            fontName="Times-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "SopH2",
            fontName="Times-Bold",
            fontSize=11,
            leading=14,
            textColor=BLUE,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "meta_label": ParagraphStyle(
            "SopMetaLabel",
            fontName="Times-Bold",
            fontSize=9,
            leading=12,
            textColor=INK,
        ),
        "meta_value": ParagraphStyle(
            "SopMetaValue",
            fontName="Times-Roman",
            fontSize=9,
            leading=12,
            textColor=INK,
        ),
        "body": ParagraphStyle(
            "SopBody",
            fontName="Times-Roman",
            fontSize=10,
            leading=13,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "SopBullet",
            fontName="Times-Roman",
            fontSize=10,
            leading=13,
            textColor=INK,
            leftIndent=12,
            spaceAfter=3,
        ),
        "formula": ParagraphStyle(
            "SopFormula",
            fontName="Times-Bold",
            fontSize=10,
            leading=13,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "formula_body": ParagraphStyle(
            "SopFormulaBody",
            fontName="Times-Roman",
            fontSize=9.5,
            leading=12.5,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "SopFooter",
            fontName="Times-Roman",
            fontSize=8,
            leading=10,
            textColor=MUTED,
            alignment=TA_LEFT,
        ),
        "toc": ParagraphStyle(
            "SopToc",
            fontName="Times-Roman",
            fontSize=10,
            leading=14,
            textColor=INK,
            leftIndent=8,
            spaceAfter=1,
        ),
        "def_term": ParagraphStyle(
            "SopDefTerm",
            fontName="Times-Bold",
            fontSize=9.5,
            leading=12.5,
            textColor=NAVY,
        ),
        "def_body": ParagraphStyle(
            "SopDefBody",
            fontName="Times-Roman",
            fontSize=9.5,
            leading=12.5,
            textColor=INK,
        ),
    }


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def P(text: str, style) -> Paragraph:
    return Paragraph(_escape(text).replace("\n", "<br/>"), style)


def header_block(styles, doc: dict):
    title = P(doc["title"], styles["title"])
    meta = Table(
        [
            [
                P("Owner: " + doc["owner"], styles["meta_label"]),
                P("Effective Date: " + doc["effective_date"], styles["meta_label"]),
            ],
            [
                P("Version: " + doc["version"], styles["meta_label"]),
                P("Department: " + doc["department"], styles["meta_label"]),
            ],
        ],
        colWidths=[3.5 * inch, 3.5 * inch],
    )
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    info_heading = Paragraph(
        '<font color="white"><b>General Information</b></font>',
        ParagraphStyle("SopInfoHead", fontName="Times-Bold", fontSize=11, leading=14),
    )
    info = Table(
        [
            [info_heading, ""],
            [
                P("Description / Objective", styles["meta_label"]),
                P(doc["objective"], styles["meta_value"]),
            ],
            [
                P("Assignee", styles["meta_label"]),
                P(doc["assignee"], styles["meta_value"]),
            ],
        ],
        colWidths=[1.7 * inch, 5.3 * inch],
    )
    info.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (-1, 0)),
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("BACKGROUND", (0, 1), (0, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return [title, meta, Spacer(1, 10), info, Spacer(1, 12)]


def glossary_block(styles, items: list[str]):
    rows = [[P("Glossary", ParagraphStyle(
        "SopGlossHead", fontName="Times-Bold", fontSize=11, leading=14, textColor=white
    )), ""]]
    body = "<br/>".join(_escape(item) for item in items)
    rows.append([Paragraph(body, styles["toc"]), ""])
    table = Table(rows, colWidths=[7 * inch, 0])
    table.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (-1, 0)),
                ("SPAN", (0, 1), (-1, 1)),
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [table, Spacer(1, 12)]


def bullets(styles, items: list[str]):
    flow = []
    for item in items:
        flow.append(P("•  " + item, styles["bullet"]))
    return flow


def formula_box(styles, title: str, lines: list[str], width=None):
    box_width = CONTENT_WIDTH if width is None else width
    rows = [[P(title, styles["formula"])]]
    for line in lines:
        rows.append([P(line, styles["formula_body"])])
    table = Table(rows, colWidths=[box_width])
    table.hAlign = "LEFT"
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), FORMULA),
                ("BOX", (0, 0), (-1, -1), 0.6, BLUE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), FORMULA_PAD),
                ("RIGHTPADDING", (0, 0), (-1, -1), FORMULA_PAD),
                ("TOPPADDING", (0, 0), (0, 0), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                ("TOPPADDING", (0, 1), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -2), 1),
            ]
        )
    )
    return [Spacer(1, 4), KeepTogether([table]), Spacer(1, 8)]


def two_col(styles, heading: str, body_flowables: list):
    head = P(heading, styles["h2"])
    table = Table([[head, body_flowables]], colWidths=[LABEL_COL_WIDTH, BODY_COL_WIDTH])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
                ("LEFTPADDING", (1, 0), (1, 0), 8),
                ("RIGHTPADDING", (1, 0), (1, 0), 6),
                ("LINEBEFORE", (1, 0), (1, 0), 0.6, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return KeepTogether([table])


def definitions_block(styles, rows: list[tuple[str, str]]):
    data = [[
        Paragraph(
            '<font color="white"><b>Definitions</b></font>',
            ParagraphStyle("SopDefHead", fontName="Times-Bold", fontSize=11, leading=14),
        ),
        "",
    ]]
    for term, meaning in rows:
        data.append([P(term, styles["def_term"]), P(meaning, styles["def_body"])])
    table = Table(data, colWidths=[1.7 * inch, 5.3 * inch])
    style_cmds = [
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 1:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), PALE))
    table.setStyle(TableStyle(style_cmds))
    return [Spacer(1, 10), table]


def signoff_block(styles):
    table = Table(
        [
            [
                P("Reviewed By:", styles["meta_label"]),
                P("Date:", styles["meta_label"]),
            ],
            [
                P("Approved By:", styles["meta_label"]),
                P("Date:", styles["meta_label"]),
            ],
            [
                P("Last Updated By:", styles["meta_label"]),
                P("Date / Time:", styles["meta_label"]),
            ],
        ],
        colWidths=[3.5 * inch, 3.5 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [Spacer(1, 16), table]


def build_story(doc: dict):
    styles = _styles()
    story = []
    story.extend(header_block(styles, doc))
    story.extend(glossary_block(styles, doc["glossary"]))
    for block in doc["body"]:
        kind = block[0]
        if kind == "h1":
            story.append(P(block[1], styles["h1"]))
            story.append(HRFlowable(width="100%", thickness=0.6, color=NAVY, spaceAfter=8))
        elif kind == "h2":
            paras = [P(text, styles["body"]) for text in block[2]]
            formula = None
            if len(block) > 3:
                extra = block[3]
                if extra.get("bullets"):
                    paras.extend(bullets(styles, extra["bullets"]))
                formula = extra.get("formula")
            story.append(two_col(styles, block[1], paras))
            if formula:
                story.extend(formula_box(styles, formula[0], formula[1:]))
        elif kind == "p":
            story.append(P(block[1], styles["body"]))
        elif kind == "bullets":
            story.extend(bullets(styles, block[1]))
        elif kind == "formula":
            story.extend(formula_box(styles, block[1], block[2]))
    story.extend(definitions_block(styles, doc["definitions"]))
    story.extend(signoff_block(styles))
    return story, styles


def draw_page(canvas, doc_meta, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, letter[1] - 18, letter[0], 18, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Times-Roman", 8)
    canvas.drawString(0.7 * inch, letter[1] - 12, "Jericho Freight  |  " + doc_meta["title"])
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, letter[0], 28, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Times-Roman", 8)
    page = canvas.getPageNumber()
    canvas.drawString(0.7 * inch, 12, "Confidential  |  Internal use")
    canvas.drawRightString(letter[0] - 0.7 * inch, 12, f"{page}")
    canvas.restoreState()


def write_pdf(path: str, doc_meta: dict) -> None:
    story, _styles_unused = build_story(doc_meta)

    def on_page(canvas, doc):
        draw_page(canvas, doc_meta, doc)

    pdf = SimpleDocTemplate(
        path,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=doc_meta["title"],
        author="Jericho Freight",
    )
    pdf.build(story, onFirstPage=on_page, onLaterPages=on_page)
