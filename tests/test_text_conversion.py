import base64
import shutil

import pytest
from pypdf import PdfReader

from reviscope.metacheck import text_to_pdf

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg==")


@pytest.mark.skipif(not (shutil.which("pandoc") and shutil.which("tectonic")), reason="needs pandoc and tectonic")
@pytest.mark.parametrize("suffix", [".txt", ".md"])
def test_untrusted_tex_and_local_links_do_not_reach_the_pdf(tmp_path, suffix):
    secret = tmp_path / "secret.tex"
    secret.write_text("SECRETCANARY")
    image = tmp_path / "local.png"
    image.write_bytes(PNG)
    manuscript = tmp_path / f"paper{suffix}"
    manuscript.write_text(f"Method\n\nWe measured things.\n\n\\input{{/etc/hosts}} \\input{{{secret}}}\n\n"
                          f"Inline math $\\input{{{secret}}}$ and \\newcommand{{\\x}}{{\\input{{{secret}}}}}\\x\n\n"
                          f"![figure]({image})\n\nResults\n\nDone.\n")
    out = tmp_path / "out"
    out.mkdir()
    pdf, _ = text_to_pdf(manuscript, out)
    reader = PdfReader(pdf)
    text = "".join(page.extract_text() or "" for page in reader.pages)
    assert "We measured things" in text
    assert "SECRETCANARY" not in text and "broadcasthost" not in text and "localhost" not in text
    assert not any(page.images for page in reader.pages)


@pytest.mark.skipif(not (shutil.which("pandoc") and shutil.which("tectonic")), reason="needs pandoc and tectonic")
def test_control_characters_from_pdf_extraction_do_not_stop_typesetting(tmp_path):
    manuscript = tmp_path / "paper.txt"
    manuscript.write_text("Method\n\nWe recruited N\x02 = 120 adults\x13 from Japan.\n\nResults\n\nDone.\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    pdf, note = text_to_pdf(manuscript, out)
    text = "".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
    assert "adults" in text and "2 control characters replaced" in note
