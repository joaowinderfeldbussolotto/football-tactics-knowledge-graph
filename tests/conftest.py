import pytest

from football_graphrag.config import get_settings


def neo4j_available() -> bool:
    try:
        from football_graphrag.graph import db

        driver = db.make_driver(get_settings())
        with driver.session() as session:
            session.run("RETURN 1").consume()
        driver.close()
        return True
    except Exception:
        return False


requires_neo4j = pytest.mark.skipif(not neo4j_available(), reason="Neo4j indisponível")


def match_data_available(match_id: int = 3869685) -> bool:
    return (get_settings().processed_dir / f"{match_id}.parquet").exists()


requires_data = pytest.mark.skipif(not match_data_available(), reason="parquet da partida não gerado")
