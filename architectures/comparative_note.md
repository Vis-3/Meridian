# Comparative Retrieval: Identified Failure Mode and Design Decision

## The Problem

Standard hybrid retrieval (dense + sparse + RRF fusion) fails on comparative queries
that ask about the same metric across multiple companies simultaneously. The failure mode
is **score compression**: all chunk RRF scores cluster near 0.015–0.016, meaning the
difference between a directly relevant Microsoft chunk and a less relevant Google chunk
is smaller than the noise introduced by embedding similarity variance. In practice, one
or two companies with filing language closer to the query phrasing (e.g. Google's 10-K
uses "research and development" verbatim in prominent headings) crowd out companies
whose filings phrase the same concept differently.

This was observed empirically during retrieval auditing: a query for "R&D research
development expense 2023" retrieved chunks from Apple, Google, Amazon, and Meta in the
top-10, but zero Microsoft chunks — despite 58 Microsoft FY2023 chunks containing
"research and development" existing in the index. The chunks existed; the ranking
suppressed them.

## The Fix

For comparative queries, retrieval runs **per-company independently** via
`hybrid.search_balanced()`. Each company gets its own top-k hybrid search with the
company filter locked, and the results are merged. This guarantees representation from
every requested company regardless of relative embedding distance, at the cost of
slightly reduced intra-company diversity (top-3 per company instead of global top-15).

## Architectural Implications

Query expansion (synonym substitution for SEC terminology) and balanced retrieval are
two separate retrieval-layer interventions that address different failure modes:

- **Synonym expansion** fixes vocabulary mismatch between natural language queries and
  SEC filing language (e.g. "revenue" vs. Apple's "net sales"). It operates at the
  query level before any retrieval runs.

- **Balanced retrieval** fixes score compression on multi-company queries. It operates
  at the result-set level by restructuring *how* retrieval is invoked rather than what
  it searches for.

Architectures that generate comparative or multi-hop questions (Phase 6) should route
through `search_balanced` when the question involves more than one company. Single-company
factual and risk questions continue to use standard `hybrid.search`.
