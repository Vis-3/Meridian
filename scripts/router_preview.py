from __future__ import annotations
import json, math
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path("data/evaluation/results")
ARCHS = ["graph","naive","hybrid","hierarchical","fusion","agentic","full_system","corrective"]
QTYPES = ["simple_factual","numerical_reasoning","temporal","comparative","multi_hop","risk_qualitative"]

ROUTING = {
    # Winner per type on quality score
    "quality":    {"simple_factual":"hierarchical","numerical_reasoning":"hierarchical","temporal":"fusion","comparative":"graph","multi_hop":"hybrid","risk_qualitative":"naive"},
    # Winner per type on efficiency score (quality / log10(p50+1)) — naive wins all 6 at 66ms
    "efficiency": {"simple_factual":"naive","numerical_reasoning":"naive","temporal":"naive","comparative":"naive","multi_hop":"naive","risk_qualitative":"naive"},
    # Winner per type on cost-quality score — corrective cheapest, wins 5/6 types
    "cost":       {"simple_factual":"corrective","numerical_reasoning":"corrective","temporal":"corrective","comparative":"corrective","multi_hop":"hybrid","risk_qualitative":"corrective"},
    # Winner per type on production score (quality + speed + cost normalised)
    "production": {"simple_factual":"hybrid","numerical_reasoning":"hierarchical","temporal":"graph","comparative":"graph","multi_hop":"hybrid","risk_qualitative":"naive"},
}

QUALITY_WEIGHTS = {"numerical_accuracy":0.35,"faithfulness_proxy":0.30,"citation_coverage":0.20,"keyword_hit_rate":0.15}

def quality_score(metrics):
    total_w, total_v = 0.0, 0.0
    for m, w in QUALITY_WEIGHTS.items():
        v = metrics.get(m)
        if v is not None:
            total_v += w * v; total_w += w
    return total_v / total_w if total_w else None

# Load data
rel = json.loads((RESULTS_DIR / "reliable_metrics.json").read_text(encoding="utf-8"))
arch_data = {}
for arch in ARCHS:
    p = RESULTS_DIR / f"{arch}.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        arch_data[arch] = {r["question_id"]: r for r in data}

# Overall scores per arch for comparison denominators
all_scores = {}
for arch in ARCHS:
    pq = rel["architectures"].get(arch, {}).get("per_question", [])
    if not pq: continue
    qs = [quality_score(q) for q in pq if quality_score(q) is not None]
    ret = sorted([r["latency_breakdown"]["retrieval_ms"] for r in arch_data[arch].values() if r.get("latency_breakdown")])
    costs = [r["estimated_cost_usd"] for r in arch_data[arch].values()]
    all_scores[arch] = {
        "quality":  round(sum(qs)/len(qs), 4),
        "p50_ms":   ret[len(ret)//2],
        "avg_cost": sum(costs)/len(costs),
    }

max_p50     = max(v["p50_ms"]   for v in all_scores.values())
max_cost    = max(v["avg_cost"] for v in all_scores.values())
min_cost    = min(v["avg_cost"] for v in all_scores.values())
max_quality = max(v["quality"]  for v in all_scores.values())

# Compute router scores per mode
router_results = {}
for mode, routing in ROUTING.items():
    per_qtype_metrics = defaultdict(list)
    per_qtype_latency = defaultdict(list)
    per_qtype_cost    = defaultdict(list)

    for arch in ARCHS:
        pq_by_id = {q["question_id"]: q for q in rel["architectures"].get(arch, {}).get("per_question", [])}
        for qtype, routed_arch in routing.items():
            if routed_arch != arch:
                continue
            for qid, qdata in arch_data[arch].items():
                if qdata.get("question_type") != qtype:
                    continue
                qs_val = quality_score(pq_by_id.get(qid, {}))
                if qs_val is not None:
                    per_qtype_metrics[qtype].append(qs_val)
                if qdata.get("latency_breakdown"):
                    per_qtype_latency[qtype].append(qdata["latency_breakdown"]["retrieval_ms"])
                per_qtype_cost[qtype].append(qdata.get("estimated_cost_usd", 0))

    all_q    = [v for vals in per_qtype_metrics.values() for v in vals]
    all_lat  = sorted([v for vals in per_qtype_latency.values() for v in vals])
    all_cost = [v for vals in per_qtype_cost.values() for v in vals]

    overall_quality = round(sum(all_q)/len(all_q), 4) if all_q else None
    eff_p50  = all_lat[len(all_lat)//2] if all_lat else 0
    avg_cost = sum(all_cost)/len(all_cost) if all_cost else 0

    cost_ratio   = avg_cost / min_cost if min_cost > 0 else 1.0
    efficiency   = round(overall_quality / math.log10(eff_p50 + 1), 4) if eff_p50 > 1 else None
    cost_quality = round(overall_quality / cost_ratio, 4)
    spd_norm     = 1 - (eff_p50 / max_p50)
    cost_norm    = 1 - (avg_cost / max_cost)
    production   = round(0.50*(overall_quality/max_quality) + 0.30*spd_norm + 0.20*cost_norm, 4)

    router_results[mode] = {
        "quality":      overall_quality,
        "efficiency":   efficiency,
        "cost_quality": cost_quality,
        "production":   production,
        "p50_ms":       round(eff_p50),
        "avg_cost":     avg_cost,
        "per_type":     {qt: round(sum(v)/len(v),4) if v else None for qt, v in per_qtype_metrics.items()},
    }

sep = "=" * 78

# ── Summary table ──────────────────────────────────────────────────────────
print(f"\n{sep}")
print("  MERIDIAN ROUTER — VIRTUAL SCORES")
print(sep)
print(f"  {'Architecture':<28}  {'Quality':>7}  {'Effic':>7}  {'CostQ':>7}  {'Prod':>7}  {'P50ms':>8}")
print(f"  {'-'*28}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*8}")

# Router rows
MODE_LABELS = {"quality":"MeridianRouter (quality)", "efficiency":"MeridianRouter (effic)", "cost":"MeridianRouter (cost)", "production":"MeridianRouter (prod)"}
for mode in ["quality","efficiency","cost","production"]:
    r = router_results[mode]
    eff = f"{r['efficiency']:.4f}" if r["efficiency"] else "  --  "
    print(f"  {MODE_LABELS[mode]:<28}  {r['quality']:>7.4f}  {eff:>7}  {r['cost_quality']:>7.4f}  {r['production']:>7.4f}  {r['p50_ms']:>8.0f}")

print(f"  {'-'*28}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*8}")

# Best single arch rows for context
for arch in ["naive","graph","hybrid","hierarchical","fusion"]:
    s = all_scores.get(arch, {})
    q = s.get("quality","--")
    p = s.get("p50_ms","--")
    print(f"  {arch:<28}  {q:>7.4f}  {'':>7}  {'':>7}  {'':>7}  {p:>8.0f}")

# ── Per-type breakdown ─────────────────────────────────────────────────────
print(f"\n{sep}")
print("  PER-TYPE QUALITY — Router modes vs best single arch")
print(sep)
print(f"  {'Type':<22}  {'R-Qual':>7}  {'R-Eff':>7}  {'R-Cost':>7}  {'R-Prod':>7}  {'Best-Single':>11}  {'(arch)':>12}")
print(f"  {'-'*22}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*11}  {'-'*12}")

for qtype in QTYPES:
    rq = router_results["quality"]["per_type"].get(qtype)
    re = router_results["efficiency"]["per_type"].get(qtype)
    rc = router_results["cost"]["per_type"].get(qtype)
    rp = router_results["production"]["per_type"].get(qtype)

    type_scores = {}
    for arch in ARCHS:
        pq = rel["architectures"].get(arch,{}).get("per_question",[])
        vals = [quality_score(q) for q in pq if q.get("question_type")==qtype and quality_score(q) is not None]
        if vals:
            type_scores[arch] = sum(vals)/len(vals)
    best_arch = max(type_scores, key=type_scores.get) if type_scores else "--"
    best_val  = type_scores.get(best_arch)

    fmt = lambda v: f"{v:.4f}" if v is not None else "  --  "
    delta = f"({rq-best_val:+.4f})" if rq and best_val else ""
    print(f"  {qtype:<22}  {fmt(rq):>7}  {fmt(re):>7}  {fmt(rc):>7}  {fmt(rp):>7}  {fmt(best_val):>11}  {best_arch:>12}  {delta}")

# ── Routing decisions ──────────────────────────────────────────────────────
print(f"\n{sep}")
print("  ROUTING DECISIONS PER MODE")
print(sep)
print(f"  {'Type':<22}  {'Quality':>14}  {'Efficiency':>12}  {'Cost':>12}  {'Production':>14}")
print(f"  {'-'*22}  {'-'*14}  {'-'*12}  {'-'*12}  {'-'*14}")
for qtype in QTYPES:
    rq = ROUTING["quality"].get(qtype,"--")
    re = ROUTING["efficiency"].get(qtype,"--")
    rc = ROUTING["cost"].get(qtype,"--")
    rp = ROUTING["production"].get(qtype,"--")
    print(f"  {qtype:<22}  {rq:>14}  {re:>12}  {rc:>12}  {rp:>14}")

print(f"\n{sep}\n")
