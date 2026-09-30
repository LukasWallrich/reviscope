import pytest


@pytest.fixture(autouse=True)
def no_real_metacheck(monkeypatch):
    """Tests never start R or upload a manuscript; a test that needs metacheck stubs run_r."""
    def refuse(script, args):
        raise AssertionError(f"test called the real metacheck script {script}")
    monkeypatch.setattr("reviscope.metacheck.run_r", refuse)
