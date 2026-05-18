"""
Meridian -- Neo4j graph population verification.

Run: python scripts/verify_graph.py
Prints node counts, relationship counts, and per-company document counts.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

try:
    from neo4j import GraphDatabase
except ImportError:
    print("[ERROR] neo4j package not installed. Run: pip install neo4j")
    sys.exit(1)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

QUERIES = [
    ("Node counts by label",
     "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"),
    ("Relationship counts by type",
     "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC"),
    ("Companies in graph",
     "MATCH (c:Company) RETURN c.name AS company ORDER BY c.name"),
    ("Documents per company",
     "MATCH (c:Company)-[:FILED]->(d:Document) "
     "RETURN c.name AS company, count(d) AS docs ORDER BY c.name"),
    ("Topics in graph",
     "MATCH (t:Topic) RETURN t.name AS topic, count(t) AS count ORDER BY count DESC"),
]

with driver.session() as session:
    for title, cypher in QUERIES:
        print(f"\n--- {title} ---")
        try:
            result = session.run(cypher)
            rows = result.data()
            if not rows:
                print("  (no results)")
            for row in rows:
                print("  ", "  ".join(f"{k}={v}" for k, v in row.items()))
        except Exception as e:
            print(f"  [ERROR] {e}")

driver.close()
print("\nDone.")
