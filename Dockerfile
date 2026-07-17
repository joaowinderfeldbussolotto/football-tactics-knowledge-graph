FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts

# Editável: o pacote roda a partir de /app/src, então o bind mount de ./src
# do docker-compose.override.yml passa a valer (hot-reload em dev funciona).
RUN uv pip install --system --no-cache -e .

EXPOSE 8000

CMD ["uvicorn", "football_graphrag.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
