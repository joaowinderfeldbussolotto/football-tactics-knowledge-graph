"""Schema do grafo em texto, LIDO DO BANCO — não escrito à mão.

Por que gerar em vez de escrever
--------------------------------
O prompt do agente carregava ~40 linhas de schema manual, das quais a maior
parte não era schema: eram avisos ("ATENÇÃO: 'dribble' é condução", "NUNCA
faça join com FINALIZOU", "não some PASSOU_PARA com REALIZOU"). Cada aviso
era um remendo para uma ambiguidade do dado — e remendo em prompt falha em
silêncio, como falhou na pergunta dos desarmes.

Com o grafo já falando futebol (ver ingestion/football_semantics.py e
graph/statistics.py), o schema volta a ser só schema. E, sendo só schema,
pode ser LIDO do banco: nomes de propriedade e vocabulários vêm de consulta,
não de memória do autor. Consequência prática: o prompt não pode ficar
desatualizado em relação ao grafo, porque não existe cópia para desatualizar.

O que continua sendo escrito à mão é apenas o que não se pode introspectar:
a ORDEM de apresentação e a frase que diz para que serve cada nó/aresta.
"""

import logging

from neo4j import Driver

logger = logging.getLogger(__name__)

# Propriedades que existem no grafo mas não devem aparecer no schema do
# agente: chaves internas e rastros de proveniência. Expor 'tipo_spadl'
# reintroduziria exatamente a ambiguidade que o projeto acabou de remover
# (o agente poderia filtrar por 'tackle' em vez de acao='desarme').
OCULTAS = {"uid", "tipo_spadl", "action_id", "pressure_idx", "fase_posse_id"}

# Propriedades de vocabulário fechado: os valores possíveis são poucos e
# são enumerados a partir do banco, para o agente nunca precisar adivinhar.
VOCABULARIOS: list[tuple[str, str, str]] = [
    # (rótulo exibido, padrão Cypher, propriedade)
    ("acao", "()-[r:REALIZOU]->()", "r.acao"),
    ("grupo_acao", "()-[r:REALIZOU]->()", "r.grupo_acao"),
    ("desfecho (finalizações)", "()-[r:FINALIZOU]->()", "r.desfecho"),
    ("terco", "()-[r:REALIZOU]->()", "r.terco"),
    ("corredor", "()-[r:REALIZOU]->()", "r.corredor"),
    ("tipo (PadraoTatico)", "(n:PadraoTatico)", "n.tipo"),
]

# Ordem e propósito. É a única parte curada: o banco sabe QUAIS campos
# existem, não PARA QUE servem.
NOS = [
    ("EstatisticaJogador", "uma linha por jogador na partida, com tudo já somado"),
    ("EstatisticaTime", "uma linha por time na partida, com tudo já somado"),
    ("Jogador", "identificação do jogador"),
    ("Time", "identificação da seleção"),
    ("Partida", "a partida"),
    ("PadraoTatico", "padrão achado pelos algoritmos de grafo (camada 2)"),
    ("Zona", "célula da grade 12x8 do campo (id_zona 0-95)"),
    ("FaseDePosse", "sequência ininterrupta de posse de um time"),
]

ARESTAS = [
    ("REALIZOU", "(:Jogador)", "(:Partida)", "toda ação com bola, uma aresta por ação"),
    ("PASSOU_PARA", "(:Jogador)", "(:Jogador)", "passes CERTOS com recebedor (a rede de passes)"),
    ("FINALIZOU", "(:Jogador)", "(:Partida)", "uma aresta por finalização"),
    ("DEU_ASSISTENCIA", "(:Jogador)", "(:Jogador)", "uma aresta por gol assistido; o destino é quem fez o gol"),
    ("PRESSIONOU", "(:Jogador)", "(:Jogador)", "uma aresta por pressão exercida"),
    ("ATUOU_EM", "(:Jogador)", "(:Zona)", "quanto o jogador agiu em cada zona"),
    ("PARTICIPOU_DE", "(:Jogador)", "(:FaseDePosse)", "toques do jogador em cada fase de posse"),
    ("PROGREDIU_PARA", "(:Zona)", "(:Zona)", "fluxo de bola entre zonas, por time"),
    ("MEMBRO_DE", "(:Jogador)", "(:Time)", "elenco"),
    ("TEM_ESTATISTICA", "(:Jogador|:Time)", "(:EstatisticaJogador|:EstatisticaTime)", "liga a entidade à sua súmula"),
    ("OBSERVADO_EM", "(:PadraoTatico)", "(:Partida)", "em que partida o padrão foi observado"),
]

CABECALHO = """\
GRAFO DA PARTIDA (Neo4j). Schema abaixo lido do banco — é o estado real.

COMECE PELAS SÚMULAS: EstatisticaJogador e EstatisticaTime já têm somado
quase todo número que se pergunta sobre um jogo. Só caia no log de ações
(REALIZOU) quando a súmula não tiver o campo.

Todas as arestas têm match_id: filtre sempre por ele.
`minuto` é o minuto de transmissão (1-120+), já com o período embutido."""

RODAPE = """\
Nomes de jogador são completos: use CONTAINS para apelidos
(ex.: j.nome CONTAINS 'Messi')."""


def _props_por_no(driver: Driver) -> dict[str, list[str]]:
    query = "CALL db.schema.nodeTypeProperties() YIELD nodeLabels, propertyName RETURN nodeLabels, propertyName"
    out: dict[str, list[str]] = {}
    with driver.session() as session:
        for row in session.run(query).data():
            # propertyName vem None para rótulos sem propriedade alguma
            if not row["nodeLabels"] or not row["propertyName"] or row["propertyName"] in OCULTAS:
                continue
            out.setdefault(row["nodeLabels"][0], []).append(row["propertyName"])
    return out


def _props_por_aresta(driver: Driver) -> dict[str, list[str]]:
    query = "CALL db.schema.relTypeProperties() YIELD relType, propertyName RETURN relType, propertyName"
    out: dict[str, list[str]] = {}
    with driver.session() as session:
        for row in session.run(query).data():
            tipo = row["relType"].strip(":`")
            out.setdefault(tipo, [])  # registra a aresta mesmo sem propriedades
            # propertyName vem None para arestas sem propriedade alguma
            if not row["propertyName"] or row["propertyName"] in OCULTAS:
                continue
            out[tipo].append(row["propertyName"])
    return out


def _vocabularios(driver: Driver) -> list[tuple[str, list[str]]]:
    out = []
    with driver.session() as session:
        for rotulo, padrao, prop in VOCABULARIOS:
            valores = session.run(
                f"MATCH {padrao} WITH DISTINCT {prop} AS v WHERE v IS NOT NULL RETURN v ORDER BY v"
            ).value()
            if valores:
                out.append((rotulo, valores))
    return out


def describe_graph(driver: Driver) -> str:
    """Monta o texto do schema a partir do banco.

    Saída:
        bloco de texto pronto para entrar no system prompt dos agentes.
        Só inclui nós/arestas/propriedades que EXISTEM no grafo agora.
    """
    props_no = _props_por_no(driver)
    props_aresta = _props_por_aresta(driver)

    linhas = [CABECALHO, "", "NÓS"]
    for label, proposito in NOS:
        if label not in props_no:
            continue  # ainda não construído: não anunciar o que não existe
        linhas.append(f"  (:{label}) — {proposito}")
        linhas.append(f"      {', '.join(sorted(props_no[label]))}")

    linhas += ["", "ARESTAS"]
    for tipo, origem, destino, proposito in ARESTAS:
        if tipo not in props_aresta:
            continue
        linhas.append(f"  {origem}-[:{tipo}]->{destino} — {proposito}")
        if props_aresta.get(tipo):
            linhas.append(f"      {', '.join(sorted(props_aresta[tipo]))}")

    vocab = _vocabularios(driver)
    if vocab:
        linhas += ["", "VALORES POSSÍVEIS (lista exaustiva, lida do banco)"]
        for rotulo, valores in vocab:
            linhas.append(f"  {rotulo}: {', '.join(valores)}")

    linhas += ["", RODAPE]
    return "\n".join(linhas)


def cached_schema(driver: Driver) -> str:
    """describe_graph com cache de processo (o schema não muda em runtime)."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = describe_graph(driver)
        logger.info("schema do grafo lido do banco: %d caracteres", len(_SCHEMA_CACHE))
    return _SCHEMA_CACHE


_SCHEMA_CACHE: str | None = None
