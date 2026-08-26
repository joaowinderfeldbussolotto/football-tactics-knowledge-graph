"""Consulta de referência para cada pergunta do golden dataset.

Para que serve
--------------
A avaliação completa (``scripts/run_evaluation.py``) mede o SISTEMA: o LLM
escreve o próprio Cypher, responde, e juízes automáticos pontuam. Custa
chamadas de API e mede duas coisas ao mesmo tempo — a qualidade do modelo de
dados e a qualidade do modelo de linguagem.

Este módulo isola a primeira. Para cada pergunta existe aqui a consulta que
um analista escreveria à mão, e ``scripts/check_golden_queries.py`` roda
todas contra o grafo. Se uma pergunta não tem resposta no grafo, o defeito é
do MODELO DE DADOS e aparece aqui — de graça, em segundos, sem depender de
crédito de API nem da sorte do dia do modelo.

É também a régua honesta do prompt: toda consulta abaixo usa apenas nomes
que aparecem no schema gerado (graph/schema.py). Se uma delas precisasse de
conhecimento que só está na cabeça de quem escreveu o projeto, isso seria
prova de que o grafo ainda não é autoexplicativo.
"""

# Perguntas estruturais: a resposta é um PadraoTatico produzido pela camada 2.
_PADRAO = """
MATCH (p:PadraoTatico {{match_id: $m, tipo: '{tipo}'{filtro}}})
RETURN p.descricao_curta AS resposta, p.nome_metrica AS metrica,
       p.valor_metrica AS valor, p.algoritmo_origem AS algoritmo
ORDER BY p.valor_metrica DESC
"""


def _padrao(tipo: str, time: str | None = None, jogador: str | None = None) -> str:
    filtro = f", time: '{time}'" if time else ""
    query = _PADRAO.format(tipo=tipo, filtro=filtro)
    if jogador:
        query = query.replace(
            "RETURN", f"WITH p WHERE any(x IN p.jogadores_envolvidos WHERE x CONTAINS '{jogador}')\nRETURN"
        )
    return query.strip()


REFERENCE_QUERIES: dict[str, str] = {
    # ---------------- estruturais (camada 2) ----------------
    "q01_pivo_argentina": _padrao("pivo_estrutural", "Argentina"),
    "q02_pivo_franca": _padrao("pivo_estrutural", "France"),
    "q03_terceiro_homem": _padrao("terceiro_homem", "Argentina"),
    "q04_gatilho_argentina": _padrao("gatilho_pressao", "Argentina"),
    "q05_ligacao_fragil": _padrao("ligacao_fragil", "Argentina"),
    "q06_papel_theo": _padrao("papel_divergente", "France", jogador="Theo"),
    "q07_mudanca_argentina": _padrao("mudanca_estado", "Argentina"),
    "q08_alvo_mbappe": _padrao("alvo_de_pressao", "England"),
    "q09_assimetria_franca": _padrao("assimetria_construcao", "France"),
    "q10_ppda_agregado": _padrao("mudanca_estado"),
    "q11_alvo_vlasic": _padrao("alvo_de_pressao", "Argentina"),
    "q12_papel_sosa": _padrao("papel_divergente", "Croatia", jogador="Sosa"),
    "q13_assimetria_croacia": _padrao("assimetria_construcao", "Croatia"),
    "q14_construcao_esteril_england": _padrao("assimetria_construcao", "England"),
    "q15_papel_kounde": _padrao("papel_divergente", "France", jogador="Koundé"),
    "q16_gatilho_franca": _padrao("gatilho_pressao", "France"),
    # ---------------- factuais (camada 1 / súmula) ----------------
    "q17_gols_final": """
MATCH (j:Jogador)-[f:FINALIZOU {match_id: $m}]->(:Partida)
WHERE f.gol
RETURN j.nome AS jogador, j.time AS time, f.minuto AS minuto,
       f.periodo_nome AS periodo, f.acao AS tipo
ORDER BY f.minuto
""".strip(),
    "q18_assistencias_final": """
MATCH (a:Jogador)-[d:DEU_ASSISTENCIA {match_id: $m}]->(autor:Jogador)
RETURN a.nome AS assistente, autor.nome AS autor_do_gol, a.time AS time,
       d.minuto AS minuto
ORDER BY d.minuto
""".strip(),
    "q19_dupla_passes": """
MATCH (a:Jogador)-[p:PASSOU_PARA {match_id: $m}]->(b:Jogador)
RETURN a.nome AS de, b.nome AS para, count(p) AS passes
ORDER BY passes DESC LIMIT 3
""".strip(),
    "q20_top_passador": """
MATCH (e:EstatisticaJogador {match_id: $m})
RETURN e.nome AS jogador, e.time AS time, e.passes_certos AS passes_certos,
       e.passes_tentados AS tentados, e.precisao_passe_pct AS precisao
ORDER BY passes_certos DESC LIMIT 3
""".strip(),
    "q21_cartoes_final": """
MATCH (e:EstatisticaJogador {match_id: $m})
WHERE e.cartoes_amarelos > 0
RETURN e.nome AS jogador, e.time AS time, e.cartoes_amarelos AS amarelos
ORDER BY e.time, e.nome
""".strip(),
    "q22_dribles_final": """
MATCH (e:EstatisticaJogador {match_id: $m})
RETURN e.nome AS jogador, e.dribles_certos AS certos, e.dribles_tentados AS tentados
ORDER BY certos DESC LIMIT 3
""".strip(),
    "q23_desarmes_final": """
MATCH (e:EstatisticaJogador {match_id: $m})
RETURN e.nome AS jogador, e.desarmes_certos AS certos, e.desarmes_tentados AS tentados
ORDER BY certos DESC LIMIT 3
""".strip(),
    "q24_defesas_goleiros": """
MATCH (e:EstatisticaJogador {match_id: $m})
WHERE e.defesas_do_goleiro > 0
RETURN e.nome AS goleiro, e.time AS time, e.defesas_do_goleiro AS defesas
ORDER BY defesas DESC
""".strip(),
    # ---------------- compostas (camada 2 cruzada com camada 1b) ----------------
    # Cada uma casa um PadraoTatico com a súmula do jogador que ele aponta.
    # Nenhuma das duas fontes responde sozinha — é isso que define a categoria.
    "q25_pivo_errou_passe": """
MATCH (p:PadraoTatico {match_id: $m, tipo: 'pivo_estrutural', time: 'Argentina'})
UNWIND p.jogadores_envolvidos AS pivo
MATCH (e:EstatisticaJogador {match_id: $m, nome: pivo})
MATCH (o:EstatisticaJogador {match_id: $m, time: 'Argentina'})
WITH pivo, p.valor_metrica AS betweenness, e, o
ORDER BY o.passes_tentados - o.passes_certos DESC
WITH pivo, betweenness, e,
     collect(o.nome + ': ' + toString(o.passes_tentados - o.passes_certos))[0..3] AS mais_erraram
RETURN pivo, betweenness, e.passes_certos AS certos, e.passes_tentados AS tentados,
       e.passes_tentados - e.passes_certos AS erros_do_pivo,
       e.precisao_passe_pct AS precisao, mais_erraram
""".strip(),
    "q26_pressao_no_mbappe_funcionou": """
MATCH (p:PadraoTatico {match_id: $m, tipo: 'alvo_de_pressao'})
UNWIND p.jogadores_envolvidos AS alvo
MATCH (e:EstatisticaJogador {match_id: $m, nome: alvo})
RETURN alvo, p.valor_metrica AS pressoes_por_toque, e.pressoes_sofridas AS pressoes_sofridas,
       e.toques AS toques, e.passes_certos AS certos, e.passes_tentados AS tentados,
       e.precisao_passe_pct AS precisao, e.dribles_certos AS dribles_certos
""".strip(),
    "q27_theo_atacante_de_fato": """
MATCH (p:PadraoTatico {match_id: $m, tipo: 'papel_divergente'})
WHERE any(x IN p.jogadores_envolvidos WHERE x CONTAINS 'Theo')
UNWIND p.jogadores_envolvidos AS jogador
MATCH (e:EstatisticaJogador {match_id: $m, nome: jogador})
RETURN jogador, p.descricao_curta AS padrao, e.toques AS toques,
       e.finalizacoes AS finalizacoes, e.cruzamentos_tentados AS cruzamentos,
       e.passes_progressivos AS progressivos, e.precisao_passe_pct AS precisao
""".strip(),
}
