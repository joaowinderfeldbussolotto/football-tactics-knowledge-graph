#!/usr/bin/env python
"""Avaliação (seção 9): três braços sobre as MESMAS perguntas e o mesmo modelo.

Braços:

1. ``grafo_sem_sumula`` — padrões da camada 2 no contexto; os números
   factuais só chegam se o agente escrever Cypher (``consultar_grafo``).
   É o braço que MEDE a autonomia do ADR-8.
2. ``grafo_com_sumula`` — o anterior mais a súmula pré-agregada (camada 1b)
   já no contexto. É o comportamento da API.
3. ``baseline`` — RAG vetorial plano, com paridade de fatos (ver
   ``evaluation/match_facts.py``).

Por que dois braços de grafo: entregar a súmula pronta economiza uma ida e
volta de ferramenta e cala o text-to-Cypher no mesmo gesto. A diferença entre
1 e 2 é a medida desse custo-benefício, em vez de uma escolha de design não
justificada. Ver ADR-10 em ``docs/05-decisoes.md``.

Duas notas de recuperação, e elas NÃO são intercambiáveis:

- ``retrieval_previo`` pontua o contexto que a recuperação entregou ANTES de
  o agente rodar. **É esta que compara com o baseline**, porque o contexto do
  baseline também é só o que a recuperação dele entregou.
- ``retrieval_final`` pontua esse contexto MAIS o resultado das consultas que
  o agente fez durante a geração. Mede o sistema inteiro, não a recuperação —
  e não tem contrapartida no baseline, que não tem ferramenta.

Até a 3ª rodada existia uma nota só, e ela era a ``final`` comparada contra a
``previo`` do baseline. A assimetria favorecia o grafo.

Salva ``data/processed/eval_results.json`` (ou o ``--saida`` pedido).
Requer chaves de LLM/embedder no .env.
"""

import argparse
import asyncio
import json
import logging
import pathlib
from datetime import datetime

from google.genai.errors import APIError as GeminiAPIError
from pydantic_ai.exceptions import UnexpectedModelBehavior

from football_graphrag.api import agents, retrieval
from football_graphrag.config import get_settings
from football_graphrag.observability import logging_setup
from football_graphrag.observability.langfuse_setup import flush, observacao, setup_observability
from football_graphrag.evaluation import baseline_rag, faithfulness, judges
from football_graphrag.evaluation.golden_dataset import GOLDEN_QUESTIONS
from football_graphrag.graph import db

logging_setup.setup(formato="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

CATEGORIAS = ("estrutural", "factual", "agregada", "composta")
# nome do braço -> passa a súmula no contexto?
BRACOS_GRAFO = {"grafo_sem_sumula": False, "grafo_com_sumula": True}


# Duas famílias de falha transitória, observadas nas duas primeiras tentativas
# desta rodada, cada uma exigindo backoff diferente: resposta bruta inválida
# do provedor de LLM (segundos bastam) e cota do Gemini estourada por minuto
# (só refaz sentido depois de um minuto — 5s não ajuda em nada).
_ERROS_TRANSITORIOS = (UnexpectedModelBehavior, GeminiAPIError)


async def _retentar(chamada, *, tentativas: int = 4, espera: float = 15.0):
    """Repete uma chamada ao modelo/embedder quando o provedor falha de forma
    transitória, em vez de deixar a exceção derrubar a rodada inteira.

    Falha 1, OpenRouter/z-ai/glm-5.3-flash: a resposta HTTP vem 200, mas com
    ``finish_reason: "error"`` dentro do corpo — valor fora do enum que o
    PydanticAI aceita — e vira ``UnexpectedModelBehavior``. Não é erro de
    validação de SAÍDA estruturada (isso o ``retries=2`` do Agent já cobre);
    é a resposta bruta do provedor sendo inválida, uma camada abaixo.

    Falha 2, embeddings do Gemini free tier (busca híbrida e baseline
    vetorial): a cota por minuto (100 req/min) estoura sob a carga de 30
    perguntas × 3 braços, o SDK esgota os retries internos dele e propaga
    ``google.genai.errors.APIError`` (ClientError 429 ou ServerError 503) sem
    ninguém tratar — derrubou esta rodada em 18 de 30 perguntas.

    Ambas são intermitentes; repetir resolve. ``espera`` é dobrada a cada
    tentativa (backoff exponencial) porque a cota por minuto só libera depois
    de um minuto — retentar com o mesmo intervalo curto reproduziria o
    mesmo 429 até esgotar as tentativas.
    """
    ultimo = None
    for tentativa in range(1, tentativas + 1):
        try:
            return await chamada()
        except _ERROS_TRANSITORIOS as exc:
            ultimo = exc
            logger.warning(
                "falha transitória do provedor (tentativa %d/%d): %s",
                tentativa, tentativas, exc,
            )
            if tentativa < tentativas:
                await asyncio.sleep(espera * tentativa)
    raise ultimo


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


async def avaliar_grafo(driver, q, *, incluir_sumula: bool, graphiti=None) -> dict:
    """Um braço do grafo, para uma pergunta."""
    patterns, stats, extra_facts, timings = await retrieval.retrieve_context(
        driver, q.match_id, q.pergunta, graphiti, incluir_sumula=incluir_sumula
    )
    resposta = await _retentar(
        lambda: agents.answer_question(q.pergunta, patterns, stats, extra_facts, driver, q.match_id)
    )
    fid = faithfulness.check_citations(driver, resposta.metricas_citadas)
    qfid = faithfulness.check_queries(driver, resposta.consultas_executadas)

    contexto_previo = _json(patterns)
    if stats:
        contexto_previo += "\n\nSÚMULA RECUPERADA:\n" + _json(stats)
    if extra_facts:
        # A ficha do jogo (e a busca híbrida) fazem parte do que a recuperação
        # entregou. Fora daqui, o juiz pontuaria um contexto que não é o que o
        # agente recebeu — a métrica mentiria na direção oposta à do vazamento
        # que a ADR-10 corrigiu.
        contexto_previo += "\n\nFATOS RECUPERADOS:\n" + "\n".join(f"- {f}" for f in extra_facts)
    contexto_final = contexto_previo
    if resposta.consultas_executadas:
        contexto_final += "\n\nCONSULTAS EXECUTADAS NO GRAFO:\n" + "\n".join(
            f"- {c.cypher} => {c.resultado_resumido}" for c in resposta.consultas_executadas
        )

    j_previo = await _retentar(
        lambda: judges.judge_retrieval(q.pergunta, q.resposta_referencia, contexto_previo)
    )
    # Sem consulta nenhuma os dois contextos são o MESMO texto. Reaproveitar a
    # nota (em vez de chamar o juiz de novo) evita que ruído de amostragem de
    # um juiz estocástico vire uma diferença aparente entre as duas métricas.
    j_final = (
        j_previo
        if contexto_final == contexto_previo
        else await _retentar(
            lambda: judges.judge_retrieval(q.pergunta, q.resposta_referencia, contexto_final)
        )
    )
    insight = await _retentar(
        lambda: judges.judge_insight(q.pergunta, q.resposta_referencia, resposta.resposta)
    )

    return {
        "resposta": resposta.resposta,
        "faithfulness": fid.score,
        "query_reexec": qfid.score,
        "n_consultas": len(resposta.consultas_executadas),
        "retrieval_previo": j_previo.score,
        "retrieval_final": j_final.score,
        "tactical_insight": insight.score,
        "timings": timings,
        # Sem isto, diagnosticar uma fidelidade baixa exige reproduzir a
        # pergunta ao vivo (custa dinheiro e tempo de novo) — foi o que
        # aconteceu na 4ª rodada, para achar que o modelo às vezes ecoa a
        # description do campo Pydantic como se fosse o valor.
        "metricas_citadas": [c.model_dump() for c in resposta.metricas_citadas],
        "consultas_executadas": [c.model_dump() for c in resposta.consultas_executadas],
        "mismatches_faithfulness": fid.mismatches,
        "mismatches_query_reexec": qfid.mismatches,
    }


async def avaliar_baseline(index, q) -> dict:
    resposta, contexto = await _retentar(lambda: baseline_rag.answer_with_baseline(index, q.pergunta))
    r = await _retentar(
        lambda: judges.judge_retrieval(q.pergunta, q.resposta_referencia, "\n".join(contexto))
    )
    i = await _retentar(lambda: judges.judge_insight(q.pergunta, q.resposta_referencia, resposta))
    # O baseline não tem ferramenta: só existe contexto prévio. O nome do
    # campo diz isso, para ninguém comparar com o retrieval_final do grafo.
    return {"resposta": resposta, "retrieval_previo": r.score, "tactical_insight": i.score}


def _caminho_parcial(settings, saida: str) -> pathlib.Path:
    return settings.processed_dir / f"{pathlib.Path(saida).stem}.parcial.json"


def carregar_parcial(settings, args) -> list[dict]:
    """Perguntas já respondidas numa execução anterior que caiu.

    Uma rodada completa leva ~2h e custa dinheiro real. Sem checkpoint, um
    daemon do Docker morrendo de ocioso na pergunta 25 joga fora as 24
    anteriores — as pagas e as demoradas.
    """
    if not args.retomar:
        return []
    caminho = _caminho_parcial(settings, args.saida)
    if not caminho.exists():
        logger.warning("--retomar pedido mas %s não existe; começando do zero", caminho.name)
        return []
    feitas = json.loads(caminho.read_text())
    logger.info("retomando: %d perguntas já respondidas em %s", len(feitas), caminho.name)
    return feitas


def selecionar(args) -> list:
    if args.ids:
        pedidos = [i.strip() for i in args.ids.split(",") if i.strip()]
        escolhidas = [q for q in GOLDEN_QUESTIONS if q.id in pedidos]
        faltando = set(pedidos) - {q.id for q in escolhidas}
        if faltando:
            raise SystemExit(f"ids inexistentes no golden dataset: {sorted(faltando)}")
        return escolhidas
    if args.amostra:
        # a primeira de cada categoria: confere o pipeline dos três braços
        # sem comprometer as 30 perguntas
        return [next(q for q in GOLDEN_QUESTIONS if q.categoria == c) for c in CATEGORIAS]
    return list(GOLDEN_QUESTIONS)


async def main(args) -> None:
    settings = get_settings()
    if not settings.llm_api_key:
        raise SystemExit("LLM_API_KEY ausente no .env: a avaliação usa o agente e os juízes")
    perguntas = selecionar(args)
    # Uma rodada = um rótulo. É por ele que se acha, no Langfuse, tudo que uma
    # execução gerou — e é o que permite comparar duas rodadas depois.
    rodada = args.rodada or f"{pathlib.Path(args.saida).stem}-{datetime.now():%Y%m%d-%H%M}"
    modelo = agents.settings_fingerprint(settings)
    observado = setup_observability(settings)
    # Busca híbrida do Graphiti: só entra se pedida E se o índice existir.
    # Ligar sem índice devolveria zero fatos silenciosamente, o que é pior que
    # não ligar — pareceria "híbrida" no rótulo da estratégia sem ser.
    graphiti = None
    if args.hibrida:
        from football_graphrag.graph.communities import make_graphiti

        with db.make_driver(settings).session() as sessao:
            indexados = sessao.run(
                "MATCH (n:Entity) WHERE n.group_id STARTS WITH 'match-' RETURN count(n)"
            ).single()[0]
        if not indexados:
            raise SystemExit(
                "--hibrida pedida mas o índice do Graphiti está vazio. "
                "Rode scripts/index_graphiti.py antes."
            )
        graphiti = make_graphiti(settings)
        logger.info("busca híbrida ligada (%d nós indexados)", indexados)
    logger.info("rodada=%s modelo=%s langfuse=%s", rodada, modelo,
                "on" if observado else "off (sem chaves)")
    driver = db.make_driver(settings)
    # Só as partidas das perguntas escolhidas: indexar as três com um
    # subconjunto de 4 perguntas gastaria cota de embeddings à toa.
    match_ids = sorted({q.match_id for q in perguntas})
    logger.info("%d perguntas, partidas %s", len(perguntas), match_ids)
    try:
        baseline_index = await baseline_rag.build_index(match_ids, settings.data_dir)
    except Exception as exc:
        # ex.: cota diária de embeddings esgotada (free tier). O lado do grafo
        # não usa embeddings — avalia só ele e registra o baseline como ausente.
        logger.warning("baseline indisponível (%s); avaliando só o sistema de grafo", exc)
        baseline_index = None

    results = carregar_parcial(settings, args)
    ja_feitas = {r["id"] for r in results}
    parcial = _caminho_parcial(settings, args.saida)
    for q in perguntas:
        if q.id in ja_feitas:
            logger.info("%s: já respondida, pulando", q.id)
            continue
        linha = {"id": q.id, "categoria": q.categoria, "insight": q.insight, "pergunta": q.pergunta}
        for braco, incluir in BRACOS_GRAFO.items():
            logger.info("%s [%s]", q.id, braco)
            with observacao(f"{q.id}/{braco}", ativo=observado, rodada=rodada,
                            categoria=q.categoria, braco=braco, modelo=modelo):
                linha[braco] = await avaliar_grafo(
                    driver, q, incluir_sumula=incluir, graphiti=graphiti
                )
        if baseline_index is not None:
            logger.info("%s [baseline]", q.id)
            with observacao(f"{q.id}/baseline", ativo=observado, rodada=rodada,
                            categoria=q.categoria, braco="baseline", modelo=modelo):
                linha["baseline"] = await avaliar_baseline(baseline_index, q)
        else:
            linha["baseline"] = None
        results.append(linha)
        # grava DEPOIS de cada pergunta: o parcial é o seguro da rodada
        parcial.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    # a ordem do golden dataset é a ordem de leitura das tabelas; uma retomada
    # não pode embaralhar isso
    ordem = {q.id: i for i, q in enumerate(GOLDEN_QUESTIONS)}
    results.sort(key=lambda r: ordem.get(r["id"], 0))
    summary = _summarize(results, settings)
    summary["rodada"] = rodada
    out = settings.processed_dir / args.saida
    out.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n-> {out}")
    parcial.unlink(missing_ok=True)
    driver.close()
    if graphiti is not None:
        await graphiti.close()
    flush(observado)


def _summarize(results: list[dict], settings) -> dict:
    def avg(rows, braco, metrica):
        vals = [r[braco][metrica] for r in rows if r.get(braco) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    by_cat = {}
    for cat in CATEGORIAS:
        rows = [r for r in results if r["categoria"] == cat]
        if not rows:
            continue
        entrada = {"n": len(rows)}
        for braco in BRACOS_GRAFO:
            entrada[braco] = {
                "retrieval_previo": avg(rows, braco, "retrieval_previo"),
                "retrieval_final": avg(rows, braco, "retrieval_final"),
                "insight": avg(rows, braco, "tactical_insight"),
                "consultas_media": avg(rows, braco, "n_consultas"),
            }
        entrada["baseline"] = {
            "retrieval_previo": avg(rows, "baseline", "retrieval_previo"),
            "insight": avg(rows, "baseline", "tactical_insight"),
        }
        by_cat[cat] = entrada

    return {
        "modelo": agents.settings_fingerprint(settings),
        "n_perguntas": len(results),
        "faithfulness_media": {
            braco: round(sum(r[braco]["faithfulness"] for r in results) / len(results), 4)
            for braco in BRACOS_GRAFO
        },
        "por_categoria": by_cat,
    }


def _args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sel = p.add_mutually_exclusive_group()
    sel.add_argument("--amostra", action="store_true", help="uma pergunta de cada categoria")
    sel.add_argument("--ids", help="ids separados por vírgula (ex.: q01,q17)")
    p.add_argument("--saida", default="eval_results.json", help="nome do arquivo em data/processed")
    p.add_argument("--rodada", help="rótulo da rodada no Langfuse (default: derivado de --saida + data)")
    p.add_argument("--retomar", action="store_true",
                   help="continua de onde a execução anterior parou (lê o .parcial.json)")
    p.add_argument("--hibrida", action="store_true",
                   help="liga a busca híbrida do Graphiti (exige scripts/index_graphiti.py antes)")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_args()))
