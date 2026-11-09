import pytest

from reviscope import metacheck
from reviscope.schemas import MetacheckRecord


@pytest.fixture(autouse=True)
def no_real_metacheck(monkeypatch):
    """Tests never start R, pandoc or an upload; tests/test_metacheck.py restores the stage with stubbed calls."""
    monkeypatch.setattr(metacheck, "run_metacheck", lambda *args, **kwargs: MetacheckRecord(status="skipped", reason="skipped in tests"))


@pytest.fixture(autouse=True)
def no_reader_pass(request, monkeypatch):
    """Offline stub backends predate the reader stage; tests marked reader_pass keep it."""
    if "reader_pass" not in request.keywords:
        from reviscope.pipeline import ReviewPipeline
        monkeypatch.setattr(ReviewPipeline, "_reader", lambda self, run, out, evidence: None)


def pytest_configure(config):
    config.addinivalue_line("markers", "reader_pass: run the final reader stage in this test")
