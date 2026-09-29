"""football_graphrag: grafo tático de futebol com insights não triviais.

Arquitetura em três camadas (ver docs/05-decisoes.md e README):
- Camada 0 (ingestion/): pipeline determinística StatsBomb -> SPADL -> métricas -> Parquet.
- Camada 1 (graph/build.py): grafo factual determinístico, sem LLM.
- Camada 2 (graph/analysis.py): insights via algoritmos de grafo (Neo4j GDS).
- Camada 3 (api/): interpretação e recuperação via Graphiti + PydanticAI.
"""

__version__ = "0.1.0"
