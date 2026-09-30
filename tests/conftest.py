import pytest

from reviscope import metacheck
from reviscope.schemas import MetacheckRecord


@pytest.fixture(autouse=True)
def no_real_metacheck(monkeypatch):
    """Tests never start R, pandoc or an upload; tests/test_metacheck.py restores the stage with stubbed calls."""
    monkeypatch.setattr(metacheck, "run_metacheck", lambda *args, **kwargs: MetacheckRecord(status="skipped", reason="skipped in tests"))
