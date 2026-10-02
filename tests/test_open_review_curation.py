import hashlib
import runpy
from pathlib import Path

import pytest


HELPERS = runpy.run_path(str(Path(__file__).parents[1] / "eval/prepare_open_reviews.py"))


def test_changed_cached_source_is_refused_without_replacing_it(tmp_path):
    source = tmp_path / "submitted.pdf"
    source.write_bytes(b"different source version")
    expected = hashlib.sha256(b"reviewed version").hexdigest()
    with pytest.raises(ValueError, match="Hash mismatch"):
        HELPERS["pinned_download"](source, "https://example.org/submitted.pdf", expected)
    assert source.read_bytes() == b"different source version"


def test_bundled_report_excludes_editor_and_other_reviewer_but_keeps_all_criticism():
    criticism = "\n".join(f"Specific concern {i}." for i in range(75))
    bundle = f"Editor decision\nReviewer One\n{criticism}\nReviewer Two\nOther report."
    selected = HELPERS["review_section"](bundle, {"start_after": "Reviewer One", "end_before": "Reviewer Two"})
    assert selected.strip() == criticism


def test_ambiguous_report_boundary_is_refused():
    with pytest.raises(ValueError, match="ambiguous"):
        HELPERS["review_section"]("Reviewer One\nA\nReviewer One\nB", {"start_after": "Reviewer One"})
