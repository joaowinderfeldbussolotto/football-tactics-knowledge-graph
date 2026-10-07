FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts

RUN uv pip install --system --no-cache -e .

# No server: this container only runs scripts (`docker compose exec app python scripts/...`).
CMD ["sleep", "infinity"]
