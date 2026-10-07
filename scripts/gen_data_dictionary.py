#!/usr/bin/env python
"""Gera a tabela do dicionário de dados (Markdown) a partir dos schema.json.

O dicionário nasce do código (SCHEMA_DOC + dtypes reais do parquet), não é
escrito à mão. Saída no stdout, para colar/incluir em docs/legado/01-pipeline.md.
"""

import json
import sys

from football_graphrag.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    match_id = int(sys.argv[1]) if len(sys.argv) > 1 else settings.match_ids[0]
    schema = json.loads((settings.processed_dir / f"{match_id}_schema.json").read_text())
    print("| Coluna | Tipo | Unidade | Passo de origem | Descrição |")
    print("|---|---|---|---|---|")
    for col in schema:
        print(f"| `{col['coluna']}` | {col['tipo']} | {col['unidade']} | {col['passo_origem']} | {col['descricao']} |")
