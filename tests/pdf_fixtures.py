"""Small real PDFs written with pypdf: one page per raw content stream, Helvetica text."""

from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject


def _font():
    return DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})


def cells(items, size=12):
    return "\n".join(f"BT /F1 {size} Tf 1 0 0 1 {x} {y} Tm ({text}) Tj ET" for x, y, text in items)


def at(x, y, items):
    return [(x + dx, y + dy, text) for dx, dy, text in items]


def write_pdf(path, contents, xobjects=None):
    """Write one page per raw content stream; xobjects maps a page index to a form XObject stream."""
    writer = PdfWriter()
    for i, content in enumerate(contents):
        page = writer.add_blank_page(width=600, height=800)
        resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): _font()})})
        if xobjects and i in xobjects:
            form = DecodedStreamObject()
            form.set_data(xobjects[i].encode())
            form.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Form"),
                         NameObject("/BBox"): ArrayObject([FloatObject(v) for v in (0, 0, 600, 800)]),
                         NameObject("/Resources"): DictionaryObject({
                             NameObject("/Font"): DictionaryObject({NameObject("/F1"): _font()})})})
            resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Fm1"): writer._add_object(form)})
        page[NameObject("/Resources")] = resources
        stream = DecodedStreamObject()
        stream.set_data(content.encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)
    return path


# A table painted column by column, unlike its reading order.
TABLE = [(0, 0, "Group"), (0, -20, "Treatment"), (0, -40, "Control"),
         (200, 0, "Mean"), (200, -20, "1.25"), (200, -40, "2.50")]


def table_pdf(path):
    return write_pdf(path, [
        cells([(50, 740, "See Table 1 for the results.")]),
        cells([(50, 740, "Table 1. Results")] + at(50, 700, TABLE)),
    ])


def sideways_pdf(path):
    """One page whose table is drawn turned a quarter, as a landscape table on a portrait page."""
    sideways = "q 0 1 -1 0 560 100 cm\n" + cells([(0, 0, "Table 5. Rotated results")] + at(0, -30, TABLE)) + "\nQ"
    return write_pdf(path, [cells([(50, 760, "Running head")]) + "\n" + sideways])
