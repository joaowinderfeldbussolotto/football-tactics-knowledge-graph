"""football_graphrag: benchmark of ways to ask natural-language questions about football events.

Layers (explained step by step in docs/02-dos-dados-ao-grafo.md):
- Layer 0 (ingestion/): deterministic pipeline StatsBomb -> SPADL -> metrics -> Parquet.
- Layer 1/1b (graph/build.py, graph/statistics.py): factual graph and per-player/team stats, no LLM.
- Layer 2 (graph/analysis.py): graph-algorithm patterns (Neo4j GDS), used to cross-check the ground truth.
"""

__version__ = "0.1.0"
