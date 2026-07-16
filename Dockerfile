FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# uv resolve e instala esse conjunto de dependências (~100 pacotes: pandas,
# numpy, scipy, xgboost, graphiti-core, pydantic-ai...) em segundos. O
# resolver do pip puro pode levar minutos de backtracking em constraints de
# versão soltas (ex: langfuse>=3,<5) — medido em ~13s com uv contra o pip
# ainda travado depois de 2m30s+ tentando resolver só o langfuse.
RUN pip install --no-cache-dir uv

# Instala as dependências num layer separado do código-fonte de verdade: só
# pyproject.toml/README.md entram aqui, com um pacote-placeholder vazio
# (só precisa existir pra gerar metadata do install editável, não do
# conteúdo). Assim, mudar qualquer arquivo em src/ não invalida este layer —
# ele só é refeito quando pyproject.toml muda de verdade, em vez de em todo
# `docker compose up --build`.
COPY pyproject.toml README.md ./
RUN mkdir -p src/football_graphrag && touch src/football_graphrag/__init__.py
RUN uv pip install --system --no-cache -e .

COPY src/ ./src/
COPY scripts/ ./scripts/

RUN mkdir -p /app/data/raw /app/data/processed

EXPOSE 8000

CMD ["uvicorn", "football_graphrag.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
