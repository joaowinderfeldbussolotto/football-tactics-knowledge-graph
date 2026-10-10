"""The text_to_cypher arm without any paid call: guard, execution, schema, agent wiring."""

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from football_graphrag.benchmark import arms, cypher
from football_graphrag.benchmark.questions import MATCH_ID
from tests.conftest import requires_neo4j


@pytest.mark.parametrize("query", [
    "CREATE (n:X) RETURN n",
    "MATCH (n) DETACH DELETE n",
    "MATCH (j:Jogador) SET j.nome = 'x'",
    "MERGE (n:X {a: 1})",
    "LOAD CSV FROM 'file:///x' AS row RETURN row",
    "CALL db.labels()",
    "CALL gds.betweenness.stream('g') YIELD nodeId RETURN nodeId",
    "RETURN apoc.text.join(['a'], ',')",
    "MATCH (p:PadraoTatico) RETURN p",
    "",
])
def test_guard_refuses_what_is_not_a_plain_read(query):
    with pytest.raises(cypher.CypherRejected):
        cypher.check_query(query)


@pytest.mark.parametrize("query", [
    "MATCH (j:Jogador) WHERE j.nome CONTAINS 'Messi' RETURN j.nome",
    "MATCH (j:Jogador) WHERE j.nome = 'CREATE SET DELETE' RETURN j  // CALL db.labels()",
    "MATCH (j:Jogador) CALL { WITH j MATCH (j)-[r:REALIZOU]->() RETURN count(r) AS n } RETURN j.nome, n",
    "MATCH (j:Jogador) CALL (j) { MATCH (j)-[r:REALIZOU]->() RETURN count(r) AS n } RETURN j.nome, n",
    "MATCH (j:Jogador) RETURN j.created_at, j.settled LIMIT 1",
])
def test_guard_lets_reads_through(query):
    cypher.check_query(query)


@pytest.fixture(scope="module")
def driver():
    from football_graphrag.config import get_settings
    from football_graphrag.graph import db

    d = db.make_driver(get_settings())
    yield d
    d.close()


@requires_neo4j
def test_rows_are_plain_data_and_capped(driver):
    r = cypher.run_query(driver, f"""MATCH (j:Jogador)-[p:PASSOU_PARA {{match_id: {MATCH_ID}}}]->(k:Jogador)
                                     RETURN j.nome AS passer, k AS receiver, p.segundo AS second LIMIT 100""")
    assert r["columns"] == ["passer", "receiver", "second"]
    assert r["rows_returned"] == cypher.MAX_ROWS and r["truncated"]
    receiver = r["rows"][0]["receiver"]
    assert receiver["_labels"] == ["Jogador"] and "nome" in receiver and "uid" not in receiver


@requires_neo4j
def test_query_errors_come_back_as_messages(driver):
    assert "syntax" in cypher.run_query(driver, "MATCH (j:Jogador RETURN j")["error"]
    assert cypher.run_query(driver, "RETURN 1 / 0")["error"]


@requires_neo4j
def test_the_session_refuses_writes_even_past_the_guard(driver, monkeypatch):
    monkeypatch.setattr(cypher, "check_query", lambda q: None)
    assert "access mode" in cypher.run_query(driver, "CREATE (n:ProbeCypherArm) RETURN n")["error"].lower()
    with driver.session() as s:
        assert s.run("MATCH (n:ProbeCypherArm) RETURN count(n)").single()[0] == 0


@requires_neo4j
def test_schema_is_read_from_the_graph_for_the_question_match(driver):
    text = cypher.describe(driver)
    assert f"match_id = {MATCH_ID}" in text
    assert "(:Jogador)-[:PASSOU_PARA]->(:Jogador)" in text and "989 in this match" in text
    assert "values: arremesso_lateral, cartao_por_reclamacao, conducao" in text  # acao, listed in full
    assert "PadraoTatico" not in text and "OBSERVADO_EM" not in text and "tipo_spadl" not in text


@requires_neo4j
async def test_the_arm_sends_the_schema_and_runs_the_models_query():
    query = (f"MATCH (j:Jogador)-[p:PASSOU_PARA {{match_id: {MATCH_ID}}}]->(k:Jogador) "
             "WHERE k.nome CONTAINS 'Messi' RETURN j.nome AS passer, count(*) AS n ORDER BY n DESC LIMIT 1")
    seen = {}

    def model(messages, info: AgentInfo):
        returns = [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
        if not returns:
            assert [t.name for t in info.function_tools] == ["run_cypher"]
            return ModelResponse(parts=[ToolCallPart("run_cypher", {"query": query})])
        seen["rows"] = returns[0].content["rows"]
        top = seen["rows"][0]["passer"]
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
            "rationale": "query", "players": [top], "value": None, "no_data": False})])

    with arms.tool_agent("text_to_cypher").override(model=FunctionModel(model)):
        result = await arms.run_arm("text_to_cypher", "Quem mais passou para Messi?")
    assert result.prompt_preview.startswith("Graph schema:\n") and "Question: Quem mais passou" in result.prompt_preview
    assert result.tool_calls == [{"tool": "run_cypher", "args": {"query": query}}]
    assert result.answer.players == ["Rodrigo Javier De Paul"]  # n11


def test_the_sixth_arm_is_optional():
    assert "text_to_cypher" in arms.ARMS and "text_to_cypher" not in arms.MAIN_ARMS
    assert arms.TOOL_ARMS["graph_tools"] == tuple(arms.TOOLS)  # graph_tools did not gain the Cypher tool
    assert arms.user_content("text_to_cypher", "Graph schema:\nx\n\nQuestion: q")[1].__class__.__name__ == "CachePoint"


@requires_neo4j
def test_plain_cypher_answers_every_answerable_question():
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "check_cypher.py"
    out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stdout[-2000:]
    assert "0 disagree; 0 without a query" in out.stdout
