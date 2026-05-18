"""
Helper: extract keyword-containing passages from processed JSONs for each
qualitative_ground_truths.py entry.

Saves to data/evaluation/_gt_passages.json for the main fill script.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PROCESSED = ROOT / "data" / "processed"
OUT       = ROOT / "data" / "evaluation" / "_gt_passages.json"

sys.path.insert(0, str(ROOT / "data" / "evaluation"))
from qualitative_ground_truths import QUALITATIVE_GROUND_TRUTHS

COMPANY_MAP = {
    "Apple":     "apple",
    "Microsoft": "microsoft",
    "Google":    "google",
    "Amazon":    "amazon",
    "Meta":      "meta",
}

def find_file(company, year):
    stem = f"{COMPANY_MAP[company]}_{year}_10k"
    p = PROCESSED / f"{stem}.json"
    return p if p.exists() else None

def get_section(doc, section_name):
    sections = doc.get("sections", {})
    # Try exact match first
    if section_name in sections:
        return sections[section_name].get("text", "")
    # Try startswith match
    for k, v in sections.items():
        if k.startswith(section_name):
            return v.get("text", "")
    return ""

def extract_passages(text, keywords, window=600):
    """Return up to 8 non-overlapping passages (window chars) around keyword hits."""
    if not text:
        return []
    text_lower = text.lower()
    passages = []
    used_ranges = []

    # Sort keywords by frequency descending so most-present keywords anchor passages
    kw_positions = []
    for kw in keywords:
        pos = 0
        while True:
            idx = text_lower.find(kw.lower(), pos)
            if idx == -1:
                break
            kw_positions.append((idx, kw))
            pos = idx + 1

    kw_positions.sort(key=lambda x: x[0])

    for idx, kw in kw_positions:
        start = max(0, idx - window // 2)
        end   = min(len(text), idx + window // 2)
        # Check overlap with already used ranges
        overlaps = any(not (end <= ur[0] or start >= ur[1]) for ur in used_ranges)
        if not overlaps:
            used_ranges.append((start, end))
            snip = text[start:end].strip()
            # Clean up leading/trailing partial words
            snip = re.sub(r'^\S+\s', '', snip) if start > 0 else snip
            passages.append({"keyword": kw, "text": snip})
        if len(passages) >= 8:
            break

    return passages

results = {}
for entry in QUALITATIVE_GROUND_TRUTHS:
    eid      = entry["id"]
    company  = entry["companies"][0]
    year     = entry["years"][0]
    section  = entry["section"]
    keywords = entry["keywords"]

    p = find_file(company, year)
    if not p:
        results[eid] = {"error": f"File not found: {COMPANY_MAP.get(company, company)}_{year}_10k.json"}
        continue

    doc = json.loads(p.read_text(encoding="utf-8"))
    sec_text = get_section(doc, section)

    if not sec_text:
        results[eid] = {"error": f"Section '{section}' not found in {p.name}"}
        continue

    found_kws = [kw for kw in keywords if kw.lower() in sec_text.lower()]
    passages  = extract_passages(sec_text, keywords)

    results[eid] = {
        "company":       company,
        "year":          year,
        "section":       section,
        "file":          p.name,
        "found_keywords": found_kws,
        "missing_keywords": [kw for kw in keywords if kw not in found_kws],
        "section_length": len(sec_text),
        "passages":      passages,
    }

OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Saved passages for {len(results)} entries to {OUT}")
for eid, r in results.items():
    if "error" in r:
        print(f"  ERROR {eid}: {r['error']}")
    else:
        found = len(r['found_keywords'])
        total = len(QUALITATIVE_GROUND_TRUTHS[0]['keywords'])  # approx
        print(f"  {eid}: {found} kws found, {len(r['passages'])} passages, section={r['section_length']} chars")
