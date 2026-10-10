# Instruções para o Claude Code neste repositório

- **Escrita do artigo:** trabalhe em `paper/` e siga `paper/CLAUDE.md` (leia também `paper/ALERTAS.md`).
- **O código do benchmark está congelado.** Ferramentas, perguntas, schema e gabarito não mudam; só se corrige
  um número errado. Não rode `scripts/run_benchmark.py`, `scripts/ask.py` ou qualquer chamada a modelo sem
  pedido explícito: cada uma gasta crédito.
- Os testes (`python -m pytest tests -q`) não fazem chamadas pagas.
- Segredos ficam no ambiente ou no `.env`; nunca os mostre.
- Mensagens de commit em inglês, curtas; respostas ao autor em português.
