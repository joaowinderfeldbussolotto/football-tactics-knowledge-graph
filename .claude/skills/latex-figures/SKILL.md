---
name: latex-figures
description: Padrão de figura do artigo (largura da coluna do template, fonte do tamanho do texto, cinza com um único destaque, PDF vetorial) e como criar ou alterar figuras em scripts/figures.py. Use ao criar, alterar ou revisar qualquer figura, gráfico ou diagrama do artigo, ou quando o autor pedir "faça a figura" ou "ajuste o gráfico ao template".
---

# Figuras do artigo

Todas as figuras de dados saem de `scripts/figures.py`, a partir dos resultados versionados, para PDF vetorial em
`paper/generated/figures/`. Nenhuma é desenhada à mão nem exportada de uma planilha.

## O padrão

1. **Largura do template.** `paper/template.json` guarda `column_width_in`, `text_width_in` (figura que ocupa
   as duas colunas), `text_font_pt` e a família da fonte. A figura é criada **no tamanho em que entra** no
   artigo e incluída sem escala (`\includegraphics{...}` sem `width`, ou `width=\columnwidth` só se o PDF já
   tem essa largura). Enquanto `confirmed` for `false`, os valores são provisórios: o script avisa.
2. **Fonte do tamanho do texto.** Rótulos, marcas, título e legenda da figura usam o mesmo corpo do texto do
   artigo (`text_font_pt`), e a mesma família (STIX, parecida com Times). Fonte menor que o texto é erro.
3. **Cinza com um destaque.** Barras e linhas em tons de cinza; **uma** cor de destaque (`ACCENT`), só no que a
   figura quer mostrar (em geral o `graph_tools`). A figura tem de se ler impressa em preto e branco: nenhuma
   informação só pela cor (use a posição, o rótulo ou o traço).
4. **Vetorial.** PDF com fontes embutidas (`pdf.fonttype` 42), sem imagens raster, sem metadados de data
   (para o arquivo não mudar a cada geração).
5. **Honestidade do eixo.** Eixo de acerto de 0 a 100; intervalo de Wilson visível quando a figura compara
   braços; $n$ no título ou na legenda quando a série muda de tamanho.
6. **Legenda no LaTeX,** não dentro da figura: o texto da legenda diz o que se vê e a unidade; a figura não
   tem título.
7. **Sem enfeite:** sem grade pesada, sem 3D, sem sombra, sem moldura; só as bordas esquerda e inferior.

## Como criar ou alterar uma figura

1. Acrescente uma função em `scripts/figures.py` que recebe `plt`, as linhas de resultado e o template, usa
   `ps.*` (módulo `paper_stats`) para os números, e termina com `save(fig, "fN_nome.pdf")`.
2. Rode `python scripts/figures.py`. **Olhe o resultado:** converta o PDF em imagem
   (`pymupdf.open(path)[0].get_pixmap(dpi=110).save("x.png")`) e leia a imagem; confira sobreposição de
   texto, legenda cobrindo barras, rótulo cortado.
3. Inclua no texto: `\begin{figure}\includegraphics{f2_ladder}\caption{...}\label{fig:escada}\end{figure}`
   (o `\graphicspath` já aponta para `generated/figures/`). Cite com `\ref`.
4. Diagramas que não vêm de dados (arquitetura F1, escada conceitual) ficam em TikZ no próprio `.tex`, com as
   mesmas regras de fonte e cor, ou em PDF vetorial exportado e versionado em `paper/figures/`.

## Figuras previstas (dossiê)

F2 escada (acerto dos seis braços em ordem de lógica pronta, com IC), F3 acerto por grupo, F4 trajetória de
ajuste (**ler `paper/ALERTAS.md`, item 1, antes de descrevê-la**: as séries não sobem de forma contínua), F1
arquitetura (a fazer), F5 exemplo de robustez (tabela). A apresentação reaproveita F1 a F4.
