"""Coverage-first discovery and a bounded, network-free numerical tool."""
from __future__ import annotations

import ast
import math
import operator
from typing import Literal

from pydantic import BaseModel, Field
from scipy import optimize, stats

from .schemas import DeferredToolCheck, Evidence, Finding, SourceDocument
from .verification import verify_quote


TOPICS = {
    'contribution': ['question_and_claims', 'theoretical_argument', 'design_addresses_question'],
    'design': ['sampling_and_assignment', 'timing_and_dependence', 'exclusions_and_missingness'],
    'measurement': ['construct_operationalization', 'scoring_and_denominators', 'comparability_and_validity'],
    'statistical_inference': ['hypothesis_test_alignment', 'numerical_and_power_claims', 'uncertainty_and_analytic_choices'],
    'interpretation': ['theory_and_mechanism_claims', 'causal_and_population_scope', 'claim_evidence_consistency'],
    'social_psychology_context': ['demand_expectancy_and_social_mechanisms', 'people_and_stimuli', 'manipulation_and_alternative_explanations'],
    'blind_spots': ['unexamined_claims_and_sections', 'omissions_with_consequences', 'unresolved_numerical_questions'],
}


class CoverageCheck(BaseModel):
    check: str
    status: Literal['assessed', 'not_applicable', 'insufficient_evidence', 'not_checked']
    rationale: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)


class DiscoveryResponse(BaseModel):
    # Resource ceiling, not an instruction to prioritize before coverage.
    findings: list[Finding] = Field(max_length=20)
    checks: list[CoverageCheck] = Field(min_length=1)
    search_incomplete: bool
    deferred_tool_checks: list[DeferredToolCheck] = Field(default_factory=list, max_length=8)


class CalculationRequest(BaseModel):
    id: str
    question: str
    expression: str = Field(min_length=1, max_length=2000)
    assumptions: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)


class CalculationPlan(BaseModel):
    requests: list[CalculationRequest] = Field(max_length=12)
    not_checkable: list[str]


class CalculationResult(BaseModel):
    request: CalculationRequest
    status: Literal['computed', 'unavailable']
    value: float | None = None
    error: str | None = None


class CalculationReport(BaseModel):
    results: list[CalculationResult]
    not_checkable: list[str]


def rm_power(n, effect, groups, measurements, correlation, alpha, epsilon):
    """Univariate repeated-measures interaction, G*Power f convention."""
    if not (2 <= groups < n <= 1e7 and groups == int(groups)
            and 2 <= measurements <= 100 and measurements == int(measurements)
            and 0 < effect <= 10 and -1 / (measurements - 1) < correlation < 1
            and 0 < alpha < 1 and 1 / (measurements - 1) <= epsilon <= 1):
        raise ValueError('Invalid repeated-measures interaction assumptions')
    df1 = (groups - 1) * (measurements - 1) * epsilon
    df2 = (n - groups) * (measurements - 1) * epsilon
    nc = effect**2 * n * measurements * epsilon / (1 - correlation)
    return stats.ncf.sf(stats.f.isf(alpha, df1, df2), df1, df2, nc)


def rm_n(effect, groups, measurements, correlation, alpha, epsilon, power):
    if not 0 < power < 1:
        raise ValueError('Power must be between zero and one')
    low, high = 2 * groups, 1e7
    fn = lambda n: rm_power(n, effect, groups, measurements, correlation, alpha, epsilon) - power
    root = low if fn(low) >= 0 else optimize.brentq(fn, low, high)
    n = math.ceil(root / groups) * groups
    return n if fn(n) >= -1e-12 else n + groups


FUNCTIONS = {
    'sqrt': math.sqrt, 'log': math.log, 'exp': math.exp, 'abs': abs,
    't_p': lambda statistic, df, tails: stats.t.sf(abs(statistic), df) * tails if tails in (1, 2) else math.nan,
    'f_p': lambda statistic, df1, df2: stats.f.sf(statistic, df1, df2),
    'chi2_p': lambda statistic, df: stats.chi2.sf(statistic, df),
    'normal_ppf': stats.norm.ppf,
    'rm_power': rm_power, 'rm_n': rm_n,
}


def calculate(expression: str) -> float:
    """Interpret only scalar arithmetic and allowlisted functions; never eval/exec."""
    if len(expression) > 2000:
        raise ValueError('Expression too long')
    tree = ast.parse(expression, mode='eval')
    if len(list(ast.walk(tree))) > 128:
        raise ValueError('Expression too complex')
    ops = {ast.Add: operator.add, ast.Sub: operator.sub,
           ast.Mult: operator.mul, ast.Div: operator.truediv}

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = float(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = (-1 if isinstance(node.op, ast.USub) else 1) * visit(node.operand)
        elif isinstance(node, ast.BinOp) and type(node.op) in ops:
            value = ops[type(node.op)](visit(node.left), visit(node.right))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            left, right = visit(node.left), visit(node.right)
            if abs(right) > 100:
                raise ValueError('Exponent outside calculation budget')
            value = math.pow(left, right)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS and not node.keywords:
            value = float(FUNCTIONS[node.func.id](*(visit(arg) for arg in node.args)))
        else:
            raise ValueError('Unsupported expression; no names, attributes, imports, or arbitrary code')
        if not math.isfinite(value) or abs(value) > 1e100:
            raise ValueError('Non-finite or out-of-budget result')
        return value

    return visit(tree.body)


def execute_plan(plan: CalculationPlan, sources: list[SourceDocument]) -> CalculationReport:
    results = []
    for request in plan.requests:
        try:
            if any(verify_quote(e.quote, [s.model_dump() for s in sources], e.source_id).status != 'supported'
                   for e in request.evidence):
                raise ValueError('Calculation source quotation could not be anchored')
            value = calculate(request.expression)
            results.append(CalculationResult(request=request, status='computed', value=value))
        except (ValueError, TypeError, SyntaxError, ArithmeticError) as exc:
            results.append(CalculationResult(request=request, status='unavailable', error=str(exc)))
    return CalculationReport(results=results, not_checkable=plan.not_checkable)


CALCULATION_PROMPT = '''Identify numerical claims in the supplied manuscript that warrant a directed calculation.
Return up to twelve explicit calculator requests; do not invent missing inputs. For each request quote the
source inputs, state the exact question, expression and assumptions (including any assumed rather than
reported parameter). Prioritize checks that could affect conclusions: sample flow, percentages, effect
sizes, test statistics, confidence limits, power and sample-size consistency. Return zero requests when
none is justified. Record unavailable inputs or unsupported calculations in not_checkable.
The host will evaluate scalar arithmetic + - * / ** and these functions only:
sqrt(x), log(x), exp(x), abs(x), t_p(t,df,tails), f_p(F,df1,df2), chi2_p(x,df), normal_ppf(p),
rm_power(N,f,groups,measurements,correlation,alpha,epsilon),
rm_n(f,groups,measurements,correlation,alpha,epsilon,target_power).
The rm functions are only univariate repeated-measures within-between interaction calculations using
G*Power's f convention and equal group sizes; they are not general power calculators. Do not use them for
other designs. t_p uses the absolute statistic: tails=1 is the tail in the observed direction; if the
prespecified direction is opposite, use 1-t_p(t,df,1). State the tested direction explicitly.
No variables, code, file access, network, imports, or research are available. A computed
answer establishes arithmetic under specified inputs, not validity of the statistical model or assumptions.'''


def discovery_instruction(module: str, base: str) -> str:
    topics = TOPICS.get(module, ['module_inferences', 'source_consistency', 'information_limits'])
    return base + '''\nThese discovery rules override earlier requests for only a few prioritized findings.
Audit the entire supplied manuscript within your assigned responsibility before selecting findings.
Keep each issue grounded in an exact quotation, a concrete consequence, and the strongest plausible
alternative explanation or defeating context. An omission needs an inferential consequence, not merely
a missing checklist item. Distinguish unreported from incorrect. For proposals/protocols evaluate theory,
mechanisms and planned inference without requiring results. Do not prescribe post-treatment exclusions
by default. Return all distinct justified issues within your responsibility; do not fill a quota.
The schema's twenty-finding ceiling is a resource guard, not a target or publication limit. Set
search_incomplete=true if that ceiling or another limit prevents a complete audit.
Return exactly one checks entry for each of: ''' + ', '.join(topics) + '''.
For assessed checks, explain what you compared and cite source evidence; empty findings do not imply
coverage. Mark not_applicable, insufficient_evidence or not_checked with a reason when appropriate.
Calculator results are arithmetic under explicit assumptions, not verified criticisms. Check those
assumptions and quoted inputs before relying on results. Unsupported calculations remain unassessed.
Record deferred_tool_checks for concrete, consequential checks you would have pursued if a currently
unavailable tool or input were supplied. Return none unless a specific manuscript passage motivates the
check. State the capability, exact bounded action, required inputs (distinguish available from missing),
how either outcome would affect the review, priority and a stopping rule. These are unexecuted proposals,
not findings or evidence of an error. Do not request generic literature exploration, benchmark answers,
or unrestricted research. Prefer a direct supplied reference/resource or a narrowly defined calculation.
Do not repeat checks already completed by the calculator. Do not claim the proposed action was performed.
Stay within the assigned module; do not repeat a cross-section contradiction outside your remit unless
you identify a distinct consequence. Editorial selection happens after discovery and verification.'''


def validate_discovery(result: DiscoveryResponse, module: str, sources: list[SourceDocument]):
    """Repair the coverage ledger without throwing away independent findings.

    A defective coverage claim is not evidence that a candidate criticism is false.
    The raw model response is retained by the caller before this normalization.
    """
    expected = TOPICS.get(module, ['module_inferences', 'source_consistency', 'information_limits'])
    by_name = {}
    for row in result.checks:
        by_name.setdefault(row.check, []).append(row)
    incomplete = result.search_incomplete or bool(set(by_name) - set(expected))
    checks = []
    source_rows = [s.model_dump() for s in sources]
    for name in expected:
        rows = by_name.get(name, [])
        if len(rows) != 1:
            checks.append(CoverageCheck(check=name, status='not_checked',
                                       rationale='Coverage entry missing or duplicated in model output.'))
            incomplete = True
            continue
        row = rows[0]
        if row.status == 'assessed' and (not row.evidence or any(
            verify_quote(e.quote, source_rows, e.source_id).status != 'supported'
            for e in row.evidence
        )):
            row = row.model_copy(update={'status': 'not_checked',
                'rationale': 'Coverage evidence could not be anchored; original account: ' + row.rationale})
            incomplete = True
        checks.append(row)
    return result.model_copy(update={'checks': checks, 'search_incomplete': incomplete})
