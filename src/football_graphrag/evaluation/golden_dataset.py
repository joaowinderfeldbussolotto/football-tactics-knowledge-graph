"""Golden dataset: perguntas verificadas à mão contra os dados ingeridos.

Cada pergunta cobre um insight da seção 7 do plano e tem resposta de
referência conferida manualmente contra a saída da camada 2 (os padrões
reais listados em docs/03-insights.md). ``categoria``:
- "estrutural": a resposta só existe na topologia do grafo (a tese do
  projeto prevê que o baseline vetorial ERRE estas);
- "factual": fato bruto do jogo (gols, assistências, contagens) respondido
  pelo modo autônomo (Cypher read-only gerado pelo LLM, ADR-8);
- "agregada": métrica agregada clássica (o baseline pode empatar).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenQuestion:
    id: str
    match_id: int
    pergunta: str
    resposta_referencia: str
    insight: str
    categoria: str  # estrutural | agregada


GOLDEN_QUESTIONS: list[GoldenQuestion] = [
    GoldenQuestion(
        id="q01_pivo_argentina",
        match_id=3869685,
        pergunta="Qual jogador foi o gargalo estrutural da progressão da Argentina na final?",
        resposta_referencia=(
            "Nicolás Otamendi: maior betweenness centrality da rede de passes argentina "
            "(50.0, contra 25.0 do segundo colocado), calculada por gds.betweenness.stream. "
            "Os caminhos de progressão passam desproporcionalmente por ele."
        ),
        insight="7.1 pivo_estrutural",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q02_pivo_franca",
        match_id=3869685,
        pergunta="Por qual jogador da França passavam os caminhos de progressão do time?",
        resposta_referencia=(
            "Jules Koundé: betweenness 40.0 na rede de passes francesa (2º colocado: 25.0), "
            "apesar de não ser o jogador de mais toques do time."
        ),
        insight="7.1 pivo_estrutural",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q03_terceiro_homem",
        match_id=3869685,
        pergunta="Que combinação de três homens a Argentina repetiu para quebrar linhas na final?",
        resposta_referencia=(
            "De Paul -> Messi -> Di María (2 ocorrências progressivas na mesma fase de posse, "
            "xT acumulado 0.021), identificada por padrão de caminho A->B->C em Cypher."
        ),
        insight="7.2 terceiro_homem",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q04_gatilho_argentina",
        match_id=3869685,
        pergunta="O que disparava a pressão da Argentina sobre a França?",
        resposta_referencia=(
            "Passe para o corredor central na faixa de meio-campo: 13 pressões em até 8s "
            "após o passe, 81% dos passes para essa região sofreram pressão."
        ),
        insight="7.3 gatilho_pressao",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q05_ligacao_fragil",
        match_id=3869685,
        pergunta="Onde a França deveria ter pressionado para desconectar a construção argentina?",
        resposta_referencia=(
            "Na ligação Tagliafico <-> Otamendi: 47% de todo o fluxo de passes entre os dois "
            "blocos (comunidades Louvain) da Argentina passa por esse único par (51 passes)."
        ),
        insight="7.4 ligacao_fragil",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q06_papel_theo",
        match_id=3869685,
        pergunta="Theo Hernández jogou mesmo como lateral esquerdo na final?",
        resposta_referencia=(
            "Não funcionalmente: escalado como Left Back, a comunidade de passes (Louvain) o "
            "agrupa com a linha de ataque (92 ações) — atuou como ala/atacante de fato."
        ),
        insight="7.5 papel_divergente",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q07_mudanca_argentina",
        match_id=3869685,
        pergunta="A Argentina mudou de comportamento defensivo durante a final? Quando?",
        resposta_referencia=(
            "Sim: bloco baixo até o minuto 50 (PPDA médio 15.4 em janelas móveis), depois "
            "pressão alta (PPDA 5.2). O estado antigo é invalidado aos 50, não apagado."
        ),
        insight="7.7 mudanca_estado",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q08_alvo_mbappe",
        match_id=3869354,
        pergunta="A Inglaterra caçou algum jogador específico da França nas quartas?",
        resposta_referencia=(
            "Sim, Mbappé: 22 pressões em 77 toques (0.29 pressões por toque, 1.6x a média "
            "dos companheiros), medido por grau de entrada ponderado na rede de pressão."
        ),
        insight="7.8 alvo_de_pressao",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q09_assimetria_franca",
        match_id=3869685,
        pergunta="A França finalizava pelo mesmo lado em que construía na final?",
        resposta_referencia=(
            "Não: o xT de chegada ao ataque concentra 68% no corredor esquerdo, mas a "
            "construção passa pela esquerda só 41% das vezes — a bola atravessava de corredor."
        ),
        insight="7.6 assimetria_construcao",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q10_ppda_agregado",
        match_id=3869685,
        pergunta="Qual time terminou a final pressionando mais alto?",
        resposta_referencia=(
            "A Argentina: a partir do minuto 50 seu PPDA em janelas móveis cai para 5.2 "
            "(pressão intensa), enquanto o da França sobe para 30 no fim do jogo."
        ),
        insight="7.7 mudanca_estado (agregável)",
        categoria="agregada",
    ),
    GoldenQuestion(
        id="q11_alvo_vlasic",
        match_id=3869519,
        pergunta="A Argentina caçou algum jogador específico da Croácia na semifinal?",
        resposta_referencia=(
            "Sim, Nikola Vlašić: 14 pressões em 39 toques (0.36 pressões por toque, "
            "2.1x a média dos companheiros), medido por grau de entrada na rede de pressão."
        ),
        insight="7.8 alvo_de_pressao",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q12_papel_sosa",
        match_id=3869519,
        pergunta="Borna Sosa atuou mesmo como lateral esquerdo na semifinal?",
        resposta_referencia=(
            "Não funcionalmente: escalado como Left Back, a comunidade de passes (Louvain) "
            "o agrupa com a linha de meio-campo (70 ações) — operou adiantado, como ala/meia."
        ),
        insight="7.5 papel_divergente",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q13_assimetria_croacia",
        match_id=3869519,
        pergunta="Por onde a Croácia chegava ao ataque na semifinal, comparado com onde construía?",
        resposta_referencia=(
            "O xT de chegada da Croácia concentra no corredor central (58%) de forma "
            "desproporcional à construção, que passa pelo centro só 21% das vezes — a bola "
            "atravessava de corredor antes de finalizar."
        ),
        insight="7.6 assimetria_construcao",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q14_construcao_esteril_england",
        match_id=3869354,
        pergunta="A construção da Inglaterra pela esquerda rendia chegada ao ataque nas quartas?",
        resposta_referencia=(
            "Não: a Inglaterra construiu 50% das progressões de defesa/meio pelo corredor "
            "esquerdo, mas só 27% do xT de chegada ao ataque veio por ele — corredor de "
            "construção estéril; a finalização acontecia do outro lado."
        ),
        insight="7.6 assimetria_construcao",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q15_papel_kounde",
        match_id=3869354,
        pergunta="Jules Koundé jogou como lateral direito de verdade nas quartas contra a Inglaterra?",
        resposta_referencia=(
            "Não funcionalmente: escalado como Right Back, a comunidade de passes o agrupa "
            "com a linha de ataque (79 ações) — atuou como ala ofensivo de fato."
        ),
        insight="7.5 papel_divergente",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q16_gatilho_franca",
        match_id=3869685,
        pergunta="O que disparava a pressão da França na final?",
        resposta_referencia=(
            "Passe para o corredor esquerdo na faixa de meio-campo adversário: 8 pressões "
            "em até 8s após o passe, 47% dos passes para essa região sofreram pressão."
        ),
        insight="7.3 gatilho_pressao",
        categoria="estrutural",
    ),
    GoldenQuestion(
        id="q17_gols_final",
        match_id=3869685,
        pergunta="Quem fez os gols da final (tempo normal e prorrogação)?",
        resposta_referencia=(
            "6 gols: Messi 2 (pênalti aos 22 do 1ºT e aos 3 da 2ª prorrogação), Di María "
            "(35 do 1ºT) pela Argentina; Mbappé 3 (pênalti aos 34 e gol aos 36 do 2ºT, "
            "pênalti aos 12 da 2ª prorrogação) pela França."
        ),
        insight="factual (FINALIZOU, modo autônomo)",
        categoria="factual",
    ),
    GoldenQuestion(
        id="q18_assistencias_final",
        match_id=3869685,
        pergunta="Quem deu as assistências dos gols da final?",
        resposta_referencia=(
            "Duas assistências registradas: Mac Allister para o gol de Di María e Thuram "
            "para o gol de Mbappé aos 36 do 2ºT; os demais gols (pênaltis e rebote) não "
            "têm assistência."
        ),
        insight="factual (DEU_ASSISTENCIA, modo autônomo)",
        categoria="factual",
    ),
    GoldenQuestion(
        id="q19_dupla_passes",
        match_id=3869685,
        pergunta="Qual dupla mais trocou passes na final e quantos foram?",
        resposta_referencia="Otamendi para Romero: 18 passes (a dupla de zagueiros argentinos).",
        insight="factual (PASSOU_PARA, modo autônomo)",
        categoria="factual",
    ),
    GoldenQuestion(
        id="q20_top_passador",
        match_id=3869685,
        pergunta="Quem deu mais passes na final?",
        resposta_referencia=(
            "Enzo Fernandez (79 passes completos com recebedor no grafo; Otamendi 68 e "
            "Romero 59 na sequência)."
        ),
        insight="factual (PASSOU_PARA, modo autônomo)",
        categoria="factual",
    ),
    GoldenQuestion(
        id="q21_cartoes_final",
        match_id=3869685,
        pergunta="Quem levou cartão amarelo na final?",
        resposta_referencia=(
            "Seis jogadores: Enzo Fernandez, Acuña, Paredes e Montiel pela Argentina; "
            "Rabiot e Thuram pela França (Paredes e Montiel na prorrogação)."
        ),
        insight="factual (REALIZOU foul/yellow_card, modo autônomo)",
        categoria="factual",
    ),
    GoldenQuestion(
        id="q22_dribles_final",
        match_id=3869685,
        pergunta="Quem mais driblou adversários com sucesso na final?",
        resposta_referencia=(
            "Mbappé, com 6 dribles certos (take_on com sucesso); Di María teve 5 e "
            "Coman 4."
        ),
        insight="factual (REALIZOU take_on, modo autônomo)",
        categoria="factual",
    ),
    GoldenQuestion(
        id="q23_desarmes_final",
        match_id=3869685,
        pergunta="Quem fez mais desarmes na final?",
        resposta_referencia=(
            "Enzo Fernandez, com 5 desarmes certos; Camavinga e Tagliafico fizeram 4 "
            "cada."
        ),
        insight="factual (REALIZOU tackle, modo autônomo)",
        categoria="factual",
    ),
    GoldenQuestion(
        id="q24_defesas_goleiros",
        match_id=3869685,
        pergunta="Quantas defesas fez cada goleiro na final?",
        resposta_referencia="Lloris fez 8 defesas; Emiliano Martínez fez 2.",
        insight="factual (REALIZOU keeper_save, modo autônomo)",
        categoria="factual",
    ),
]
