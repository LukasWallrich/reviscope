"""Two-pane validation workspace: the owner labels each criticism beside his own manuscript.

`build` writes one self-contained HTML file. The left pane shows one criticism at a time (claim,
reasoning, suggested remedy, outside sources, quoted passages) with the label form; the right pane
holds the full text of the manuscript and its supplements, with the current criticism's quotations
highlighted. Quotations are anchored at build time with `reviscope.verification.verify_quote` and
stored as character offsets into the extracted text; those that cannot be located are marked as not
found verbatim.

Selection, order, packet id, label schema and leak checks are those of `owner_packet.py`, so a
workspace and a packet built from the same `result.json`, seed and `--max-variants` share a packet
id, and labels exported from either are scored by `owner_packet.py score`. Like the packet, the
workspace never embeds origins (arm, run, module, status, severity), judge outputs or cluster
labels; the build refuses to write a file that does.

    uv run python eval/validation_workspace.py build runs/criticism-judge/p/result.json \
        --manuscript paper.pdf [--supplement supp.pdf] --out runs/criticism-judge/p/workspace.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import owner_packet as op  # noqa: E402
from reviscope.ingest import ingest  # noqa: E402
from reviscope.verification import verify_quote  # noqa: E402

WORKSPACE_FORMAT = "reviscope-validation-workspace-v1"

# Single-key shortcuts per question, in the order of each question's options.
KEYS = {"correctness": "1234", "materiality": "qwer", "remedy": "asdfg", "act": "zxc"}

QUESTIONS = (
    ("correctness", "Is the criticism correct?", "Check every part against your manuscript.", op.CORRECTNESS_OPTIONS),
    ("materiality", "How much would it matter if true?", "Your own judgment; answer even if the criticism is wrong.",
     op.MATERIALITY_OPTIONS),
    ("remedy", "The requested action", "What it asks you to do, in the remedy or in its text.", op.REMEDY_OPTIONS),
    ("act", "Would you act on this?", "", op.ACT_OPTIONS),
)


# ---------------------------------------------------------------- manuscript text

def _blocks(text: str, paged: bool, line_paragraphs: bool) -> list[list[Any]]:
    """Display blocks as [start, end, kind, page] over `text`, which stays unchanged so that quote
    offsets keep pointing into it. Kinds: "page" (a "[Page N]" marker), "p" (a paragraph) and
    "lines" (a run of short lines, such as a table, shown with its line breaks).

    PDF text arrives one line per row, so a paragraph ends at a blank line or after a line that is
    clearly shorter than a full line of running text. Word files give one paragraph per line;
    Markdown and plain text separate paragraphs by blank lines."""
    rows: list[tuple[int, int]] = []
    position = 0
    for line in text.split("\n"):
        rows.append((position, position + len(line)))
        position += len(line) + 1
    lengths = sorted(len(text[s:e].strip()) for s, e in rows if text[s:e].strip())
    full = lengths[int(0.8 * (len(lengths) - 1))] if lengths else 0
    short = lambda s, e: len(text[s:e].strip()) < 0.7 * full  # noqa: E731

    # Stage one: units of consecutive lines, each ending at a short line, a blank line or a page marker.
    units: list[Any] = []  # (start, end, single_short) or ("page", start, end, number)
    current: list[tuple[int, int]] = []

    def close() -> None:
        if current:
            units.append((current[0][0], current[-1][1], len(current) == 1 and short(*current[0])))
            current.clear()

    for s, e in rows:
        line = text[s:e].strip()
        if paged and line.startswith("[Page ") and line.endswith("]") and line[6:-1].isdigit():
            close()
            units.append(("page", s, e, int(line[6:-1])))
        elif not line:
            close()
        else:
            current.append((s, e))
            if line_paragraphs or (paged and short(s, e)):
                close()
    close()

    # Stage two: in PDF text, three or more single short lines in a row (a table, a list of
    # values, a reference block) form one block shown with its line breaks.
    blocks: list[list[Any]] = []
    page: int | None = None
    run: list[tuple[int, int, bool]] = []

    def trim(start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end

    def emit_run() -> None:
        if paged and len(run) >= 3:
            blocks.append([*trim(run[0][0], run[-1][1]), "lines", page])
        else:
            blocks.extend([*trim(a, b), "p", page] for a, b, _ in run)
        run.clear()

    for unit in units:
        if unit[0] == "page":
            emit_run()
            page = unit[3]
            blocks.append([unit[1], unit[2], "page", page])
        elif unit[2] and paged:
            run.append(unit)
        else:
            emit_run()
            blocks.append([*trim(unit[0], unit[1]), "p", page])
    emit_run()
    return [b for b in blocks if b[1] > b[0]]


def _page_at(blocks: Sequence[Sequence[Any]], offset: int) -> int | None:
    page = None
    for start, _, kind, number in blocks:
        if start > offset:
            break
        page = number
    return page


def load_sources(manuscript: Path, supplements: Sequence[Path] = ()) -> list[dict[str, Any]]:
    sources = []
    for index, (path, kind) in enumerate([(manuscript, "manuscript"), *((p, "supplement") for p in supplements)]):
        document = ingest(path, kind)
        suffix = Path(document.path).suffix.lower()
        title = "Manuscript" if kind == "manuscript" else (f"Supplement {index}" if len(supplements) > 1 else "Supplement")
        sources.append({"title": title, "file": Path(document.path).name, "text": document.text,
                        "blocks": _blocks(document.text, suffix == ".pdf", suffix == ".docx")})
    return sources


def anchor_quotes(quotes: Sequence[str], sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Each quotation with its source index and character offsets, or src None when not found verbatim."""
    maps = [{"source_id": str(i), "text": s["text"]} for i, s in enumerate(sources)]
    out = []
    for quote in quotes:
        found = verify_quote(quote, maps)
        if found.source_id is None or found.source_char_start is None:
            out.append({"t": quote, "src": None})
            continue
        index = int(found.source_id)
        out.append({"t": quote, "src": index, "s": found.source_char_start, "e": found.source_char_end,
                    "el": found.elided, "pg": _page_at(sources[index]["blocks"], found.source_char_start)})
    return out


# ---------------------------------------------------------------- page

def workspace_data(content: Mapping[str, Any], sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    issues = []
    for issue in content["issues"]:
        variants = [{"id": v["id"], "label": v["label"], "claim": v["claim"], "rationale": v["rationale"], "remedy": v["remedy"],
                     "external": v["external"], "quotes": anchor_quotes(v["quotes"], sources)} for v in issue["variants"]]
        issues.append({"cluster_id": issue["cluster_id"], "number": issue["number"], "variants": variants})
    options = {field: [[value, label, definition, KEYS.get(field, "")[i:i + 1]]
                       for i, (value, label, definition) in enumerate(opts)] for field, _, _, opts in QUESTIONS}
    options["same_issue"] = [[value, label, definition, ""] for value, label, definition in op.SAME_OPTIONS]
    return {"issues": issues, "sources": [{k: s[k] for k in ("title", "file", "text", "blocks")} for s in sources],
            "options": options}


def _json_script(element_id: str, value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    return f'<script type="application/json" id="{element_id}">{payload}</script>'


def _question(field: str, legend: str, hint: str, options: Sequence[tuple[str, str, str]], name: str) -> str:
    keys = KEYS.get(field, "")
    rows = []
    for i, (value, label, definition) in enumerate(options):
        key = keys[i:i + 1]
        input_id = f"{name}-{value}"
        key_html = f'<kbd class="key" aria-hidden="true">{key}</kbd>' if key else ""
        shortcut = f' aria-keyshortcuts="{key}"' if key else ""
        rows.append(f'<label class="opt" for="{input_id}" title="{html.escape(definition)}">'
                    f'<input type="radio" id="{input_id}" name="{name}" value="{value}" data-field="{field}" '
                    f'data-def="{html.escape(definition)}"{shortcut}><span class="opt-label">{html.escape(label)}</span>{key_html}</label>')
    hint_html = f'<span class="hint">{html.escape(hint)}</span>' if hint else ""
    return (f'<fieldset class="q" data-q="{field}"><legend>{html.escape(legend)}{hint_html}</legend>'
            f'<div class="opts">{"".join(rows)}</div><p class="def" aria-live="polite"></p></fieldset>')


def _shortcuts() -> str:
    rows = [("1 2 3 4", "Correct, partly correct, incorrect, cannot tell"), ("q w e r", "Materiality 0 to 3"),
            ("a s d f g", "Requested action, in the order shown"), ("z x c", "Would act: yes, no, already addressed"),
            ("j k", "Next or previous criticism"), ("n", "Next unlabelled criticism or grouping"),
            ("/", "Search the manuscript"), ("?", "Open or close this help"), ("Esc", "Close a panel or leave the search")]
    return "<table class=\"keys\">" + "".join(
        f"<tr><th scope=\"row\">{' '.join(f'<kbd>{html.escape(k)}</kbd>' for k in keys.split())}</th><td>{html.escape(text)}</td></tr>"
        for keys, text in rows) + "</table>"


def render_html(meta: Mapping[str, Any], data: Mapping[str, Any]) -> str:
    n_variants = len(meta["variant_ids"])
    form = "".join(_question(field, legend, hint, options, f"f-{field}") for field, legend, hint, options in QUESTIONS)
    same = "".join(
        f'<label class="opt" for="{{p}}-{value}" title="{html.escape(d)}"><input type="radio" id="{{p}}-{value}" name="{{p}}" '
        f'value="{value}" data-field="same_issue" data-def="{html.escape(d)}"><span class="opt-label">{html.escape(label)}</span></label>'
        for value, label, d in op.SAME_OPTIONS)
    help_html = (
        f"<p>There are {n_variants} criticisms of your manuscript, grouped into {len(data['issues'])} issues. Automated reviewers "
        "wrote them; the order is random and the letters are arbitrary. Assess each criticism on its own against your manuscript, "
        "as a careful reader who knows the paper would.</p>"
        "<p>Answer four questions per criticism; the note is optional. Where an issue groups several criticisms, also say "
        "whether they raise the same issue: <b>Compare</b> shows them side by side. Answers save in this browser as you go. "
        "<b>Export</b> downloads them as a file to send back; <b>Import</b> continues from a file on another device.</p>"
        "<p>Passages the criticism quotes are highlighted in the manuscript on the right. A quotation marked "
        "<i>not found verbatim</i> does not occur in the extracted text as quoted: it may be paraphrased, misquoted or "
        "broken by the PDF's text layer.</p>"
        "<h3>Keyboard</h3>" + _shortcuts() + "<h3>Definitions</h3>" + op._definitions())
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; img-src data:\">"
        f"<title>Criticism labels: workspace {meta['packet_id']}</title><style>{CSS}</style></head><body>"
        "<a class=\"skip\" href=\"#form\">Skip to the label form</a>"
        "<header class=\"top\">"
        "<button type=\"button\" class=\"icon\" id=\"nav-toggle\" aria-controls=\"nav\" aria-expanded=\"true\" title=\"Show or hide the issue list\">"
        "<span aria-hidden=\"true\">&#9776;</span><span class=\"sr\">Issue list</span></button>"
        "<h1>Criticism labels</h1>"
        "<div class=\"progress\" role=\"group\" aria-label=\"Progress\"><div class=\"track\"><div class=\"fill\" id=\"fill\"></div></div>"
        "<span id=\"progress-text\"></span></div>"
        "<button type=\"button\" id=\"next\" title=\"Next unlabelled (n)\">Next unlabelled</button>"
                "<span class=\"status\" id=\"status\" role=\"status\" aria-live=\"polite\"></span>"
        "<button type=\"button\" id=\"export\" class=\"primary\">Export labels</button>"
        "<button type=\"button\" id=\"import\">Import</button>"
        "<input id=\"import-file\" type=\"file\" accept=\"application/json,.json\" hidden>"
        "<button type=\"button\" class=\"icon\" id=\"theme\" title=\"Colour scheme\"><span id=\"theme-label\">Theme: auto</span></button>"
        "<button type=\"button\" class=\"icon\" id=\"help-open\" title=\"Help and shortcuts (?)\" aria-keyshortcuts=\"?\">?</button>"
        "</header>"
        "<div class=\"work\" id=\"work\">"
        "<nav id=\"nav\" aria-label=\"Issues and criticisms\">"
        "<div class=\"nav-head\"><label class=\"filter\"><input type=\"checkbox\" id=\"filter\"> Unlabelled only</label>"
        "<span class=\"nav-tools\"><button type=\"button\" class=\"link\" id=\"expand-all\">Expand all</button>"
        "<button type=\"button\" class=\"link\" id=\"collapse-all\">Collapse all</button></span></div>"
        "<ol id=\"nav-list\" class=\"nav-list\"></ol>"
        "<p class=\"nav-foot\"><kbd>j</kbd><kbd>k</kbd> move <kbd>n</kbd> next unlabelled <kbd>/</kbd> search <kbd>?</kbd> help</p>"
        "</nav>"
        "<section class=\"crit-pane\" id=\"crit-pane\" aria-label=\"Current criticism\">"
        "<div class=\"crit-scroll\" id=\"crit-scroll\">"
        "<div class=\"crit-head\"><h2 id=\"crit-title\"></h2><span id=\"crit-pos\" class=\"pos\"></span>"
        "<span class=\"stepper\"><button type=\"button\" id=\"prev\" title=\"Previous criticism (k)\" aria-keyshortcuts=\"k\">Previous</button>"
        "<button type=\"button\" id=\"forward\" title=\"Next criticism (j)\" aria-keyshortcuts=\"j\">Next</button></span></div>"
        "<article id=\"crit\" class=\"crit\" tabindex=\"-1\"></article>"
        "<form id=\"form\" class=\"form\" autocomplete=\"off\" aria-label=\"Labels for this criticism\" onsubmit=\"return false\">"
        f"{form}"
        "<label class=\"note\" for=\"f-note\">Note <span class=\"hint-inline\">optional</span>"
        "<textarea id=\"f-note\" rows=\"2\" data-field=\"note\"></textarea></label>"
        "<p class=\"form-state\" id=\"form-state\" aria-live=\"polite\"></p>"
        "</form>"
        "<section class=\"group\" id=\"group\" hidden aria-labelledby=\"group-q\">"
        "<fieldset class=\"q\" data-q=\"same_issue\"><legend id=\"group-q\"></legend>"
        f"<div class=\"opts\">{same.replace('{p}', 'g-same')}</div><p class=\"def\" aria-live=\"polite\"></p></fieldset>"
        "<button type=\"button\" id=\"compare-open\">Compare side by side</button></section>"
        "</div></section>"
        "<section class=\"doc-pane\" id=\"doc-pane\" aria-label=\"Manuscript\">"
        "<div class=\"doc-bar\"><div class=\"search\"><label class=\"sr\" for=\"search\">Search the manuscript</label>"
        "<input type=\"search\" id=\"search\" placeholder=\"Search the manuscript  /\" aria-keyshortcuts=\"/\">"
        "<span id=\"search-count\" class=\"search-count\" aria-live=\"polite\"></span>"
        "<button type=\"button\" id=\"search-prev\" class=\"icon\" title=\"Previous match (Shift+Enter)\">&#8593;<span class=\"sr\">Previous match</span></button>"
        "<button type=\"button\" id=\"search-next\" class=\"icon\" title=\"Next match (Enter)\">&#8595;<span class=\"sr\">Next match</span></button></div>"
        "<div class=\"doc-jump\" id=\"doc-jump\"></div></div>"
        "<div class=\"doc-scroll\" id=\"doc-scroll\" tabindex=\"0\" aria-label=\"Manuscript text\"><div class=\"doc\" id=\"doc\"></div></div>"
        "</section>"
        "<section class=\"compare\" id=\"compare\" hidden aria-labelledby=\"compare-title\">"
        "<div class=\"compare-head\"><h2 id=\"compare-title\"></h2><button type=\"button\" id=\"compare-close\">Close <kbd>Esc</kbd></button></div>"
        "<div class=\"compare-cols\" id=\"compare-cols\"></div>"
        "<div class=\"compare-foot\"><fieldset class=\"q\" data-q=\"same_issue\"><legend>Do these criticisms raise the same issue?"
        "<span class=\"hint\">Answer after reading all of them.</span></legend>"
        f"<div class=\"opts\">{same.replace('{p}', 'c-same')}</div><p class=\"def\" aria-live=\"polite\"></p></fieldset>"
        "<label class=\"note\" for=\"c-note\">Note on the grouping <span class=\"hint-inline\">optional</span>"
        "<textarea id=\"c-note\" rows=\"1\" data-field=\"cluster_note\"></textarea></label></div>"
        "</section>"
        "</div>"
        f"<dialog id=\"help\" aria-labelledby=\"help-title\"><div class=\"help-head\"><h2 id=\"help-title\">How this works</h2>"
        f"<button type=\"button\" id=\"help-close\">Close</button></div><div class=\"help-body\">{help_html}"
        f"<p class=\"muted\">Packet {html.escape(meta['packet_id'])}.</p></div></dialog>"
        + _json_script("packet-meta", meta) + _json_script("workspace-data", data)
        + f"<script>{JS}</script></body></html>\n")


def template_text() -> str:
    """The workspace's fixed text around neutral placeholder content; identical for every workspace."""
    variants = [{"label": label, "id": f"V{label}", "claim": "x", "rationale": "x", "remedy": "x", "quotes": ["x"], "external": ["x"]}
                for label in ("A", "B")]
    meta = {"packet_id": "0", "variant_ids": ["VA", "VB"], "cluster_ids": ["K"], "multi_variant_cluster_ids": ["K"]}
    sources = [{"title": "Manuscript", "file": "x", "text": "x", "blocks": [[0, 1, "p", None]]}]
    return render_html(meta, workspace_data({"issues": [{"cluster_id": "K", "number": 1, "variants": variants}]}, sources))


def build(result_path: Path, manuscript: Path, out: Path, supplements: Sequence[Path] = (), seed: int = op.DEFAULT_SEED,
          max_variants: int | None = None) -> dict[str, Any]:
    result = op.load_result(result_path)
    content = op.packet_content(result, op.sha256_file(result_path), seed, max_variants)
    meta = {**content["meta"], "format": WORKSPACE_FORMAT}
    sources = load_sources(manuscript, supplements)
    data = workspace_data(content, sources)
    document = render_html(meta, data)
    if found := op.leaks(document, result, fixed=template_text(), allowed=[s["text"] for s in sources]
                         + [f"{s['title']} {s['file']}" for s in sources]):
        raise RuntimeError(f"workspace would reveal origin or judge information: {found}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding="utf-8")
    quotes = [q for issue in data["issues"] for v in issue["variants"] for q in v["quotes"]]
    anchored = [q for q in quotes if q["src"] is not None]
    return {**meta, "quotes": len(quotes), "quotes_anchored": len(anchored), "quotes_elided": sum(bool(q.get("el")) for q in anchored)}


# ---------------------------------------------------------------- CLI

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="write the two-pane HTML labelling workspace")
    b.add_argument("result", type=Path)
    b.add_argument("--manuscript", type=Path, required=True)
    b.add_argument("--supplement", type=Path, action="append", default=[])
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--seed", type=int, default=op.DEFAULT_SEED)
    b.add_argument("--max-variants", type=int, default=None, help="target size; larger pools are sampled by whole clusters")
    args = parser.parse_args(argv)
    meta = build(args.result, args.manuscript, args.out, args.supplement, args.seed, args.max_variants)
    sampling = meta["sampling"]
    print(f"wrote {args.out}: packet {meta['packet_id']}, {len(meta['variant_ids'])} of {sampling['pool_variants']} criticisms "
          f"in {len(meta['cluster_ids'])} of {sampling['pool_clusters']} issues ({sampling['design']}); "
          f"{meta['quotes_anchored']} of {meta['quotes']} quotations anchored ({meta['quotes_elided']} shortened)")
    return 0


# Palette: a cool grey desk, white paper for the manuscript, ink-blue controls, and a
# highlighter yellow that marks the current criticism's quotations.
DARK = ("color-scheme:dark;--desk:#12161b;--panel:#191e25;--paper:#1f252d;--ink:#e3e8ee;--muted:#a3aebb;--line:#39424d;"
        "--line-soft:#2a3139;--accent:#8fb3ff;--accent-ink:#0f1620;--accent-soft:#25324a;--done:#6cc69a;--done-soft:#1f3a2e;"
        "--part:#e0b25c;--warn:#ff9a8f;--warn-soft:#45231f;--mark:#6a5a12;--mark-ink:#fff6cf;--mark-cur:#9a7d0a;--hit:#2f4670;"
        "--hit-cur:#4a6db0")

CSS = """
:root{color-scheme:light;
--desk:#e6eaef;--panel:#f6f8fa;--paper:#ffffff;--ink:#17202b;--muted:#4f5d6c;--line:#c9d1da;--line-soft:#e1e6ec;
--accent:#244f9e;--accent-ink:#ffffff;--accent-soft:#dfe8f7;--done:#1f6f4c;--done-soft:#dcefe5;--part:#8a5a00;
--warn:#a1261c;--warn-soft:#f8e2df;--mark:#ffe680;--mark-ink:#17202b;--mark-cur:#ffc928;--hit:#cfe0ff;--hit-cur:#8fb2f5;
--serif:Charter,"Bitstream Charter","Iowan Old Style","Source Serif 4","Source Serif Pro","Sitka Text",Cambria,Georgia,serif;
--sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;--radius:6px}
:root[data-theme=dark]{@DARK@}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){@DARK@}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--desk);color:var(--ink);font:14px/1.45 var(--sans);display:flex;flex-direction:column;overflow:hidden}
button,input,textarea{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.skip{position:absolute;left:-999px;top:0;background:var(--paper);padding:.4rem .8rem;z-index:30}.skip:focus{left:.5rem}
kbd{font:600 11px/1 var(--sans);display:inline-block;min-width:1.35em;padding:.2em .35em;border:1px solid var(--line);border-bottom-width:2px;
border-radius:4px;background:var(--paper);color:var(--muted);text-align:center;margin:0 .1em}
button{cursor:pointer;background:var(--paper);border:1px solid var(--line);border-radius:var(--radius);padding:.32rem .7rem;white-space:nowrap}
button:hover{border-color:var(--accent)}
button.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent);font-weight:600}
button.link{border:0;background:none;padding:0;color:var(--accent);text-decoration:underline;text-underline-offset:2px}
button.icon{padding:.32rem .55rem;min-width:2rem}
.nav-item,.nav-group,.quote,.nav-issue>button{white-space:normal}
.top{display:flex;align-items:center;gap:.6rem;padding:.45rem .8rem;background:var(--panel);border-bottom:1px solid var(--line);flex:none}
.top h1{font-size:15px;font-weight:650;margin:0 .4rem 0 0;white-space:nowrap}
.progress{display:flex;align-items:center;gap:.6rem;flex:0 1 24rem;min-width:9rem}
.track{flex:1;height:8px;background:var(--line-soft);border-radius:4px;overflow:hidden;border:1px solid var(--line)}
.fill{height:100%;width:0;background:var(--done);transition:width .25s}
#progress-text{color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
.status{flex:1 1 0;min-width:0;color:var(--muted);font-size:13px;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.status.stale{color:var(--part)}
.work{flex:1;min-height:0;display:grid;grid-template-columns:15.5rem minmax(23rem,31rem) minmax(0,1fr);position:relative}
.work.nav-hidden{grid-template-columns:0 minmax(23rem,33rem) minmax(0,1fr)}
.work.nav-hidden nav{visibility:hidden}
nav{border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:0;overflow:hidden;background:var(--desk)}
.nav-head{padding:.6rem .7rem;display:flex;flex-wrap:wrap;justify-content:space-between;gap:.3rem .6rem;border-bottom:1px solid var(--line)}
.filter{display:flex;gap:.35rem;align-items:center;cursor:pointer}
.nav-tools{display:flex;gap:.6rem;font-size:13px}
.nav-list{list-style:none;margin:0;padding:.3rem 0 1rem;overflow:auto;flex:1}
.nav-issue>button{width:100%;display:flex;align-items:center;gap:.45rem;border:0;border-radius:0;background:none;padding:.4rem .7rem;text-align:left;font-weight:600}
.nav-issue>button:hover{background:var(--line-soft)}
.caret{display:inline-block;width:.8em;color:var(--muted)}
.nav-issue.open .caret{transform:rotate(90deg)}
.nav-issue .tally{margin-left:auto;font-weight:400;color:var(--muted);font-variant-numeric:tabular-nums;font-size:12px}
.nav-issue.complete .tally{color:var(--done);font-weight:600}
.nav-issue ol{list-style:none;margin:0 0 .3rem;padding:0}
.nav-issue:not(.open) ol{display:none}
.nav-item{width:100%;display:grid;grid-template-columns:1.2rem 1fr;gap:.1rem .4rem;border:0;border-radius:0;background:none;padding:.28rem .7rem .28rem 1.55rem;text-align:left;color:var(--ink)}
.nav-item:hover{background:var(--line-soft)}
.nav-item[aria-current=true]{background:var(--accent-soft);box-shadow:inset 3px 0 0 var(--accent)}
.nav-item .snip{grid-column:2;color:var(--muted);font-size:12.5px;line-height:1.3;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.nav-item b{font-weight:600}
.dot{width:.75rem;height:.75rem;border-radius:50%;border:1.5px solid var(--muted);margin-top:.2rem;grid-row:span 2}
.dot.part{background:linear-gradient(90deg,var(--part) 50%,transparent 50%);border-color:var(--part)}
.dot.full{background:var(--done);border-color:var(--done)}
.nav-group{width:100%;border:0;border-radius:0;background:none;padding:.25rem .7rem .3rem 1.55rem;font-size:12.5px;color:var(--muted);display:flex;gap:.4rem;align-items:center;text-align:left}
.nav-group:hover{background:var(--line-soft)}
.nav-group .dot{grid-row:auto;margin:0;border-radius:2px}
.nav-list.filtered .is-done,.nav-list.filtered .nav-issue.complete{display:none}
.nav-foot{margin:0;padding:.5rem .7rem;border-top:1px solid var(--line);color:var(--muted);font-size:12px;line-height:1.9}
.crit-pane{background:var(--panel);border-right:1px solid var(--line);min-height:0;display:flex;flex-direction:column}
.crit-scroll{overflow:auto;padding:.9rem 1.1rem 3rem;flex:1}
.crit-head{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
.crit-head h2{font-size:13px;font-weight:600;margin:0;color:var(--muted)}
.pos{color:var(--muted);font-size:13px}
.stepper{margin-left:auto;display:flex;gap:.3rem}.stepper button{padding:.2rem .6rem;font-size:13px}
.crit{outline:none}
.claim{font-size:18px;line-height:1.4;font-weight:600;margin:.55rem 0 .9rem;letter-spacing:-.005em}
.crit h3{font-size:13px;font-weight:600;color:var(--muted);margin:1rem 0 .25rem}
.crit p.body{margin:0 0 .3rem;font-size:15px;line-height:1.55;white-space:pre-line}
.crit .none{color:var(--muted);font-style:italic;font-size:14px;margin:0}
.ext{margin:.2rem 0;padding-left:1.1rem;font-size:14px}
.quotes{list-style:none;margin:.3rem 0;padding:0;display:flex;flex-direction:column;gap:.4rem}
.quote{display:grid;grid-template-columns:1.6rem 1fr;gap:.5rem;width:100%;text-align:left;padding:.5rem .6rem;background:var(--paper);border:1px solid var(--line);border-radius:var(--radius)}
.quote .num{font:700 12px/1.4rem var(--sans);text-align:center;border-radius:3px;background:var(--ink);color:var(--paper);height:1.4rem;width:1.5rem}
.quote q{font:15px/1.5 var(--serif);quotes:none;display:block}
.quote .where{display:block;font-size:12px;color:var(--muted);margin-top:.2rem}
.quote.missing{cursor:default;border-style:dashed}
.quote.missing .num{background:transparent;border:1.5px dashed var(--warn);color:var(--warn);line-height:1.2rem}
.quote.missing .where{color:var(--warn);font-weight:600}
.quote.active{border-color:var(--ink);box-shadow:inset 3px 0 0 var(--mark-cur)}
.form{margin-top:1.3rem;border-top:2px solid var(--ink);padding-top:.4rem}
.q{border:0;margin:.65rem 0 0;padding:0;min-width:0}
.q legend{font-weight:650;padding:0;margin-bottom:.3rem;font-size:14px}
.hint{display:block;font-weight:400;color:var(--muted);font-size:12.5px}
.hint-inline{font-weight:400;color:var(--muted);font-size:12.5px}
.opts{display:flex;flex-wrap:wrap;gap:.25rem}
.opt{position:relative;display:inline-flex;align-items:center;gap:.35rem;padding:.26rem .35rem .26rem .5rem;font-size:13.5px;border:1px solid var(--line);border-radius:var(--radius);background:var(--paper);cursor:pointer;user-select:none}
.opt input{position:absolute;opacity:0;pointer-events:none;margin:0}
.opt:hover{border-color:var(--accent)}
.opt:has(input:focus-visible){outline:2px solid var(--accent);outline-offset:2px}
.opt:has(input:checked){background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.opt:has(input:checked) .key{background:transparent;color:var(--accent-ink);border-color:currentColor}
.opt .key{font-size:10.5px;padding:.15em .3em}
.def{margin:.25rem 0 0;color:var(--muted);font-size:12.5px;min-height:1.1em}
.note{display:block;margin-top:.8rem;font-weight:650}
textarea{display:block;width:100%;margin-top:.25rem;font:14px/1.4 var(--sans);background:var(--paper);border:1px solid var(--line);border-radius:var(--radius);padding:.4rem .5rem;resize:vertical}
.form-state{margin:.6rem 0 0;font-size:13px;color:var(--muted);min-height:1.2em}
.form-state.ok{color:var(--done);font-weight:600}
.group{margin-top:1.2rem;padding:.7rem .8rem;border:1px dashed var(--muted);border-radius:var(--radius);background:var(--paper)}
.group.is-done{border-style:solid;border-color:var(--done)}
.group .q{margin:0}
.group button{margin-top:.6rem}
.doc-pane{display:flex;flex-direction:column;min-height:0;background:var(--paper)}
.doc-bar{display:flex;flex-wrap:wrap;gap:.4rem .8rem;align-items:center;padding:.45rem .9rem;border-bottom:1px solid var(--line);background:var(--panel)}
.search{display:flex;align-items:center;gap:.3rem;flex:1 1 12rem;max-width:30rem}
.search input{flex:1;min-width:8rem;padding:.3rem .55rem;border:1px solid var(--line);border-radius:var(--radius);background:var(--paper)}
.search-count{color:var(--muted);font-size:12.5px;white-space:nowrap;font-variant-numeric:tabular-nums;min-width:4.5rem;text-align:right}
.doc-jump{display:flex;gap:.3rem}.doc-jump button{font-size:13px;padding:.2rem .6rem}
.doc-scroll{overflow:auto;flex:1}
.doc-scroll:focus-visible{outline-offset:-3px}
.doc{max-width:38rem;margin:0 auto;padding:1.6rem 2.2rem 45vh;font:17px/1.7 var(--serif);color:var(--ink);font-kerning:normal}
.doc h2.src{font:650 13px/1.3 var(--sans);color:var(--muted);margin:3rem 0 1.2rem;padding-top:.9rem;border-top:3px double var(--line)}
.doc h2.src:first-child{margin-top:0;border-top:0;padding-top:0}
.doc p{margin:0 0 .85em}
.doc .lines{white-space:pre-line;font-size:14.5px;line-height:1.5;margin:0 0 .85em;padding-left:.8rem;border-left:2px solid var(--line-soft)}
.doc .page{font:12px/1 var(--sans);color:var(--muted);display:flex;align-items:center;gap:.6rem;margin:1.3rem 0}
.doc .page::after{content:"";flex:1;border-top:1px dotted var(--line)}
mark{background:none;color:inherit}
mark.q{background:var(--mark);color:var(--mark-ink);border-radius:2px;box-shadow:0 0 0 1px var(--mark);-webkit-box-decoration-break:clone;box-decoration-break:clone}
mark.q.el{background:repeating-linear-gradient(135deg,var(--mark) 0 7px,var(--mark-cur) 7px 9px)}
mark.q.qcur{background:var(--mark-cur);box-shadow:0 0 0 2px var(--mark-cur)}
.qtab{font:700 10.5px/1 var(--sans);vertical-align:.4em;background:var(--ink);color:var(--paper);border-radius:3px;padding:.14em .34em;margin:0 .2em 0 .05em;user-select:none}
mark.hit{background:var(--hit);color:var(--ink);border-radius:2px}
mark.hit.hcur{background:var(--hit-cur);outline:2px solid var(--accent)}
@keyframes pulse{0%{outline:3px solid var(--accent);outline-offset:1px}100%{outline:3px solid transparent;outline-offset:8px}}
mark.q.pulse{animation:pulse .8s ease-out 2}
.compare{position:absolute;top:0;right:0;bottom:0;left:15.5rem;background:var(--panel);z-index:10;display:flex;flex-direction:column;border-left:1px solid var(--line)}
.work.nav-hidden .compare{left:0}
.compare[hidden]{display:none}
.compare-head{display:flex;align-items:center;justify-content:space-between;padding:.7rem 1.1rem;border-bottom:1px solid var(--line)}
.compare-head h2{font-size:16px;margin:0}
.compare-cols{flex:1;overflow:auto;display:grid;grid-auto-flow:column;grid-auto-columns:minmax(19rem,1fr)}
.col{padding:1rem 1.1rem;border-right:1px solid var(--line)}
.col:last-child{border-right:0}
.col-head{display:flex;justify-content:space-between;align-items:center;gap:.5rem}
.col-head h3{margin:0;font-size:13px;color:var(--muted)}
.col-head .dot{grid-row:auto;margin:0}
.col .claim{font-size:16px}
.col h4{font-size:12.5px;color:var(--muted);margin:.8rem 0 .2rem}
.col p{margin:0 0 .3rem;font-size:14px}
.col blockquote{margin:.3rem 0;padding:.3rem .6rem;border-left:3px solid var(--mark-cur);font:14px/1.45 var(--serif);background:var(--paper)}
.compare-foot{border-top:2px solid var(--ink);padding:.7rem 1.1rem 1rem;background:var(--panel)}
.compare-foot .q{margin-top:0}
dialog{max-width:46rem;width:calc(100% - 2rem);max-height:85vh;padding:0;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)}
dialog::backdrop{background:rgba(10,16,24,.45)}
.help-head{display:flex;justify-content:space-between;align-items:center;padding:.8rem 1.2rem;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--panel)}
.help-head h2{margin:0;font-size:17px}
.help-body{padding:.4rem 1.2rem 1.2rem;font-size:14.5px;line-height:1.5}
.help-body h3{font-size:14px;margin:1.2rem 0 .4rem}
.keys{border-collapse:collapse}.keys th{text-align:left;font-weight:400;padding:.15rem 1rem .15rem 0;white-space:nowrap}.keys td{padding:.15rem 0}
.defs dt{font-weight:650;margin-top:.6rem}.defs dd{margin:0}.defs ul{margin:.15rem 0;padding-left:1.1rem}
.muted{color:var(--muted)}
@media (max-width:1180px){
.work,.work.nav-hidden{grid-template-columns:minmax(21rem,27rem) minmax(0,1fr)}
nav{position:absolute;top:0;bottom:0;left:0;width:17rem;z-index:15;box-shadow:4px 0 18px rgba(0,0,0,.2)}
.work.nav-hidden nav{display:none}
.compare,.work.nav-hidden .compare{left:0}
#progress-text{font-size:12.5px}
.top h1{display:none}
}
@media (max-width:760px){body{overflow:auto;height:auto}.work{display:block}.crit-pane,.doc-pane{min-height:70vh}.top{flex-wrap:wrap}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
""".replace("@DARK@", DARK)

JS = r"""
(function(){
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const META = JSON.parse($('#packet-meta').textContent);
const DATA = JSON.parse($('#workspace-data').textContent);
const KEY = 'reviscope-owner-packet:' + META.packet_id;  // shared with the one-page packet
const UI_KEY = 'reviscope-workspace:' + META.packet_id;
const FIELDS = ['correctness', 'materiality', 'remedy', 'act'];
const OPT = DATA.options;
const KEYMAP = {};
FIELDS.forEach(f => OPT[f].forEach(o => { if (o[3]) KEYMAP[o[3]] = [f, o[0]]; }));
const SMOOTH = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function el(tag, cls, text){ const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined && text !== null) n.textContent = text; return n; }
function btn(cls, text){ const b = el('button', cls, text); b.type = 'button'; return b; }

// ------------------------------------------------------------ order and storage
const ORDER = [], BY_ID = {};
DATA.issues.forEach(issue => issue.variants.forEach(v => { const item = {issue, v, idx: ORDER.length}; ORDER.push(item); BY_ID[v.id] = item; }));
const MULTI = DATA.issues.filter(i => i.variants.length > 1);

let canStore = true;
function readJSON(key){ try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : null; } catch (e) { canStore = false; return null; } }
function writeJSON(key, value){ try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (e) { canStore = false; return false; } }
let state = readJSON(KEY) || {};
state = {started_at: state.started_at || null, updated_at: state.updated_at || null, variants: state.variants || {}, clusters: state.clusters || {}};
let ui = readJSON(UI_KEY) || {};
ui.open = ui.open || {};
function saveUI(){ writeJSON(UI_KEY, ui); }
function now(){ return new Date().toISOString(); }

function answered(id){ const r = state.variants[id] || {}; return FIELDS.filter(f => r[f] !== undefined && r[f] !== null).length; }
function variantDone(id){ return answered(id) === FIELDS.length; }
function groupDone(cid){ const r = state.clusters[cid]; return !!(r && r.same_issue); }

function fmtTime(iso){
  const d = new Date(iso), t = d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
  return d.toDateString() === new Date().toDateString() ? t : d.toLocaleDateString([], {day: 'numeric', month: 'short'}) + ' ' + t;
}
function unexported(){ return !!state.updated_at && (!ui.exported_state || state.updated_at > ui.exported_state); }
function updateStatus(message){
  const node = $('#status');
  let text;
  if (!canStore) text = 'Browser storage unavailable: export often';
  else if (!state.updated_at) text = 'No labels yet';
  else text = 'Saved in this browser';
  if (state.updated_at && canStore) text = 'Saved';
  if (ui.exported_at) text += unexported() ? ', changed since export at ' + fmtTime(ui.exported_at) : ', exported ' + fmtTime(ui.exported_at);
  else if (state.updated_at) text += ', not exported yet';
  node.textContent = message || text;
  node.title = text;
  node.classList.toggle('stale', !canStore || unexported());
}
function save(){ writeJSON(KEY, state); updateStatus(); }

// ------------------------------------------------------------ manuscript
const SRC = DATA.sources.map(s => ({...s, els: []}));
const docScroll = $('#doc-scroll');

function display(text, kind){
  if (kind === 'lines') return text.replace(/[ \t]+\n/g, '\n');
  return text.replace(/(\w)-[ \t]*\n\s*/g, '$1-').replace(/\s*\n\s*/g, ' ');
}
function paint(si, bi, ranges){
  const src = SRC[si], b = src.blocks[bi], node = src.els[bi], kind = b[2];
  node.replaceChildren();
  if (!ranges.length) { node.textContent = display(src.text.slice(b[0], b[1]), kind); return; }
  const cuts = new Set([b[0], b[1]]);
  ranges.forEach(r => { cuts.add(Math.max(b[0], Math.min(b[1], r.s))); cuts.add(Math.max(b[0], Math.min(b[1], r.e))); });
  const points = [...cuts].sort((x, y) => x - y);
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], z = points[i + 1];
    if (z <= a) continue;
    const text = display(src.text.slice(a, z), kind);
    const active = ranges.filter(r => r.s < z && r.e > a);
    if (!active.length) { node.append(text); continue; }
    active.filter(r => r.q && r.s === a).forEach(r => {
      const tab = el('span', 'qtab', String(r.q)); tab.setAttribute('aria-hidden', 'true'); node.append(tab);
    });
    const mark = el('mark');
    const quotes = active.filter(r => r.q), hit = active.find(r => r.hit);
    if (quotes.length) {
      mark.classList.add('q'); mark.dataset.q = quotes.map(r => r.q).join(' ');
      if (quotes.every(r => r.el)) mark.classList.add('el');
      if (active.some(r => r.q && r.cur)) mark.classList.add('qcur');
    }
    if (hit) { mark.classList.add('hit'); mark.dataset.hit = hit.n; if (hit.cur) mark.classList.add('hcur'); }
    mark.append(text);
    node.append(mark);
  }
}
function blocksFor(si, s, e){
  const blocks = SRC[si].blocks;
  let lo = 0, hi = blocks.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (blocks[mid][1] <= s) lo = mid + 1; else hi = mid; }
  const out = [];
  for (let i = lo; i < blocks.length && blocks[i][0] < e; i++) if (blocks[i][2] !== 'page') out.push(i);
  return out;
}
let quoteRanges = [], hits = [], hitIndex = -1, activeQuote = null;
const painted = new Set();
function repaint(){
  const want = {};
  const add = r => blocksFor(r.si, r.s, r.e).forEach(bi => { const k = r.si + ':' + bi; (want[k] = want[k] || []).push(r); });
  quoteRanges.forEach(r => { r.cur = r.q === activeQuote; add(r); });
  hits.forEach((h, i) => { h.cur = i === hitIndex; add(h); });
  new Set([...painted, ...Object.keys(want)]).forEach(k => { const [si, bi] = k.split(':').map(Number); paint(si, bi, want[k] || []); });
  painted.clear();
  Object.keys(want).forEach(k => painted.add(k));
}
function scrollDocTo(node, smooth){
  if (!node) return;
  const r = node.getBoundingClientRect(), box = docScroll.getBoundingClientRect();
  docScroll.scrollTo({top: docScroll.scrollTop + r.top - box.top - box.height * 0.28, behavior: smooth && SMOOTH ? 'smooth' : 'auto'});
}
function buildDoc(){
  const doc = $('#doc'), jump = $('#doc-jump');
  SRC.forEach((src, si) => {
    const head = el('h2', 'src', src.title + (src.file ? ': ' + src.file : ''));
    head.id = 'src-' + si;
    doc.append(head);
    if (SRC.length > 1) {
      const b = btn('', src.title);
      b.addEventListener('click', () => { docScroll.scrollTop += head.getBoundingClientRect().top - docScroll.getBoundingClientRect().top - 8; });
      jump.append(b);
    }
    src.blocks.forEach(b => {
      const node = b[2] === 'page' ? el('div', 'page', 'Page ' + b[3]) : el(b[2] === 'lines' ? 'div' : 'p', b[2] === 'lines' ? 'lines' : '');
      if (b[2] !== 'page') node.textContent = display(src.text.slice(b[0], b[1]), b[2]);
      src.els.push(node);
      doc.append(node);
    });
  });
}
function focusQuote(n, smooth){
  activeQuote = n;
  repaint();
  $$('#crit .quote').forEach(q => q.classList.toggle('active', Number(q.dataset.q) === n));
  const marks = $$('#doc mark.q[data-q~="' + n + '"]');
  scrollDocTo(marks[0], smooth);
  if (smooth) { marks.forEach(m => m.classList.add('pulse')); setTimeout(() => marks.forEach(m => m.classList.remove('pulse')), 1700); }
}

// ------------------------------------------------------------ search
const searchInput = $('#search');
function runSearch(){
  const query = searchInput.value.trim();
  hits = []; hitIndex = -1;
  if (query.length >= 2) {
    const pattern = query.split(/\s+/).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/-/g, '-\\s*')).join('\\s+');
    const re = new RegExp(pattern, 'gi');
    SRC.forEach((src, si) => {
      re.lastIndex = 0;
      let m;
      while (hits.length < 1000 && (m = re.exec(src.text))) {
        if (!m[0].length) { re.lastIndex++; continue; }
        hits.push({si, s: m.index, e: m.index + m[0].length, hit: true, n: hits.length});
      }
    });
    if (hits.length) hitIndex = 0;
  }
  repaint();
  showHit(false);
}
function showHit(smooth){
  const count = $('#search-count');
  if (!searchInput.value.trim()) count.textContent = '';
  else if (!hits.length) count.textContent = searchInput.value.trim().length < 2 ? '' : 'No matches';
  else count.textContent = (hitIndex + 1) + ' of ' + hits.length + (hits.length >= 1000 ? '+' : '');
  if (hitIndex >= 0) scrollDocTo($('#doc mark[data-hit="' + hitIndex + '"]'), smooth);
}
function stepHit(delta){
  if (!hits.length) return;
  hitIndex = (hitIndex + delta + hits.length) % hits.length;
  repaint();
  showHit(true);
}
let searchTimer = null;
searchInput.addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 160); });
searchInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); clearTimeout(searchTimer); if (!hits.length) runSearch(); else stepHit(e.shiftKey ? -1 : 1); }
});
$('#search-next').addEventListener('click', () => stepHit(1));
$('#search-prev').addEventListener('click', () => stepHit(-1));

// ------------------------------------------------------------ current criticism
let current = null;
function section(parent, title){ parent.append(el('h3', '', title)); }
function where(q){
  if (q.src === null) return 'Not found verbatim in the manuscript or supplements';
  let text = SRC[q.src].title + (q.pg ? ', page ' + q.pg : '');
  if (q.el) text += '; shortened, so the highlight spans the omitted words';
  return text;
}
function renderCrit(){
  const {issue, v} = current;
  $('#crit-title').textContent = 'Issue ' + issue.number + ', criticism ' + v.label;
  $('#crit-pos').textContent = (current.idx + 1) + ' of ' + ORDER.length;
  const art = $('#crit');
  art.replaceChildren();
  art.setAttribute('aria-label', 'Issue ' + issue.number + ', criticism ' + v.label);
  art.append(el('p', 'claim', v.claim));
  if (v.rationale) { section(art, 'Reasoning given'); art.append(el('p', 'body', v.rationale)); }
  section(art, 'Suggested remedy');
  art.append(v.remedy ? el('p', 'body', v.remedy) : el('p', 'none', 'None stated separately.'));
  if (v.quotes.length) {
    section(art, v.quotes.length === 1 ? 'Quoted from the manuscript' : 'Quoted from the manuscript (' + v.quotes.length + ')');
    const list = el('ol', 'quotes');
    v.quotes.forEach((q, i) => {
      const n = i + 1, found = q.src !== null;
      const item = found ? btn('quote') : el('div', 'quote missing');
      item.dataset.q = n;
      if (found) item.title = 'Show in the manuscript';
      const num = el('span', 'num', String(n));
      const body = el('span');
      body.append(el('q', '', q.t), el('span', 'where', where(q)));
      item.append(num, body);
      if (found) item.addEventListener('click', () => focusQuote(n, true));
      const li = el('li'); li.append(item); list.append(li);
    });
    art.append(list);
  }
  if (v.external && v.external.length) {
    section(art, 'Outside sources cited');
    const list = el('ul', 'ext');
    v.external.forEach(x => list.append(el('li', '', x)));
    art.append(list);
  }
  const group = $('#group');
  group.hidden = issue.variants.length < 2;
  if (!group.hidden) $('#group-q').textContent = 'Issue ' + issue.number + ' groups ' + issue.variants.length + ' criticisms. Do they raise the same issue?';
}
function applyForm(){
  if (!current) return;
  const row = state.variants[current.v.id] || {}, crow = state.clusters[current.issue.cluster_id] || {};
  $$('input[type=radio][data-field]').forEach(input => {
    const value = input.dataset.field === 'same_issue' ? crow.same_issue : row[input.dataset.field];
    input.checked = value !== undefined && value !== null && String(value) === input.value;
  });
  $('#f-note').value = row.note || '';
  $('#c-note').value = crow.note || '';
  $$('fieldset.q').forEach(resetDef);
  const n = answered(current.v.id), st = $('#form-state');
  st.textContent = n === FIELDS.length ? 'All four answered. Press n for the next unlabelled.' : n + ' of 4 answered';
  st.classList.toggle('ok', n === FIELDS.length);
  $('#group').classList.toggle('is-done', groupDone(current.issue.cluster_id));
}
function resetDef(fs){
  const checked = fs.querySelector('input:checked'), out = fs.querySelector('.def');
  if (out) out.textContent = checked ? checked.parentNode.querySelector('.opt-label').textContent + ': ' + checked.dataset.def : '';
}
function showDef(input){
  const out = input.closest('fieldset').querySelector('.def');
  out.textContent = input.parentNode.querySelector('.opt-label').textContent + ': ' + input.dataset.def;
}
document.addEventListener('mouseover', e => { const o = e.target.closest && e.target.closest('.opt'); if (o) showDef(o.querySelector('input')); });
document.addEventListener('mouseout', e => { const o = e.target.closest && e.target.closest('.opt'); if (o && !o.contains(e.relatedTarget)) resetDef(o.closest('fieldset')); });
document.addEventListener('focusin', e => { if (e.target.matches('.opt input')) showDef(e.target); });
document.addEventListener('focusout', e => { if (e.target.matches('.opt input')) resetDef(e.target.closest('fieldset')); });

function go(idx, options){
  options = options || {};
  idx = Math.max(0, Math.min(ORDER.length - 1, idx));
  const issueChanged = !current || current.issue !== ORDER[idx].issue;
  current = ORDER[idx];
  ui.pos = current.v.id;
  if (!ui.open[current.issue.cluster_id]) { ui.open[current.issue.cluster_id] = true; }
  saveUI();
  renderCrit();
  applyForm();
  $('#crit-scroll').scrollTop = 0;
  quoteRanges = [];
  current.v.quotes.forEach((q, i) => { if (q.src !== null) quoteRanges.push({si: q.src, s: q.s, e: q.e, q: i + 1, el: q.el}); });
  const first = quoteRanges.length ? quoteRanges[0].q : null;
  if (first !== null) focusQuote(first, false);
  else { activeQuote = null; repaint(); }
  refresh();
  if (!$('#compare').hidden) { if (issueChanged && current.issue.variants.length < 2) closeCompare(); else renderCompare(); }
  if (options.focus) $('#crit').focus({preventScroll: true});
}

// ------------------------------------------------------------ labels
function record(field, value){
  const cluster = field === 'same_issue' || field === 'cluster_note';
  const id = cluster ? current.issue.cluster_id : current.v.id;
  const bucket = cluster ? state.clusters : state.variants;
  const row = bucket[id] || (bucket[id] = {});
  if (field === 'note' || field === 'cluster_note') { if (value.trim()) row.note = value; else delete row.note; }
  else row[field] = field === 'materiality' ? Number(value) : value;
  const t = now();
  row.updated_at = t;
  if (!state.started_at) state.started_at = t;
  state.updated_at = t;
  save();
  if (field === 'note' || field === 'cluster_note') { refresh(); return; }
  applyForm();
  refresh();
}
document.addEventListener('change', e => { if (e.target.matches('input[type=radio][data-field]')) record(e.target.dataset.field, e.target.value); });
document.addEventListener('input', e => { if (e.target.matches('textarea[data-field]')) record(e.target.dataset.field, e.target.value); });
function setField(field, value){
  const input = $('#f-' + field + '-' + value);
  if (!input) return;
  input.checked = true;
  record(field, value);
  showDef(input);
}

// ------------------------------------------------------------ navigator and progress
const navRefs = {};
function buildNav(){
  const list = $('#nav-list');
  DATA.issues.forEach(issue => {
    const li = el('li', 'nav-issue');
    const head = btn('');
    head.append(el('span', 'caret', '\u25B8'), el('span', '', 'Issue ' + issue.number), el('span', 'tally', ''));
    head.addEventListener('click', () => { ui.open[issue.cluster_id] = !li.classList.contains('open'); saveUI(); refresh(); });
    const ol = el('ol');
    const items = issue.variants.map(v => {
      const b = btn('nav-item');
      const dot = el('span', 'dot');
      b.append(dot, el('b', '', 'Criticism ' + v.label), el('span', 'snip', v.claim));
      b.addEventListener('click', () => { go(BY_ID[v.id].idx); closeCompare(); if (narrow()) setNav(false); });
      const item = el('li'); item.append(b); ol.append(item);
      return {id: v.id, b, dot};
    });
    let group = null;
    if (issue.variants.length > 1) {
      const b = btn('nav-group'), dot = el('span', 'dot');
      b.append(dot, el('span', '', 'Same issue?'));
      b.addEventListener('click', () => { go(BY_ID[issue.variants[0].id].idx); openCompare(); if (narrow()) setNav(false); });
      const item = el('li'); item.append(b); ol.append(item);
      group = {b, dot};
    }
    li.append(head, ol);
    list.append(li);
    navRefs[issue.cluster_id] = {li, head, items, group};
  });
}
function refresh(){
  let doneV = 0, doneC = 0;
  DATA.issues.forEach(issue => {
    const ref = navRefs[issue.cluster_id];
    let complete = 0;
    ref.items.forEach(it => {
      const n = answered(it.id), full = n === FIELDS.length;
      it.dot.className = 'dot' + (full ? ' full' : n ? ' part' : '');
      it.b.classList.toggle('is-done', full);
      it.b.setAttribute('aria-current', current && current.v.id === it.id ? 'true' : 'false');
      it.b.setAttribute('aria-label', 'Criticism ' + BY_ID[it.id].v.label + (full ? ', labelled' : n ? ', ' + n + ' of 4 answered' : ', not labelled'));
      if (full) { complete++; doneV++; }
    });
    let groupOk = true;
    if (ref.group) {
      groupOk = groupDone(issue.cluster_id);
      if (groupOk) doneC++;
      ref.group.dot.className = 'dot' + (groupOk ? ' full' : '');
      ref.group.b.classList.toggle('is-done', groupOk);
    }
    const all = complete === ref.items.length && groupOk;
    ref.li.classList.toggle('complete', all);
    const open = !!ui.open[issue.cluster_id];
    ref.li.classList.toggle('open', open);
    ref.head.setAttribute('aria-expanded', open ? 'true' : 'false');
    ref.head.querySelector('.tally').textContent = all ? 'done' : complete + ' / ' + ref.items.length;
  });
  const nv = ORDER.length, nc = MULTI.length;
  $('#progress-text').textContent = doneV + ' of ' + nv + ' criticisms' + (nc ? ', ' + doneC + ' of ' + nc + ' groupings' : '');
  $('#fill').style.width = ((doneV + doneC) / Math.max(1, nv + nc) * 100) + '%';
  $('#nav-list').classList.toggle('filtered', $('#filter').checked);
  const cur = current && navRefs[current.issue.cluster_id].items.find(it => it.id === current.v.id);
  if (cur) ensureVisible($('#nav-list'), cur.b);
}
function ensureVisible(box, node){
  const b = box.getBoundingClientRect(), r = node.getBoundingClientRect();
  if (!r.height) return;
  if (r.top < b.top) box.scrollTop -= b.top - r.top + 8;
  else if (r.bottom > b.bottom) box.scrollTop += r.bottom - b.bottom + 8;
}
$('#filter').addEventListener('change', () => { ui.filter = $('#filter').checked; saveUI(); refresh(); });
$('#expand-all').addEventListener('click', () => { DATA.issues.forEach(i => { ui.open[i.cluster_id] = true; }); saveUI(); refresh(); });
$('#collapse-all').addEventListener('click', () => { ui.open = {}; if (current) ui.open[current.issue.cluster_id] = true; saveUI(); refresh(); });

function tasks(){
  const out = [];
  DATA.issues.forEach(issue => {
    issue.variants.forEach(v => out.push({kind: 'v', id: v.id, issue}));
    if (issue.variants.length > 1) out.push({kind: 'c', id: issue.cluster_id, issue});
  });
  return out;
}
function nextUnlabelled(){
  const list = tasks();
  const compareOpen = !$('#compare').hidden;
  let start = list.findIndex(t => compareOpen ? (t.kind === 'c' && t.id === current.issue.cluster_id) : (t.kind === 'v' && t.id === current.v.id));
  for (let step = 1; step <= list.length; step++) {
    const t = list[(start + step) % list.length];
    if (t.kind === 'v' && !variantDone(t.id)) { closeCompare(); go(BY_ID[t.id].idx, {focus: true}); return; }
    if (t.kind === 'c' && !groupDone(t.id)) {
      if (current.issue !== t.issue) go(BY_ID[t.issue.variants[0].id].idx);
      openCompare(); return;
    }
  }
  updateStatus('Everything is labelled. Export your labels to send them back.');
}
$('#next').addEventListener('click', nextUnlabelled);
$('#prev').addEventListener('click', () => go(current.idx - 1));
$('#forward').addEventListener('click', () => go(current.idx + 1));

// ------------------------------------------------------------ compare view
function renderCompare(){
  const issue = current.issue;
  $('#compare-title').textContent = 'Issue ' + issue.number + ': ' + issue.variants.length + ' criticisms side by side';
  const cols = $('#compare-cols');
  cols.replaceChildren();
  issue.variants.forEach(v => {
    const col = el('section', 'col');
    const head = el('div', 'col-head');
    const n = answered(v.id);
    const dot = el('span', 'dot' + (n === FIELDS.length ? ' full' : n ? ' part' : ''));
    const title = el('h3', '', 'Criticism ' + v.label);
    const open = btn('', 'Label this one');
    open.addEventListener('click', () => { closeCompare(); go(BY_ID[v.id].idx, {focus: true}); });
    const left = el('span'); left.style.display = 'flex'; left.style.gap = '.45rem'; left.style.alignItems = 'center';
    left.append(dot, title);
    head.append(left, open);
    col.append(head, el('p', 'claim', v.claim));
    if (v.rationale) { col.append(el('h4', '', 'Reasoning given'), el('p', '', v.rationale)); }
    col.append(el('h4', '', 'Suggested remedy'), v.remedy ? el('p', '', v.remedy) : el('p', 'muted', 'None stated separately.'));
    if (v.quotes.length) {
      col.append(el('h4', '', 'Quoted from the manuscript'));
      v.quotes.forEach(q => { const b = el('blockquote', '', q.t); if (q.src === null) b.append(el('span', 'muted', ' (not found verbatim)')); col.append(b); });
    }
    if (v.external && v.external.length) {
      col.append(el('h4', '', 'Outside sources cited'));
      const ul = el('ul', 'ext'); v.external.forEach(x => ul.append(el('li', '', x))); col.append(ul);
    }
    cols.append(col);
  });
  applyForm();
}
function openCompare(){
  if (!current || current.issue.variants.length < 2) return;
  renderCompare();
  $('#compare').hidden = false;
  $('#compare-close').focus();
}
function closeCompare(){
  const box = $('#compare');
  if (box.hidden) return;
  box.hidden = true;
  if (box.contains(document.activeElement) || document.activeElement === document.body) $('#crit').focus({preventScroll: true});
}
$('#compare-open').addEventListener('click', openCompare);
$('#compare-close').addEventListener('click', closeCompare);

// ------------------------------------------------------------ export and import
function exportLabels(){
  const t = now();
  const payload = {format: META.labels_format, packet_id: META.packet_id, packet_format: META.format, paper_id: META.paper_id,
    result_sha256: META.result_sha256, seed: META.seed, max_variants: META.max_variants, generated_at: META.generated_at,
    started_at: state.started_at, updated_at: state.updated_at, exported_at: t, sampling: META.sampling,
    variant_ids: META.variant_ids, cluster_ids: META.cluster_ids, labels: {variants: state.variants, clusters: state.clusters}};
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'owner-labels-' + META.packet_id + '.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  ui.exported_at = t; ui.exported_state = state.updated_at || t; saveUI();
  updateStatus();
}
function importLabels(file){
  const reader = new FileReader();
  reader.onload = () => {
    let data;
    try { data = JSON.parse(reader.result); } catch (e) { alert('This file is not JSON. Choose a labels file exported from this workspace or packet.'); return; }
    if (data.format !== META.labels_format || !data.labels) { alert('This file is not a labels export. Choose a file named owner-labels-' + META.packet_id + '.json.'); return; }
    if (data.packet_id !== META.packet_id) { alert('These labels belong to packet ' + data.packet_id + ', not ' + META.packet_id + '. Nothing was imported.'); return; }
    const has = Object.keys(state.variants).length + Object.keys(state.clusters).length;
    if (has && !confirm('Replace the labels saved in this browser with the imported file?')) return;
    state = {started_at: data.started_at || null, updated_at: data.updated_at || null,
             variants: data.labels.variants || {}, clusters: data.labels.clusters || {}};
    ui.exported_at = data.exported_at || now(); ui.exported_state = state.updated_at || ui.exported_at; saveUI();
    save(); applyForm(); refresh();
    updateStatus('Imported labels from ' + file.name);
  };
  reader.readAsText(file);
}
$('#export').addEventListener('click', exportLabels);
$('#import').addEventListener('click', () => $('#import-file').click());
$('#import-file').addEventListener('change', e => { if (e.target.files[0]) importLabels(e.target.files[0]); e.target.value = ''; });
window.addEventListener('beforeunload', e => { if (unexported()) { e.preventDefault(); e.returnValue = ''; } });

// ------------------------------------------------------------ chrome: navigator, theme, help
function narrow(){ return window.matchMedia('(max-width: 1180px)').matches; }
function setNav(show){
  $('#work').classList.toggle('nav-hidden', !show);
  $('#nav-toggle').setAttribute('aria-expanded', show ? 'true' : 'false');
  if (!narrow()) { ui.nav_hidden = !show; saveUI(); }
}
$('#nav-toggle').addEventListener('click', () => setNav($('#work').classList.contains('nav-hidden')));
const THEMES = ['auto', 'light', 'dark'];
function applyTheme(){
  const theme = THEMES.includes(ui.theme) ? ui.theme : 'auto';
  if (theme === 'auto') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = theme;
  $('#theme-label').textContent = 'Theme: ' + theme;
  $('#theme').title = 'Colour scheme: ' + (theme === 'auto' ? 'follows your system' : theme) + '. Click to change.';
}
$('#theme').addEventListener('click', () => { ui.theme = THEMES[(THEMES.indexOf(ui.theme || 'auto') + 1) % THEMES.length]; saveUI(); applyTheme(); });
const help = $('#help');
function toggleHelp(){ if (help.open) help.close(); else help.showModal(); }
$('#help-open').addEventListener('click', toggleHelp);
$('#help-close').addEventListener('click', () => help.close());

document.addEventListener('keydown', e => {
  const t = e.target;
  const typing = t && t.matches && t.matches('textarea, input[type=search], input[type=text]');
  if (e.key === 'Escape') {
    if (help.open) return;
    if (typing) { t.blur(); e.preventDefault(); return; }
    if (!$('#compare').hidden) { closeCompare(); e.preventDefault(); return; }
    if (narrow() && !$('#work').classList.contains('nav-hidden')) setNav(false);
    return;
  }
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === '?') { e.preventDefault(); toggleHelp(); return; }
  if (help.open || e.shiftKey) return;
  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  if (KEYMAP[key] && $('#compare').hidden) { e.preventDefault(); setField(KEYMAP[key][0], KEYMAP[key][1]); return; }
  if (key === 'j') { e.preventDefault(); go(current.idx + 1); }
  else if (key === 'k') { e.preventDefault(); go(current.idx - 1); }
  else if (key === 'n') { e.preventDefault(); nextUnlabelled(); }
  else if (key === '/') { e.preventDefault(); searchInput.focus(); searchInput.select(); }
});

// ------------------------------------------------------------ start
applyTheme();
buildDoc();
buildNav();
$('#filter').checked = !!ui.filter;
if (narrow()) setNav(false); else setNav(!ui.nav_hidden);
window.matchMedia('(max-width: 1180px)').addEventListener('change', e => setNav(e.matches ? false : !ui.nav_hidden));
const start = ui.pos && BY_ID[ui.pos] ? BY_ID[ui.pos].idx : 0;
go(start);
updateStatus(canStore && state.updated_at ? 'Restored your saved labels' : undefined);
setTimeout(updateStatus, 4000);
if (!ui.seen_help) { ui.seen_help = true; saveUI(); help.showModal(); }
})();
"""

if __name__ == "__main__":
    sys.exit(main())
