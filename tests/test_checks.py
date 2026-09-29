from reviscope.checks import run_statistical_checks


def test_checks_supported_statistics_and_reports_coverage():
    report = run_statistical_checks([{
        "source_id": "paper", "text": "The effects were t(18) = 2.10, p = .050; F(1, 18) = 4.41, p = .050; χ²(1) = 3.84, p < .051."
    }])
    assert report.coverage.eligible == 3
    assert report.coverage.checked == 3
    assert report.coverage.unsupported_or_unparsed == 0
    assert all(item.consistent for item in report.findings)


def test_flags_clear_inconsistency_and_counts_unparsed():
    report = run_statistical_checks(["t(18) = 2.10, p = .90. F(1, ?) was not fully reported."])
    assert report.findings[0].consistent is False
    assert report.coverage.eligible == 2
    assert report.coverage.checked == 1
    assert report.coverage.unsupported_or_unparsed == 1


def test_statistic_rounding_interval_is_respected():
    report = run_statistical_checks(["t(20) = 2.1, p = .05"])
    assert report.findings[0].consistent


def test_adjusted_result_is_not_counted_or_flagged():
    report = run_statistical_checks(["t(30) = 2.1, adjusted p = .08"])
    assert report.coverage.eligible == 1
    assert report.coverage.checked == 0
    assert report.findings[0].consistent is None
    assert report.findings[0].status == "not_checked"


def test_scientific_notation_is_parsed_whole():
    report = run_statistical_checks(["χ²(1) = 25.0, p = 5e-7"])
    assert report.coverage.checked == 1
    assert report.findings[0].reported_p == 5e-7


def test_invalid_inputs_are_unsupported_and_zero_rounding_crossing_is_valid():
    invalid = run_statistical_checks(["t(0) = 2.0, p = .05"])
    assert invalid.coverage.checked == 0
    assert invalid.findings[0].consistent is None
    zero = run_statistical_checks(["t(20) = 0.0, p = 1.0"])
    assert zero.findings[0].consistent is True
