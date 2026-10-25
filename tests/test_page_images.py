import hashlib
import struct
from pathlib import Path

import pytest

from reviscope import page_images
from reviscope.ingest import ingest
from reviscope.page_images import fingerprint, manifest_text, page_files, render_source

from pdf_fixtures import sideways_pdf, table_pdf


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def test_every_page_is_rendered_with_quarters_and_recorded_hashes(tmp_path):
    source = ingest(table_pdf(tmp_path / "table.pdf"))
    rendered = render_source(source, tmp_path / "run")
    assert rendered.error is None and rendered.pages == 2
    assert rendered.source_sha256 == source.sha256 and rendered.config["renderer"] == "pypdfium2"
    assert [(i.page, i.view) for i in rendered.images] == [
        (page, view) for page in (1, 2) for view in ("page", "upper-left", "upper-right", "lower-left", "lower-right")]
    assert page_files([rendered], source.id, 2) == [f"{source.id}/p002.png"] + [f"{source.id}/p002-{n}.png" for n in range(1, 5)]
    for image in rendered.images:
        data = (Path(rendered.directory) / image.file).read_bytes()
        assert hashlib.sha256(data).hexdigest() == image.sha256
        assert _png_size(data) == (image.width, image.height)
    whole = rendered.images[0]
    assert max(whole.width, whole.height) == page_images.PAGE_LONG_EDGE
    # Quarters are magnified: each covers just over half the page at a higher resolution.
    assert rendered.images[1].height > whole.height / 2 * 1.5
    assert (Path(rendered.directory) / source.id / "manifest.json").is_file()


def test_sideways_text_gets_upright_copies(tmp_path):
    source = ingest(sideways_pdf(tmp_path / "sideways.pdf"))
    rendered = render_source(source, tmp_path / "run")
    turned = [i for i in rendered.images if i.rotation]
    assert [i.view for i in turned] == ["turned", "turned-upper-left", "turned-upper-right", "turned-lower-left", "turned-lower-right"]
    assert turned[0].file == f"{source.id}/p001-turned.png" and turned[0].width > turned[0].height
    assert "Pages 1 have sideways text" in manifest_text([rendered])
    upright = render_source(ingest(table_pdf(tmp_path / "table.pdf")), tmp_path / "run")
    assert not any(i.rotation for i in upright.images)


def test_rendering_is_reused_only_while_files_and_configuration_match(tmp_path, monkeypatch):
    source = ingest(table_pdf(tmp_path / "table.pdf"))
    first = render_source(source, tmp_path / "run")
    import pypdfium2

    monkeypatch.setattr(pypdfium2, "PdfDocument", lambda *_: (_ for _ in ()).throw(AssertionError("re-rendered")))
    assert render_source(source, tmp_path / "run") == first
    monkeypatch.undo()

    damaged = Path(first.directory) / first.images[3].file
    damaged.write_bytes(b"not the rendered image")
    repaired = render_source(source, tmp_path / "run")
    assert repaired.images == first.images and fingerprint([repaired]) == fingerprint([first])

    monkeypatch.setattr(page_images, "QUARTER_DPI", 200)
    changed = render_source(source, tmp_path / "run")
    assert changed.config_hash != first.config_hash and changed.directory != first.directory
    assert fingerprint([changed]) != fingerprint([first])


def test_failures_and_non_pdf_sources(tmp_path):
    pdf = table_pdf(tmp_path / "table.pdf")
    source = ingest(pdf)
    pdf.write_bytes(pdf.read_bytes() + b"\n% edited after extraction\n")
    failed = render_source(source, tmp_path / "run")
    assert failed.error and "changed after its text was extracted" in failed.error and not failed.images
    assert "no page images" in manifest_text([failed])
    note = tmp_path / "paper.md"
    note.write_text("Plain text manuscript.")
    assert render_source(ingest(note), tmp_path / "run") is None
    assert manifest_text([]) == ""


@pytest.mark.parametrize("name", ["mackinnon", "satrevik"])
def test_corpus_landscape_and_portrait_pages_render(name):
    pdf = Path(__file__).resolve().parents[1] / f"eval/corpus/cache/open-review-curation-20261002/{name}/manuscript/original.pdf"
    if not pdf.is_file():
        pytest.skip("requires the local, untracked manuscript corpus cache")
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        rendered = render_source(ingest(pdf), Path(tmp))
        assert not rendered.error and {i.page for i in rendered.images} == set(range(1, rendered.pages + 1))
        page = {"mackinnon": 21, "satrevik": 29}[name]
        whole = next(i for i in rendered.images if i.page == page and i.view == "page")
        assert (whole.width > whole.height) == (name == "satrevik")  # satrevik's table page is landscape
