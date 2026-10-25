"""Build table_mismatch.pdf: a short synthetic manuscript whose text and Table 1 disagree.

The Results say the gratitude condition reported higher life satisfaction than the control
condition; Table 1 prints the higher mean in the control row (5.42 vs 4.61). The table's cells
are drawn in a shuffled order, so the extracted text lists the numbers without their rows and
only the printed page shows which mean belongs to which condition. Positive affect is
consistent with the text, so the error is confined to one row-column association.

    uv run python examples/table_mismatch/build.py
"""
import random
import textwrap
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

TITLE = "Brief gratitude journaling and life satisfaction: a randomised experiment"
PAGES = [
    [("h", TITLE),
     ("h", "Abstract"),
     ("p", "Gratitude interventions are widely recommended, but evidence for brief, unsupervised versions is mixed. "
           "We randomly assigned 120 undergraduates to list three things they were grateful for each evening for two "
           "weeks or to list three neutral events. Participants who wrote gratitude lists reported higher life "
           "satisfaction than controls, and slightly more positive affect (Table 1). We conclude that a two-week "
           "gratitude exercise can raise life satisfaction in student samples."),
     ("h", "Method"),
     ("p", "Participants were 120 undergraduates (78 women, 42 men; mean age 20.4 years) recruited from a psychology "
           "participant pool in exchange for course credit. The sample size was chosen to detect an effect of d = 0.55 "
           "with 80% power in a two-sided test at alpha = .05. Participants were randomly assigned by the survey "
           "software to the gratitude condition (n = 60) or the control condition (n = 60); no participant was excluded."),
     ("p", "Each evening for fourteen days, participants in the gratitude condition listed three things for which they "
           "were grateful that day. Participants in the control condition listed three events from their day without "
           "evaluating them. Compliance was high in both conditions: participants completed a median of 13 of the 14 "
           "entries."),
     ("p", "At the end of the two weeks, participants completed the Satisfaction With Life Scale (five items, rated "
           "from 1 = strongly disagree to 7 = strongly agree; alpha = .86) and the positive affect subscale of the PANAS "
           "(ten items, rated from 1 = very slightly to 5 = extremely; alpha = .88). Scale scores are item means."),
     ("h", "Results"),
     ("p", "Table 1 reports the means and standard deviations of both outcomes by condition. As predicted, the "
           "gratitude condition reported higher life satisfaction than the control condition, t(118) = 3.75, p < .001, "
           "d = 0.68. Positive affect was also slightly higher in the gratitude condition, t(118) = 3.48, p < .001, "
           "d = 0.64. Neither effect was moderated by gender (both interaction ps > .40)."),
     ],
    [("table", None),
     ("h", "Discussion"),
     ("p", "A brief gratitude exercise raised life satisfaction relative to a neutral listing task, with an effect of "
           "medium size. Because the control task matched the gratitude task in time and structure, the difference is "
           "unlikely to reflect demand to write or reflect each evening. These findings support recommending brief "
           "gratitude journaling to students who wish to improve their well-being."),
     ("p", "Limitations include the student sample, the short follow-up and reliance on self-report. Future work "
           "should test whether the effect persists beyond the end of the intervention and whether it generalises to "
           "community samples."),
     ],
]
# Condition, life satisfaction M, SD, positive affect M, SD. Control is higher on life satisfaction,
# contrary to the text; t(118) = 3.75 matches the size of the difference.
ROWS = [("Gratitude (n = 60)", "4.61", "1.25", "3.48", "0.71"),
        ("Control (n = 60)", "5.42", "1.10", "3.02", "0.72")]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text(x: float, y: float, text: str, size: float = 10.5, font: str = "F1") -> str:
    return f"BT /{font} {size} Tf 1 0 0 1 {x:.1f} {y:.1f} Tm ({_escape(text)}) Tj ET"


def _line(x0: float, x1: float, y: float) -> str:
    return f"0.6 w {x0} {y:.1f} m {x1} {y:.1f} l S"


def _table(y: float) -> tuple[list[str], float]:
    ops = [_text(72, y, "Table 1", font="F2"), _text(72, y - 15, "Life satisfaction and positive affect by condition")]
    top = y - 26
    cols = [72, 250, 310, 400, 460]
    cells = [(cols[1] + 10, top - 14, "Life satisfaction"), (cols[3] + 10, top - 14, "Positive affect")]
    cells += [(x, top - 30, label) for x, label in zip(cols, ["Condition", "M", "SD", "M", "SD"])]
    for r, row in enumerate(ROWS):
        cells += [(x, top - 48 - 16 * r, value) for x, value in zip(cols, row)]
    random.Random(7).shuffle(cells)  # drawing order, not reading order
    ops += [_line(72, 520, top), _line(250, 350, top - 19), _line(400, 500, top - 19), _line(72, 520, top - 35)]
    ops += [_text(x, yy, value) for x, yy, value in cells]
    bottom = top - 48 - 16 * len(ROWS) + 6
    ops += [_line(72, 520, bottom), _text(72, bottom - 14, "Note. Scale scores are item means. Life satisfaction: 1-7; positive affect: 1-5.", size=9)]
    return ops, bottom - 40


def _page(blocks: list[tuple[str, str | None]], number: int) -> str:
    ops, y = [], 740.0
    for kind, content in blocks:
        if kind == "table":
            table, y = _table(y)
            ops += table
        elif kind == "h":
            y -= 6
            ops.append(_text(72, y, content, size=12 if content != TITLE else 13, font="F2"))
            y -= 20
        else:
            for line in textwrap.wrap(content, 92):
                ops.append(_text(72, y, line))
                y -= 14
            y -= 8
    ops.append(_text(300, 40, str(number), size=9))
    return "\n".join(ops)


def build(path: Path) -> Path:
    writer = PdfWriter()
    fonts = DictionaryObject({NameObject(f"/{name}"): DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject(base)}) for name, base in (("F1", "/Helvetica"), ("F2", "/Helvetica-Bold"))})
    for number, blocks in enumerate(PAGES, 1):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fonts})
        stream = DecodedStreamObject()
        stream.set_data(_page(blocks, number).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)
    return path


if __name__ == "__main__":
    print(build(Path(__file__).with_name("table_mismatch.pdf")))
