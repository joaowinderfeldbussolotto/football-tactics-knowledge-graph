"""Detecção de comunidades e leitura de seus resumos (seção 6.4/7 do plano).

A detecção de comunidades só faz sentido depois que a partida foi ingerida
por completo (o endpoint `GET /report/{match_id}` dispara isso sob demanda,
nunca durante o replay incremental).
"""

from __future__ import annotations

from graphiti_core import Graphiti
from graphiti_core.nodes import CommunityNode

from football_graphrag.graph.client import group_id_for_match


async def build_match_communities(graphiti: Graphiti, match_id: str) -> list[CommunityNode]:
    """Roda a detecção de comunidades restrita ao `group_id` da partida e
    devolve os nós de comunidade (já com `summary` preenchido pelo Graphiti)."""
    community_nodes, _community_edges = await graphiti.build_communities(group_ids=[group_id_for_match(match_id)])
    return community_nodes


async def get_match_communities(graphiti: Graphiti, match_id: str) -> list[CommunityNode]:
    """Lê as comunidades já detectadas para a partida, sem recalcular."""
    return await CommunityNode.get_by_group_ids(graphiti.driver, [group_id_for_match(match_id)])
