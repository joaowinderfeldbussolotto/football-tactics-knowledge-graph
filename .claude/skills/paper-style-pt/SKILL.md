---
name: paper-style-pt
description: Guia de estilo do artigo em português (voz impessoal, tempos verbais, sem adjetivo de propaganda, sem travessão, glossário fixo). Use ao escrever, reescrever ou revisar qualquer trecho de paper/sections/*.tex, ou quando o autor pedir "no estilo do artigo", "revise o tom" ou "rode o lint".
---

# Estilo do artigo (português)

Aplique estas regras a todo texto em `paper/sections/`. O verificador mecânico é
`python paper/scripts/lint_paper.py`; ele pega números soltos, travessão, primeira pessoa do plural, adjetivo de
propaganda e termos fora do glossário. Rode-o depois de cada seção e conserte o que apontar. O que o lint não
pega (tempo verbal, afirmação sem fonte, força da conclusão) é com você.

## Regras

1. **Voz impessoal.** "Foram avaliadas seis formas de acesso", não "avaliamos". Sem "nós", "nosso", "vamos".
2. **Tempo verbal.** Passado para o que foi feito ("a rodada usou", "o gabarito foi calculado"). Presente para o
   que os resultados mostram ("o `graph_tools` acerta", "a diferença é de 17 pontos") e para o que o artigo faz
   ("a Seção 4 descreve").
3. **Sem adjetivo de propaganda.** Nada de "poderoso", "inovador", "robusto" como elogio, "notável",
   "impressionante". Diga o número. ("Robustez" no sentido técnico do teste de leituras continua valendo.)
4. **Sem travessão.** Nem "—" nem "–" nem " - ". Reescreva com vírgula, dois-pontos, parênteses ou duas frases.
   Faixas numéricas usam "a" ("de 31 a 59") ou duas macros.
5. **Toda afirmação tem uma citação ou uma macro de número.** Afirmação sobre a literatura: `\cite{chave}` e a
   frase precisa ter passado no `cite-check`. Afirmação sobre os resultados: a macro (`\accGraphTools`).
   Afirmação sobre o método: aponte o arquivo ou a seção. Sem nenhum dos três, corte ou marque `% TODO fonte`.
6. **Nenhum número digitado.** Use a macro (skill `paper-numbers`). Número por extenso só para contagem que não
   vem dos resultados ("duas condições").
7. **Glossário fixo** (`paper/glossary.tsv`): braço, degrau, primeiro contato, gabarito, execução, repetição,
   acerto, consulta, ferramentas prontas, abstenção. Um conceito, um termo, no artigo inteiro. Se faltar um
   termo, acrescente no glossário antes de usar.
8. **Força da conclusão proporcional à evidência.** Com uma repetição por pergunta: "indica", "sugere",
   "é compatível com". "Demonstra" e "prova" só com o teste (`\mc...PHolm` abaixo de 0,05) e com as repetições.
   "Significativa" só para diferença testada. Correlação não vira causa: o texto compara braços, não explica
   por que o modelo errou, a menos que mostre o trace.
9. **Limites ditos onde se aplicam,** não só em "Ameaças": a assimetria de ajuste na comparação entre
   `text_to_cypher` e `graph_tools`; "uma partida, um modelo" ao generalizar.
10. **Nomes de braços e código em `\texttt{}`.** Frases curtas. Um parágrafo, uma ideia.

## Padrões de frase

| Em vez de | Escreva |
|---|---|
| "Nosso método supera os demais" | "O `graph_tools` acertou \accGraphTools{} das perguntas com resposta, contra \accEventsInPrompt{} do `events_in_prompt`." |
| "O grafo é mais robusto" | "A diferença entre os braços concentra-se nas jogadas (\accPlaysGraphTools{} contra \accPlaysTextToCypher{})." |
| "Resultado notável de 87%" | "Acerto de \accGraphTools{} (IC 95\%: \ciLowGraphTools{} a \ciHighGraphTools{})." |
| "Isso mostra que ferramentas são melhores" | "Isso é compatível com a hipótese de que ferramentas prontas ajudam onde escondem lógica difícil." |
| "— que é o caso aqui —" | "(o caso aqui)" ou duas frases |

## Ao revisar

Leia o trecho, rode o lint, depois verifique à mão o que o lint não alcança: cada frase tem fonte? o tempo
verbal está certo? a conclusão cabe na evidência? o limite relevante está dito? Entregue a lista de mudanças
curta, com o motivo de cada uma.
