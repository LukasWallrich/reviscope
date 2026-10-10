"""Blind human validation packet for the criticism-level judge, and scoring of its labels.

`build` turns a criticism judge `result.json` into one self-contained HTML file in which the
manuscript's author labels every criticism variant (correctness, materiality, remedy, whether
he would act on it) and every multi-variant cluster (same issue or not). Issues and their
variants appear in seeded random order under opaque labels. The packet never contains origins
(arm, run, module, status, severity), judge outputs or cluster labels; the build checks its own
embedded text against them and refuses to write a leaking packet.

`score` maps the author's labels onto the judge's scale and reports agreement per judge family
and for the conservative combined view, owner-labelled metrics per arm and run (weighted by
inverse inclusion probability when the packet sampled clusters), and the cluster boundary check.

    uv run python eval/owner_packet.py build runs/criticism-judge/p/result.json --out packet.html --max-variants 80
    uv run python eval/owner_packet.py score runs/criticism-judge/p/result.json labels.json --out owner-report.json
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from reviscope.criticism_judge import CORRECTNESS, _kappa, combine

PACKET_FORMAT = "reviscope-owner-packet-v1"
LABELS_FORMAT = "reviscope-owner-labels-v1"
DEFAULT_SEED = 20261009

CORRECTNESS_OPTIONS = (
    ("correct", "Correct", "Every part holds: what it says the paper reports or does, the reasoning, and the consequence it states."),
    ("partly_correct", "Partly correct", "A substantive part is wrong, e.g. the problem exists but its consequence is overstated, "
                                         "or one of several points is mistaken."),
    ("incorrect", "Incorrect", "Its main premise or reasoning is wrong."),
    ("cannot_tell", "Cannot tell", "Deciding would need data, analyses or sources you cannot check now, or it is too vague to check."),
)
MATERIALITY_OPTIONS = (
    ("0", "0 Cosmetic", "Wording, formatting or preference."),
    ("1", "1 Local", "A local or reporting issue with no effect on the inferences."),
    ("2", "2 Weakens", "Weakens a primary claim, or affects a secondary claim."),
    ("3", "3 Undermines", "Undermines a primary claim."),
)
REMEDY_OPTIONS = (
    ("essential", "Essential", "Needed for the claims to stand as stated."),
    ("strengthen", "Would strengthen", "Improves the paper, but the claims stand without it."),
    ("extension", "Extension beyond scope", "Asks for work beyond what this paper sets out to do."),
    ("wrong_or_harmful", "Remedy wrong or harmful", "The change would be invalid, would not address the problem, or would make the paper worse."),
    ("none_given", "No remedy given", "The criticism asks for no action, neither in a remedy nor in its text."),
)
ACT_OPTIONS = (
    ("yes", "Yes", "You would change the paper in response."),
    ("no", "No", "You would not change the paper."),
    ("already_addressed", "Already addressed", "The paper already deals with this."),
)
SAME_OPTIONS = (
    ("yes", "Yes", "Same underlying problem and the same consequence for the paper."),
    ("split", "No, should be split", "At least one raises a different problem or a different consequence."),
)
VARIANT_FIELDS = ("correctness", "materiality", "remedy", "act")

# Owner correctness on the judge's scale. Strict follows the complete-criticism rule.
STRICT = {"correct": "supported", "partly_correct": "contradicted", "incorrect": "contradicted", "cannot_tell": "unresolved"}
LENIENT = {**STRICT, "partly_correct": "supported"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_result(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    for key in ("variants", "origins"):
        if key not in result:
            raise ValueError(f"{path}: not a criticism judge result (missing {key!r})")
    return result


def issue_clusters(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The result's clusters, or one singleton per variant when clustering failed."""
    if result.get("clusters"):
        return [{"cluster_id": c["cluster_id"], "variant_ids": list(c["variant_ids"])} for c in result["clusters"]]
    return [{"cluster_id": f"S-{v['id']}", "variant_ids": [v["id"]]} for v in sorted(result["variants"], key=lambda v: v["id"])]


# ---------------------------------------------------------------- sampling

def sample_clusters(result: Mapping[str, Any], seed: int, max_variants: int | None) -> dict[str, Any]:
    """Stratified simple random sample of whole clusters.

    Strata are the sets of arms represented in a cluster, so clusters raised by only one arm and
    shared clusters are all represented. Every stratum keeps at least one cluster; otherwise one
    sampling fraction applies to all strata, chosen as the largest whose expected number of variants
    stays within `max_variants`. The cap is a target: realized cluster sizes can exceed it. Within a
    stratum of N clusters, n are drawn without replacement, so each has inclusion probability n / N."""
    clusters = sorted(issue_clusters(result), key=lambda c: c["cluster_id"])
    total = sum(len(c["variant_ids"]) for c in clusters)
    origins = result["origins"]
    if not max_variants or total <= max_variants:
        return {"design": "census", "max_variants": max_variants, "pool_variants": total, "pool_clusters": len(clusters),
                "included": [c["cluster_id"] for c in clusters], "inclusion_probability": {c["cluster_id"]: 1.0 for c in clusters},
                "strata": {}}
    strata: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for cluster in clusters:
        key = tuple(sorted({origins[v]["arm"] for v in cluster["variant_ids"]}))
        strata.setdefault(key, []).append(cluster)

    def sizes(fraction: float) -> dict[tuple[str, ...], int]:
        return {k: min(len(m), max(1, round(fraction * len(m)))) for k, m in strata.items()}

    def expected(counts: Mapping[tuple[str, ...], int]) -> float:
        return sum(n * sum(len(c["variant_ids"]) for c in strata[k]) / len(strata[k]) for k, n in counts.items())

    low, high = 0.0, 1.0
    for _ in range(60):
        middle = (low + high) / 2
        low, high = (middle, high) if expected(sizes(middle)) <= max_variants else (low, middle)
    counts = sizes(low)
    included, probability, record = [], {}, {}
    for key, members in sorted(strata.items()):
        chosen = random.Random(f"{seed}:stratum:{'|'.join(key)}").sample(members, counts[key])
        included += [c["cluster_id"] for c in chosen]
        for c in members:
            probability[c["cluster_id"]] = round(counts[key] / len(members), 6)
        record["|".join(key)] = {"clusters": len(members), "sampled": counts[key]}
    included_set = set(included)
    return {"design": "stratified cluster sample", "max_variants": max_variants,
            "pool_variants": total, "pool_clusters": len(clusters),
            "included": sorted(included_set), "inclusion_probability": {k: v for k, v in probability.items() if k in included_set},
            "strata": record}


# ---------------------------------------------------------------- packet

def _letters(index: int) -> str:
    out = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        out = chr(65 + rest) + out
    return out


def packet_content(result: Mapping[str, Any], result_sha: str, seed: int, max_variants: int | None) -> dict[str, Any]:
    """Display order and the metadata the packet may carry. Contains no origin or judge data."""
    sampling = sample_clusters(result, seed, max_variants)
    variants = {v["id"]: v for v in result["variants"]}
    by_id = {c["cluster_id"]: c for c in issue_clusters(result)}
    order = random.Random(f"{seed}:order").sample(sampling["included"], len(sampling["included"]))
    issues = []
    for number, cid in enumerate(order, start=1):
        members = sorted(by_id[cid]["variant_ids"])
        random.Random(f"{seed}:variants:{cid}").shuffle(members)
        issues.append({"cluster_id": cid, "number": number,
                       "variants": [{"label": _letters(i), **_shown(variants[vid])} for i, vid in enumerate(members)]})
    variant_ids = sorted(v["id"] for issue in issues for v in issue["variants"])
    packet_id = hashlib.sha256(json.dumps({"result": result_sha, "seed": seed, "max_variants": max_variants,
                                           "clusters": sampling["included"]}, sort_keys=True).encode()).hexdigest()[:16]
    meta = {"format": PACKET_FORMAT, "labels_format": LABELS_FORMAT, "packet_id": packet_id, "paper_id": result.get("paper_id"),
            "result_sha256": result_sha, "seed": seed, "max_variants": max_variants,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sampling": {"design": sampling["design"], "pool_variants": sampling["pool_variants"],
                         "pool_clusters": sampling["pool_clusters"], "inclusion_probability": sampling["inclusion_probability"]},
            "variant_ids": variant_ids, "cluster_ids": sorted(sampling["included"]),
            "multi_variant_cluster_ids": sorted(i["cluster_id"] for i in issues if len(i["variants"]) > 1)}
    return {"meta": meta, "issues": issues}


def _shown(variant: Mapping[str, Any]) -> dict[str, Any]:
    return {"id": variant["id"], "claim": variant.get("claim") or "", "rationale": variant.get("rationale") or "",
            "remedy": variant.get("remedy") or None, "quotes": list(variant.get("quotes") or []),
            "external": list(variant.get("external") or [])}


def forbidden_terms(result: Mapping[str, Any]) -> set[str]:
    """Strings that would reveal origin or judge output: arm, run, module, status, severity and path
    values, cluster labels, judge family names and identities, and judge explanations."""
    terms: set[str] = set()
    for origin in result["origins"].values():
        for key in ("arm", "run", "path", "module", "status", "severity"):
            if origin.get(key):
                terms.add(str(origin[key]))
    for family, rows in (result.get("judgments") or {}).items():
        terms.add(family)
        for row in rows.values():
            if row.get("explanation"):
                terms.add(row["explanation"])
    for identity in (result.get("judges") or {}).values():
        terms.add(str(identity))
    for cluster in result.get("clusters") or []:
        if cluster.get("label"):
            terms.add(cluster["label"])
    return {t for t in terms if t.strip()}


def template_text() -> str:
    """The packet's fixed text (instructions, scales, CSS, script) around neutral placeholder content.
    It is identical for every packet, so a term occurring in it reveals nothing; tests check that it
    contains no origin or verdict vocabulary."""
    variants = [{"label": label, "id": f"V{label}", "claim": "x", "rationale": "x", "remedy": "x", "quotes": ["x"], "external": ["x"]}
                for label in ("A", "B")]
    meta = {"packet_id": "0", "variant_ids": ["VA", "VB"], "cluster_ids": ["K"], "multi_variant_cluster_ids": ["K"]}
    return render_html({"meta": meta, "issues": [{"cluster_id": "K", "number": 1, "variants": variants}]})


def leaks(document: str, result: Mapping[str, Any], fixed: str | None = None, allowed: Sequence[str] = ()) -> list[str]:
    """Forbidden terms found in `document` outside the criticism text itself and the fixed template.
    A term counts as criticism text when it occurs in any variant's shown fields. `fixed` is the
    document type's template (this packet's by default); `allowed` holds further text the reader
    already has, such as the manuscript itself, in which a term reveals nothing."""
    shown = " ".join(" ".join([v.get("claim") or "", v.get("rationale") or "", v.get("remedy") or "", *v.get("quotes", []),
                               *v.get("external", [])]) for v in result["variants"]).casefold()
    shown += " " + " ".join(allowed).casefold()
    fixed = (template_text() if fixed is None else fixed).casefold()
    text = document.casefold()
    found = []
    for term in sorted(forbidden_terms(result)):
        pattern = r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)"
        if re.search(pattern, text) and not re.search(pattern, shown) and not re.search(pattern, fixed):
            found.append(term)
    return found


def _options(name: str, field: str, options: Sequence[tuple[str, str, str]], kind: str, oid: str) -> str:
    rows = []
    for value, label, definition in options:
        input_id = f"{name}-{field}-{value}"
        rows.append(f'<label class="opt" for="{input_id}"><input type="radio" id="{input_id}" name="{name}-{field}" '
                    f'value="{value}" data-kind="{kind}" data-id="{oid}" data-field="{field}">'
                    f'<span class="opt-label">{html.escape(label)}</span><span class="opt-def">{html.escape(definition)}</span></label>')
    return "".join(rows)


QUESTIONS = (
    ("correctness", "Is the criticism correct?", "Check every part against your manuscript.", CORRECTNESS_OPTIONS),
    ("materiality", "How much would it matter if true?", "Your own judgment, not the reviewer's framing; answer even if the "
                                                          "criticism is wrong.", MATERIALITY_OPTIONS),
    ("remedy", "The requested action", "What it asks you to do, in the suggested remedy or in its text.", REMEDY_OPTIONS),
    ("act", "Would you act on this?", "", ACT_OPTIONS),
)


def _variant_html(issue: Mapping[str, Any], variant: Mapping[str, Any]) -> str:
    vid = variant["id"]
    name = f"v-{vid}"
    title = f"Issue {issue['number']}, criticism {variant['label']}"
    parts = [f'<article class="criticism" id="{name}" data-variant="{vid}" tabindex="-1" aria-label="{title}">',
             f'<header class="crit-head"><h3>{title}</h3><span class="done-mark" aria-hidden="true"></span></header>',
             '<div class="crit-body">',
             f'<p class="claim">{html.escape(variant["claim"])}</p>']
    if variant["rationale"]:
        parts.append(f'<h4>Reasoning given</h4><p class="text">{html.escape(variant["rationale"])}</p>')
    if variant["remedy"]:
        parts.append(f'<h4>Suggested remedy</h4><p class="text">{html.escape(variant["remedy"])}</p>')
    else:
        parts.append('<h4>Suggested remedy</h4><p class="text muted">None stated separately.</p>')
    if variant["quotes"]:
        parts.append("<h4>Quoted from the manuscript</h4>" + "".join(f"<blockquote>{html.escape(q)}</blockquote>" for q in variant["quotes"]))
    if variant["external"]:
        parts.append("<h4>Outside sources cited</h4><ul class=\"ext\">" + "".join(f"<li>{html.escape(e)}</li>" for e in variant["external"]) + "</ul>")
    parts.append("</div><div class=\"questions\">")
    for field, legend, hint, options in QUESTIONS:
        hint_html = f'<span class="hint">{html.escape(hint)}</span>' if hint else ""
        parts.append(f'<fieldset class="q q-{field}"><legend>{html.escape(legend)}{hint_html}</legend>'
                     f'{_options(name, field, options, "variant", vid)}</fieldset>')
    parts.append(f'<label class="note" for="{name}-note">Note (optional)'
                 f'<textarea id="{name}-note" rows="2" data-kind="variant" data-id="{vid}" data-field="note"></textarea></label>')
    parts.append("</div></article>")
    return "".join(parts)


def _issue_html(issue: Mapping[str, Any]) -> str:
    cid = issue["cluster_id"]
    count = len(issue["variants"])
    parts = [f'<section class="issue" id="issue-{issue["number"]}" data-cluster="{cid}">',
             f'<h2>Issue {issue["number"]}<span class="count">{count} criticism{"s" if count != 1 else ""}</span></h2>']
    parts += [_variant_html(issue, v) for v in issue["variants"]]
    if count > 1:
        name = f"c-{cid}"
        parts.append(f'<fieldset class="q same" data-cluster-q="{cid}"><legend>Do these {count} criticisms raise the same issue?'
                     f'<span class="hint">Answer after reading all of them.</span></legend>{_options(name, "same_issue", SAME_OPTIONS, "cluster", cid)}'
                     f'<label class="note" for="{name}-note">Note (optional)<textarea id="{name}-note" rows="1" data-kind="cluster" '
                     f'data-id="{cid}" data-field="note"></textarea></label></fieldset>')
    parts.append("</section>")
    return "".join(parts)


def _definitions() -> str:
    def block(title: str, options: Sequence[tuple[str, str, str]]) -> str:
        return f"<dt>{html.escape(title)}</dt><dd><ul>" + "".join(
            f"<li><b>{html.escape(label)}</b>: {html.escape(definition)}</li>" for _, label, definition in options) + "</ul></dd>"
    return ("<dl class=\"defs\">" + block("Correctness", CORRECTNESS_OPTIONS) + block("Materiality (if the criticism were true)", MATERIALITY_OPTIONS)
            + block("Requested action", REMEDY_OPTIONS) + block("Would you act on this?", ACT_OPTIONS)
            + block("Same issue?", SAME_OPTIONS) + "</dl>")


CSS = """
:root{color-scheme:light dark;--bg:#fbfaf7;--fg:#22211f;--muted:#6b6862;--card:#fff;--line:#e3dfd6;--accent:#2f5d8a;--accent-soft:#e7eef6;--done:#3f7d4e;--quote:#f3f0e8;
--serif:"Iowan Old Style","Charter","Source Serif 4","Georgia",serif;--ui:system-ui,-apple-system,"Segoe UI",sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#191a1c;--fg:#e6e3dc;--muted:#a19d94;--card:#222326;--line:#36373b;--accent:#8db4dc;--accent-soft:#2a3441;--done:#7fbf8e;--quote:#2a2b2e}}
*{box-sizing:border-box}html{scroll-padding-top:6rem}
body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.6 var(--serif);overflow-wrap:anywhere}
.bar{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);font-family:var(--ui);font-size:14px}
.bar-in{max-width:52rem;margin:0 auto;padding:.6rem 1.2rem;display:flex;flex-wrap:wrap;gap:.6rem 1rem;align-items:center}
.bar h1{font-size:15px;margin:0;font-weight:600;flex:1 1 auto}
.progress{order:5;flex:1 1 20rem;display:flex;align-items:center;gap:.6rem;white-space:nowrap}
.track{flex:1;min-width:5rem;height:6px;background:var(--line);border-radius:3px;overflow:hidden}.fill{height:100%;width:0;background:var(--accent);transition:width .2s}
.bar button,.bar .btn{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);padding:.3rem .7rem;border-radius:6px;cursor:pointer}
.bar button:hover,.bar .btn:hover{border-color:var(--accent)}
.status{order:6;color:var(--muted);font-size:13px;min-width:10rem;text-align:right}
main{max-width:52rem;margin:0 auto;padding:1.5rem 1.2rem 6rem}
.intro{font-size:17px}.intro details{margin:.8rem 0;font-family:var(--ui);font-size:14px}.intro summary{cursor:pointer;color:var(--accent)}
.defs dt{font-weight:600;margin-top:.6rem}.defs dd{margin:0}.defs ul{margin:.2rem 0;padding-left:1.2rem}
.issue{margin:2.5rem 0}.issue>h2{font-family:var(--ui);font-size:20px;border-bottom:2px solid var(--fg);padding-bottom:.3rem;display:flex;justify-content:space-between;align-items:baseline}
.count{font-size:14px;font-weight:400;color:var(--muted)}
.criticism{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:1.2rem 0;padding:1.1rem 1.3rem;outline:none}
.criticism:focus-visible,.criticism.flash{box-shadow:0 0 0 3px var(--accent-soft),0 0 0 4px var(--accent)}
.crit-head{display:flex;justify-content:space-between;align-items:center}
.crit-head h3{font-family:var(--ui);font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);margin:0}
.criticism.done .done-mark::after{content:"\\2713 labelled";font-family:var(--ui);font-size:13px;color:var(--done)}
.claim{font-size:19px;font-weight:600;margin:.4rem 0 .8rem}
h4{font-family:var(--ui);font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin:1rem 0 .2rem}
.text{margin:.2rem 0}.muted{color:var(--muted);font-style:italic}
blockquote{margin:.4rem 0;padding:.5rem .9rem;background:var(--quote);border-left:3px solid var(--line);font-size:16px}
.ext{font-size:16px;margin:.2rem 0}
.questions{margin-top:1.2rem;border-top:1px solid var(--line);padding-top:.6rem;font-family:var(--ui);font-size:14px;line-height:1.4}
.q{border:0;margin:.8rem 0;padding:0}.q legend{font-weight:600;padding:0;margin-bottom:.35rem}
.hint{display:block;font-weight:400;color:var(--muted);font-size:13px}
.opt{display:grid;grid-template-columns:1.4rem 13.5rem 1fr;column-gap:.4rem;align-items:baseline;padding:.25rem .4rem;border-radius:6px;cursor:pointer}
.opt:hover{background:var(--accent-soft)}.opt input{margin:0;accent-color:var(--accent)}
.opt:has(input:checked){background:var(--accent-soft)}.opt-label{font-weight:500}.opt-def{color:var(--muted)}
@media (max-width:640px){.opt{grid-template-columns:1.4rem 1fr}.opt-def{grid-column:2}}
.note{display:block;margin-top:.6rem;color:var(--muted);font-size:13px}
textarea{display:block;width:100%;margin-top:.2rem;font:15px/1.4 var(--ui);color:var(--fg);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:.4rem .5rem}
textarea:focus,input:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.same{background:var(--card);border:1px dashed var(--line);border-radius:10px;padding:1rem 1.3rem;font-family:var(--ui);font-size:14px;line-height:1.4}
.same legend{float:left;width:100%;font-size:16px;margin-bottom:.5rem}.same legend+*{clear:both}
.same.done{border-style:solid;border-color:var(--done)}
kbd{font-family:var(--ui);font-size:12px;border:1px solid var(--line);border-radius:4px;padding:0 .3rem}
"""

JS = r"""
(function(){
const META = JSON.parse(document.getElementById('packet-meta').textContent);
const KEY = 'reviscope-owner-packet:' + META.packet_id;
const FIELDS = ['correctness','materiality','remedy','act'];
const statusEl = document.getElementById('status');
let canStore = true;
function empty(){ return {started_at:null, updated_at:null, variants:{}, clusters:{}}; }
function load(){ try { const raw = localStorage.getItem(KEY); return raw ? JSON.parse(raw) : null; } catch(e){ canStore = false; return null; } }
let state = load() || empty();
function now(){ return new Date().toISOString(); }
function save(){
  try { localStorage.setItem(KEY, JSON.stringify(state)); canStore = true;
    statusEl.textContent = 'Saved in this browser ' + new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}); }
  catch(e){ canStore = false; statusEl.textContent = 'Autosave unavailable: export regularly'; }
}
function bucket(kind){ return kind === 'cluster' ? state.clusters : state.variants; }
function record(input){
  const b = bucket(input.dataset.kind), id = input.dataset.id, field = input.dataset.field;
  const row = b[id] || (b[id] = {});
  let value = input.value;
  if (field === 'materiality') value = Number(value);
  if (field === 'note') { value = value.trim(); if (!value) { delete row.note; } else { row.note = input.value; } }
  else { row[field] = value; }
  row.updated_at = now();
  if (!state.started_at) state.started_at = row.updated_at;
  state.updated_at = row.updated_at;
  save(); refresh();
}
function variantDone(id){ const r = state.variants[id]; return !!r && FIELDS.every(f => r[f] !== undefined && r[f] !== null); }
function clusterDone(id){ const r = state.clusters[id]; return !!r && !!r.same_issue; }
function refresh(){
  let v = 0, c = 0;
  document.querySelectorAll('article.criticism').forEach(a => { const d = variantDone(a.dataset.variant); a.classList.toggle('done', d); if (d) v++; });
  document.querySelectorAll('fieldset.same').forEach(f => { const d = clusterDone(f.dataset.clusterQ); f.classList.toggle('done', d); if (d) c++; });
  const nv = META.variant_ids.length, nc = META.multi_variant_cluster_ids.length;
  document.getElementById('progress-text').textContent = v + ' / ' + nv + ' criticisms' + (nc ? ' · ' + c + ' / ' + nc + ' groupings' : '');
  document.getElementById('fill').style.width = ((v + c) / Math.max(1, nv + nc) * 100) + '%';
}
function apply(){
  document.querySelectorAll('[data-field]').forEach(input => {
    const row = bucket(input.dataset.kind)[input.dataset.id] || {};
    const value = row[input.dataset.field];
    if (input.type === 'radio') input.checked = value !== undefined && String(value) === input.value;
    else input.value = value || '';
  });
  refresh();
}
document.addEventListener('change', e => { if (e.target.matches('input[type=radio][data-field]')) record(e.target); });
document.addEventListener('input', e => { if (e.target.matches('textarea[data-field]')) record(e.target); });
function exportLabels(){
  const payload = {format: META.labels_format, packet_id: META.packet_id, packet_format: META.format, paper_id: META.paper_id,
    result_sha256: META.result_sha256, seed: META.seed, max_variants: META.max_variants, generated_at: META.generated_at,
    started_at: state.started_at, updated_at: state.updated_at, exported_at: now(), sampling: META.sampling,
    variant_ids: META.variant_ids, cluster_ids: META.cluster_ids,
    labels: {variants: state.variants, clusters: state.clusters}};
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'owner-labels-' + META.packet_id + '.json';
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  statusEl.textContent = 'Exported';
}
function importLabels(file){
  const reader = new FileReader();
  reader.onload = () => {
    let data;
    try { data = JSON.parse(reader.result); } catch(e){ alert('Not a JSON file.'); return; }
    if (data.packet_id !== META.packet_id) { alert('These labels belong to another packet (' + data.packet_id + '), not ' + META.packet_id + '.'); return; }
    const has = Object.keys(state.variants).length + Object.keys(state.clusters).length;
    if (has && !confirm('Replace the labels saved in this browser with the imported file?')) return;
    const labels = data.labels || {};
    state = {started_at: data.started_at || null, updated_at: data.updated_at || null, variants: labels.variants || {}, clusters: labels.clusters || {}};
    save(); apply(); statusEl.textContent = 'Imported';
  };
  reader.readAsText(file);
}
function nextOpen(){
  const items = [...document.querySelectorAll('article.criticism, fieldset.same')];
  const target = items.find(el => el.matches('article') ? !variantDone(el.dataset.variant) : !clusterDone(el.dataset.clusterQ));
  if (!target) { statusEl.textContent = 'Everything is labelled'; return; }
  target.scrollIntoView({behavior:'smooth', block:'start'});
  target.classList.add('flash'); setTimeout(() => target.classList.remove('flash'), 1200);
  let focus = null;
  if (target.matches('article')) {
    const r = state.variants[target.dataset.variant] || {};
    const field = FIELDS.find(f => r[f] === undefined);
    focus = target.querySelector('input[data-field="' + field + '"]');
  } else focus = target.querySelector('input');
  (focus || target).focus({preventScroll:true});
}
document.getElementById('export').addEventListener('click', exportLabels);
document.getElementById('import').addEventListener('click', () => document.getElementById('import-file').click());
document.getElementById('import-file').addEventListener('change', e => { if (e.target.files[0]) importLabels(e.target.files[0]); e.target.value = ''; });
document.getElementById('next').addEventListener('click', nextOpen);
document.addEventListener('keydown', e => {
  if (e.target.matches('textarea') || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === 'n') { e.preventDefault(); nextOpen(); }
});
if (!canStore) statusEl.textContent = 'Autosave unavailable: export regularly';
else if (state.updated_at) statusEl.textContent = 'Restored saved labels';
apply();
})();
"""


def render_html(content: Mapping[str, Any]) -> str:
    meta = content["meta"]
    issues = content["issues"]
    meta_json = json.dumps(meta, ensure_ascii=False).replace("</", "<\\/")
    n_variants = len(meta["variant_ids"])
    intro = (f"<p>Below are {n_variants} criticisms of your manuscript, grouped into {len(issues)} issues. Automated reviewers "
             "wrote them; their order is random and the labels are arbitrary. Assess each criticism on its own against "
             "your manuscript, as a careful reader who knows the paper would.</p>"
             "<p>Answer four questions per criticism; the note is optional. Where an issue groups several criticisms, "
             "also say whether they raise the same issue. Answers save in this browser as you go; use "
             "<b>Export labels</b> to download them, and <b>Import labels</b> to continue on another device. "
             "<kbd>n</kbd> jumps to the next open question.</p>"
             "<details><summary>All definitions</summary>" + _definitions() + "</details>")
    return ("<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'; img-src data:\">"
            f"<title>Criticism labels: packet {meta['packet_id']}</title><style>{CSS}</style></head><body>"
            "<div class=\"bar\"><div class=\"bar-in\">"
            f"<h1>Criticism labels</h1><div class=\"progress\"><div class=\"track\"><div class=\"fill\" id=\"fill\"></div></div>"
            "<span id=\"progress-text\"></span></div>"
            "<button id=\"next\" type=\"button\" title=\"Next open question (n)\">Next open</button>"
            "<button id=\"export\" type=\"button\">Export labels</button>"
            "<button id=\"import\" type=\"button\">Import labels</button>"
            "<input id=\"import-file\" type=\"file\" accept=\"application/json,.json\" hidden>"
            "<span class=\"status\" id=\"status\" role=\"status\" aria-live=\"polite\"></span></div></div>"
            f"<main><section class=\"intro\">{intro}</section>"
            + "".join(_issue_html(issue) for issue in issues)
            + f"<p class=\"muted\">Packet {meta['packet_id']}. End of packet: remember to export your labels.</p></main>"
            f"<script type=\"application/json\" id=\"packet-meta\">{meta_json}</script><script>{JS}</script></body></html>\n")


def build(result_path: Path, out: Path, seed: int = DEFAULT_SEED, max_variants: int | None = None) -> dict[str, Any]:
    result = load_result(result_path)
    content = packet_content(result, sha256_file(result_path), seed, max_variants)
    document = render_html(content)
    if found := leaks(document, result):
        raise RuntimeError(f"packet would reveal origin or judge information: {found}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding="utf-8")
    return content["meta"]


# ---------------------------------------------------------------- scoring

def _ratio(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _complete(row: Mapping[str, Any] | None) -> bool:
    return bool(row) and all(row.get(f) is not None for f in VARIANT_FIELDS)  # type: ignore[union-attr]


def _views(result: Mapping[str, Any], ids: Sequence[str]) -> dict[str, dict[str, Mapping[str, Any] | None]]:
    judgments = result.get("judgments") or {}
    views: dict[str, dict[str, Mapping[str, Any] | None]] = {f: {v: rows.get(v) for v in ids} for f, rows in judgments.items()}
    if len(judgments) > 1:
        views["combined"] = {v: combine([judgments[f].get(v) for f in judgments]) for v in ids}
    return views


def judge_agreement(view: Mapping[str, Mapping[str, Any] | None], owner: Mapping[str, Mapping[str, Any]],
                    variants: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Judge (rows) against owner (columns) on the judge's correctness scale; materiality 0-3."""
    both = [v for v in sorted(owner) if view.get(v) is not None and owner[v].get("correctness")]
    out: dict[str, Any] = {"n": len(both)}
    for name, mapping in (("strict", STRICT), ("lenient", LENIENT)):
        pairs = [(view[v]["correctness"], mapping[owner[v]["correctness"]]) for v in both]  # type: ignore[index]
        matrix = {j: {o: sum(1 for a, b in pairs if a == j and b == o) for o in CORRECTNESS} for j in CORRECTNESS}
        out[name] = {"agreement": _ratio(sum(a == b for a, b in pairs), len(pairs)), "kappa": _kappa(pairs, CORRECTNESS),
                     "confusion_judge_by_owner": matrix}
    mat = [v for v in both if owner[v].get("materiality") is not None]
    pairs_m = [(int(view[v]["materiality"]), int(owner[v]["materiality"])) for v in mat]  # type: ignore[index]
    out["materiality"] = {"n": len(pairs_m), "agreement": _ratio(sum(a == b for a, b in pairs_m), len(pairs_m)),
                          "weighted_kappa_linear": _kappa(pairs_m, (0, 1, 2, 3), "linear"),
                          "judge_higher": sum(a > b for a, b in pairs_m), "judge_lower": sum(a < b for a, b in pairs_m)}
    disagreements = []
    for v in both:
        judge, own = view[v], owner[v]
        strict = STRICT[own["correctness"]]
        far = own.get("materiality") is not None and abs(int(judge["materiality"]) - int(own["materiality"])) >= 2  # type: ignore[index]
        if judge["correctness"] != strict or far:  # type: ignore[index]
            disagreements.append({"variant_id": v, "claim": variants[v].get("claim"), "rationale": variants[v].get("rationale"),
                                  "owner": {k: own.get(k) for k in (*VARIANT_FIELDS, "note")},
                                  "owner_on_judge_scale": strict,
                                  "judge": {k: judge.get(k) for k in ("correctness", "materiality", "explanation")}})  # type: ignore[union-attr]
    out["disagreements"] = disagreements
    return out


def _arm_stats(rows: Sequence[tuple[Mapping[str, Any], float]], runs: int) -> dict[str, Any]:
    """Raw and inverse-probability-weighted owner metrics for labelled variants."""
    def tally(weighted: bool) -> dict[str, Any]:
        w = lambda weight: weight if weighted else 1.0  # noqa: E731
        n = sum(w(x) for _, x in rows)
        strict = sum(w(x) for r, x in rows if STRICT[r["correctness"]] == "supported")
        lenient = sum(w(x) for r, x in rows if LENIENT[r["correctness"]] == "supported")
        resolved = sum(w(x) for r, x in rows if STRICT[r["correctness"]] != "unresolved")
        counts = {
            "labelled": n,
            "supported": strict,
            "contradicted": sum(w(x) for r, x in rows if STRICT[r["correctness"]] == "contradicted"),
            "partly_correct": sum(w(x) for r, x in rows if r["correctness"] == "partly_correct"),
            "cannot_tell": sum(w(x) for r, x in rows if r["correctness"] == "cannot_tell"),
            "supported_material": sum(w(x) for r, x in rows if STRICT[r["correctness"]] == "supported" and int(r["materiality"]) >= 2),
            "supported_material_lenient": sum(w(x) for r, x in rows if LENIENT[r["correctness"]] == "supported" and int(r["materiality"]) >= 2),
            "would_act": sum(w(x) for r, x in rows if r["act"] == "yes"),
            "already_addressed": sum(w(x) for r, x in rows if r["act"] == "already_addressed"),
            "remedy_harm": sum(w(x) for r, x in rows if r["remedy"] == "wrong_or_harmful"),
        }
        out: dict[str, Any] = {k: round(v, 4) for k, v in counts.items()}
        out |= {"supported_rate": _ratio(strict, n), "supported_rate_lenient": _ratio(lenient, n),
                "supported_of_resolved": _ratio(strict, resolved)}
        if runs > 1:
            out["per_run_mean"] = {k: round(v / runs, 4) for k, v in counts.items()}
        return out
    return {"runs": runs, "raw": tally(False), "weighted": tally(True)}


def score(result_path: Path, labels_path: Path) -> dict[str, Any]:
    result = load_result(result_path)
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    if labels.get("format") != LABELS_FORMAT:
        raise ValueError(f"{labels_path}: not an owner labels export ({labels.get('format')!r})")
    result_sha = sha256_file(result_path)
    if labels.get("result_sha256") != result_sha:
        raise ValueError(f"{labels_path}: labels were made for result sha256 {labels.get('result_sha256')}, not {result_sha}")
    expected = packet_content(result, result_sha, labels["seed"], labels.get("max_variants"))["meta"]
    if expected["packet_id"] != labels.get("packet_id"):
        raise ValueError(f"{labels_path}: packet id {labels.get('packet_id')} does not match a rebuild ({expected['packet_id']})")
    probability = expected["sampling"]["inclusion_probability"]
    if labels.get("sampling", {}).get("inclusion_probability", probability) != probability:
        raise ValueError(f"{labels_path}: inclusion probabilities differ from a rebuild of the packet")
    variants = {v["id"]: v for v in result["variants"]}
    origins = result["origins"]
    packet_ids = set(expected["variant_ids"])
    raw_owner = labels.get("labels", {}).get("variants", {})
    unknown = sorted(set(raw_owner) - packet_ids)
    if unknown:
        raise ValueError(f"{labels_path}: labels for variants outside the packet: {unknown[:5]}")
    complete = {v: row for v, row in raw_owner.items() if _complete(row)}
    clusters = {c["cluster_id"]: c for c in issue_clusters(result)}
    weight = {vid: 1 / probability[cid] for cid in expected["cluster_ids"] for vid in clusters[cid]["variant_ids"]}

    views = _views(result, sorted(packet_ids))
    agreement = {name: judge_agreement(view, complete, variants) for name, view in views.items()}

    arms = list(dict.fromkeys(r["arm"] for r in result.get("runs", []))) or sorted({o["arm"] for o in origins.values()})
    runs_by_arm = {arm: [r["run"] for r in result.get("runs", []) if r["arm"] == arm] or
                   sorted({o["run"] for o in origins.values() if o["arm"] == arm}) for arm in arms}
    per_arm, per_run = {}, []
    for arm in arms:
        in_packet = [v for v in packet_ids if origins[v]["arm"] == arm]
        rows = [(complete[v], weight[v]) for v in in_packet if v in complete]
        per_arm[arm] = {"variants_in_packet": len(in_packet), **_arm_stats(rows, len(runs_by_arm[arm]))}
        for run in runs_by_arm[arm]:
            run_ids = [v for v in in_packet if origins[v]["run"] == run]
            run_rows = [(complete[v], weight[v]) for v in run_ids if v in complete]
            per_run.append({"arm": arm, "run": run, "variants_in_packet": len(run_ids), **_arm_stats(run_rows, 1)})

    multi = expected["multi_variant_cluster_ids"]
    answers = labels.get("labels", {}).get("clusters", {})
    answered = [c for c in multi if (answers.get(c) or {}).get("same_issue")]
    split = [c for c in answered if answers[c]["same_issue"] == "split"]
    wsum = lambda ids: sum(1 / probability[c] for c in ids)  # noqa: E731
    boundaries = {"multi_variant_clusters": len(multi), "answered": len(answered), "should_split": len(split),
                  "split_share": _ratio(len(split), len(answered)), "split_share_weighted": _ratio(wsum(split), wsum(answered)),
                  "split_clusters": [{"cluster_id": c, "note": answers[c].get("note"),
                                      "claims": [variants[v]["claim"] for v in clusters[c]["variant_ids"]]} for c in split]}
    return {"format": "reviscope-owner-score-v1", "paper_id": result.get("paper_id"), "result_sha256": result_sha,
            "packet_id": labels["packet_id"], "seed": labels["seed"], "max_variants": labels.get("max_variants"),
            "sampling_design": expected["sampling"]["design"], "sampled": expected["sampling"]["design"] != "census",
            "sampling_strata": sample_clusters(result, labels["seed"], labels.get("max_variants"))["strata"],
            "labels_exported_at": labels.get("exported_at"),
            "coverage": {"variants_in_packet": len(packet_ids), "fully_labelled": len(complete),
                         "partly_labelled": len(raw_owner) - len(complete)},
            "mapping": {"strict": STRICT, "lenient": LENIENT},
            "agreement": agreement, "per_arm": per_arm, "per_run": per_run, "cluster_boundaries": boundaries}


def _fmt(value: Any) -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:.2f}"
    return str(value)


ARM_FIELDS = ("labelled", "supported", "supported_rate", "supported_rate_lenient", "contradicted", "partly_correct",
              "cannot_tell", "supported_material", "would_act", "already_addressed", "remedy_harm")


def report_markdown(report: Mapping[str, Any], max_disagreements: int = 15) -> str:
    cov = report["coverage"]
    lines = [f"# Owner validation: {report['paper_id']}", "",
             f"Packet {report['packet_id']} (seed {report['seed']}; {report['sampling_design']}). "
             f"Fully labelled {cov['fully_labelled']} of {cov['variants_in_packet']} criticisms"
             + (f"; {cov['partly_labelled']} partly labelled and excluded" if cov["partly_labelled"] else "") + ".",
             "One rater, one manuscript: a first estimate, not a validated accuracy. No significance tests.", "",
             "Owner correctness on the judge scale: strict maps partly correct to contradicted (complete-criticism rule); "
             "lenient maps it to supported. Cannot tell maps to unresolved.", "", "## Judge agreement with the owner", "",
             "| view | n | agreement (strict) | kappa (strict) | agreement (lenient) | kappa (lenient) | materiality agreement | weighted kappa | judge higher / lower |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, a in report["agreement"].items():
        m = a["materiality"]
        lines.append(f"| {name} | {a['n']} | {_fmt(a['strict']['agreement'])} | {_fmt(a['strict']['kappa'])} | "
                     f"{_fmt(a['lenient']['agreement'])} | {_fmt(a['lenient']['kappa'])} | {_fmt(m['agreement'])} | "
                     f"{_fmt(m['weighted_kappa_linear'])} | {m['judge_higher']} / {m['judge_lower']} |")
    for name, a in report["agreement"].items():
        lines += ["", f"### {name}: judge (rows) by owner, strict", "", "| judge \\ owner | " + " | ".join(CORRECTNESS) + " |",
                  "|---" * (len(CORRECTNESS) + 1) + "|"]
        for judge, row in a["strict"]["confusion_judge_by_owner"].items():
            lines.append(f"| {judge} | " + " | ".join(str(row[o]) for o in CORRECTNESS) + " |")
        if a["disagreements"]:
            lines += ["", f"Disagreements ({len(a['disagreements'])}; correctness differs or materiality by 2 or more):", ""]
            for d in a["disagreements"][:max_disagreements]:
                o, j = d["owner"], d["judge"]
                lines.append(f"- {d['variant_id']}: owner {o['correctness']} / M{o['materiality']}, judge {j['correctness']} / "
                             f"M{j['materiality']}. {d['claim']}" + (f" Owner note: {o['note']}" if o.get("note") else ""))
            if len(a["disagreements"]) > max_disagreements:
                lines.append(f"- … {len(a['disagreements']) - max_disagreements} more in the JSON report")
    weighted = report["sampled"]
    lines += ["", "## Per arm (owner labels)", "",
              ("Weighted by inverse cluster inclusion probability; counts are estimated pool totals." if weighted
               else "All clusters were included; raw counts."), "",
              "| arm | runs | in packet | " + " | ".join(ARM_FIELDS) + " |", "|---" * (len(ARM_FIELDS) + 3) + "|"]
    for arm, s in report["per_arm"].items():
        values = s["weighted" if weighted else "raw"]
        lines.append(f"| {arm} | {s['runs']} | {s['variants_in_packet']} | " + " | ".join(_fmt(values[k]) for k in ARM_FIELDS) + " |")
    lines += ["", "### Per run", "", "| arm | run | in packet | " + " | ".join(ARM_FIELDS) + " |", "|---" * (len(ARM_FIELDS) + 3) + "|"]
    for row in report["per_run"]:
        values = row["weighted" if weighted else "raw"]
        lines.append(f"| {row['arm']} | {row['run']} | {row['variants_in_packet']} | " + " | ".join(_fmt(values[k]) for k in ARM_FIELDS) + " |")
    b = report["cluster_boundaries"]
    lines += ["", "## Cluster boundaries", "",
              f"{b['should_split']} of {b['answered']} answered multi-criticism clusters should be split "
              f"(share {_fmt(b['split_share'])}" + (f", weighted {_fmt(b['split_share_weighted'])}" if weighted else "")
              + f"); {b['multi_variant_clusters']} multi-criticism clusters in the packet.", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="write a blind HTML labelling packet")
    b.add_argument("result", type=Path)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--seed", type=int, default=DEFAULT_SEED)
    b.add_argument("--max-variants", type=int, default=None, help="target size; larger pools are sampled by whole clusters")
    s = sub.add_parser("score", help="score exported owner labels against the judges")
    s.add_argument("result", type=Path)
    s.add_argument("labels", type=Path)
    s.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.command == "build":
        meta = build(args.result, args.out, args.seed, args.max_variants)
        sampling = meta["sampling"]
        print(f"wrote {args.out}: packet {meta['packet_id']}, {len(meta['variant_ids'])} of {sampling['pool_variants']} criticisms "
              f"in {len(meta['cluster_ids'])} of {sampling['pool_clusters']} issues ({sampling['design']})")
        return 0
    report = score(args.result, args.labels)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(report_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
