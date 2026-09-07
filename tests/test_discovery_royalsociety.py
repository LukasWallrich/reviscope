from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "eval" / "discover_royalsociety_preprints.py"
SPEC = spec_from_file_location("discover_royalsociety_preprints", SCRIPT)
MODULE = module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_received_date_does_not_cross_revision_boundaries(monkeypatch):
    xml = """<article><history>
      <date date-type="received"><day>17</day><month>1</month><year>2024</year></date>
      <date date-type="rev-recd"><day>12</day><month>7</month><year>2024</year></date>
      <date date-type="accepted"><day>27</day><month>8</month><year>2024</year></date>
    </history></article>"""
    monkeypatch.setattr(MODULE, "get", lambda url: (200, xml))
    assert MODULE.received_date("PMC-test") == "2024-01-17"
