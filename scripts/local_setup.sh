#!/usr/bin/env bash
# Prepara o projeto para rodar FORA do container `app` (scripts no host, Neo4j no Docker).
#
# Quando usar: o container não resolve nomes (Codespaces com DNS quebrado no
# Docker), ou você simplesmente prefere o ambiente Python no host. O Neo4j
# continua no compose — é o único serviço que precisa dele.
#
# O que faz, nesta ordem, e cada passo é idempotente (pode rodar de novo):
#   1. confere Docker e instala o `uv` se faltar
#   2. cria .venv com Python 3.11 e instala o projeto
#      (socceraction não instala em Python >= 3.13; por isso 3.11, como no Dockerfile)
#   3. cria/ajusta o .env (NEO4J_URI aponta para localhost, não para o serviço `neo4j`)
#   4. sobe SÓ o Neo4j e espera ficar saudável; confere o plugin GDS
#   5. camadas 0, 1/1b e 2 (de graça: sem LLM, sem API)
#
# Uso:
#   scripts/local_setup.sh                    # tudo
#   scripts/local_setup.sh --sem-camadas      # só ambiente + Neo4j (pula o passo 5)
#   scripts/local_setup.sh --testes           # roda o pytest no fim
#
# Nada aqui gasta API: LLM e embeddings só entram no benchmark, que este
# script nunca chama.

set -euo pipefail
cd "$(dirname "$0")/.."

PY_VERSION="3.11"
FAZER_CAMADAS=1
FAZER_TESTES=0

for arg in "$@"; do
  case "$arg" in
    --sem-camadas) FAZER_CAMADAS=0 ;;
    --testes)      FAZER_TESTES=1 ;;
    -h|--help)     sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "argumento desconhecido: $arg (use --help)" >&2; exit 1 ;;
  esac
done

passo() { printf '\n==> %s\n' "$*"; }
aviso() { printf '    ! %s\n' "$*" >&2; }
ok()    { printf '    ok: %s\n' "$*"; }

# ---------------------------------------------------------------- 1. Docker + uv
passo "1/5 Docker e uv"
command -v docker >/dev/null || { aviso "docker não encontrado"; exit 1; }
docker info >/dev/null 2>&1 || { aviso "o daemon do Docker não responde (docker info falhou)"; exit 1; }
ok "docker respondendo"

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
  echo "    instalando uv (gerenciador de Python/venv)..."
  python3 -m pip install --user --quiet uv
fi
ok "uv $(uv --version | awk '{print $2}')"

# ---------------------------------------------------------------- 2. venv + projeto
passo "2/5 Ambiente Python ${PY_VERSION}"
VENV_OK=0
if [ -x .venv/bin/python ] && .venv/bin/python --version 2>&1 | grep -q "Python ${PY_VERSION}\."; then
  VENV_OK=1
fi
if [ "$VENV_OK" -eq 0 ]; then
  [ -d .venv ] && aviso ".venv existente não é Python ${PY_VERSION}; recriando"
  rm -rf .venv
  uv venv --python "$PY_VERSION" .venv
fi
PY=".venv/bin/python"
ok "$($PY --version)"
uv pip install --python "$PY" --quiet -e ".[dev]"
ok "projeto instalado (editável, com extras de teste)"

# ---------------------------------------------------------------- 3. .env
passo "3/5 Arquivo .env"
if [ ! -f .env ]; then
  cp .env.example .env
  ok ".env criado a partir do .env.example"
  AVISAR_CHAVES=1
else
  AVISAR_CHAVES=0
fi
# Dentro do compose o Neo4j é `neo4j`; no host é localhost (a porta 7687 está publicada).
if grep -qE '^NEO4J_URI=bolt://neo4j[:/]' .env; then
  cp .env ".env.bak-local"
  sed -i -E 's#^NEO4J_URI=bolt://neo4j(:[0-9]+)?#NEO4J_URI=bolt://localhost\1#' .env
  ok "NEO4J_URI ajustado para localhost (cópia do original em .env.bak-local)"
else
  ok "NEO4J_URI já está correto para o host"
fi
if [ "$AVISAR_CHAVES" -eq 1 ]; then
  aviso "preencha as chaves em .env antes de qualquer passo que use LLM:"
  aviso "  LLM_PROVIDER / LLM_API_KEY / LLM_MODEL, EMBEDDER_PROVIDER / EMBEDDER_API_KEY / EMBEDDER_MODEL"
fi

# ---------------------------------------------------------------- 4. Neo4j
passo "4/5 Neo4j (só ele; o container app não é necessário)"
SENHA="$(grep -E '^NEO4J_PASSWORD=' .env | head -1 | cut -d= -f2-)"
SENHA="${SENHA:-changeme}"

cypher() { docker compose exec -T neo4j cypher-shell -u neo4j -p "$SENHA" "$@"; }

esperar_neo4j() {
  local estado=""
  for _ in $(seq 1 48); do
    estado="$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q neo4j)" 2>/dev/null || true)"
    [ "$estado" = "healthy" ] && return 0
    sleep 5
  done
  aviso "Neo4j não ficou saudável (estado: ${estado:-desconhecido}). Veja: docker compose logs neo4j"
  return 1
}

tem_gds() { cypher "RETURN gds.version() AS gds" >/dev/null 2>&1; }

# O plugin GDS é baixado pelo PRÓPRIO container do Neo4j na primeira subida
# (NEO4J_PLUGINS no compose). Se o container não resolve nomes — o problema que
# motiva este script —, o download falha e o Neo4j "continua a subir sem o
# plugin", em silêncio: só a camada 2 reclama, depois de as camadas 0 e 1 já
# terem rodado. O host, que resolve, baixa o jar e copia para dentro.
instalar_gds_pelo_host() {
  local versao url jar tmp
  versao="$(cypher --format plain "CALL dbms.components() YIELD versions RETURN versions[0]" 2>/dev/null | tail -1 | tr -d '"\r ')"
  [ -n "$versao" ] || { aviso "não consegui ler a versão do Neo4j"; return 1; }
  echo "    Neo4j ${versao}: procurando o jar do GDS compatível..."
  url="$(curl -fsS -m 30 https://graphdatascience.ninja/versions.json | "$PY" -c '
import json, sys
alvo = sys.argv[1]
for e in json.load(sys.stdin):
    if e.get("neo4j") == alvo:
        print(e["downloadUrl"])
        break
' "$versao")" || true
  [ -n "$url" ] || { aviso "sem jar de GDS listado para o Neo4j ${versao}, ou o host também não alcança graphdatascience.ninja"; return 1; }
  jar="$(basename "$url")"
  tmp="$(mktemp -d)"
  echo "    baixando ${jar} pelo host..."
  curl -fL --retry 3 -m 900 -o "${tmp}/${jar}" "$url" || { aviso "download do jar falhou"; rm -rf "$tmp"; return 1; }
  docker cp "${tmp}/${jar}" "$(docker compose ps -q neo4j):/plugins/${jar}"
  rm -rf "$tmp"
  echo "    reiniciando o Neo4j para carregar o plugin..."
  docker compose restart neo4j >/dev/null
  esperar_neo4j
}

docker compose up -d neo4j
echo "    esperando ficar saudável (até 4 min)..."
esperar_neo4j || exit 1
ok "Neo4j saudável"

if tem_gds; then
  ok "plugin GDS carregado ($(cypher --format plain 'RETURN gds.version()' 2>/dev/null | tail -1 | tr -d '"\r '))"
else
  aviso "plugin GDS não carregado (o container não conseguiu baixá-lo); tentando pelo host..."
  if instalar_gds_pelo_host && tem_gds; then
    ok "plugin GDS instalado pelo host ($(cypher --format plain 'RETURN gds.version()' 2>/dev/null | tail -1 | tr -d '"\r '))"
  else
    aviso "GDS continua indisponível — a camada 2 (run_analysis.py) vai falhar."
    aviso "veja: docker compose logs neo4j | grep -i -E 'plugin|graph-data-science'"
    [ "$FAZER_CAMADAS" -eq 1 ] && aviso "o passo 5 roda mesmo assim; as camadas 0 e 1 não dependem do GDS."
  fi
fi

# ---------------------------------------------------------------- 5. camadas
if [ "$FAZER_CAMADAS" -eq 1 ]; then
  passo "5/5 Camadas 0, 1/1b e 2 (sem custo de API)"
  "$PY" scripts/run_pipeline.py
  "$PY" scripts/build_graph.py
  "$PY" scripts/run_analysis.py
  ok "camadas montadas"
else
  passo "5/5 Camadas — pulado (--sem-camadas)"
fi

# ---------------------------------------------------------------- testes (opcional)
if [ "$FAZER_TESTES" -eq 1 ]; then
  passo "Testes"
  "$PY" -m pytest tests/ -q
fi

cat <<FIM

pronto. Em cada terminal novo, ative o ambiente antes de rodar qualquer script:

    source .venv/bin/activate

próximos passos (os que usam LLM precisam das chaves no .env):

    python scripts/check_ground_truth.py       # gabarito x grafo, sem custo
    python scripts/smoke_llm.py                # confere tool calling + saída estruturada do modelo
    python scripts/run_benchmark.py --sample   # 1 pergunta por tipo (centavos)

FIM
