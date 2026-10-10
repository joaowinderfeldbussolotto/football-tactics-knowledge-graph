---
name: cite-check
description: Confere cada \cite do artigo contra o resumo da fonte (busca título, autores e resumo pelo DOI e registra se a frase é sustentada em paper/claims.md). Use depois de escrever ou alterar trechos com citação, antes de fechar uma seção, ou quando o autor pedir "confira as citações" ou "rode o cite-check".
---

# Conferência de citações

Objetivo: nenhuma frase do artigo atribui à fonte o que a fonte não diz. O script faz a parte mecânica; **o
julgamento é seu**.

## Passo a passo

1. `python paper/scripts/cite_check.py` (use `--offline` sem rede). Ele acha cada par (frase, chave), busca título,
   ano e resumo pelo DOI (Crossref, arXiv, Semantic Scholar), guarda em `paper/.cache/refs/` e escreve
   `paper/claims.md` com `PENDENTE` em cada par. Chave que não está em `paper/refs.bib` é erro: corrija a chave
   (ou acrescente a referência em `paper/refs/references.tsv` com o DOI e rode `fetch_bibtex.py`).
2. Para cada linha `PENDENTE`, compare a frase com o resumo e decida:
   - **SUSTENTA:** o resumo diz o que a frase afirma, ou diz algo de que a frase decorre sem acréscimo. Números
     e nomes têm de bater com o resumo.
   - **SUSTENTA EM PARTE:** a fonte apoia o núcleo, mas a frase acrescenta (um número, um escopo, uma
     comparação). Reescreva a frase para o que a fonte diz.
   - **NAO SUSTENTA:** a fonte não diz isso ou diz o contrário. Corrija a frase ou troque a citação; nunca
     mantenha.
   - **SEM RESUMO:** nenhuma fonte devolveu o resumo. Diga ao autor, que abre o artigo; não presuma.
   Escreva a decisão nas colunas `veredito` e `nota` (na nota, o trecho do resumo que sustenta, ou o que
   falta). Edite só essas duas colunas; elas sobrevivem a uma nova execução.
3. Aplique as correções em `paper/sections/*.tex`, rode o script de novo e confirme que não sobrou
   `PENDENTE` nem `NAO SUSTENTA`.
4. Entregue ao autor a lista do que mudou e do que ficou sem resumo.

## Critérios

- O resumo é a única evidência disponível sem abrir o artigo. Se a frase depende de um detalhe que um resumo
  não traz (um número de uma tabela, um experimento específico), é **SUSTENTA EM PARTE** no máximo, com a nota
  "detalhe não verificável pelo resumo".
- Cuidado com atribuição de resultado: "X mostrou que Y" exige que o resumo diga Y, não só que X estudou o tema.
- Citação de autoria, ano e veículo vem do `refs.bib` (gerado do DOI); nunca digite autores ou ano no texto.
- Não use outra fonte para "salvar" uma frase sem avisar: citação nova entra em `references.tsv` e passa pelo
  mesmo ciclo.

## Frases do dossiê que merecem conferência primeiro

O dossiê (`paper/dossie.md`) foi escrito a partir de pesquisa na web por outra sessão. Confira antes de reusar:
TacticAI e os "90%" de preferência dos especialistas; SportQA e "mais de 70 mil perguntas"; "RAG vence em
perguntas de um salto e GraphRAG em vários saltos" (Han et al.); a conclusão de Li et al. sobre contexto longo e
Self-Route; o que Text2Cypher diz sobre fine-tuning; a descrição de NLGraph e de StructGPT. O rascunho do
colega citava Pollard (2002) para uma afirmação que a fonte contradiz: nenhuma referência dele entra.
