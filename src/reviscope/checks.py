"""Conservative deterministic checks of explicitly reported test statistics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any, Iterable, Literal, Mapping

from scipy import stats


@dataclass(frozen=True)
class StatisticalFinding:
    check: str
    source_id: str
    reported: str
    computed_p: float
    reported_relation: str
    reported_p: float
    consistent: bool | None
    status: Literal["consistent", "inconsistent_lead", "not_checked"]
    explanation: str


@dataclass(frozen=True)
class CheckCoverage:
    eligible: int
    checked: int
    unsupported_or_unparsed: int
    by_test: Mapping[str, int]


@dataclass(frozen=True)
class CheckReport:
    findings: tuple[StatisticalFinding, ...]
    coverage: CheckCoverage

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_NUM = r"(?:(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
_P = rf"p\s*(?P<rel>(?:<=|>=|<|>|=|≤|≥|&lt;=?|&gt;=?))\s*(?P<p>{_NUM})(?!\w)"
_GAP = r"(?:(?!\b(?:t|F)\s*\(|(?:χ\s*[²2]|chi(?:-?square(?:d)?)?|X\s*²)\s*\().){0,80}?"
_PATTERNS = {
    "t": re.compile(rf"\bt\s*\(\s*(?P<df>{_NUM})\s*\)\s*=\s*(?P<stat>-?{_NUM}){_GAP}{_P}", re.S),
    "chi2": re.compile(rf"(?:χ\s*[²2]|chi(?:-?square(?:d)?)?|X\s*²)\s*\(\s*(?P<df>{_NUM})\s*\)\s*=\s*(?P<stat>{_NUM}){_GAP}{_P}", re.I | re.S),
    "F": re.compile(rf"\bF\s*\(\s*(?P<df1>{_NUM})\s*,\s*(?P<df2>{_NUM})\s*\)\s*=\s*(?P<stat>{_NUM}){_GAP}{_P}", re.S),
}
_HEAD = re.compile(r"(?:\bt|\bF)\s*\(|(?:χ\s*[²2]|[Cc]hi(?:-?square(?:d)?)?|X\s*²)\s*\(")
_ADJUSTED = re.compile(r"\b(?:adjusted|corrected|Bonferroni|Holm|FDR|Greenhouse[- ]Geisser)\b", re.I)
_ONE_TAILED = re.compile(r"\b(?:one[- ]tailed|one[- ]sided)\b", re.I)


def _p_value(kind: str, match: re.Match[str], statistic: float | None = None) -> float:
    stat = float(match["stat"]) if statistic is None else statistic
    if kind == "t":
        return float(2 * stats.t.sf(abs(stat), float(match["df"])))
    if kind == "F":
        return float(stats.f.sf(stat, float(match["df1"]), float(match["df2"])))
    return float(stats.chi2.sf(stat, float(match["df"])))


def _rounding_interval(raw: str) -> tuple[float, float]:
    value = float(raw)
    mantissa, _, exponent = raw.lower().partition("e")
    decimals = len(mantissa.partition(".")[2])
    half_unit = 0.5 * 10 ** (-decimals) * 10 ** (int(exponent) if exponent else 0)
    return value - half_unit, value + half_unit


def _consistent(computed_low: float, computed_high: float, relation: str,
                reported_raw: str) -> bool:
    relation = relation.replace("&lt;", "<").replace("&gt;", ">").replace("≤", "<=").replace("≥", ">=")
    reported = float(reported_raw)
    if relation in {"<", "<="}:
        return computed_low <= reported
    if relation in {">", ">="}:
        return computed_high >= reported
    reported_low, reported_high = _rounding_interval(reported_raw)
    return computed_low <= reported_high and computed_high >= reported_low


def run_statistical_checks(sources: Iterable[Mapping[str, Any] | str]) -> CheckReport:
    """Check supported complete reports. Returns explicit coverage even when empty."""
    findings: list[StatisticalFinding] = []
    counts = {kind: 0 for kind in _PATTERNS}
    eligible = checked = 0
    for index, source in enumerate(sources):
        text = source if isinstance(source, str) else str(source.get("text", ""))
        source_id = str(index) if isinstance(source, str) else str(source.get("source_id", source.get("id", index)))
        eligible += len(_HEAD.findall(text))
        for kind, pattern in _PATTERNS.items():
            for match in pattern.finditer(text):
                relation, reported_raw = match["rel"], match["p"]
                reported_p = float(reported_raw)
                dfs = [float(match[name]) for name in ("df", "df1", "df2") if name in match.groupdict()]
                statistic = float(match["stat"])
                valid = all(math.isfinite(value) and value > 0 for value in dfs)
                valid = valid and math.isfinite(statistic) and (kind == "t" or statistic >= 0)
                valid = valid and math.isfinite(reported_p) and 0 <= reported_p <= 1
                context = text[max(0, match.start() - 80):min(len(text), match.end() + 80)]
                adjusted = bool(_ADJUSTED.search(context))
                computed = float("nan")
                ok: bool | None = None
                if valid and not adjusted:
                    checked += 1
                    counts[kind] += 1
                    stat_low, stat_high = _rounding_interval(match["stat"])
                    computed = _p_value(kind, match)
                    p_at_low = _p_value(kind, match, stat_low)
                    p_at_high = _p_value(kind, match, stat_high)
                    computed_low, computed_high = sorted((p_at_low, p_at_high))
                    if kind == "t" and stat_low <= 0 <= stat_high:
                        computed_high = 1.0
                    ok = _consistent(computed_low, computed_high, relation, reported_raw)
                    if ok is False and kind == "t" and _ONE_TAILED.search(context):
                        ok = _consistent(computed_low / 2, computed_high / 2, relation, reported_raw)
                status = "not_checked" if ok is None else ("consistent" if ok else "inconsistent_lead")
                findings.append(StatisticalFinding(
                    check=f"reported_{kind}_p_consistency", source_id=source_id,
                    reported=match.group(0), computed_p=computed,
                    reported_relation=relation, reported_p=reported_p, consistent=ok, status=status,
                    explanation=("The report has invalid or unsupported numeric inputs, so it was not checked."
                                 if not valid else "An adjusted or corrected p-value is reported, so the default distribution check was not applied."
                                 if ok is None else "The reported p-value is consistent with the statistic and degrees of freedom under the stated/default tail assumption."
                                 if ok else "The printed values are not reproducible under default assumptions. Treat this as a lead and verify tails, corrections, transcription, and model details before making a criticism."),
                ))
    return CheckReport(tuple(findings), CheckCoverage(eligible, checked, max(0, eligible - checked), counts))
