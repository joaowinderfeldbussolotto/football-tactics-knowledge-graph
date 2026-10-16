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
         ("Pós-graduação em Inteligência Artificial Aplicada, UniSENAI", {"size": 16, "color": RGBColor(0xBB, 0xBB, 0xBB)})], gap=4)
s.notes_slide.notes_text_frame.text = (
    "[0:15] Apresentação dos autores e do título. Em uma frase: o trabalho compara seis maneiras de dar a um modelo de "
    "linguagem acesso aos dados de uma partida e mede qual delas acerta mais.")


# 2 problema e pergunta de pesquisa
s = new_slide(2, "Perguntas de futebol exigem ligar eventos: qual forma de dar os dados ao modelo funciona melhor?",
              "[1:15] Contexto de futebol: a final da Copa de 2022, Argentina contra França, decidida nos pênaltis. Os dados de "
              "eventos registram cada ação, com jogador, momento e posição no campo. As três perguntas do slide são do conjunto do "
              "trabalho e nenhuma tem a resposta em um único evento: é preciso juntar vários. O modelo precisa receber os dados da "
              "partida, e há mais de uma forma de fazer isso. Perguntas de pesquisa: qual abordagem acerta mais, como o acerto muda de "
              "um modelo para outro e quanto cada uma custa em tokens e tempo. O aprendizado em contexto é usado em sentido amplo: o "
              "modelo não é treinado de novo e o que entra no contexto são os dados. Contribuições: o conjunto de perguntas com "
              "gabarito por código e a comparação sob as mesmas perguntas, o mesmo prompt e a mesma saída. Trabalhos relacionados: no "
              "esporte, SoccerRAG, SPORTSQL e Tzikas et al. avaliam cada um uma única forma de recuperação; fora do esporte, Li et al. e "
              "LOFT comparam formas de recuperação sem dados de futebol. Não foram encontrados trabalhos que comparem formas de "
              "recuperação em perguntas encadeadas sobre eventos de futebol, com conferência por código contra um gabarito por código.")
textbox(s, 0.7, 1.75, 5.6, 0.5, [("Perguntas de pesquisa", {"bold": True, "size": 20, "color": ACCENT})])
bullets(s, 0.7, 2.3, 5.6, 2.3,
        ["Qual abordagem acerta mais?",
         "Como o acerto muda de um modelo para outro?",
         "Quanto cada abordagem custa em tokens e em tempo?"], size=18, gap=8)
panel(s, 0.7, 4.4, 5.6, 1.9)
textbox(s, 0.85, 4.43, 5.3, 1.85,
        [("Contribuições", {"bold": True, "size": 16, "color": ACCENT}),
         (f"{m('nQuestions')} perguntas sobre a final, com gabarito calculado por código, fora do grafo.", {"size": 15}),
         (f"Comparação de {m('nArms')} abordagens com as mesmas perguntas, o mesmo prompt e a mesma saída, em {m('nModels')} modelos.", {"size": 15})], gap=5)
textbox(s, 6.8, 1.75, 5.8, 0.5, [("Exemplos de pergunta do conjunto", {"bold": True, "size": 20})])
ex = [("Quem passou para quem",
       "Qual dupla da França mais trocou passes entre si na final?"),
      ("Ordem das ações em uma jogada",
       "Qual jogador participou de mais jogadas da Argentina que terminaram em finalização?"),
      ("Antes e depois de uma substituição",
       "Depois que Dembélé foi substituído no primeiro tempo, qual companheiro mais passou a bola para Mbappé?")]
y = 2.3
for head, q in ex:
    panel(s, 6.8, y, 5.8, 1.2, fill=ACCENT_BG)
    textbox(s, 6.95, y + 0.03, 5.5, 1.15, [(head, {"bold": True, "size": 15, "color": ACCENT}), (q, {"size": 15})], gap=2)
    y += 1.35

panel(s, 0.7, 6.4, 11.9, 0.55, fill=PANEL)
textbox(s, 0.85, 6.42, 11.6, 0.5,
        ["Relacionados: no esporte, cada trabalho avalia uma única forma de recuperação (SoccerRAG, SPORTSQL, Tzikas et al.); fora dele, as formas são comparadas sem dados de futebol (Li et al., LOFT)."],
        size=12, color=INK, anchor=MSO_ANCHOR.MIDDLE)

# 3 dados: JSON bruto
s = new_slide(3, "Os dados: eventos da StatsBomb da final de 2022, em JSON",
              f"[1:30] Os dados são os eventos abertos da StatsBomb: dois arquivos, a lista de eventos da partida, em ordem, e as "
              f"escalações, com nome completo e apelido de cada jogador. São {m('nEvents')} eventos no JSON bruto. O exemplo é o gol de "
              "Di María e o passe de Mac Allister que o precede, resumidos aos campos principais (valores de docs/02 e da Figura 1 do "
              "artigo, não recalculados nesta sessão). Três coisas que importam depois: cada tipo de evento tem campos próprios, "
              "então o JSON é rico e irregular; a mesma informação pode estar em lugares diferentes, como o cartão amarelo, que vem "
              "dentro da falta ou, sem falta, em um evento de comportamento; e o nome é o de registro, não o apelido, e o minuto é "
              "decorrido, então o gol aos 35 aparece como 36 na transmissão.",
              kicker="Exemplo resumido: o passe de Mac Allister e o gol de Di María (docs/02 e Figura 1 do artigo).")
panel(s, 0.7, 1.7, 7.1, 2.9, fill=RGBColor(0x2B, 0x2B, 0x2B))
code = ['{ "type": "Pass", "minute": 35, "second": 20,',
        '  "player": "Alexis Mac Allister",',
        '  "pass": { "recipient": "Ángel Fabián Di María",',
        '            "goal_assist": true } }',
        '',
        '{ "type": "Shot", "minute": 35, "second": 22,',
        '  "team": "Argentina",',
        '  "player": "Ángel Fabián Di María",',
        '  "shot": { "outcome": "Goal",',
        '            "body_part": "Left Foot" } }']
tb = s.shapes.add_textbox(Inches(0.9), Inches(1.85), Inches(6.8), Inches(3.4))
tf = tb.text_frame
tf.word_wrap = True
for i, ln in enumerate(code):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    r = p.add_run()
    r.text = ln if ln else " "
    r.font.name, r.font.size = "Courier New", Pt(12)
    r.font.color.rgb = RGBColor(0xE8, 0xE8, 0xE8)
bullets(s, 8.1, 1.7, 4.6, 5.0,
        [("Fonte: ", "StatsBomb Open Data, lista de eventos e escalações da partida."),
         (f"{m('nEvents')} eventos, ", "cada um com tipo, tempo, time, jogador e posição."),
         ("Campos próprios por tipo: ", "o passe traz o recebedor; a finalização, o resultado."),
         ("Mesma informação em lugares diferentes: ", "o cartão amarelo vem na falta ou em outro evento."),
         ("Nome de registro e minuto decorrido: ", "o gol aos 35 aparece como 36 na transmissão.")], size=16, gap=9)

# 4 JSON -> tabela de ações
s = new_slide(4, "Do JSON à tabela de ações: um vocabulário fechado, com contexto acrescentado",
              f"[1:30] Os eventos da partida, sem a disputa de pênaltis, foram convertidos com a biblioteca socceraction para o formato "
              f"SPADL, que guarda só as ações com bola, em um vocabulário fechado e com os mesmos campos em todas. Os {m('nEvents')} eventos "
              f"viram {m('nActions')} ações. Sobre essa tabela foram acrescentadas colunas de contexto: direção de ataque, zona em uma "
              f"grade de {m('nZones')} zonas, fase de posse ({m('nPhases')} fases na final), recebedor do passe, placar e minuto. É essa "
              "tabela que o Contexto longo entrega ao modelo. O SPADL perde o desfecho da finalização e o cartão sem falta, que foram "
              "recuperados do JSON. Nenhuma etapa usa modelo de linguagem.",
              kicker="Pênaltis fora da tabela. Fonte: Tabela 1 do artigo e docs/09.")
panel(s, 0.7, 1.55, 3.3, 0.85, fill=PANEL)
textbox(s, 0.8, 1.58, 3.1, 0.8, [("JSON bruto", {"bold": True, "size": 14, "color": MUTED}), (f"{m('nEvents')} eventos", {"bold": True, "size": 20})], gap=0)
textbox(s, 4.0, 1.65, 0.8, 0.7, ["→"], size=30, color=MUTED, align=PP_ALIGN.CENTER)
panel(s, 4.8, 1.55, 3.9, 0.85, fill=ACCENT_BG)
textbox(s, 4.9, 1.58, 3.7, 0.8, [("Tabela de ações (SPADL)", {"bold": True, "size": 14, "color": ACCENT}), (f"{m('nActions')} ações", {"bold": True, "size": 20})], gap=0)
textbox(s, 9.0, 1.6, 3.7, 0.8, [f"{m('nZones')} zonas, {m('nPhases')} fases de posse, {m('nPlayers')} jogadores"], size=15, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
rows = [["Transformação", "O que faz", "Motivo"],
        ["Direção de ataque", "toda ação ataca da esquerda para a direita", "mesmo sentido do campo para os dois times"],
        ["Zona, terço e corredor", "situa o início e o fim de cada ação", "localizar a ação no campo"],
        ["Recebedor do passe", "jogador do mesmo time que age em seguida", "saber quem passou para quem"],
        ["Fase de posse", "agrupa as ações seguidas do mesmo time", "identificar as jogadas"],
        ["Placar, minuto e período", "placar antes de cada ação; minuto da transmissão", "situar a ação antes ou depois de um momento"],
        ["Dados recuperados do JSON", "desfecho da finalização e cartão sem falta", "o SPADL perde essas informações"],
        ["Rótulos em português", "passe, condução, drible", "o SPADL chama a condução de dribble"]]
table(s, 0.7, 2.6, 11.9, 4.2, rows, col_w=[3.1, 4.7, 4.1], size=14, left=True)

# 5 grafo e súmula
s = new_slide(5, "Da tabela ao grafo: cada ação vira uma aresta, e a súmula é contada pelo banco",
              f"[1:15] A tabela de ações foi carregada em um grafo Neo4j. Cada ação vira uma aresta do jogador para a partida, com as "
              f"colunas da linha como propriedades; cada passe certo com recebedor vira uma aresta entre dois jogadores. O grafo tem "
              f"{m('nPlayers')} jogadores, {m('nPhases')} fases de posse e {m('nZones')} zonas. As arestas não acrescentam informação à "
              "tabela, só a reorganizam em ligações; já a súmula, com totais por jogador e por time, é calculada: o próprio banco conta "
              "os totais a partir das arestas. A abordagem Estatísticas resumidas lê só a súmula; Consulta e Ferramentas leem o grafo. "
              "Nenhuma etapa usa modelo de linguagem.",
              kicker="Esquema simplificado: Figura 2 do artigo. A camada de padrões táticos não é lida por nenhuma abordagem.")


def node(slide, x, y, w, title, sub=None, accent=False):
    b = panel(slide, x, y, w, 0.9, fill=ACCENT_BG if accent else PANEL, line=ACCENT if accent else LINE)
    tf = b.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run(p, title, 15, True)
    if sub:
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        run(p2, sub, 12, False, MUTED)
    return (x + w / 2, y + 0.45)


def edge(slide, a, b, label, lx, ly, lw=1.7):
    c = slide.shapes.add_connector(1, Inches(a[0]), Inches(a[1]), Inches(b[0]), Inches(b[1]))
    c.line.color.rgb = MUTED
    c.line.width = Pt(1.5)
    tb = textbox(slide, lx, ly, lw, 0.3, [label], size=10, color=MUTED, align=PP_ALIGN.CENTER)
    tb.fill.solid()
    tb.fill.fore_color.rgb = RGBColor(255, 255, 255)


J = (3.9, 3.75)
time_c = (1.1, 3.75)
part_c = (6.7, 3.75)
fase_c = (1.1, 5.75)
sum_c = (3.9, 5.75)
zona_c = (6.7, 5.75)
edge(s, J, time_c, "MEMBRO_DE", 1.75, 3.4, 1.2)
edge(s, J, part_c, "REALIZOU", 4.85, 3.4, 1.2)
edge(s, J, fase_c, "PARTICIPOU_DE", 1.4, 4.7, 1.6)
edge(s, J, sum_c, "TEM_ESTATISTICA", 3.2, 4.6, 1.6)
edge(s, J, zona_c, "ATUOU_EM", 5.0, 4.7, 1.2)
node(s, 0.5, 3.3, 1.2, "Time")
node(s, 3.0, 3.3, 1.8, "Jogador", f"{m('nPlayers')} na final", accent=True)
node(s, 6.1, 3.3, 1.2, "Partida")
node(s, 0.5, 5.3, 1.2, "Fase", f"{m('nPhases')}")
node(s, 3.0, 5.3, 1.8, "Súmula", "por jogador e time")
node(s, 6.1, 5.3, 1.2, "Zona", f"{m('nZones')}")
textbox(s, 1.3, 2.1, 5.2, 0.9, [("Entre jogadores: PASSOU_PARA, DEU_ASSISTENCIA, PRESSIONOU", {"size": 12, "color": MUTED}),
                                ("Entre zonas: PROGREDIU_PARA", {"size": 12, "color": MUTED})], align=PP_ALIGN.CENTER, gap=2)
bullets(s, 7.8, 1.7, 4.9, 5.0,
        [("Cada ação ", "vira uma aresta do jogador para a partida, com as colunas da linha como propriedades."),
         ("Cada passe certo com recebedor ", "vira uma aresta entre dois jogadores."),
         ("As arestas reorganizam a tabela, ", "não acrescentam informação."),
         ("A súmula é calculada: ", "o próprio banco conta os totais por jogador e por time."),
         ("Nenhuma etapa usa modelo de linguagem; ", "só o benchmark chama modelos.")], size=16, gap=9)

# 6 perguntas e gabarito
s = new_slide(6, f"{m('nQuestions')} perguntas em cinco grupos, com gabarito calculado por código",
              f"[1:15] Das {m('nQuestions')} perguntas, {m('nAnswerable')} têm resposta nos dados e {m('nControl')} são de controle: a "
              "resposta certa é a ausência de dados, como a distância percorrida por um jogador. As perguntas de busca e contagem "
              "são diretas: a resposta sai de um evento ou de uma soma. Os outros três grupos são encadeados: dependem de ligar "
              "eventos entre si. As perguntas foram escritas manualmente e o gabarito de cada uma foi calculado por código, sem "
              "passar pelo grafo, a partir do JSON bruto e da tabela de ações. A conferência com o gabarito é determinística: a "
              "mesma resposta recebe sempre o mesmo veredito.")
rows = [["Grupo", "n", "Exemplo (resposta esperada)"],
        ["Busca e contagem", m("nGroupSearch"), "Quem recebeu o primeiro cartão amarelo da final? (jogador)"],
        ["Relações na rede de passes", m("nGroupRelations"), "Qual dupla da França mais trocou passes entre si? (conjunto de jogadores)"],
        ["Jogadas e sequências", m("nGroupPlays"), "Qual jogador participou de mais jogadas da Argentina que terminaram em finalização? (jogador)"],
        ["Antes e depois de uma substituição", m("nGroupMoments"), "Depois que Dembélé saiu, qual companheiro mais passou a bola para Mbappé? (jogador)"],
        ["Controle", m("nGroupControl"), "Qual foi a distância total percorrida por Rodrigo De Paul? (ausência de dados)"]]
table(s, 0.7, 1.7, 11.9, 4.3, rows, col_w=[3.4, 0.7, 7.8], size=16, left=True)
textbox(s, 0.7, 6.2, 11.9, 0.7,
        [f"{m('nAnswerable')} perguntas com resposta e {m('nControl')} de controle. Gabarito calculado por código, fora do grafo, a partir do JSON bruto e da tabela de ações."],
        size=15, color=MUTED)

# 7 seis abordagens
s = new_slide(7, "Seis abordagens, da ausência de dados à consulta ao grafo",
              "[1:30] Ordem de complexidade do que existe entre a pergunta e o modelo. Sem dados: só a pergunta, linha de base. "
              f"Contexto longo: a tabela inteira de {m('nActions')} ações no prompt. Estatísticas resumidas: a súmula, com totais por "
              f"jogador e por time. Busca vetorial: as {m('nTopK')} linhas mais parecidas com a pergunta, como em geração aumentada por "
              "recuperação. Consulta escrita pelo modelo: o modelo recebe o esquema do grafo e escreve a consulta Cypher. "
              f"Ferramentas sobre o grafo: {m('nTools')} ferramentas com a consulta já escrita; o modelo só escolhe qual chamar e "
              f"com quais argumentos. As duas últimas consultam o mesmo grafo e têm o mesmo limite de {m('nMaxCalls')} chamadas por "
              "pergunta: muda quem escreve a consulta. Duas diferenças a declarar: a Consulta não tem a biblioteca de algoritmos "
              "de grafos nem os nós de padrões prontos, e as ferramentas foram ajustadas olhando erros, enquanto a Consulta é o "
              "primeiro contato. Todas usam o mesmo prompt de sistema e a mesma saída estruturada.")
rows = [["Abordagem", "O que o modelo recebe"],
        [ARM_NAME["NoContext"], "só a pergunta (linha de base)"],
        [ARM_NAME["EventsInPrompt"], f"a tabela com as {m('nActions')} ações, inteira, no prompt"],
        [ARM_NAME["StatsInPrompt"], "a súmula: totais por jogador e por time"],
        [ARM_NAME["Vector"], f"as {m('nTopK')} linhas mais parecidas com a pergunta (embeddings)"],
        [ARM_NAME["TextToCypher"], "o esquema do grafo e o resultado da consulta que o modelo escreveu"],
        [ARM_NAME["GraphTools"], f"o resultado de {m('nTools')} ferramentas com consulta fixa, que o modelo chama"]]
t = table(s, 0.7, 1.6, 11.9, 3.6, rows, col_w=[4.2, 7.7], size=17, left=True)
for r in (5, 6):
    for c in range(2):
        t.cell(r, c).fill.fore_color.rgb = ACCENT_BG

# 8 exemplo a01: duas formas de consultar o grafo
import json
import re as _re


def a01_calls():
    out = {}
    for line in (ROOT / "data" / "benchmark" / "final_results.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["question_id"] == "a01" and "haiku" in r["model"] and r["repeat"] == 1 and r["arm"] in ("text_to_cypher", "graph_tools"):
            out[r["arm"]] = r
    return out


A01 = a01_calls()


def cypher_lines(q):
    q = _re.sub(r"\{match_id: \d+\}", "[...]", q)
    q = _re.sub(r" AND r\.match_id = \d+", " [...]", q)
    q = _re.sub(r"\s+(WHERE|RETURN|ORDER BY|LIMIT)\s", lambda mo: "\n" + mo.group(1) + " ", q)
    q = _re.sub(r"\)-\[r:REALIZOU\]->\(", ")-[r:REALIZOU]->\n  (", q)
    q = q.replace(" AND ", "\n  AND ").replace(", count(r)", ",\n  count(r)")
    return q.split("\n")


def args_lines(a):
    f = a["filters"]
    jq = lambda v: json.dumps(v, ensure_ascii=False)
    return ["filters: {team: %s," % jq(f["team"]),
            "  action: %s, success: %s," % (jq(f["action"]), jq(f["success"]).lower()),
            "  third: %s}," % jq(f["third"]),
            "group_by: %s, metric: %s," % (jq(a["group_by"]), jq(a["metric"])),
            "top: %s" % a["top"]]


c_call = A01["text_to_cypher"]["tool_calls"][0]
g_call = A01["graph_tools"]["tool_calls"][0]
assert A01["text_to_cypher"]["answer"]["players"] == A01["graph_tools"]["answer"]["players"]
a01_answer = A01["graph_tools"]["answer"]["players"][0]
s = new_slide(8, "Mesmo grafo, duas formas de consultar: o modelo escreve a consulta ou escolhe a ferramenta",
              f"[1:15] Registro real de uma execução em cada abordagem com agente, pergunta a01, {m('modelHaiku')}. Na Consulta escrita "
              "pelo modelo, ele chama run_cypher com a consulta Cypher que escreveu, inclusive os filtros de time, ação, sucesso e "
              "terço do campo; a ferramenta executa a consulta no grafo e devolve o resultado. Nas Ferramentas sobre o grafo, o "
              "modelo escolhe query_actions e preenche os argumentos; a consulta já está no código e a ferramenta a executa com esses "
              "filtros. As duas consultam o mesmo grafo, com o mesmo limite de "
              f"{m('nMaxCalls')} chamadas por pergunta; muda quem escreve a consulta. Nesta pergunta, uma chamada bastou nas duas. "
              f"As {m('nTools')} ferramentas: listar jogadores, contar ações, listar ações, contar posses, rede de passes, métrica da "
              "rede, ligações da rede e sequências de passes. Diferenças a declarar: a Consulta não tem a biblioteca de algoritmos de "
              "grafos nem os nós de padrões prontos, e as ferramentas foram ajustadas olhando erros, enquanto a Consulta é o primeiro "
              "contato. A consulta, os argumentos e a resposta vêm de data/benchmark/final_results.jsonl; os valores devolvidos pela "
              "ferramenta (24 e 18) estão só no trace e foram copiados da figura do artigo.",
              kicker=f"Registro real ({m('modelHaiku')}, a01); trechos abreviados com [...]. Uma chamada bastou nas duas; limite de {m('nMaxCalls')} chamadas.")
panel(s, 0.7, 1.55, 11.9, 0.55, fill=ACCENT_BG)
textbox(s, 0.85, 1.58, 11.6, 0.5, [("Pergunta a01: Quem deu mais passes certos no terço final do campo pela Argentina?", {"size": 16, "bold": True})],
        anchor=MSO_ANCHOR.MIDDLE)


def code_box(slide, x, y, w, h, lines):
    panel(slide, x, y, w, h, fill=RGBColor(0x2B, 0x2B, 0x2B))
    tb = slide.shapes.add_textbox(Inches(x + 0.1), Inches(y + 0.05), Inches(w - 0.2), Inches(h - 0.1))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = ln
        r.font.name, r.font.size = "Courier New", Pt(11)
        r.font.color.rgb = RGBColor(0xE8, 0xE8, 0xE8)


tool_out = ["Lionel Andrés Messi Cuccittini: 24", "Alexis Mac Allister: 18 [...]"]
cols = [(0.7, ARM_NAME["TextToCypher"], False, "Modelo chama run_cypher com a consulta que escreveu:", cypher_lines(c_call["args"]["query"]),
         "Ferramenta executa essa consulta no grafo e devolve:"),
        (6.75, ARM_NAME["GraphTools"], True, "Modelo escolhe query_actions e preenche os argumentos:", args_lines(g_call["args"]),
         "Ferramenta executa a consulta fixa do código e devolve:")]
for x, name, acc, step1, code1, step2 in cols:
    panel(s, x, 2.25, 5.85, 4.65, fill=ACCENT_BG if acc else PANEL)
    textbox(s, x + 0.15, 2.3, 5.5, 0.4, [(name, {"bold": True, "size": 17, "color": ACCENT if acc else INK})])
    textbox(s, x + 0.15, 2.72, 5.55, 0.35, [step1], size=12)
    code_box(s, x + 0.15, 3.07, 5.55, 1.95, code1)
    textbox(s, x + 0.15, 5.07, 5.55, 0.4, [step2], size=12)
    code_box(s, x + 0.15, 5.47, 5.55, 0.65, tool_out)
    textbox(s, x + 0.15, 6.25, 5.55, 0.55, [(f"Modelo responde: {a01_answer}", {"size": 13, "bold": True})], anchor=MSO_ANCHOR.MIDDLE)


# 8 resultado 1
s = new_slide(9, f"Ferramentas sobre o grafo: {m('accRangeGraphTools')} de acerto nos {m('nModels')} modelos",
              f"[2:15] Acerto nas {m('nAnswerable')} perguntas com resposta. A barra azul é Ferramentas sobre o grafo: "
              f"{m('accRangeGraphTools')} em todos os modelos. Consulta escrita pelo modelo: {m('accRangeLowTextToCypher')} nos menores e "
              f"{m('accRangeHighTextToCypher')} nos maiores. Contexto longo: {m('accRangeLowEventsInPrompt')} nos menores e "
              f"{m('accRangeHighEventsInPrompt')} nos maiores. As outras três ficam baixas: Busca vetorial {m('accRangeVector')}, "
              f"Estatísticas resumidas {m('accRangeStatsInPrompt')}, e Sem dados {m('accRangeNoContext')}, porque se abstém. "
              "Nos maiores, Consulta empata com Ferramentas no Sonnet e fica à frente no Kimi; os intervalos se sobrepõem. Setup: quatro "
              "modelos, dois menores (Haiku e Qwen, sem raciocínio estendido, temperatura zero) e dois maiores (Sonnet e Kimi, com "
              f"raciocínio estendido), agrupados pela faixa de preço por token; {m('nQuestions')} perguntas em {m('nArms')} abordagens, "
              f"{m('nRuns')} execuções por modelo, {m('nRepeats')} repetição por pergunta; intervalo de Wilson de 95%; diferenças lidas como indícios.",
              kicker=f"Acerto nas {m('nAnswerable')} perguntas com resposta, uma repetição por pergunta.")
cd = CategoryChartData()
cd.categories = [MODEL_LABEL[x] for x in MODELS]
for a in ARMS:
    cd.add_series(ARM_NAME[a], [mi(f"acc{x}{a}") for x in MODELS])
textbox(s, 0.7, 1.45, 11.9, 0.9,
        [f"{m('nModels')} modelos: {m('modelHaiku')} e {m('modelQwen')} (menores, sem raciocínio estendido, temperatura zero); {m('modelSonnet')} e {m('modelKimi')} (maiores, com raciocínio estendido).",
         f"{m('nQuestions')} perguntas × {m('nArms')} abordagens = {m('nRuns')} execuções por modelo, {m('nRepeats')} repetição por pergunta. Intervalo de Wilson de 95%; diferenças lidas como indícios."],
        size=13, color=MUTED, gap=2)
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(2.3), Inches(12.3), Inches(4.65), cd)
style_chart(gf.chart, GRAYS + [ACCENT], size=13)

# 9 resultado 2: encadeadas
chain = ["Relações", "Jogadas", "Momento"]
n_chain = sum(GROUPS[g][0] for g in chain)
ARM_COL = {"EventsInPrompt": 0, "TextToCypher": 1, "GraphTools": 2}


def chain_acc(model, arm):
    mi_ = MODELS.index(model)
    return round(100 * sum(GROUPS[g][1][mi_][ARM_COL[arm]] for g in chain) / n_chain)


s = new_slide(10, "Nas perguntas encadeadas, Consulta e Contexto longo dependem do modelo",
              f"[1:30] Recorte das {n_chain} perguntas encadeadas (relações na rede de passes, jogadas e antes e depois de uma "
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
s = new_slide(11, "Busca vetorial, Estatísticas resumidas e Sem dados ficam baixas por motivos diferentes",
              f"[1:00] Busca vetorial ({m('accRangeVector')}): traz as {m('nTopK')} linhas mais parecidas com a pergunta, de "
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
s = new_slide(12, "Contexto longo nos modelos maiores custa milhares de tokens de saída e dezenas de segundos",
              f"[1:15] Mediana por execução das três abordagens que leem os dados. O Contexto longo leva a tabela inteira em cada "
              f"pergunta, de {m('inRangeEventsInPrompt')} mil tokens de entrada. Nos maiores, produz de {m('outRangeHighEventsInPrompt')} "
              f"tokens de saída, quase todos de raciocínio, e leva de {m('latRangeHighEventsInPrompt')} segundos. Cuidado ao comparar: "
              "Ferramentas não usa cache de prompt e Consulta usa, então a latência mistura as duas condições; no Contexto longo, a "
              "maior parte da entrada veio do cache, o que o favorece. Sem preço em dólar, porque os preços mudam.",
              )
LAT_ROWS = {a: COST[("Latência (s)", a)] for a in ("Contexto", "Consulta", "Ferramentas")}
OUT_ROWS = COST[("Tokens de saída (mil)", "Contexto")]
for i, (big, small) in enumerate([(f"{LAT_ROWS['Contexto'][2]} s e {LAT_ROWS['Contexto'][3]} s", "latência por pergunta"),
                                  (f"{OUT_ROWS[2]} e {OUT_ROWS[3]} mil", "tokens de saída por pergunta")]):
    panel(s, 0.7, 1.7 + i * 2.5, 4.2, 2.3, fill=ACCENT_BG)
    textbox(s, 0.85, 1.85 + i * 2.5, 3.9, 2.0,
            [(big, {"bold": True, "size": 40, "color": ACCENT}), (small, {"size": 18}),
             (f"{ARM_NAME['EventsInPrompt']}, modelos maiores (Sonnet e Kimi)", {"size": 13, "color": MUTED})], gap=6)
cd = CategoryChartData()
cd.categories = ["Sonnet 4.6 (maior)", "Kimi K3 (maior)"]
for a, nm in [("Contexto", ARM_NAME["EventsInPrompt"]), ("Consulta", ARM_NAME["TextToCypher"]), ("Ferramentas", ARM_NAME["GraphTools"])]:
    cd.add_series(nm, [float(v.replace(",", ".")) for v in LAT_ROWS[a][2:]])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5.2), Inches(1.55), Inches(7.7), Inches(5.3), cd)
style_chart(gf.chart, [GRAYS[2], GRAYS[4], ACCENT], size=14)
gf.chart.value_axis.axis_title.text_frame.paragraphs[0].runs[0].text = "Latência mediana (s)"
gf.chart.plots[0].gap_width = 80

# 13 limitações e conclusão
s = new_slide(13, "Ferramentas mantiveram o acerto alto, com limites claros",
              f"[1:15] Conclusão: Ferramentas sobre o grafo foi a única abordagem que manteve o acerto alto nos {m('nModels')} modelos, "
              f"{m('accRangeGraphTools')}. Consulta e Contexto longo dependem do modelo; nos maiores, com raciocínio estendido, a "
              "Consulta chegou ao mesmo nível e o Contexto longo se aproximou, este com mais tokens de saída e tempo. Busca vetorial e "
              "Estatísticas resumidas ficaram baixas em todos. Limitações, ditas pelo próprio artigo: uma partida e "
              f"{m('nRepeats')} repetição por pergunta, com {m('nAnswerable')} perguntas com resposta, então os intervalos são largos; "
              "tamanho e raciocínio estendido vieram juntos nos maiores; as ferramentas e as perguntas foram escritas pelos mesmos "
              "autores e as ferramentas foram ajustadas olhando erros, então o acerto vale dentro da cobertura delas; o ganho pode vir "
              "das ferramentas, do grafo ou dos algoritmos de grafo, e separar isso é trabalho futuro; e as abordagens com agente "
              "supõem chamada de ferramenta confiável.")
textbox(s, 0.7, 1.6, 5.9, 0.5, [("Conclusão", {"bold": True, "size": 22, "color": ACCENT})])
bullets(s, 0.7, 2.2, 5.9, 4.6,
        [("Ferramentas sobre o grafo: ", f"{m('accRangeGraphTools')} em todos os modelos."),
         ("Consulta: ", f"{m('accRangeLowTextToCypher')} nos menores; {m('accRangeHighTextToCypher')} nos maiores."),
         ("Contexto longo: ", f"{m('accRangeLowEventsInPrompt')} nos menores; {m('accRangeHighEventsInPrompt')} nos maiores, com mais tokens de saída e tempo."),
         ("Busca vetorial e Estatísticas resumidas: ", f"{m('accRangeVector')} e {m('accRangeStatsInPrompt')}.")], size=18, gap=12)
textbox(s, 7.0, 1.6, 5.6, 0.5, [("Limitações", {"bold": True, "size": 22, "color": ACCENT})])
bullets(s, 7.0, 2.2, 5.6, 4.6,
        [(f"Uma partida e {m('nRepeats')} repetição ", f"por pergunta; {m('nAnswerable')} perguntas com resposta e intervalos largos."),
         ("Tamanho e raciocínio ", "vieram juntos nos modelos maiores."),
         ("Ferramentas e perguntas dos mesmos autores: ", "o acerto vale dentro da cobertura das ferramentas."),
         ("Ferramentas, grafo ou algoritmos de grafo? ", "Separar é trabalho futuro."),
         ("Agentes ", "supõem chamada de ferramenta confiável.")], size=18, gap=12)

# 14 próximos passos
s = new_slide(14, "Próximos passos: mais evidência, efeitos separados e outros domínios",
              "[1:15] Fecho. Três frentes, todas ligadas às limitações. Primeira, mais evidência: repetir as execuções mede a variação "
              "entre rodadas e permite testar as diferenças entre abordagens, e estender as perguntas a várias partidas tira a "
              "dependência de uma só. Segunda, separar efeitos: avaliar modelos maiores sem raciocínio estendido separa o efeito do "
              "tamanho do efeito do raciocínio; aplicar as mesmas ferramentas a uma tabela, sem o grafo, separa o efeito das "
              "ferramentas do efeito do grafo; e testar uma busca vetorial em que cada trecho traga também os eventos vizinhos, como "
              "em Tzikas et al., responde à lacuna da Busca vetorial. Terceira, outros domínios, entre eles os dados industriais: parte "
              "deles tem a forma dos dados de futebol, registros de eventos com agente, momento e local, ligados entre si, como as "
              "paradas, os alertas e as movimentações de uma linha de produção ou de uma frota. Testar as mesmas abordagens ali é um "
              "próximo passo natural para uma pós em IA aplicada à indústria, mas exige implementação própria: a preparação dos dados, "
              "o grafo e as ferramentas dependem das perguntas que se quer responder.")
cols = [("Mais evidência", ["Repetir as execuções: medir a variação entre rodadas e testar as diferenças entre abordagens.",
                            "Estender as perguntas a várias partidas."], False),
        ("Separar os efeitos", ["Modelos maiores sem raciocínio estendido: tamanho ou raciocínio?",
                               "As mesmas ferramentas sobre uma tabela, sem o grafo: ferramentas ou grafo?",
                               "Busca vetorial com os eventos vizinhos em cada trecho."], False),
        ("Outros domínios", ["Dados industriais: registros de eventos com agente, momento e local, como paradas, alertas e movimentações.",
                             "Exige preparação dos dados, grafo e ferramentas próprios do domínio."], True)]
x = 0.7
for head, items, acc in cols:
    panel(s, x, 1.7, 3.8, 4.6, fill=ACCENT_BG if acc else PANEL)
    textbox(s, x + 0.15, 1.8, 3.5, 0.5, [(head, {"bold": True, "size": 20, "color": ACCENT})])
    bullets(s, x + 0.15, 2.45, 3.5, 3.8, items, size=18, gap=14)
    x += 4.05

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
