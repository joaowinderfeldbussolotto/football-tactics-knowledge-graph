"""Gera apresentacao/apresentacao.pptx (16:9, 15 slides) para abrir no Google Slides.

Todo número de resultado é lido de paper/generated/numbers.tex e paper/generated/tables/*.tex.
Nenhuma chamada a modelo. Uso: python apresentacao/build_deck.py
"""
import re
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "paper" / "generated"
OUT = Path(__file__).resolve().parent / "apresentacao.pptx"

# ---------- números ----------
MACROS = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", (GEN / "numbers.tex").read_text()))


def m(name):
    """Valor de uma macro como texto (sem barras)."""
    return MACROS[name].replace("\\%", "%").replace("\\", "")


def mi(name):
    return int(re.sub(r"\D", "", MACROS[name]))


ARMS = ["NoContext", "StatsInPrompt", "Vector", "EventsInPrompt", "TextToCypher", "GraphTools"]
MODELS = ["Haiku", "Qwen", "Sonnet", "Kimi"]
ARM_NAME = {a: m("arm" + a) for a in ARMS}


def parse_cost():
    rows, block = {}, None
    for line in (GEN / "tables" / "cost_models.tex").read_text().splitlines():
        if "multicolumn" in line:
            block = re.search(r"textit\{(.*?)\}", line).group(1)
        elif "&" in line and not line.startswith("Abordagem"):
            cells = [c.strip(" \\") for c in line.replace("\\\\", "").split("&")]
            rows[(block, cells[0])] = cells[1:]
    return rows


def parse_groups():
    out = {}
    for line in (GEN / "tables" / "groups_models.tex").read_text().splitlines():
        if "/" in line and "&" in line:
            cells = [c.strip(" \\") for c in line.replace("\\\\", "").split("&")]
            out[cells[0]] = (int(cells[1]), [list(map(int, c.split("/"))) for c in cells[2:]])
    return out


COST = parse_cost()
GROUPS = parse_groups()

# ---------- visual ----------
W, H = Inches(13.333), Inches(7.5)
INK = RGBColor(0x22, 0x22, 0x22)
MUTED = RGBColor(0x66, 0x66, 0x66)
LINE = RGBColor(0xD0, 0xD0, 0xD0)
PANEL = RGBColor(0xF2, 0xF2, 0xF2)
ACCENT = RGBColor(0x1F, 0x5C, 0x99)
ACCENT_BG = RGBColor(0xE6, 0xEE, 0xF6)
GRAYS = [RGBColor(0xDA, 0xDA, 0xDA), RGBColor(0xC0, 0xC0, 0xC0), RGBColor(0xA6, 0xA6, 0xA6),
         RGBColor(0x8C, 0x8C, 0x8C), RGBColor(0x5E, 0x5E, 0x5E)]
FONT = "Arial"
TOTAL = 15

prs = Presentation()
prs.slide_width, prs.slide_height = W, H


def run(p, text, size, bold=False, color=INK):
    r = p.add_run()
    r.text = text
    r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
    r.font.color.rgb = color
    return r


def textbox(slide, x, y, w, h, paras, size=20, color=INK, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, gap=6):
    """paras: lista de str ou de (str, dict(bold, size, color))."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    for i, para in enumerate(paras):
        text, o = (para, {}) if isinstance(para, str) else para
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(gap)
        run(p, text, o.get("size", size), o.get("bold", False), o.get("color", color))
    return tb


def bullets(slide, x, y, w, h, items, size=20, gap=10):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        run(p, "• ", size, True, ACCENT)
        if isinstance(it, tuple):
            run(p, it[0], size, True)
            run(p, it[1], size)
        else:
            run(p, it, size)
    return tb


def panel(slide, x, y, w, h, fill=PANEL, line=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line:
        s.line.color.rgb = line
        s.line.width = Pt(1.5)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    return s


def new_slide(n, title, notes, kicker=None):
    s = prs.slides.add_slide(prs.slide_layouts[5])  # Title Only: dá o título ao índice do Slides
    t = s.shapes.title
    t.left, t.top, t.width, t.height = Inches(0.7), Inches(0.4), Inches(11.9), Inches(1.1)
    tf = t.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run(p, title, 30, True)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0.4), Inches(0.28), Inches(0.9))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    textbox(s, 11.9, 7.0, 1.2, 0.35, [f"{n} / {TOTAL}"], size=12, color=MUTED, align=PP_ALIGN.RIGHT)
    if kicker:
        textbox(s, 0.7, 7.0, 10, 0.35, [kicker], size=12, color=MUTED)
    s.notes_slide.notes_text_frame.text = notes
    return s


def table(slide, x, y, w, h, data, col_w=None, size=14, header=True, hl_col=None, left=False):
    rows, cols = len(data), len(data[0])
    gt = slide.shapes.add_table(rows, cols, Inches(x), Inches(y), Inches(w), Inches(h))
    tbl = gt.table
    tblPr = gt._element.graphic.graphicData.tbl.tblPr
    tblPr.set("firstRow", "0")
    tblPr.set("bandRow", "0")
    if col_w:
        for i, cw in enumerate(col_w):
            tbl.columns[i].width = Inches(cw)
    for r in range(rows):
        for c in range(cols):
            cell = tbl.cell(r, c)
            cell.fill.solid()
            head = header and r == 0
            cell.fill.fore_color.rgb = INK if head else (ACCENT_BG if hl_col is not None and c == hl_col else (PANEL if r % 2 == 0 else RGBColor(255, 255, 255)))
            tf = cell.text_frame
            tf.word_wrap = True
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if (c == 0 or left) else PP_ALIGN.CENTER
            run(p, str(data[r][c]), size, bold=head or c == 0, color=RGBColor(255, 255, 255) if head else INK)
    return tbl


def style_chart(chart, colors, legend=True, size=12, labels=True, maxv=100):
    chart.font.name, chart.font.size = FONT, Pt(size)
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)
    va = chart.value_axis
    va.maximum_scale, va.minimum_scale, va.major_unit = maxv, 0, 25
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = LINE
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(size)
    va.has_title = True
    va.axis_title.text_frame.text = "Acerto (%)"
    va.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(size)
    va.axis_title.text_frame.paragraphs[0].runs[0].font.bold = False
    chart.category_axis.tick_labels.font.size = Pt(size)
    chart.category_axis.format.line.color.rgb = LINE
    plot = chart.plots[0]
    plot.gap_width, plot.overlap = 60, -5
    for ser, col in zip(plot.series, colors):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = col
        if labels:
            ser.data_labels.show_value = True
            ser.data_labels.number_format = "0"
            ser.data_labels.number_format_is_linked = False
            ser.data_labels.font.size = Pt(size - 2)
            ser.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END


MODEL_LABEL = {"Haiku": "Haiku 5.5 (menor)", "Qwen": "Qwen3.8-flash (menor)",
               "Sonnet": "Sonnet 4.6 (maior)", "Kimi": "Kimi K3 (maior)"}

# ============ slides ============
# 1 capa
s = prs.slides.add_slide(prs.slide_layouts[6])
panel(s, 0, 0, 13.333, 7.5, fill=INK)
panel(s, 0.7, 2.0, 0.12, 2.6, fill=ACCENT)
textbox(s, 1.1, 1.9, 11, 2.4,
        [("Aprendizado em contexto com dados de eventos de futebol", {"size": 40, "bold": True, "color": RGBColor(255, 255, 255)}),
         ("uma comparação de seis abordagens", {"size": 28, "color": RGBColor(0xDD, 0xDD, 0xDD)})], gap=10)
textbox(s, 1.1, 4.9, 11, 1.4,
        [("Daniel Alfredo Quiteque e João Victor Winderfeld Bussolotto", {"size": 20, "color": RGBColor(255, 255, 255)}),
         ("Pós-graduação em Inteligência Artificial Aplicada, UniSENAI", {"size": 16, "color": RGBColor(0xBB, 0xBB, 0xBB)}),
         ("AV2, 2026", {"size": 16, "color": RGBColor(0xBB, 0xBB, 0xBB)})], gap=4)
s.notes_slide.notes_text_frame.text = (
    "[0:15] Apresentação dos autores e do título. Em uma frase: o trabalho compara seis maneiras de dar a um modelo de "
    "linguagem acesso aos dados de uma partida e mede qual delas acerta mais.")

# 2 problema
s = new_slide(2, "Perguntas de análise de futebol exigem ligar eventos entre si",
              "[1:00] Contexto de futebol: a final da Copa de 2022, Argentina contra França, decidida nos pênaltis. Os dados "
              "de eventos registram cada ação, com jogador, momento e posição no campo. As três perguntas do slide são do conjunto "
              "do trabalho. Nenhuma tem a resposta em um único evento: é preciso juntar vários. O modelo precisa receber os dados "
              "da partida, e há mais de uma forma de fazer isso. É isso que o trabalho compara.")
textbox(s, 0.7, 1.7, 5.6, 1.2,
        ["Dados de eventos: cada ação da partida com jogador, momento e posição no campo."], size=20)
panel(s, 0.7, 3.1, 5.6, 2.4)
textbox(s, 0.9, 3.2, 5.2, 3.3,
        [("Final da Copa do Mundo de 2022", {"bold": True, "size": 20}),
         ("Argentina e França, decidida nos pênaltis", {"size": 18}),
         (f"{m('nEvents')} eventos no JSON bruto", {"size": 18}),
         (f"{m('nActions')} ações depois da preparação", {"size": 18})], gap=10)

textbox(s, 6.8, 1.6, 5.8, 0.5, [("Exemplos de pergunta do conjunto", {"bold": True, "size": 20})])
ex = [("Quem passou para quem",
       "Qual dupla da França mais trocou passes entre si na final?"),
      ("Ordem das ações em uma jogada",
       "Qual jogador participou de mais jogadas da Argentina que terminaram em finalização?"),
      ("Antes e depois de uma substituição",
       "Depois que Dembélé foi substituído no primeiro tempo, qual companheiro mais passou a bola para Mbappé?")]
y = 2.3
for head, q in ex:
    panel(s, 6.8, y, 5.8, 1.35, fill=ACCENT_BG)
    textbox(s, 6.95, y + 0.05, 5.5, 1.3, [(head, {"bold": True, "size": 15, "color": ACCENT}), (q, {"size": 16})], gap=3)
    y += 1.5

# 3 pergunta e contribuições
s = new_slide(3, "Qual forma de levar os dados ao modelo funciona melhor?",
              "[0:45] Três perguntas de pesquisa: qual abordagem acerta mais, como o acerto muda de um modelo para outro e quanto "
              "cada uma custa em tokens e tempo. O aprendizado em contexto é usado em sentido amplo: o modelo não é treinado "
              "de novo e o que entra no contexto são os dados. Duas contribuições: o conjunto de perguntas com gabarito "
              "calculado por código fora do grafo e a comparação sob as mesmas perguntas, o mesmo prompt e a mesma saída.")
textbox(s, 0.7, 1.7, 5.9, 0.5, [("Perguntas de pesquisa", {"bold": True, "size": 22, "color": ACCENT})])
bullets(s, 0.7, 2.3, 5.9, 4.2,
        ["Qual abordagem acerta mais?",
         "Como o acerto muda de um modelo para outro?",
         "Quanto cada abordagem custa em tokens e em tempo?"], size=22, gap=16)
textbox(s, 7.0, 1.7, 5.6, 0.5, [("Contribuições", {"bold": True, "size": 22, "color": ACCENT})])
bullets(s, 7.0, 2.3, 5.6, 4.2,
        [f"Conjunto de {m('nQuestions')} perguntas sobre a final, com gabarito calculado por código, fora do grafo.",
         f"Comparação de {m('nArms')} abordagens de aprendizado em contexto, com as mesmas perguntas, o mesmo prompt e a mesma saída, em {m('nModels')} modelos.",
         "Código, perguntas e gabarito públicos."], size=20, gap=14)

# 4 dados e perguntas
s = new_slide(4, f"{m('nQuestions')} perguntas em cinco grupos, com gabarito calculado por código",
              f"[1:15] Os dados são os eventos abertos da StatsBomb, convertidos para o formato SPADL e enriquecidos com colunas "
              f"de contexto (zona, fase de posse, placar). A disputa de pênaltis fica fora. Das {m('nQuestions')} perguntas, "
              f"{m('nAnswerable')} têm resposta nos dados e {m('nControl')} são de controle: a resposta certa é a ausência de dados, "
              "como a distância percorrida por um jogador. As perguntas de busca e contagem são diretas. Os outros três grupos "
              "são encadeados: dependem de ligar eventos entre si. O gabarito é calculado por código sem passar pelo grafo.")
rows = [["Grupo", "n", "Exemplo (resposta esperada)"],
        ["Busca e contagem", m("nGroupSearch"), "Quem recebeu o primeiro cartão amarelo da final? (jogador)"],
        ["Relações na rede de passes", m("nGroupRelations"), "Qual dupla da França mais trocou passes entre si? (conjunto de jogadores)"],
        ["Jogadas e sequências", m("nGroupPlays"), "Qual jogador participou de mais jogadas da Argentina que terminaram em finalização? (jogador)"],
        ["Antes e depois de uma substituição", m("nGroupMoments"), "Depois que Dembélé saiu, qual companheiro mais passou a bola para Mbappé? (jogador)"],
        ["Controle", m("nGroupControl"), "Qual foi a distância total percorrida por Rodrigo De Paul? (ausência de dados)"]]
table(s, 0.7, 1.7, 11.9, 4.3, rows, col_w=[3.4, 0.7, 7.8], size=16, left=True)
textbox(s, 0.7, 6.2, 11.9, 0.7,
        [f"Dados: eventos abertos da StatsBomb, convertidos para SPADL. {m('nEvents')} eventos viram {m('nActions')} ações. "
         f"{m('nAnswerable')} perguntas com resposta e {m('nControl')} de controle."], size=15, color=MUTED)

# 5 seis abordagens
s = new_slide(5, "Seis abordagens, da ausência de dados à consulta ao grafo",
              "[1:45] Ordem de complexidade do que existe entre a pergunta e o modelo. Sem dados: só a pergunta, linha de base. "
              f"Contexto longo: a tabela inteira de {m('nActions')} ações no prompt. Estatísticas resumidas: a súmula, com totais por "
              f"jogador e por time. Busca vetorial: as {m('nTopK')} linhas mais parecidas com a pergunta, como em geração aumentada por "
              "recuperação. Consulta escrita pelo modelo: o modelo recebe o esquema do grafo e escreve a consulta Cypher. "
              f"Ferramentas sobre o grafo: {m('nTools')} ferramentas com a consulta já escrita; o modelo só escolhe qual chamar e "
              "com quais argumentos. Todas usam o mesmo prompt de sistema e a mesma saída estruturada.")
rows = [["Abordagem", "O que o modelo recebe"],
        [ARM_NAME["NoContext"], "só a pergunta (linha de base)"],
        [ARM_NAME["EventsInPrompt"], f"a tabela com as {m('nActions')} ações, inteira, no prompt"],
        [ARM_NAME["StatsInPrompt"], "a súmula: totais por jogador e por time"],
        [ARM_NAME["Vector"], f"as {m('nTopK')} linhas mais parecidas com a pergunta (embeddings)"],
        [ARM_NAME["TextToCypher"], "o esquema do grafo e o resultado da consulta que o modelo escreveu"],
        [ARM_NAME["GraphTools"], f"o resultado de {m('nTools')} ferramentas com consulta fixa, que o modelo chama"]]
t = table(s, 0.7, 1.7, 11.9, 4.6, rows, col_w=[4.2, 7.7], size=19, left=True)
for c in range(2):
    t.cell(6, c).fill.fore_color.rgb = ACCENT_BG

# 6 consulta x ferramentas
s = new_slide(6, "Mesmo grafo, mesmo limite de chamadas: muda quem escreve a consulta",
              f"[1:15] As duas abordagens com agente consultam o mesmo grafo e têm o mesmo limite de {m('nMaxCalls')} chamadas por "
              "pergunta. Na Consulta escrita pelo modelo, ele escreve a consulta Cypher, com os filtros de time, tipo de ação e "
              "terço do campo. Nas Ferramentas, a consulta já está no código e o modelo só preenche argumentos. Duas diferenças a "
              "declarar: a Consulta não tem a biblioteca de algoritmos de grafos nem os nós de padrões prontos; e as ferramentas "
              "foram ajustadas olhando erros, enquanto a Consulta é o primeiro contato.")


def flow(slide, y, label, middle, accent=False):
    boxes = [("Pergunta", PANEL), ("Modelo (agente)", PANEL), (middle, ACCENT_BG if accent else PANEL), ("Grafo Neo4j", PANEL)]
    x = 0.7
    textbox(slide, x, y - 0.55, 8, 0.45, [(label, {"bold": True, "size": 18, "color": ACCENT if accent else INK})])
    for i, (txt, fill) in enumerate(boxes):
        b = panel(slide, x, y, 2.55, 1.0, fill=fill, line=ACCENT if (accent and i == 2) else None)
        tf = b.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run(p, txt, 15, i == 2)
        if i < 3:
            textbox(slide, x + 2.55, y + 0.25, 0.5, 0.5, ["→"], size=24, color=MUTED, align=PP_ALIGN.CENTER)
        x += 3.1


flow(s, 2.3, ARM_NAME["TextToCypher"], "O modelo escreve a consulta Cypher")
flow(s, 4.3, ARM_NAME["GraphTools"], "Ferramenta com consulta fixa", accent=True)
textbox(s, 0.7, 5.7, 11.9, 1.2,
        [f"Limite de {m('nMaxCalls')} chamadas por pergunta nas duas. A Consulta não tem a biblioteca de algoritmos (GDS) nem os nós de padrões prontos.",
         "As Ferramentas foram ajustadas olhando erros; a Consulta é o primeiro contato."], size=16, color=MUTED)

# 7 setup
s = new_slide(7, f"{m('nModels')} modelos em duas faixas, {m('nRuns')} execuções por modelo",
              f"[1:00] Quatro modelos, dois menores e dois maiores, agrupados pela faixa de preço por token, já que nem todo fabricante "
              f"divulga o número de parâmetros. Em cada grupo há um modelo de código fechado e um de pesos abertos. Os menores rodaram "
              f"sem raciocínio estendido e com temperatura zero; os maiores, com raciocínio estendido ligado. São {m('nQuestions')} "
              f"perguntas em {m('nArms')} abordagens: {m('nRuns')} execuções por modelo, com {m('nRepeats')} repetição por pergunta. "
              "Acerto com intervalo de Wilson de 95%. Ponto de honestidade: como é uma repetição, as diferenças são lidas como indícios.")
panel(s, 0.7, 1.8, 5.8, 3.6)
textbox(s, 0.9, 1.9, 5.4, 3.4,
        [("Modelos menores", {"bold": True, "size": 20, "color": ACCENT}),
         (f"{m('modelHaiku')} e {m('modelQwen')}", {"size": 18}),
         ("sem raciocínio estendido, temperatura zero", {"size": 16, "color": MUTED}),
         ("Modelos maiores", {"bold": True, "size": 20, "color": ACCENT}),
         (f"{m('modelSonnet')} e {m('modelKimi')}", {"size": 18}),
         ("com raciocínio estendido", {"size": 16, "color": MUTED})], gap=8)
bullets(s, 7.0, 1.8, 5.6, 4.5,
        [f"{m('nQuestions')} perguntas × {m('nArms')} abordagens = {m('nRuns')} execuções por modelo",
         f"{m('nRepeats')} repetição por pergunta",
         "Acerto com intervalo de Wilson de 95%",
         "Diferenças lidas como indícios, não como demonstração"], size=19, gap=14)

# 8 resultado 1
s = new_slide(8, f"Ferramentas sobre o grafo: {m('accRangeGraphTools')} de acerto nos {m('nModels')} modelos",
              f"[2:15] Acerto nas {m('nAnswerable')} perguntas com resposta. A barra azul é Ferramentas sobre o grafo: "
              f"{m('accRangeGraphTools')} em todos os modelos. Consulta escrita pelo modelo: {m('accRangeLowTextToCypher')} nos menores e "
              f"{m('accRangeHighTextToCypher')} nos maiores. Contexto longo: {m('accRangeLowEventsInPrompt')} nos menores e "
              f"{m('accRangeHighEventsInPrompt')} nos maiores. As outras três ficam baixas: Busca vetorial {m('accRangeVector')}, "
              f"Estatísticas resumidas {m('accRangeStatsInPrompt')}, e Sem dados {m('accRangeNoContext')}, porque se abstém. "
              "Nos maiores, Consulta empata com Ferramentas no Sonnet e fica à frente no Kimi; os intervalos se sobrepõem.",
              kicker=f"Acerto nas {m('nAnswerable')} perguntas com resposta, uma repetição por pergunta.")
cd = CategoryChartData()
cd.categories = [MODEL_LABEL[x] for x in MODELS]
for a in ARMS:
    cd.add_series(ARM_NAME[a], [mi(f"acc{x}{a}") for x in MODELS])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.5), Inches(12.3), Inches(5.4), cd)
style_chart(gf.chart, GRAYS + [ACCENT], size=13)

# 9 resultado 2: encadeadas
chain = ["Relações", "Jogadas", "Momento"]
n_chain = sum(GROUPS[g][0] for g in chain)
ARM_COL = {"EventsInPrompt": 0, "TextToCypher": 1, "GraphTools": 2}


def chain_acc(model, arm):
    mi_ = MODELS.index(model)
    return round(100 * sum(GROUPS[g][1][mi_][ARM_COL[arm]] for g in chain) / n_chain)


s = new_slide(9, "Nas perguntas encadeadas, Consulta e Contexto longo dependem do modelo",
              f"[1:45] Recorte das {n_chain} perguntas encadeadas (relações na rede de passes, jogadas e antes e depois de uma "
              "substituição). Nos modelos menores, Contexto longo e Consulta caem justamente aqui, e Ferramentas se mantêm: a "
              "consulta já escrita e o cálculo no código tiram do modelo o trabalho de juntar eventos espalhados. Nos maiores, com "
              "raciocínio estendido, as três se aproximam. Ressalva: tamanho e raciocínio vieram juntos, então não dá para separar o "
              "efeito de um do outro. A interpretação é compatível com a literatura de contexto longo (informação no meio do contexto, "
              "raciocínio composicional) e com a dificuldade de LLMs em gerar Cypher.",
              kicker=f"Acerto nas {n_chain} perguntas encadeadas com resposta (soma dos grupos Relações, Jogadas e Momento).")
cd = CategoryChartData()
cd.categories = [MODEL_LABEL[x] for x in MODELS]
for a, col in [("EventsInPrompt", 0), ("TextToCypher", 1), ("GraphTools", 2)]:
    cd.add_series(ARM_NAME[a], [chain_acc(x, a) for x in MODELS])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.5), Inches(8.2), Inches(5.4), cd)
style_chart(gf.chart, [GRAYS[2], GRAYS[4], ACCENT], size=13)
panel(s, 9.0, 1.7, 3.7, 4.8)
textbox(s, 9.15, 1.8, 3.4, 4.6,
        [("Leitura", {"bold": True, "size": 18, "color": ACCENT}),
         ("Ferramentas: a consulta já vem escrita e o cálculo fica no código.", {"size": 15}),
         ("Consulta: o modelo escreve o Cypher; o acerto acompanha essa capacidade.", {"size": 15}),
         ("Contexto longo: o modelo acha e combina as linhas certas na tabela inteira.", {"size": 15})], gap=10)

# 10 por que as outras ficam baixas
s = new_slide(10, "Busca vetorial, Estatísticas resumidas e Sem dados ficam baixas por motivos diferentes",
              f"[1:15] Busca vetorial ({m('accRangeVector')}): traz as {m('nTopK')} linhas mais parecidas com a pergunta, de "
              f"{m('nActions')}. Parecer com a pergunta não é servir para respondê-la; contar exige todas as linhas de um tipo e "
              "ligar eventos exige as linhas vizinhas. Erra por abstenção e por resposta errada, conforme o modelo. Estatísticas "
              f"resumidas ({m('accRangeStatsInPrompt')}): a súmula tem só totais da partida inteira, sem recorte de tempo ou de campo "
              "e sem quem passou para quem; como o prompt pede para indicar ausência de dados, os modelos se abstêm. Sem dados: "
              f"0 de {m('nAnswerable')} com resposta, por obediência ao prompt, que proíbe responder de memória; o 0% mede obediência, "
              f"não ignorância. Nas perguntas de controle, Sem dados acerta as {m('nControl')}.")
cards = [(ARM_NAME["Vector"], m("accRangeVector"),
          f"Traz as {m('nTopK')} linhas mais parecidas com a pergunta, de {m('nActions')}. Contar exige todas as linhas de um tipo e ligar eventos exige as vizinhas."),
         (ARM_NAME["StatsInPrompt"], m("accRangeStatsInPrompt"),
          "A súmula tem totais da partida inteira, sem recorte de tempo ou de campo e sem quem passou para quem. Os modelos se abstêm."),
         (ARM_NAME["NoContext"], m("accRangeNoContext"),
          f"Se abstém nas {m('nAnswerable')} perguntas com resposta: o prompt proíbe responder de memória. Mede obediência.")]
x = 0.7
for head, val, txt in cards:
    panel(s, x, 1.9, 3.8, 4.6)
    textbox(s, x + 0.15, 2.0, 3.5, 4.4,
            [(head, {"bold": True, "size": 20}), (val, {"bold": True, "size": 34, "color": ACCENT}),
             ("acerto", {"size": 13, "color": MUTED}), (txt, {"size": 18})], gap=10)
    x += 4.05

# 11 custo
s = new_slide(11, "Contexto longo nos modelos maiores custa milhares de tokens de saída e dezenas de segundos",
              f"[1:30] Mediana por execução das três abordagens que leem os dados. O Contexto longo leva a tabela inteira em cada "
              f"pergunta, de {m('inRangeEventsInPrompt')} mil tokens de entrada. Nos maiores, produz de {m('outRangeHighEventsInPrompt')} "
              f"tokens de saída, quase todos de raciocínio, e leva de {m('latRangeHighEventsInPrompt')} segundos. Cuidado ao comparar: "
              "Ferramentas não usa cache de prompt e Consulta usa, então a latência mistura as duas condições; no Contexto longo, a "
              "maior parte da entrada veio do cache, o que o favorece. Sem preço em dólar, porque os preços mudam.",
              kicker="Mediana por execução. Os tokens de entrada incluem os lidos do cache do prompt.")
arms3 = ["Contexto", "Consulta", "Ferramentas"]
hdr = ["", "Haiku 5.5", "Qwen3.8-flash", "Sonnet 4.6", "Kimi K3"]
data = [["Abordagem / medida", "Haiku 5.5", "Qwen3.8-flash", "Sonnet 4.6", "Kimi K3"]]
for blk, lab in [("Tokens de saída (mil)", "saída (mil tokens)"), ("Latência (s)", "latência (s)"), ("Tokens de entrada (mil)", "entrada (mil tokens)")]:
    for a in arms3:
        data.append([f"{a}, {lab}"] + COST[(blk, a)])
t = table(s, 0.7, 1.7, 11.9, 4.9, data, col_w=[4.7, 1.8, 1.9, 1.7, 1.8], size=14)
for r in range(1, len(data)):
    if data[r][0].startswith("Ferramentas"):
        for c in range(5):
            t.cell(r, c).fill.fore_color.rgb = ACCENT_BG

# 12 limitações
s = new_slide(12, "Os resultados valem para uma partida, uma repetição e perguntas dentro da cobertura das ferramentas",
              f"[1:15] Cinco limitações, ditas pelo próprio artigo. Uma partida e {m('nRepeats')} repetição por pergunta, com "
              f"{m('nAnswerable')} perguntas com resposta: os intervalos são largos. Tamanho e raciocínio estendido vieram juntos "
              "nos maiores. As ferramentas e as perguntas foram escritas pelos mesmos autores, e as ferramentas foram ajustadas "
              "olhando erros do Haiku: o acerto de Ferramentas vale para perguntas dentro da cobertura delas. A comparação com a "
              "Consulta é, portanto, o teto do ganho de engenharia. As abordagens com agente supõem modelo que chame ferramentas de "
              "forma confiável. E o ganho pode vir das ferramentas, do grafo ou dos algoritmos de grafo; separar isso é trabalho futuro.")
bullets(s, 0.7, 1.7, 11.9, 5.0,
        [("Uma partida e uma repetição ", f"por pergunta; {m('nAnswerable')} perguntas com resposta e intervalos largos."),
         ("Tamanho e raciocínio vieram juntos ", "nos modelos maiores; não dá para separar os dois efeitos."),
         ("Ferramentas e perguntas dos mesmos autores. ", "O acerto de Ferramentas vale dentro da cobertura delas, e elas foram ajustadas olhando erros."),
         ("Ferramentas, grafo ou algoritmos de grafo? ", "Separar os três é trabalho futuro."),
         ("Agentes supõem chamada de ferramenta confiável, ", "e esse suporte varia entre modelos e provedores.")], size=23, gap=18)

# 13 conclusão
s = new_slide(13, "Só as Ferramentas sobre o grafo mantiveram o acerto alto em todos os modelos",
              f"[1:00] Três mensagens. Primeira: Ferramentas sobre o grafo foi a única que manteve o acerto alto nos {m('nModels')} "
              f"modelos, {m('accRangeGraphTools')}. Segunda: Consulta e Contexto longo dependem do modelo; nos maiores, com raciocínio "
              "estendido, a Consulta chegou ao mesmo nível e o Contexto longo se aproximou, este com mais tokens de saída e tempo. "
              "Terceira: Busca vetorial e Estatísticas resumidas ficaram baixas em todos. Em uma frase: a forma de levar os dados ao "
              "modelo pesa tanto quanto o modelo.")
rows = [("Ferramentas sobre o grafo", f"{m('accRangeGraphTools')} em todos os modelos"),
        ("Consulta escrita pelo modelo", f"{m('accRangeLowTextToCypher')} nos menores; {m('accRangeHighTextToCypher')} nos maiores"),
        ("Contexto longo", f"{m('accRangeLowEventsInPrompt')} nos menores; {m('accRangeHighEventsInPrompt')} nos maiores, com mais tokens de saída e tempo"),
        ("Busca vetorial", m("accRangeVector")),
        ("Estatísticas resumidas", m("accRangeStatsInPrompt")),
        ("Sem dados", f"0 de {m('nAnswerable')}: se abstém")]
y = 1.7
for i, (a, b) in enumerate(rows):
    hl = i == 0
    panel(s, 0.7, y, 11.9, 0.75, fill=ACCENT_BG if hl else PANEL)
    textbox(s, 0.9, y + 0.1, 4.6, 0.6, [(a, {"bold": True, "size": 18})], anchor=MSO_ANCHOR.MIDDLE)
    textbox(s, 5.5, y + 0.1, 7.0, 0.6, [(b, {"size": 18, "bold": hl, "color": ACCENT if hl else INK})], anchor=MSO_ANCHOR.MIDDLE)
    y += 0.85

# 14 indústria
s = new_slide(14, "Próximo passo: testar as mesmas abordagens em dados industriais",
              "[1:30] Fecho. Parte dos dados industriais tem a forma dos dados de futebol: registros de eventos com agente, momento "
              "e local, ligados entre si, como as paradas, os alertas e as movimentações de uma linha de produção ou de uma frota. "
              "Como o resultado do futebol mostra que a forma de levar os dados ao contexto pesa tanto quanto o modelo, testar as seis "
              "abordagens nesses dados é o passo natural para uma pós em IA aplicada à indústria. O que não transfere de graça: a "
              "preparação dos dados, o grafo e as ferramentas dependem das perguntas que se quer responder, então exige implementação "
              "própria para o domínio. A tabela de correspondência é uma proposta de analogia, não um resultado.")
rows = [["No futebol", "Em dados industriais (proposta)"],
        ["Jogador", "máquina, operador ou veículo"],
        ["Minuto da partida", "carimbo de tempo do registro"],
        ["Zona do campo", "posto, linha ou rota"],
        ["Passe entre dois jogadores", "evento que liga dois agentes (parada, alerta, movimentação)"],
        ["Jogada: sequência de ações", "sequência de eventos até uma parada ou falha"]]
table(s, 0.7, 1.7, 7.4, 4.2, rows, col_w=[3.0, 4.4], size=17, left=True)
panel(s, 8.4, 1.7, 4.2, 4.2, fill=ACCENT_BG)
textbox(s, 8.55, 1.8, 3.9, 4.0,
        [("O que testar", {"bold": True, "size": 20, "color": ACCENT}),
         (f"As {m('nArms')} abordagens, nos mesmos moldes.", {"size": 17}),
         ("Exige preparação dos dados, grafo e ferramentas próprios do domínio.", {"size": 17}),
         ("A forma de levar os dados ao modelo pode pesar tanto quanto pesou no futebol.", {"size": 17})], gap=10)
textbox(s, 0.7, 6.1, 11.9, 0.7,
        ["Também: várias partidas, repetições, modelos maiores sem raciocínio estendido, ferramentas sobre tabela e busca vetorial com eventos vizinhos."],
        size=14, color=MUTED)

# 15 perguntas
s = prs.slides.add_slide(prs.slide_layouts[6])
panel(s, 0, 0, 13.333, 7.5, fill=INK)
panel(s, 0.7, 2.4, 0.12, 1.6, fill=ACCENT)
textbox(s, 1.1, 2.3, 11, 1.8, [("Perguntas", {"size": 54, "bold": True, "color": RGBColor(255, 255, 255)})])
textbox(s, 1.1, 4.4, 11, 1.8,
        [("Código, perguntas e gabarito:", {"size": 18, "color": RGBColor(0xBB, 0xBB, 0xBB)}),
         ("github.com/joaowinderfeldbussolotto/football-tactics-knowledge-graph", {"size": 20, "color": RGBColor(255, 255, 255)})], gap=6)
s.notes_slide.notes_text_frame.text = (
    "Slides de apoio não foram incluídos para respeitar o limite de 15. As respostas às perguntas prováveis estão em "
    "apresentacao/perguntas-banca.md.")

prs.save(OUT)
print("salvo", OUT, len(prs.slides), "slides")
