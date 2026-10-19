"""
Step 3 of the pipeline: quick human review in your browser.

    python src/review.py                    # builds data/review/<style>.html for every style
    python src/review.py --style mangalagiri

Open the HTML file. Each candidate shows its source, trust tier, license and
any quality flags, with that style's visual-marker checklist from cards/ on the
side. Click an image to reject it (click again to undo). For Wikimedia images,
choose artifact or craft. Then press "Export decisions"; it saves
review_<style>.json to your Downloads.

    python src/review.py --apply ~/Downloads/review_mangalagiri.json

Kept images move to data/images/<style>/ (ready for training);
rejected ones move to data/rejected/<style>/.
"""

import argparse
import html
import json
import os
from pathlib import Path

from common import CARDS, DATA, STYLES, image_path, load_metadata, move, save_metadata

REVIEW = DATA / "review"


def visual_markers(style):
    card = CARDS / f"{style}.md"
    if not card.exists():
        return []
    out, inside = [], False
    for line in card.read_text(encoding="utf-8").splitlines():
        if line.startswith("- **Visual markers:**"):
            inside = True
            continue
        if inside:
            if line.startswith("  - "):
                out.append(line[4:].strip())
            else:
                break
    return out


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Review {style}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#f6f4ef;color:#222}}
header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:10px 16px;
display:flex;gap:16px;align-items:center;flex-wrap:wrap;z-index:2}}
button{{font-size:15px;padding:8px 14px;border-radius:6px;border:1px solid #888;background:#fff;cursor:pointer}}
button.primary{{background:#8a3b12;color:#fff;border-color:#8a3b12}}
.wrap{{display:flex;gap:16px;padding:16px}}
aside{{flex:0 0 260px;position:sticky;top:70px;align-self:flex-start;background:#fff;padding:12px;
border-radius:8px;border:1px solid #ddd;font-size:14px}}
.grid{{flex:1;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
.card{{background:#fff;border:3px solid #3a7d44;border-radius:8px;overflow:hidden;font-size:12px}}
.card.reject{{border-color:#b3261e;opacity:.45}}
.card img{{width:100%;height:220px;object-fit:cover;cursor:pointer;display:block;background:#eee}}
.meta{{padding:6px 8px;line-height:1.4}}
.flag{{display:inline-block;background:#fde7c7;color:#7a4300;border-radius:4px;padding:1px 5px;margin:2px 2px 0 0}}
.tier{{font-weight:700}}
@media (max-width:700px){{.wrap{{flex-direction:column}} aside{{position:static;flex:auto}}}}
</style></head><body>
<header><strong>{title} — {n} candidates</strong>
<span id="count"></span>
<button class="primary" onclick="exportJson()">Export decisions</button>
<span style="font-size:13px">Click an image to reject / undo.</span></header>
<div class="wrap"><aside><strong>Check for these markers</strong><ul>{markers}</ul>
<p><strong>Reject if:</strong> wrong style, machine print or imitation, mostly not the textile,
same piece already kept, or you are not sure.</p>
<p><strong>Tiers:</strong> A verified piece · B museum record · C open web</p></aside>
<div class="grid">{cards}</div></div>
<script>
const STYLE={style_json};
const KEY="vv_review_"+STYLE;
let state={{}};
try{{state=JSON.parse(localStorage.getItem(KEY)||"{{}}")}}catch(e){{state={{}}}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(state))}}catch(e){{}};count()}}
function count(){{const all=document.querySelectorAll('.card').length;
const rej=Object.values(state).filter(s=>s.decision==='reject').length;
document.getElementById('count').textContent=(all-rej)+' keep · '+rej+' reject'}}
document.querySelectorAll('.card').forEach(c=>{{
  const f=c.dataset.file; state[f]=state[f]||{{decision:'keep'}};
  if(state[f].decision==='reject')c.classList.add('reject');
  const sel=c.querySelector('select'); if(sel){{ if(state[f].type)sel.value=state[f].type;
    sel.onchange=()=>{{state[f].type=sel.value;save()}} }}
  c.querySelector('img').onclick=()=>{{
    state[f].decision=state[f].decision==='reject'?'keep':'reject';
    c.classList.toggle('reject');save()}};
}});
save();
function exportJson(){{
  const b=new Blob([JSON.stringify({{style:STYLE,decisions:state}},null,1)],{{type:'application/json'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);
  a.download='review_'+STYLE+'.json';a.click()}}
</script></body></html>"""


def card_html(r):
    rel = os.path.relpath(image_path(r), REVIEW).replace(os.sep, "/")
    flags = "".join(f'<span class="flag">{html.escape(f)}</span>'
                    for f in r["quality_flags"].split(";") if f)
    type_ctl = ""
    if r["type"] == "to_check":
        type_ctl = ('<br>type: <select><option value="">choose…</option>'
                    '<option value="artifact">artifact (old object)</option>'
                    '<option value="craft">craft (made today)</option></select>')
    link = (f'<a href="{html.escape(r["source_url"])}" target="_blank">source</a>'
            if r["source_url"].startswith("http") else html.escape(r["source_url"]))
    return (f'<div class="card" data-file="{html.escape(r["file_name"])}">'
            f'<img loading="lazy" src="{html.escape(rel)}" alt="">'
            f'<div class="meta"><span class="tier">Tier {html.escape(r["trust_tier"] or "?")}</span> · '
            f'{html.escape(r["source"])} · {link}<br>{html.escape(r["license"])}<br>'
            f'{html.escape(r["notes"][:120])}<br>{flags}{type_ctl}</div></div>')


def build(styles):
    rows = load_metadata()
    REVIEW.mkdir(parents=True, exist_ok=True)
    for style in styles:
        cands = [r for r in rows if r["status"] == "candidate" and r["style"] == style
                 and image_path(r).exists()]
        if not cands:
            print(f"{style}: no candidates")
            continue
        cands.sort(key=lambda r: (r["quality_flags"] == "", r["trust_tier"]))  # flagged first
        markers = "".join(f"<li>{html.escape(m)}</li>" for m in visual_markers(style))
        page = PAGE.format(style=style, style_json=json.dumps(style),
                           title=style.replace("_", " ").title(), n=len(cands),
                           markers=markers, cards="".join(card_html(r) for r in cands))
        out = REVIEW / f"{style}.html"
        out.write_text(page, encoding="utf-8")
        print(f"{style}: {len(cands)} candidates  ->  {out}")


def apply(json_path):
    data = json.loads(Path(json_path).expanduser().read_text(encoding="utf-8"))
    style, decisions = data["style"], data["decisions"]
    rows = load_metadata()
    kept = rejected = 0
    for r in rows:
        if r["style"] != style or r["status"] != "candidate" or r["file_name"] not in decisions:
            continue
        d = decisions[r["file_name"]]
        if d.get("type") and r["type"] == "to_check":
            r["type"] = d["type"]
        if d.get("decision") == "reject":
            move(r, "rejected"); rejected += 1
        else:
            move(r, "accepted"); kept += 1
    save_metadata(rows)
    total = sum(1 for r in rows if r["style"] == style and r["status"] == "accepted")
    print(f"{style}: kept {kept}, rejected {rejected}. Training images for {style}: {total}")
    left = [r["file_name"] for r in rows if r["style"] == style and r["type"] == "to_check"
            and r["status"] == "accepted"]
    if left:
        print(f"  note: {len(left)} kept images still have type=to_check; set them in metadata.csv")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Review candidate images in the browser.")
    p.add_argument("--style", choices=STYLES)
    p.add_argument("--apply", metavar="JSON", help="apply an exported review_<style>.json")
    a = p.parse_args()
    if a.apply:
        apply(a.apply)
    else:
        build([a.style] if a.style else STYLES)
