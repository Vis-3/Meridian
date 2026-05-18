"""
Meridian — Neo4j graph loader.

Run once to populate the knowledge graph:
    python graph/loader.py

Schema:
  (:Company {name})
  (:Document {id, company, fiscal_year, document_type, quarter, path})
  (:Section  {id, name, company, fiscal_year, document_type})
  (:Topic    {name})

Relationships:
  (:Company)-[:FILED]->(:Document)
  (:Document)-[:HAS_SECTION]->(:Section)
  (:Section)-[:MENTIONS]->(:Topic)
  (:Document)-[:NEXT_PERIOD]->(:Document)   # temporal chain per company
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PROCESSED_DIR, KEY_TOPICS, NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD

try:
    from neo4j import GraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False


def get_driver():
    if not _NEO4J_AVAILABLE:
        raise RuntimeError("neo4j driver not installed: pip install neo4j")
    return GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _topic_matches(text: str) -> list[str]:
    t = text.lower()
    return [topic for topic in KEY_TOPICS if topic in t]


def load(driver) -> None:
    docs = sorted(PROCESSED_DIR.glob("*.json"))
    print(f"Loading {len(docs)} documents into Neo4j...")

    with driver.session() as sess:
        # Constraints
        sess.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company)  REQUIRE c.name IS UNIQUE")
        sess.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE")
        sess.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Section)  REQUIRE s.id IS UNIQUE")
        sess.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic)    REQUIRE t.name IS UNIQUE")

        # Track documents per company (for NEXT_PERIOD edges)
        company_docs: dict[str, list[dict]] = {}

        for i, doc_path in enumerate(docs, 1):
            doc      = json.loads(doc_path.read_text(encoding="utf-8"))
            meta     = doc.get("metadata", {})
            company  = doc.get("company",       meta.get("company", ""))
            year     = doc.get("fiscal_year",   meta.get("fiscal_year"))
            dtype    = doc.get("document_type", meta.get("document_type", ""))
            quarter  = doc.get("quarter",       meta.get("quarter")) or ""
            doc_id   = doc_path.stem

            # Company node
            sess.run(
                "MERGE (c:Company {name: $name})",
                name=company,
            )

            # Document node
            sess.run(
                """
                MERGE (d:Document {id: $id})
                SET d.company=$company, d.fiscal_year=$year,
                    d.document_type=$dtype, d.quarter=$quarter, d.path=$path
                """,
                id=doc_id, company=company, year=year,
                dtype=dtype, quarter=quarter, path=str(doc_path),
            )

            # Company → Document
            sess.run(
                """
                MATCH (c:Company {name:$company}), (d:Document {id:$doc_id})
                MERGE (c)-[:FILED]->(d)
                """,
                company=company, doc_id=doc_id,
            )

            # Sections + Topics
            for sec_name, sec_content in doc.get("sections", {}).items():
                text   = sec_content.get("text", "")
                sec_id = f"{doc_id}_{sec_name.replace(' ', '_')}"

                sess.run(
                    """
                    MERGE (s:Section {id: $sid})
                    SET s.name=$name, s.company=$company,
                        s.fiscal_year=$year, s.document_type=$dtype
                    """,
                    sid=sec_id, name=sec_name,
                    company=company, year=year, dtype=dtype,
                )
                sess.run(
                    """
                    MATCH (d:Document {id:$doc_id}), (s:Section {id:$sid})
                    MERGE (d)-[:HAS_SECTION]->(s)
                    """,
                    doc_id=doc_id, sid=sec_id,
                )

                for topic in _topic_matches(text):
                    sess.run("MERGE (t:Topic {name:$name})", name=topic)
                    sess.run(
                        """
                        MATCH (s:Section {id:$sid}), (t:Topic {name:$topic})
                        MERGE (s)-[:MENTIONS]->(t)
                        """,
                        sid=sec_id, topic=topic,
                    )

            # Collect for temporal chaining
            company_docs.setdefault(company, []).append(
                {"id": doc_id, "year": year, "quarter": quarter, "dtype": dtype}
            )

            if i % 10 == 0 or i == len(docs):
                print(f"  Loaded {i}/{len(docs)}")

        # NEXT_PERIOD edges: sort each company's annual 10-Ks by year
        print("Creating NEXT_PERIOD edges...")
        for company, doc_list in company_docs.items():
            annuals = sorted(
                [d for d in doc_list if d["dtype"] == "10-K"],
                key=lambda x: x["year"],
            )
            for prev, nxt in zip(annuals, annuals[1:]):
                sess.run(
                    """
                    MATCH (a:Document {id:$a}), (b:Document {id:$b})
                    MERGE (a)-[:NEXT_PERIOD]->(b)
                    """,
                    a=prev["id"], b=nxt["id"],
                )

    print("Graph loading complete.")


if __name__ == "__main__":
    if not _NEO4J_AVAILABLE:
        print("neo4j package not installed. Run: pip install neo4j")
        sys.exit(1)
    driver = get_driver()
    try:
        load(driver)
    finally:
        driver.close()
