import re, html, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from refs import REFS

body = open(HERE / "body.html").read()
order = []

def number(key):
    if key not in REFS:
        raise SystemExit(f"unknown ref {key}")
    if key not in order:
        order.append(key)
    return order.index(key) + 1

def repl(m):
    keys = [k.strip().lstrip("@") for k in m.group(1).split(",")]
    nums = sorted({number(k) for k in keys})
    links = ", ".join(f'<a href="#ref-{n}">{n}</a>' for n in nums)
    return f"[{links}]"

body = re.sub(r"\[(@[^\]]+)\]", repl, body)
unused = [k for k in REFS if k not in order]
if unused:
    print("unused refs:", unused, file=sys.stderr)

items = []
for i, k in enumerate(order, 1):
    text, url = REFS[k]
    items.append(f'<li id="ref-{i}"><span class="refnum">{i}.</span> {html.escape(text)} <a href="{url}">{html.escape(url)}</a></li>')
refs_html = '<section id="refs"><h2>12. References</h2><ol class="refs">' + "\n".join(items) + "</ol></section>"

css = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#5d5b55;--rule:#dcd8cf;--accent:#7a3b1d;--panel:#f2efe8;--link:#1f4e79}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#e8e6e1;--muted:#a19e96;--rule:#3a3833;--accent:#e0a37a;--panel:#211f1c;--link:#8cb8e6}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.62 Charter,"Bitstream Charter","Sitka Text",Cambria,Georgia,serif}
main{max-width:46rem;margin:0 auto;padding:3rem 1.4rem 5rem}
.masthead{border-bottom:2px solid var(--fg);padding-bottom:1.2rem;margin-bottom:1.6rem}
.kicker{font:600 .78rem/1.2 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:0 0 .6rem}
h1{font-size:2.2rem;line-height:1.15;margin:0 0 .6rem;font-weight:700}
.dek{font-size:1.12rem;color:var(--muted);margin:0}
h2{font-size:1.45rem;margin:3rem 0 .8rem;padding-top:.6rem;border-top:1px solid var(--rule)}
h3{font:600 1.02rem/1.3 system-ui,sans-serif;margin:1.9rem 0 .5rem}
a{color:var(--link)}
.cite{font-size:.82em;white-space:nowrap}
.cite a{text-decoration:none}
.toc{background:var(--panel);padding:.9rem 1.2rem;border-radius:4px;font:.92rem/1.5 system-ui,sans-serif}
.toc ol{margin:0;padding-left:1.3rem;columns:2;column-gap:2rem}
.callout{background:var(--panel);border-left:4px solid var(--accent);padding:1rem 1.3rem;margin:1.4rem 0}
.callout-title{font:600 .8rem/1 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.07em;color:var(--accent);margin:0 0 .6rem}
.callout ol{margin:0;padding-left:1.2rem}.callout li{margin:.45rem 0}
.note{font-size:.95rem;color:var(--muted);border-left:2px solid var(--rule);padding-left:1rem}
table{border-collapse:collapse;width:100%;margin:1rem 0;font:.86rem/1.45 system-ui,sans-serif}
th,td{text-align:left;vertical-align:top;padding:.5rem .55rem;border-bottom:1px solid var(--rule)}
th{font-weight:600;border-bottom:2px solid var(--fg)}
table.compact{font-size:.8rem}
.table-wrap{overflow-x:auto;margin:0 -1rem;padding:0 1rem}
@media (min-width:1100px){.table-wrap{margin:0 -8rem;padding:0}}
ol.refs{list-style:none;padding:0;font-size:.86rem;line-height:1.5}
ol.refs li{margin:.5rem 0;padding-left:2.2rem;text-indent:-2.2rem}
ol.refs a{word-break:break-all}
.refnum{display:inline-block;width:2.2rem;text-indent:0;color:var(--muted)}
li:target{background:color-mix(in srgb,var(--accent) 18%,transparent)}
@media print{.toc{display:none}body{font-size:11pt}}
"""

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Designing and evaluating an LLM manuscript reviewer</title>
<style>{css}</style></head>
<body><main>
{body}
{refs_html}
</main></body></html>
"""
out = sys.argv[1] if len(sys.argv) > 1 else str(HERE.parent / "llm-reviewer-design-and-evaluation.html")
open(out, "w").write(page)
print(f"wrote {out}: {len(order)} references")
