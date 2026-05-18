import json
from collections import Counter

with open("data/raw/manifest.json") as f:
    manifest = json.load(f)

total   = len(manifest)
success = sum(1 for r in manifest if r["success"])
failed  = [r for r in manifest if not r["success"]]

by_company = Counter(r["company"] for r in manifest if r["success"])
by_type    = Counter(r["document_type"] for r in manifest if r["success"])

print(f"Total:   {total}")
print(f"Success: {success}")
print(f"Failed:  {len(failed)}")
print()
print("By company:", dict(by_company))
print("By type:   ", dict(by_type))

if failed:
    print("\nFailed filings:")
    for r in failed:
        q = r.get("quarter") or ""
        print(f"  {r['company']} FY{r['fiscal_year']} {r['document_type']} {q}")
