"""Write passages for each entry in compact text form to a file."""
import json, sys, re
from pathlib import Path

ROOT = Path(__file__).parent.parent
P    = ROOT / "data" / "evaluation" / "_gt_passages.json"
data = json.loads(P.read_text(encoding="utf-8"))

START   = int(sys.argv[1]) if len(sys.argv) > 1 else 0
END     = int(sys.argv[2]) if len(sys.argv) > 2 else 999
OUTFILE = ROOT / "data" / "evaluation" / f"_passages_{START}_{END}.txt"

def clean(s):
    # Replace non-printable / problematic chars with ASCII equivalents
    s = s.replace('‑', '-').replace('’', "'").replace('‘', "'")
    s = s.replace('“', '"').replace('”', '"').replace('–', '--')
    s = s.replace('—', '--').replace('â', "'")
    s = re.sub(r'[^\x00-\x7F]', '?', s)
    return s

lines = []
entries = list(data.items())[START:END]
for eid, r in entries:
    lines.append(f"\n{'='*70}")
    lines.append(f"ENTRY: {eid}")
    if "error" in r:
        lines.append(f"  ERROR: {r['error']}")
        continue
    lines.append(f"  file={r['file']}  section={r['section']}  len={r['section_length']}")
    lines.append(f"  found_kws: {r['found_keywords']}")
    lines.append(f"  missing_kws: {r['missing_keywords']}")
    for i, p in enumerate(r['passages'], 1):
        lines.append(f"  --- passage {i} [kw: {p['keyword']}] ---")
        lines.append(f"  {clean(p['text'][:900])}")

OUTFILE.write_text("\n".join(lines), encoding="utf-8")
print(f"Written to {OUTFILE}")
