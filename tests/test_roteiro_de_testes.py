"""O roteiro de testes manuais não pode apodrecer em silêncio.

``docs/10-roteiro-de-testes.md`` manda o leitor colar consultas no Neo4j Browser
e comparar com valores "esperados". Se uma consulta tiver erro de digitação, ou o
modelo do grafo mudar e ela passar a devolver vazio, o leitor conclui que o APP
está quebrado — quando quem quebrou foi o documento. Estes testes executam cada
bloco ``cypher`` do roteiro contra o grafo real.

Exigem Neo4j de pé e as camadas montadas; sem isso, são pulados (como os demais
testes que precisam do banco).
"""

import re
from pathlib import Path

import pytest

from football_graphrag.config import get_settings
from football_graphrag.graph import db
from tests.conftest import requires_data, requires_neo4j

ROTEIRO = Path(__file__).resolve().parent.parent / "docs" / "10-roteiro-de-testes.md"

# Blocos em que "vazio" é justamente o resultado esperado: o placeholder que o
# leitor substitui (caso 27) e a busca por um jogador que NÃO existe (caso 23).
VAZIO_E_O_ESPERADO = ("COLE-O-UID-AQUI", "'ronaldo'")


def _blocos_cypher() -> list[tuple[str, str]]:
    """(número do caso, consulta) de cada bloco ``cypher`` do roteiro."""
    texto = ROTEIRO.read_text(encoding="utf-8")
    caso, blocos = "?", []
    for m in re.finditer(r"### Caso (\d+)|```cypher\n(.*?)```", texto, re.S):
        if m.group(1):
            caso = m.group(1)
        else:
            blocos.append((caso, m.group(2).strip()))
    return blocos


def test_o_roteiro_tem_consultas_para_executar():
    """Guarda do próprio teste: se a regex parar de achar blocos, nada abaixo
    seria exercitado e o teste passaria sem provar coisa alguma."""
    assert len(_blocos_cypher()) >= 10


@requires_neo4j
@requires_data
@pytest.mark.parametrize(("caso", "consulta"), _blocos_cypher(), ids=lambda v: f"caso{v}" if len(str(v)) < 4 else "")
def test_cada_consulta_do_roteiro_executa_e_devolve_o_prometido(caso, consulta):
    driver = db.make_driver(get_settings())
    try:
        with driver.session() as session:
            linhas = session.run(consulta).data()  # erro de sintaxe estoura aqui
    finally:
        driver.close()

    if any(marca in consulta for marca in VAZIO_E_O_ESPERADO):
        assert linhas == [], f"caso {caso}: era para voltar vazio"
    else:
        assert linhas, f"caso {caso}: a consulta rodou mas voltou vazia — o roteiro promete resultado"
