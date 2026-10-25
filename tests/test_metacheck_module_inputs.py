"""R adapter regressions; no model calls or reference lookups (online() may probe)."""
import json
import shutil
import subprocess

import pytest

from reviscope import metacheck
from reviscope.schemas import MetacheckModule, MetacheckRecord


RSCRIPT = shutil.which("Rscript")
SCRIPTS = metacheck.VENDOR / "scripts"


def r(code):
    result = subprocess.run([RSCRIPT, "-"], input=code, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not RSCRIPT, reason="R is unavailable")
def test_input_guard_does_not_hide_unknown_extraction_or_other_modules():
    r(f'''source({json.dumps(str(SCRIPTS / "_module_inputs.R"))})
    fail <- function(p) stop("parser failed")
    stopifnot(is.null(mc_missing_module_input("other", NULL, fail)))
    stopifnot(is.null(mc_missing_module_input("stat_effect_size", NULL, fail)))
    for (value in list(NULL, data.frame(), data.frame(other="r"), data.frame(lhs=NA_character_))) {{
      stopifnot(is.null(mc_missing_module_input("stat_effect_size", NULL, function(p) value)))
    }}
    stopifnot(!is.null(mc_missing_module_input("stat_effect_size", NULL,
      function(p) data.frame(lhs=c("r", "p")))))
    for (test in c("t", "F")) {{
      stopifnot(is.null(mc_missing_module_input("stat_effect_size", NULL,
        function(p) data.frame(lhs=c(test, "p")))))
    }}''')


@pytest.mark.skipif(not RSCRIPT, reason="R is unavailable")
@pytest.mark.parametrize("text,status,light,coherence", [
    ("The association was r = .3, p = .05.", "skipped_missing_input", None, None),
    ("The difference was t(48) = 2.00, d = .57.", "ok", "green", "match_under_assumptions"),
    ("The difference was t(48) = 2.00, d = 3.00.", "ok", "red", "no_match"),
    ("The difference was F(1, 37.4) = 4.00, eta = .10.", "failed", None, None),
])
def test_real_package_module_retains_missing_and_inconsistent_checks(tmp_path, text, status, light, coherence):
    available = subprocess.run([RSCRIPT, "-e", "quit(status=if(requireNamespace('metacheck',quietly=TRUE)) 0 else 1)"],
                               capture_output=True, timeout=30)
    if available.returncode:
        pytest.skip("metacheck R package is unavailable")
    r(f'''suppressPackageStartupMessages(library(metacheck))
    paper <- demopaper()
    paper$text <- paper$text[1,,drop=FALSE]
    paper$text$text <- {json.dumps(text)}
    saveRDS(paper, {json.dumps(str(tmp_path / "paper.rds"))})''')
    result = subprocess.run([RSCRIPT, str(SCRIPTS / "mc_run.R"), "--run-dir", str(tmp_path),
                             "--modules", "stat_effect_size"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "ok"
    payload = json.loads((tmp_path / "modules" / "stat_effect_size.json").read_text())
    assert payload["status"] == status and payload["traffic_light"] == light
    if coherence:
        assert len(payload["table"]) == 1 and payload["table"][0]["d_coherence"] == coherence
    elif status == "skipped_missing_input":
        assert payload["table"] == [] and "not checked" in payload["error"]
        assert "Package error:" in payload["error"]
        assert not (tmp_path / "modules" / "stat_effect_size.rds").exists()
        counts = json.loads((tmp_path / "run_status.json").read_text())["counts"]
        assert counts["skipped_missing_input"] == 1
        module = MetacheckModule(module="stat_effect_size", status=status, error=payload["error"])
        record = MetacheckRecord(status="partial", modules=[module], output_dir=str(tmp_path))
        assert "could not check" in metacheck.leads(record, ["statistical_inference", "blind_spots"])["statistical_inference"]
    else:
        assert payload["table"] == [] and "Join columns" in payload["error"]
