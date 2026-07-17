"""Testes da camada 2 (insights). Parte unitária + parte contra Neo4j vivo."""

from tests.conftest import requires_data, requires_neo4j

from football_graphrag.config import get_settings
from football_graphrag.graph import analysis, db

MATCH_ID = 3869685


def test_nominal_line_mapping():
    assert analysis.nominal_line("Left Back") == "defesa"
    assert analysis.nominal_line("Right Wing Back") == "defesa"
    assert analysis.nominal_line("Left Defensive Midfield") == "meio"
    assert analysis.nominal_line("Attacking Midfield") == "ataque"
    assert analysis.nominal_line("Right Wing") == "ataque"
    assert analysis.nominal_line("Center Forward") == "ataque"
    assert analysis.nominal_line("Goalkeeper") == "gol"
    assert analysis.nominal_line("Substitute") is None
    assert analysis.nominal_line(None) is None


@requires_neo4j
@requires_data
def test_pivo_estrutural_produces_traceable_patterns():
    settings = get_settings()
    driver = db.make_driver(settings)
    try:
        patterns = analysis.pivo_estrutural(driver, MATCH_ID)
        assert len(patterns) == 2  # um por time
        for p in patterns:
            assert p.algoritmo_origem == "gds.betweenness.stream"
            assert p.valor_metrica > 0
            assert p.jogadores_envolvidos
    finally:
        driver.close()


@requires_neo4j
@requires_data
def test_mudanca_estado_is_bitemporal():
    settings = get_settings()
    driver = db.make_driver(settings)
    try:
        patterns = analysis.mudanca_estado(driver, MATCH_ID, settings.data_dir)
        # estados vêm em pares: o antigo invalidado (invalid_at) e o novo vigente
        invalidated = [p for p in patterns if p.invalid_at is not None]
        current = [p for p in patterns if p.invalid_at is None]
        assert invalidated and current
        for old in invalidated:
            assert old.valid_at == 0.0
            assert old.invalid_at == old.minuto_fim
    finally:
        driver.close()
