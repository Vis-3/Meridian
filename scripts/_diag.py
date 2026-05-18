"""Diagnostic script — run once, then delete."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from config import QDRANT_URL

client = QdrantClient(url=QDRANT_URL, prefer_grpc=False)
COLLECTION = "meridian_fixed"

def scroll_chunks(company, year, section_kw, n=10):
    from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
    filt = Filter(must=[
        FieldCondition(key="company",     match=MatchValue(value=company)),
        FieldCondition(key="fiscal_year", match=MatchValue(value=year)),
    ])
    results, _ = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=filt,
        limit=200,
        with_payload=True,
        with_vectors=False,
    )
    hits = [r for r in results
            if section_kw.lower() in r.payload.get("section", "").lower()]
    return hits[:n]

# ---- Test 1 diagnostic: Apple FY2023 ----
print("\n=== Apple FY2023 Item 8 — scroll (bypass ranking) ===")
hits = scroll_chunks("Apple", 2023, "Item 8", n=10)
print(f"Found {len(hits)} Item 8 chunks")
found_383 = found_391 = False
for h in hits:
    text = h.payload.get("text", "")
    has_383 = "383" in text
    has_391 = "391" in text
    if has_383 or has_391:
        found_383 |= has_383
        found_391 |= has_391
        print(f"  [HIT] chunk_id={h.payload.get('chunk_id','?')}")
        print(f"        {text[:200]}\n")
if not found_383 and not found_391:
    print("  Neither '383' nor '391' found in any Item 8 chunk — CHUNKING PROBLEM")
    print("\n  First 5 Item 8 chunks (200 chars each):")
    for h in hits[:5]:
        print(f"  chunk_id={h.payload.get('chunk_id','?')}")
        print(f"  {h.payload.get('text','')[:200]}\n")

print("\n=== Apple FY2023 Item 7 — scroll (bypass ranking) ===")
hits7 = scroll_chunks("Apple", 2023, "Item 7", n=20)
print(f"Found {len(hits7)} Item 7 chunks")
for h in hits7:
    text = h.payload.get("text", "")
    if "383" in text or "391" in text:
        print(f"  [HIT 383/391] {text[:200]}\n")

# Check ALL sections for 383/391
print("\n=== Apple FY2023 ALL sections — any chunk with 383 or 391 ===")
all_apple, _ = client.scroll(
    collection_name=COLLECTION,
    scroll_filter=__import__("qdrant_client.models", fromlist=["Filter"]).Filter(must=[
        __import__("qdrant_client.models", fromlist=["FieldCondition"]).FieldCondition(
            key="company", match=__import__("qdrant_client.models", fromlist=["MatchValue"]).MatchValue(value="Apple")),
        __import__("qdrant_client.models", fromlist=["FieldCondition"]).FieldCondition(
            key="fiscal_year", match=__import__("qdrant_client.models", fromlist=["MatchValue"]).MatchValue(value=2023)),
    ]),
    limit=500,
    with_payload=True,
    with_vectors=False,
)
revenue_hits = []
for r in all_apple:
    text = r.payload.get("text", "")
    if "383" in text or "391" in text:
        revenue_hits.append(r)
print(f"Chunks containing '383' or '391': {len(revenue_hits)}")
for r in revenue_hits[:5]:
    print(f"  section={r.payload.get('section')}  chunk_id={r.payload.get('chunk_id','?')}")
    print(f"  {r.payload.get('text','')[:200]}\n")

# ---- Test 3 diagnostic: Microsoft FY2023 R&D ----
print("\n=== Microsoft FY2023 Item 7 — scroll ===")
ms_hits = scroll_chunks("Microsoft", 2023, "Item 7", n=10)
print(f"Found {len(ms_hits)} Item 7 chunks")
for h in ms_hits[:5]:
    text = h.payload.get("text", "")
    has_rd = any(kw in text.lower() for kw in ["research and development", "r&d"])
    print(f"  has_R&D={has_rd}  chunk_id={h.payload.get('chunk_id','?')}")
    print(f"  {text[:200]}\n")

# Check all MS FY2023 sections for R&D
print("\n=== Microsoft FY2023 ALL sections — any chunk with R&D ===")
all_ms, _ = client.scroll(
    collection_name=COLLECTION,
    scroll_filter=__import__("qdrant_client.models", fromlist=["Filter"]).Filter(must=[
        __import__("qdrant_client.models", fromlist=["FieldCondition"]).FieldCondition(
            key="company", match=__import__("qdrant_client.models", fromlist=["MatchValue"]).MatchValue(value="Microsoft")),
        __import__("qdrant_client.models", fromlist=["FieldCondition"]).FieldCondition(
            key="fiscal_year", match=__import__("qdrant_client.models", fromlist=["MatchValue"]).MatchValue(value=2023)),
    ]),
    limit=500,
    with_payload=True,
    with_vectors=False,
)
rd_hits = [r for r in all_ms
           if any(kw in r.payload.get("text","").lower()
                  for kw in ["research and development", "r&d"])]
print(f"Chunks with R&D keywords: {len(rd_hits)}")
for r in rd_hits[:5]:
    print(f"  section={r.payload.get('section')}  chunk_id={r.payload.get('chunk_id','?')}")
    print(f"  {r.payload.get('text','')[:200]}\n")

# Also run "net sales" query to see if it outperforms "revenue"
print("\n=== Query comparison: 'revenue' vs 'net sales' for Apple FY2023 ===")
import torch
from sentence_transformers import SentenceTransformer
from qdrant_client.models import Filter, FieldCondition, MatchValue

model = SentenceTransformer("BAAI/bge-large-en-v1.5", device="cuda" if torch.cuda.is_available() else "cpu")
model.max_seq_length = 512

apple_filt = Filter(must=[
    FieldCondition(key="company",     match=MatchValue(value="Apple")),
    FieldCondition(key="fiscal_year", match=MatchValue(value=2023)),
])

for q_label, q in [("revenue query", "Apple total revenue fiscal year 2023"),
                   ("net sales query", "Apple total net sales fiscal year 2023")]:
    vec = model.encode(q, normalize_embeddings=True).tolist()
    resp = client.query_points(
        collection_name=COLLECTION,
        query=vec,
        limit=3,
        query_filter=apple_filt,
        with_payload=True,
    )
    print(f"\n  [{q_label}] top-3:")
    for hit in resp.points:
        text = hit.payload.get("text", "")
        has_num = "383" in text or "391" in text
        print(f"    score={hit.score:.4f}  section={hit.payload.get('section')}  has_383/391={has_num}")
        print(f"    {text[:150]}")
