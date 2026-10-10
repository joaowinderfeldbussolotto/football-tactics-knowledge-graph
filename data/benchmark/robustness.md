# Teste de robustez do gabarito

Gerado por `scripts/robustness_report.py` a partir de `ground_truth.json`. Cada pergunta escrita aparece com a resposta em cada leitura razoável. Fica no benchmark só a pergunta em que todas as leituras concordam no que a conferência olha (o jogador, o conjunto ou o número). Empate conta como instável.

Nos rankings, o número ao lado do nome é a pontuação naquela leitura (passes, contagem ou intermediação); ele muda entre leituras sem tornar a pergunta instável quando a conferência olha só o jogador.

| pergunta | tipo | estágio | estável | leituras |
|---|---|---|---|---|
| [f01](#f01) | fact | full | sim | 1 |
| [f02](#f02) | fact | pilot | sim | 1 |
| [f03](#f03) | fact | pilot | sim | 1 |
| [f04](#f04) | fact | full | sim | 2 |
| [f05](#f05) | fact | full | sim | 3 |
| [f06](#f06) | fact | candidate | sim | 1 |
| [a01](#a01) | filtered_aggregation | full | sim | 4 |
| [a02](#a02) | filtered_aggregation | removed | **não** | 4 |
| [a03](#a03) | filtered_aggregation | pilot | sim | 4 |
| [a04](#a04) | filtered_aggregation | removed | **não** | 4 |
| [a05](#a05) | filtered_aggregation | pilot | sim | 4 |
| [a06](#a06) | filtered_aggregation | full | sim | 1 |
| [a07](#a07) | filtered_aggregation | full | sim | 2 |
| [a08](#a08) | filtered_aggregation | candidate | sim | 2 |
| [a09](#a09) | filtered_aggregation | removed | **não** | 2 |
| [n01](#n01) | network | removed | **não** | 12 |
| [n02](#n02) | network | removed | **não** | 12 |
| [n03](#n03) | network | pilot | sim | 2 |
| [n04](#n04) | network | pilot | sim | 4 |
| [n05](#n05) | network | full | sim | 4 |
| [n06](#n06) | network | full | sim | 6 |
| [n07](#n07) | network | removed | **não** | 6 |
| [n08](#n08) | network | candidate | sim | 2 |
| [n09](#n09) | network | full | sim | 8 |
| [n10](#n10) | network | candidate | sim | 8 |
| [n11](#n11) | network | candidate | sim | 2 |
| [s01](#s01) | network_slice | pilot | sim | 12 |
| [s02](#s02) | network_slice | removed | **não** | 24 |
| [s03](#s03) | network_slice | full | sim | 8 |
| [s04](#s04) | network_slice | pilot | sim | 4 |
| [s05](#s05) | network_slice | candidate | sim | 2 |
| [s06](#s06) | network_slice | full | sim | 2 |
| [s07](#s07) | network_slice | full | sim | 8 |
| [s08](#s08) | network_slice | removed | **não** | 6 |
| [s09](#s09) | network_slice | removed | **não** | 6 |
| [s10](#s10) | network_slice | graph | sim | 16 |
| [s11](#s11) | network_slice | graph | sim | 8 |
| [s12](#s12) | network_slice | graph | sim | 4 |
| [s13](#s13) | network_slice | graph | sim | 6 |
| [u01](#u01) | unanswerable | pilot | sim | – |
| [u02](#u02) | unanswerable | full | sim | – |
| [u03](#u03) | unanswerable | pilot | sim | – |
| [u04](#u04) | unanswerable | full | sim | – |
| [u05](#u05) | unanswerable | full | sim | – |
| [u06](#u06) | unanswerable | candidate | sim | – |
| [t01](#t01) | structure | removed | sim | 4 |
| [t02](#t02) | structure | removed | sim | 4 |
| [t03](#t03) | structure | removed | sim | 4 |
| [t04](#t04) | structure | removed | sim | 4 |
| [t05](#t05) | structure | removed | sim | 4 |
| [t06](#t06) | structure | graph | sim | 2 |
| [t07](#t07) | structure | removed | **não** | 4 |
| [c01](#c01) | counterfactual | graph | sim | 12 |
| [c02](#c02) | counterfactual | graph | sim | 2 |
| [c03](#c03) | counterfactual | removed | **não** | 12 |
| [c04](#c04) | counterfactual | removed | **não** | 12 |
| [c05](#c05) | counterfactual | removed | **não** | 12 |
| [q01](#q01) | sequence | graph | sim | 4 |
| [q02](#q02) | sequence | removed | **não** | 4 |
| [q03](#q03) | sequence | removed | **não** | 4 |
| [q04](#q04) | sequence | removed | **não** | 4 |
| [p01](#p01) | play | graph | sim | 1 |
| [p02](#p02) | play | graph | sim | 4 |
| [p03](#p03) | play | graph | sim | 2 |
| [p04](#p04) | play | graph | sim | 2 |
| [p05](#p05) | play | graph | sim | 2 |
| [p06](#p06) | play | graph | sim | 2 |
| [p07](#p07) | play | removed | **não** | 1 |
| [p08](#p08) | play | removed | **não** | 2 |
| [p09](#p09) | play | removed | **não** | 3 |
| [p10](#p10) | play | candidate | sim | 2 |
| [b01](#b01) | substitution | removed | **não** | 24 |
| [b02](#b02) | substitution | graph | sim | 4 |
| [b03](#b03) | substitution | graph | sim | 4 |
| [b04](#b04) | substitution | removed | **não** | 24 |
| [b05](#b05) | substitution | graph | sim | 4 |
| [b06](#b06) | substitution | removed | **não** | 8 |
| [b07](#b07) | substitution | removed | **não** | 4 |
| [b08](#b08) | substitution | removed | **não** | 12 |
| [b09](#b09) | substitution | graph | sim | 4 |

## fact

### f01

> Quem recebeu o primeiro cartão amarelo da final?

Estágio: **full** · conferência: `player` · estável: **sim**

| leitura | resposta |
|---|---|
| raw JSON | Enzo Fernandez |

### f02

> Quem cometeu a falta que deu origem ao primeiro pênalti da final?

Estágio: **pilot** · conferência: `player` · estável: **sim**

Nota: Dembélé, em Di María (20'). O pênalti é cobrado no minuto seguinte; é preciso achar a falta antes dele.

| leitura | resposta |
|---|---|
| raw JSON (foul flagged as penalty) | Ousmane Dembélé |

### f03

> No lance do gol de Messi na prorrogação, o goleiro francês tinha feito uma defesa instantes antes. Quem deu o chute que ele defendeu?

Estágio: **pilot** · conferência: `player` · estável: **sim**

Nota: Lautaro Martínez (108'); Messi marcou no rebote.

| leitura | resposta |
|---|---|
| raw JSON (saved shot in the goal's possession) | Lautaro Javier Martínez |

### f04

> Quem deu o passe para o gol que deixou o placar em 2 a 2 no tempo normal?

Estágio: **full** · conferência: `player` · estável: **sim**

| leitura | resposta |
|---|---|
| raw JSON (goal_assist) | Marcus Thuram |
| layer 0 (last pass to the scorer) | Marcus Thuram |

### f05

> Quem fez a última finalização da França na final, antes da disputa de pênaltis?

Estágio: **full** · conferência: `player` · estável: **sim**

Nota: Kolo Muani (122'), defendida por Emiliano Martínez. Escrita depois do congelamento da v2.2.

| leitura | resposta |
|---|---|
| raw JSON / every shot | Randal Kolo Muani |
| raw JSON / penalties excluded | Randal Kolo Muani |
| layer 0 | Randal Kolo Muani |

### f06

> Quem levou cartão amarelo na final sem ter cometido falta?

Estágio: **candidate** · conferência: `player` · estável: **sim**

Nota: Giroud (94'), por reclamação.

| leitura | resposta |
|---|---|
| raw JSON (Bad Behaviour card) | Olivier Giroud |

## filtered_aggregation

### a01

> Quem deu mais passes certos no terço final do campo pela Argentina?

Estágio: **full** · conferência: `player` · estável: **sim**

| leitura | resposta |
|---|---|
| all passes / third where the pass starts | Lionel Andrés Messi Cuccittini · 25 |
| all passes / third where it ends | Lionel Andrés Messi Cuccittini · 29 |
| open-play passes / third where the pass starts | Lionel Andrés Messi Cuccittini · 24 |
| open-play passes / third where it ends | Lionel Andrés Messi Cuccittini · 28 |

### a02

> Quem deu mais passes certos no terço final do campo pela França?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Rabiot e Mbappé empatam ou se alternam conforme o terço seja o de origem ou o de destino do passe, e conforme entrem cruzamentos e bolas paradas.

| leitura | resposta |
|---|---|
| all passes / third where the pass starts | **empate:** Adrien Rabiot; Kylian Mbappé Lottin |
| all passes / third where it ends | **empate:** Adrien Rabiot; Kylian Mbappé Lottin |
| open-play passes / third where the pass starts | Adrien Rabiot · 10 |
| open-play passes / third where it ends | Adrien Rabiot · 12 |

### a03

> Depois do gol que deixou o placar em 2 a 2 no tempo normal, quantas finalizações a Argentina fez até o fim da prorrogação?

Estágio: **pilot** · conferência: `value` · estável: **sim**

| leitura | resposta |
|---|---|
| layer 0 / with the 2-2 shot | 10 |
| layer 0 / without the 2-2 shot | 10 |
| raw JSON / with the 2-2 shot | 10 |
| raw JSON / without the 2-2 shot | 10 |

### a04

> Depois do gol que deixou o placar em 2 a 2 no tempo normal, quantas finalizações a França fez até o fim da prorrogação?

Estágio: **removed** · conferência: `value` · estável: **não**

Nota: Muda com a leitura: o próprio chute do 2 a 2 é da França e entra ou não no "depois".

| leitura | resposta |
|---|---|
| layer 0 / with the 2-2 shot | 7 |
| layer 0 / without the 2-2 shot | 6 |
| raw JSON / with the 2-2 shot | 7 |
| raw JSON / without the 2-2 shot | 6 |

### a05

> Enquanto a Argentina vencia por 2 a 0, qual jogador argentino acertou mais passes, e quantos?

Estágio: **pilot** · conferência: `player_and_value` · estável: **sim**

| leitura | resposta |
|---|---|
| all passes / goals included | Enzo Fernandez · 26 |
| all passes / goals excluded | Enzo Fernandez · 26 |
| open-play passes / goals included | Enzo Fernandez · 26 |
| open-play passes / goals excluded | Enzo Fernandez · 26 |

### a06

> Na prorrogação, quem fez mais desarmes certos pela Argentina?

Estágio: **full** · conferência: `player` · estável: **sim**

| leitura | resposta |
|---|---|
| layer 0 (tackles won) | Enzo Fernandez · 2 |

### a07

> No segundo tempo, quem cometeu mais faltas?

Estágio: **full** · conferência: `player` · estável: **sim**

Nota: Julián Álvarez (4). Escrita depois do congelamento da v2.2.

| leitura | resposta |
|---|---|
| raw JSON | Julián Álvarez · 4 |
| layer 0 | Julián Álvarez · 4 |

### a08

> Na prorrogação, quem completou mais dribles?

Estágio: **candidate** · conferência: `player` · estável: **sim**

| leitura | resposta |
|---|---|
| raw JSON | Kylian Mbappé Lottin · 3 |
| layer 0 | Kylian Mbappé Lottin · 3 |

### a09

> No primeiro tempo, quem fez mais interceptações?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a fonte: no JSON bruto (toda interceptação) é Tchouaméni; na camada 0 (só as certas) é Rabiot.

| leitura | resposta |
|---|---|
| raw JSON (every interception) | Aurélien Djani Tchouaméni · 3 |
| layer 0 (successful only) | Adrien Rabiot · 4 |

## network

### n01

> Quem era o principal elo da circulação de bola da Argentina?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Otamendi na maioria das leituras, Enzo Fernández quando a ligação pesa pelo número de passes e as duas direções se somam.

| leitura | resposta |
|---|---|
| all passes / directed / none | Nicolás Hernán Otamendi · 45.07 |
| all passes / directed / passes | Nicolás Hernán Otamendi · 87.0 |
| all passes / directed / xt | Nicolás Hernán Otamendi · 36.0 |
| all passes / undirected / none | Nicolás Hernán Otamendi · 19.71 |
| all passes / undirected / passes | Enzo Fernandez · 49.5 |
| all passes / undirected / xt | Nicolás Hernán Otamendi · 16.0 |
| open-play passes / directed / none | Nicolás Hernán Otamendi · 47.63 |
| open-play passes / directed / passes | Enzo Fernandez · 100.5 |
| open-play passes / directed / xt | Nicolás Hernán Otamendi · 37.0 |
| open-play passes / undirected / none | Nicolás Hernán Otamendi · 21.06 |
| open-play passes / undirected / passes | Enzo Fernandez · 64.5 |
| open-play passes / undirected / xt | Nicolás Hernán Otamendi · 16.0 |

### n02

> Quem era o principal elo da circulação de bola da França?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Koundé, Varane ou Rabiot conforme o peso e a direção.

| leitura | resposta |
|---|---|
| all passes / directed / none | Jules Koundé · 31.6 |
| all passes / directed / passes | Raphaël Varane · 83.5 |
| all passes / directed / xt | Jules Koundé · 34.0 |
| all passes / undirected / none | Jules Koundé · 14.07 |
| all passes / undirected / passes | Jules Koundé · 57.0 |
| all passes / undirected / xt | Adrien Rabiot · 13.0 |
| open-play passes / directed / none | Jules Koundé · 31.0 |
| open-play passes / directed / passes | Jules Koundé · 99.5 |
| open-play passes / directed / xt | Jules Koundé · 33.0 |
| open-play passes / undirected / none | Jules Koundé · 14.85 |
| open-play passes / undirected / passes | Jules Koundé · 62.0 |
| open-play passes / undirected / xt | Adrien Rabiot · 16.0 |

### n03

> Na troca de passes da Argentina, qual jogador, se não estivesse em campo, deixaria algum companheiro sem trocar passes com ninguém do time?

Estágio: **pilot** · conferência: `player` · estável: **sim**

Nota: Otamendi: Pezzella, que entrou no fim da prorrogação, só trocou passes com ele.

| leitura | resposta |
|---|---|
| all passes | Nicolás Hernán Otamendi |
| open-play passes | Nicolás Hernán Otamendi |

### n04

> Qual dupla da França mais trocou passes entre si na final?

Estágio: **pilot** · conferência: `set` · estável: **sim**

| leitura | resposta |
|---|---|
| all passes / directed | Dayotchanculle Upamecano e Raphaël Varane · 16 |
| all passes / undirected | Dayotchanculle Upamecano e Raphaël Varane · 30 |
| open-play passes / directed | Dayotchanculle Upamecano e Raphaël Varane · 15 |
| open-play passes / undirected | Dayotchanculle Upamecano e Raphaël Varane · 29 |

### n05

> Qual dupla da Argentina mais trocou passes entre si na final?

Estágio: **full** · conferência: `set` · estável: **sim**

| leitura | resposta |
|---|---|
| all passes / directed | Cristian Gabriel Romero e Nicolás Hernán Otamendi · 18 |
| all passes / undirected | Cristian Gabriel Romero e Nicolás Hernán Otamendi · 30 |
| open-play passes / directed | Cristian Gabriel Romero e Nicolás Hernán Otamendi · 18 |
| open-play passes / undirected | Cristian Gabriel Romero e Nicolás Hernán Otamendi · 30 |

### n06

> Qual jogador da Argentina trocou passes com o maior número de companheiros diferentes na final?

Estágio: **full** · conferência: `player` · estável: **sim**

Nota: Enzo Fernández, em qualquer direção e conjunto de passes. Escrita depois do congelamento da v2.2.

| leitura | resposta |
|---|---|
| all passes / either direction | Enzo Fernandez · 15 |
| all passes / passed to | Enzo Fernandez · 13 |
| all passes / received from | Enzo Fernandez · 15 |
| open-play passes / either direction | Enzo Fernandez · 15 |
| open-play passes / passed to | Enzo Fernandez · 13 |
| open-play passes / received from | Enzo Fernandez · 15 |

### n07

> Qual jogador da França trocou passes com o maior número de companheiros diferentes na final?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Koundé (nas duas direções), Tchouaméni (só para quem passou), empate Rabiot e Koundé (só de quem recebeu).

| leitura | resposta |
|---|---|
| all passes / either direction | Jules Koundé · 15 |
| all passes / passed to | Aurélien Djani Tchouaméni · 13 |
| all passes / received from | **empate:** Adrien Rabiot; Jules Koundé |
| open-play passes / either direction | **empate:** Adrien Rabiot; Aurélien Djani Tchouaméni; Jules Koundé |
| open-play passes / passed to | **empate:** Aurélien Djani Tchouaméni; Dayotchanculle Upamecano; Jules Koundé |
| open-play passes / received from | Adrien Rabiot · 14 |

### n08

> Qual companheiro mais recebeu passes de Messi na final?

Estágio: **candidate** · conferência: `player` · estável: **sim**

| leitura | resposta |
|---|---|
| all passes | Rodrigo Javier De Paul · 12 |
| open-play passes | Rodrigo Javier De Paul · 12 |

### n09

> Qual sequência de três jogadores da França, com a bola passando de um para o outro, mais se repetiu na final?

Estágio: **full** · conferência: `set` · estável: **sim**

Nota: Upamecano, Varane e Koundé (6 vezes) em todas as leituras. A conferência é por conjunto: a ordem não é conferida. Escrita depois do congelamento da v2.2.

| leitura | resposta |
|---|---|
| all passes / same possession / consecutive passes | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 6 |
| all passes / same possession / other passes between allowed | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 6 |
| all passes / any possession / consecutive passes | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 6 |
| all passes / any possession / other passes between allowed | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 6 |
| open-play passes / same possession / consecutive passes | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 6 |
| open-play passes / same possession / other passes between allowed | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 6 |
| open-play passes / any possession / consecutive passes | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 6 |
| open-play passes / any possession / other passes between allowed | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 6 |

### n10

> Qual sequência de três jogadores da Argentina, com a bola passando de um para o outro, mais se repetiu na final?

Estágio: **candidate** · conferência: `set` · estável: **sim**

| leitura | resposta |
|---|---|
| all passes / same possession / consecutive passes | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 5 |
| all passes / same possession / other passes between allowed | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 5 |
| all passes / any possession / consecutive passes | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 5 |
| all passes / any possession / other passes between allowed | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 5 |
| open-play passes / same possession / consecutive passes | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 5 |
| open-play passes / same possession / other passes between allowed | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 5 |
| open-play passes / any possession / consecutive passes | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 5 |
| open-play passes / any possession / other passes between allowed | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 5 |

### n11

> Para cortar a bola que chega a Messi, preciso saber: qual companheiro mais passou a bola para ele na final?

Estágio: **candidate** · conferência: `player` · estável: **sim**

Nota: De Paul. Visão do técnico adversário.

| leitura | resposta |
|---|---|
| all passes | Rodrigo Javier De Paul · 14 |
| open-play passes | Rodrigo Javier De Paul · 13 |

## network_slice

### s01

> Na prorrogação, quem foi o principal elo da circulação de bola da França?

Estágio: **pilot** · conferência: `player` · estável: **sim**

| leitura | resposta |
|---|---|
| all passes / directed / none / extra time | Jules Koundé · 23.83 |
| all passes / directed / passes / extra time | Jules Koundé · 31.0 |
| all passes / directed / xt / extra time | Jules Koundé · 24.0 |
| all passes / undirected / none / extra time | Jules Koundé · 17.62 |
| all passes / undirected / passes / extra time | Jules Koundé · 25.83 |
| all passes / undirected / xt / extra time | Jules Koundé · 16.0 |
| open-play passes / directed / none / extra time | Jules Koundé · 23.08 |
| open-play passes / directed / passes / extra time | Jules Koundé · 31.0 |
| open-play passes / directed / xt / extra time | Jules Koundé · 23.0 |
| open-play passes / undirected / none / extra time | Jules Koundé · 17.77 |
| open-play passes / undirected / passes / extra time | Jules Koundé · 27.5 |
| open-play passes / undirected / xt / extra time | Jules Koundé · 15.0 |

### s02

> Enquanto perdia por 2 a 0, quem era o principal elo da circulação de bola da França?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Estável em peso e direção (Tchouaméni), mas muda quando só os passes de bola rolando contam (Rabiot, Varane).

| leitura | resposta |
|---|---|
| all passes / directed / none / goals included | Aurélien Djani Tchouaméni · 29.25 |
| all passes / directed / none / goals excluded | Aurélien Djani Tchouaméni · 29.25 |
| all passes / directed / passes / goals included | Aurélien Djani Tchouaméni · 48.0 |
| all passes / directed / passes / goals excluded | Aurélien Djani Tchouaméni · 48.0 |
| all passes / directed / xt / goals included | Aurélien Djani Tchouaméni · 31.0 |
| all passes / directed / xt / goals excluded | Aurélien Djani Tchouaméni · 31.0 |
| all passes / undirected / none / goals included | Aurélien Djani Tchouaméni · 26.3 |
| all passes / undirected / none / goals excluded | Aurélien Djani Tchouaméni · 26.3 |
| all passes / undirected / passes / goals included | Aurélien Djani Tchouaméni · 36.0 |
| all passes / undirected / passes / goals excluded | Aurélien Djani Tchouaméni · 36.0 |
| all passes / undirected / xt / goals included | Aurélien Djani Tchouaméni · 26.0 |
| all passes / undirected / xt / goals excluded | Aurélien Djani Tchouaméni · 26.0 |
| open-play passes / directed / none / goals included | Adrien Rabiot · 22.63 |
| open-play passes / directed / none / goals excluded | Adrien Rabiot · 22.63 |
| open-play passes / directed / passes / goals included | Raphaël Varane · 37.0 |
| open-play passes / directed / passes / goals excluded | Raphaël Varane · 37.0 |
| open-play passes / directed / xt / goals included | Aurélien Djani Tchouaméni · 21.0 |
| open-play passes / directed / xt / goals excluded | Aurélien Djani Tchouaméni · 21.0 |
| open-play passes / undirected / none / goals included | Aurélien Djani Tchouaméni · 13.5 |
| open-play passes / undirected / none / goals excluded | Aurélien Djani Tchouaméni · 13.5 |
| open-play passes / undirected / passes / goals included | Aurélien Djani Tchouaméni · 24.0 |
| open-play passes / undirected / passes / goals excluded | Aurélien Djani Tchouaméni · 24.0 |
| open-play passes / undirected / xt / goals included | Aurélien Djani Tchouaméni · 13.0 |
| open-play passes / undirected / xt / goals excluded | Aurélien Djani Tchouaméni · 13.0 |

### s03

> Depois do gol que deixou o placar em 2 a 2 no tempo normal, qual dupla da França mais trocou passes entre si?

Estágio: **full** · conferência: `set` · estável: **sim**

| leitura | resposta |
|---|---|
| all passes / directed / with the 2-2 goal | Jules Koundé e Raphaël Varane · 8 |
| all passes / directed / without the 2-2 goal | Jules Koundé e Raphaël Varane · 8 |
| all passes / undirected / with the 2-2 goal | Jules Koundé e Raphaël Varane · 10 |
| all passes / undirected / without the 2-2 goal | Jules Koundé e Raphaël Varane · 10 |
| open-play passes / directed / with the 2-2 goal | Jules Koundé e Raphaël Varane · 8 |
| open-play passes / directed / without the 2-2 goal | Jules Koundé e Raphaël Varane · 8 |
| open-play passes / undirected / with the 2-2 goal | Jules Koundé e Raphaël Varane · 10 |
| open-play passes / undirected / without the 2-2 goal | Jules Koundé e Raphaël Varane · 10 |

### s04

> A dupla da Argentina que mais trocou passes entre si no primeiro tempo continuou sendo a principal no segundo tempo? Qual foi a dupla que mais trocou passes no segundo tempo?

Estágio: **pilot** · conferência: `set` · estável: **sim**

Nota: Comparação entre recortes. Só a dupla do 2º tempo é conferida.

| leitura | resposta |
|---|---|
| all passes / directed / 2nd half | Enzo Fernandez e Rodrigo Javier De Paul · 9 |
| all passes / undirected / 2nd half | Enzo Fernandez e Rodrigo Javier De Paul · 14 |
| open-play passes / directed / 2nd half | Enzo Fernandez e Rodrigo Javier De Paul · 9 |
| open-play passes / undirected / 2nd half | Enzo Fernandez e Rodrigo Javier De Paul · 14 |

Premissa que a pergunta afirma (também tem de ser estável):

| leitura | resposta |
|---|---|
| all passes / directed / 1st half | Cristian Gabriel Romero e Nicolás Hernán Otamendi · 12 |
| all passes / undirected / 1st half | Cristian Gabriel Romero e Nicolás Hernán Otamendi · 21 |
| open-play passes / directed / 1st half | Cristian Gabriel Romero e Nicolás Hernán Otamendi · 12 |
| open-play passes / undirected / 1st half | Cristian Gabriel Romero e Nicolás Hernán Otamendi · 21 |

### s05

> Na prorrogação, qual jogador da Argentina, se não estivesse em campo, deixaria algum companheiro sem trocar passes com ninguém do time?

Estágio: **candidate** · conferência: `player` · estável: **sim**

Nota: Mesma resposta da n03 (Otamendi): fica na reserva para não repetir o conceito.

| leitura | resposta |
|---|---|
| all passes / extra time | Nicolás Hernán Otamendi |
| open-play passes / extra time | Nicolás Hernán Otamendi |

### s06

> No segundo tempo, qual companheiro mais recebeu passes de Enzo Fernández?

Estágio: **full** · conferência: `player` · estável: **sim**

Nota: De Paul (9). Escrita depois do congelamento da v2.2.

| leitura | resposta |
|---|---|
| all passes / 2nd half | Rodrigo Javier De Paul · 9 |
| open-play passes / 2nd half | Rodrigo Javier De Paul · 9 |

### s07

> Na prorrogação, qual sequência de três jogadores da Argentina, com a bola passando de um para o outro, mais se repetiu?

Estágio: **full** · conferência: `set` · estável: **sim**

Nota: Otamendi, Romero e Enzo Fernández (3 vezes) em todas as leituras. Conferência por conjunto. Escrita depois do congelamento da v2.2.

| leitura | resposta |
|---|---|
| all passes / same possession / consecutive passes | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 3 |
| all passes / same possession / other passes between allowed | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 3 |
| all passes / any possession / consecutive passes | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 3 |
| all passes / any possession / other passes between allowed | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 3 |
| open-play passes / same possession / consecutive passes | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 3 |
| open-play passes / same possession / other passes between allowed | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 3 |
| open-play passes / any possession / consecutive passes | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 3 |
| open-play passes / any possession / other passes between allowed | Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez · 3 |

### s08

> No primeiro tempo, qual jogador da França trocou passes com o maior número de companheiros diferentes?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Tchouaméni, Koundé, ou empate de três quando conta só de quem recebeu.

| leitura | resposta |
|---|---|
| all passes / either direction / 1st half | Aurélien Djani Tchouaméni · 10 |
| all passes / passed to / 1st half | Aurélien Djani Tchouaméni · 9 |
| all passes / received from / 1st half | Jules Koundé · 8 |
| open-play passes / either direction / 1st half | Aurélien Djani Tchouaméni · 10 |
| open-play passes / passed to / 1st half | Aurélien Djani Tchouaméni · 9 |
| open-play passes / received from / 1st half | **empate:** Aurélien Djani Tchouaméni; Dayotchanculle Upamecano; Jules Koundé |

### s09

> Na prorrogação, qual jogador da Argentina trocou passes com o maior número de companheiros diferentes?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Empate entre Enzo Fernández e Otamendi numa leitura (só passes de bola rolando, para quem passou).

| leitura | resposta |
|---|---|
| all passes / either direction / extra time | Enzo Fernandez · 11 |
| all passes / passed to / extra time | Enzo Fernandez · 9 |
| all passes / received from / extra time | Enzo Fernandez · 9 |
| open-play passes / either direction / extra time | Enzo Fernandez · 11 |
| open-play passes / passed to / extra time | **empate:** Enzo Fernandez; Nicolás Hernán Otamendi |
| open-play passes / received from / extra time | Enzo Fernandez · 9 |

### s10

> No campo de ataque, pelo lado direito, quais dois jogadores da Argentina mais trocaram passes entre si?

Estágio: **graph** · conferência: `set` · estável: **sim**

Nota: Messi e De Paul. Leitura tática: por onde a Argentina combinava pela direita.

| leitura | resposta |
|---|---|
| all passes / directed / corridor / opponent half | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 8 |
| all passes / directed / corridor / attacking third | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 7 |
| all passes / directed / width third / opponent half | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 8 |
| all passes / directed / width third / attacking third | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 7 |
| all passes / undirected / corridor / opponent half | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 14 |
| all passes / undirected / corridor / attacking third | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 10 |
| all passes / undirected / width third / opponent half | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 14 |
| all passes / undirected / width third / attacking third | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 10 |
| open-play passes / directed / corridor / opponent half | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 8 |
| open-play passes / directed / corridor / attacking third | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 7 |
| open-play passes / directed / width third / opponent half | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 8 |
| open-play passes / directed / width third / attacking third | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 7 |
| open-play passes / undirected / corridor / opponent half | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 13 |
| open-play passes / undirected / corridor / attacking third | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 9 |
| open-play passes / undirected / width third / opponent half | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 13 |
| open-play passes / undirected / width third / attacking third | Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 9 |

### s11

> No campo de ataque, pelo lado esquerdo, quem foi o jogador da Argentina mais procurado pelos companheiros?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Mac Allister, não Di María. Leitura tática: quem era a referência do lado esquerdo.

| leitura | resposta |
|---|---|
| all passes / corridor / opponent half | Alexis Mac Allister · 17 |
| all passes / corridor / attacking third | Alexis Mac Allister · 11 |
| all passes / width third / opponent half | Alexis Mac Allister · 17 |
| all passes / width third / attacking third | Alexis Mac Allister · 11 |
| open-play passes / corridor / opponent half | Alexis Mac Allister · 15 |
| open-play passes / corridor / attacking third | Alexis Mac Allister · 10 |
| open-play passes / width third / opponent half | Alexis Mac Allister · 15 |
| open-play passes / width third / attacking third | Alexis Mac Allister · 10 |

### s12

> Enquanto a França perdia por 2 a 0, quem foi o jogador francês mais procurado pelos companheiros?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Upamecano. Leitura tática: a França rodava a bola atrás sem conseguir avançar.

| leitura | resposta |
|---|---|
| all passes / goals included | Dayotchanculle Upamecano · 32 |
| all passes / goals excluded | Dayotchanculle Upamecano · 32 |
| open-play passes / goals included | Dayotchanculle Upamecano · 29 |
| open-play passes / goals excluded | Dayotchanculle Upamecano · 29 |

### s13

> Depois do gol que deixou o placar em 2 a 2 no tempo normal, quem passou a ser o jogador da França mais procurado pelos companheiros?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Koundé.

| leitura | resposta |
|---|---|
| all passes / with the 2-2 goal | Jules Koundé · 19 |
| all passes / without the 2-2 goal | Jules Koundé · 19 |
| all passes / regular time only | Jules Koundé · 9 |
| open-play passes / with the 2-2 goal | Jules Koundé · 15 |
| open-play passes / without the 2-2 goal | Jules Koundé · 15 |
| open-play passes / regular time only | Jules Koundé · 6 |

## unanswerable

### u01

> Quantos minutos Messi passou no campo de ataque durante a final?

Estágio: **pilot** · conferência: `no_data` · estável: **sim**

Nota: Dados de eventos só têm posição no instante de cada ação com bola; o tempo em cada parte do campo exige rastreamento (tracking). Os dados 360 também são instantâneos.

Sem leituras: a resposta esperada é "sem dados".

### u02

> Qual foi a distância total percorrida por Rodrigo De Paul na final?

Estágio: **full** · conferência: `no_data` · estável: **sim**

Nota: Distância percorrida exige rastreamento contínuo, que o StatsBomb aberto não tem.

Sem leituras: a resposta esperada é "sem dados".

### u03

> Quantos piques em alta velocidade Mbappé deu na prorrogação?

Estágio: **pilot** · conferência: `no_data` · estável: **sim**

Nota: Velocidade de jogador exige rastreamento; os eventos não registram corridas sem bola.

Sem leituras: a resposta esperada é "sem dados".

### u04

> A que velocidade saiu o chute de Mbappé no gol que deixou o placar em 2 a 2?

Estágio: **full** · conferência: `no_data` · estável: **sim**

Nota: O StatsBomb registra local, parte do corpo e desfecho do chute, não a velocidade da bola.

Sem leituras: a resposta esperada é "sem dados".

### u05

> Em quantos lances Mbappé ficou em posição de impedimento sem participar da jogada?

Estágio: **full** · conferência: `no_data` · estável: **sim**

Nota: Os eventos só registram o impedimento marcado; impedimento passivo não vira evento. Os dados 360 mostram posições só no instante de cada ação, e não dizem se o jogador participou. Escrita depois do congelamento da v2.2.

Sem leituras: a resposta esperada é "sem dados".

### u06

> Quantas vezes Messi pediu a bola a um companheiro e não a recebeu?

Estágio: **candidate** · conferência: `no_data` · estável: **sim**

Nota: Pedido de bola não é registrado em dados de eventos.

Sem leituras: a resposta esperada é "sem dados".

## structure

### t01

> No primeiro tempo, qual trio argentino mais trocou passes entre si, com os três passando a bola uns para os outros?

Estágio: **removed** · conferência: `set` · estável: **sim**

Nota: Retirada: a formulação é artificial (ninguém pergunta por trios que trocaram passes entre si) e é lida como sequência A -> B -> C; na execução 10, os dois braços a leram assim.

| leitura | resposta |
|---|---|
| all passes / each pair in some direction / 1st half | Cristian Gabriel Romero e Enzo Fernandez e Nicolás Hernán Otamendi · 51 |
| all passes / all six directions / 1st half | Cristian Gabriel Romero e Enzo Fernandez e Nicolás Hernán Otamendi · 51 |
| open-play passes / each pair in some direction / 1st half | Cristian Gabriel Romero e Enzo Fernandez e Nicolás Hernán Otamendi · 51 |
| open-play passes / all six directions / 1st half | Cristian Gabriel Romero e Enzo Fernandez e Nicolás Hernán Otamendi · 51 |

### t02

> Qual trio da França mais trocou passes entre si na final, com os três passando a bola uns para os outros?

Estágio: **removed** · conferência: `set` · estável: **sim**

Nota: Retirada: a formulação é artificial (ninguém pergunta por trios que trocaram passes entre si) e é lida como sequência A -> B -> C; na execução 10, os dois braços a leram assim.

| leitura | resposta |
|---|---|
| all passes / each pair in some direction | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 66 |
| all passes / all six directions | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 66 |
| open-play passes / each pair in some direction | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 63 |
| open-play passes / all six directions | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 63 |

### t03

> No segundo tempo, qual trio argentino mais trocou passes entre si, com os três passando a bola uns para os outros?

Estágio: **removed** · conferência: `set` · estável: **sim**

Nota: Retirada: a formulação é artificial (ninguém pergunta por trios que trocaram passes entre si) e é lida como sequência A -> B -> C; na execução 10, os dois braços a leram assim.

| leitura | resposta |
|---|---|
| all passes / each pair in some direction / 2nd half | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 30 |
| all passes / all six directions / 2nd half | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 30 |
| open-play passes / each pair in some direction / 2nd half | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 30 |
| open-play passes / all six directions / 2nd half | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 30 |

### t04

> No primeiro tempo, qual trio francês mais trocou passes entre si, com os três passando a bola uns para os outros?

Estágio: **removed** · conferência: `set` · estável: **sim**

Nota: Retirada: a formulação é artificial (ninguém pergunta por trios que trocaram passes entre si) e é lida como sequência A -> B -> C; na execução 10, os dois braços a leram assim.

| leitura | resposta |
|---|---|
| all passes / each pair in some direction / 1st half | Aurélien Djani Tchouaméni e Dayotchanculle Upamecano e Raphaël Varane · 32 |
| all passes / all six directions / 1st half | Aurélien Djani Tchouaméni e Dayotchanculle Upamecano e Raphaël Varane · 32 |
| open-play passes / each pair in some direction / 1st half | Aurélien Djani Tchouaméni e Dayotchanculle Upamecano e Raphaël Varane · 31 |
| open-play passes / all six directions / 1st half | Aurélien Djani Tchouaméni e Dayotchanculle Upamecano e Raphaël Varane · 31 |

### t05

> Na prorrogação, qual trio argentino mais trocou passes entre si, com os três passando a bola uns para os outros?

Estágio: **removed** · conferência: `set` · estável: **sim**

Nota: Retirada: a formulação é artificial (ninguém pergunta por trios que trocaram passes entre si) e é lida como sequência A -> B -> C; na execução 10, os dois braços a leram assim.

| leitura | resposta |
|---|---|
| all passes / each pair in some direction / extra time | Enzo Fernandez e Gonzalo Ariel Montiel e Leandro Daniel Paredes · 17 |
| all passes / all six directions / extra time | Enzo Fernandez e Gonzalo Ariel Montiel e Leandro Daniel Paredes · 17 |
| open-play passes / each pair in some direction / extra time | Enzo Fernandez e Gonzalo Ariel Montiel e Leandro Daniel Paredes · 16 |
| open-play passes / all six directions / extra time | Enzo Fernandez e Gonzalo Ariel Montiel e Leandro Daniel Paredes · 16 |

### t06

> Na prorrogação, qual jogador da França, se não estivesse em campo, deixaria algum companheiro sem trocar passes com ninguém do time?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Koundé: Coman só trocou passes com ele na prorrogação.

| leitura | resposta |
|---|---|
| all passes / extra time | Jules Koundé |
| open-play passes / extra time | Jules Koundé |

### t07

> Na prorrogação, qual trio francês mais trocou passes entre si, com os três passando a bola uns para os outros?

Estágio: **removed** · conferência: `set` · estável: **não**

Nota: Muda com a leitura: empate de três trios contando todos os passes, outro trio quando só contam passes de bola rolando ou as seis direções.

| leitura | resposta |
|---|---|
| all passes / each pair in some direction / extra time | **empate:** Aurélien Djani Tchouaméni e Dayotchanculle Upamecano e Eduardo Camavinga; Aurélien Djani Tchouaméni e Jules Koundé e Youssouf Fofana; Jules Koundé e Raphaël Varane e Youssouf Fofana |
| all passes / all six directions / extra time | Aurélien Djani Tchouaméni e Eduardo Camavinga e Youssouf Fofana · 8 |
| open-play passes / each pair in some direction / extra time | Jules Koundé e Raphaël Varane e Youssouf Fofana · 10 |
| open-play passes / all six directions / extra time | **empate:**  |

## counterfactual

### c01

> Se Enzo Fernández não estivesse em campo, quem passaria a ser o principal elo da circulação de bola da Argentina?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Otamendi em todas as leituras.

| leitura | resposta |
|---|---|
| all passes / directed / none | Nicolás Hernán Otamendi · 44.5 |
| all passes / directed / passes | Nicolás Hernán Otamendi · 85.5 |
| all passes / directed / xt | Nicolás Hernán Otamendi · 35.0 |
| all passes / undirected / none | Nicolás Hernán Otamendi · 20.74 |
| all passes / undirected / passes | Nicolás Hernán Otamendi · 46.0 |
| all passes / undirected / xt | Nicolás Hernán Otamendi · 17.0 |
| open-play passes / directed / none | Nicolás Hernán Otamendi · 47.29 |
| open-play passes / directed / passes | Nicolás Hernán Otamendi · 92.5 |
| open-play passes / directed / xt | Nicolás Hernán Otamendi · 36.0 |
| open-play passes / undirected / none | Nicolás Hernán Otamendi · 23.65 |
| open-play passes / undirected / passes | Nicolás Hernán Otamendi · 55.0 |
| open-play passes / undirected / xt | Nicolás Hernán Otamendi · 18.0 |

### c02

> Sem Otamendi em campo, algum companheiro da Argentina ficaria sem trocar passes com ninguém do time? Quem?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Pezzella, que entrou no fim da prorrogação e só trocou passes com Otamendi.

| leitura | resposta |
|---|---|
| all passes | Germán Alejandro Pezzella |
| open-play passes | Germán Alejandro Pezzella |

### c03

> Se Messi não estivesse em campo, quem passaria a ser o principal elo da circulação de bola da Argentina?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Enzo Fernández na maioria, Otamendi sem peso e sem direção, empate Acuña e Otamendi com peso de xT.

| leitura | resposta |
|---|---|
| all passes / directed / none | Enzo Fernandez · 48.5 |
| all passes / directed / passes | Enzo Fernandez · 89.5 |
| all passes / directed / xt | Enzo Fernandez · 44.0 |
| all passes / undirected / none | Nicolás Hernán Otamendi · 18.24 |
| all passes / undirected / passes | Enzo Fernandez · 45.5 |
| all passes / undirected / xt | **empate:** Marcos Javier Acuña; Nicolás Hernán Otamendi |
| open-play passes / directed / none | Enzo Fernandez · 49.27 |
| open-play passes / directed / passes | Enzo Fernandez · 94.5 |
| open-play passes / directed / xt | Enzo Fernandez · 49.0 |
| open-play passes / undirected / none | Nicolás Hernán Otamendi · 19.64 |
| open-play passes / undirected / passes | Enzo Fernandez · 58.5 |
| open-play passes / undirected / xt | **empate:** Marcos Javier Acuña; Nicolás Hernán Otamendi |

### c04

> Se Varane não estivesse em campo, quem passaria a ser o principal elo da circulação de bola da França?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Koundé em 10 de 12, Rabiot com peso de xT sem direção.

| leitura | resposta |
|---|---|
| all passes / directed / none | Jules Koundé · 33.06 |
| all passes / directed / passes | Jules Koundé · 78.5 |
| all passes / directed / xt | Jules Koundé · 35.0 |
| all passes / undirected / none | Jules Koundé · 14.57 |
| all passes / undirected / passes | Jules Koundé · 47.0 |
| all passes / undirected / xt | Adrien Rabiot · 14.0 |
| open-play passes / directed / none | Jules Koundé · 32.84 |
| open-play passes / directed / passes | Jules Koundé · 91.0 |
| open-play passes / directed / xt | Jules Koundé · 34.0 |
| open-play passes / undirected / none | Jules Koundé · 15.41 |
| open-play passes / undirected / passes | Jules Koundé · 46.0 |
| open-play passes / undirected / xt | Adrien Rabiot · 16.0 |

### c05

> Se Koundé não estivesse em campo, quem passaria a ser o principal elo da circulação de bola da França?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Rabiot, Tchouaméni, Kolo Muani ou Upamecano.

| leitura | resposta |
|---|---|
| all passes / directed / none | Adrien Rabiot · 24.34 |
| all passes / directed / passes | Aurélien Djani Tchouaméni · 55.0 |
| all passes / directed / xt | Adrien Rabiot · 29.0 |
| all passes / undirected / none | Randal Kolo Muani · 14.21 |
| all passes / undirected / passes | Aurélien Djani Tchouaméni · 31.0 |
| all passes / undirected / xt | Adrien Rabiot · 15.0 |
| open-play passes / directed / none | Adrien Rabiot · 25.24 |
| open-play passes / directed / passes | Dayotchanculle Upamecano · 50.0 |
| open-play passes / directed / xt | Adrien Rabiot · 27.0 |
| open-play passes / undirected / none | Randal Kolo Muani · 14.11 |
| open-play passes / undirected / passes | Dayotchanculle Upamecano · 38.0 |
| open-play passes / undirected / xt | Adrien Rabiot · 16.0 |

## sequence

### q01

> Qual jogador argentino mais vezes finalizou logo depois de receber um passe de um companheiro?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Lautaro Martínez.

| leitura | resposta |
|---|---|
| all passes / anything | Lautaro Javier Martínez · 4 |
| all passes / only his carries and take-ons | Lautaro Javier Martínez · 4 |
| open-play passes / anything | Lautaro Javier Martínez · 3 |
| open-play passes / only his carries and take-ons | Lautaro Javier Martínez · 3 |

### q02

> Quem deu mais vezes o último passe antes de uma finalização da Argentina?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Di María contando todos os passes; Messi, ou empate Messi e Acuña, só com passes de bola rolando.

| leitura | resposta |
|---|---|
| all passes / receiver shoots | Ángel Fabián Di María Hernández · 4 |
| all passes / any pass in the possession | Ángel Fabián Di María Hernández · 4 |
| open-play passes / receiver shoots | **empate:** Lionel Andrés Messi Cuccittini; Marcos Javier Acuña |
| open-play passes / any pass in the possession | Lionel Andrés Messi Cuccittini · 4 |

### q03

> Quem deu mais vezes o penúltimo passe nas jogadas da Argentina que terminaram em finalização?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Empate entre Julián Álvarez e Mac Allister quando só contam passes de bola rolando.

| leitura | resposta |
|---|---|
| all passes / receiver shoots | Julián Álvarez · 4 |
| all passes / any pass in the possession | Julián Álvarez · 4 |
| open-play passes / receiver shoots | **empate:** Alexis Mac Allister; Julián Álvarez |
| open-play passes / any pass in the possession | **empate:** Alexis Mac Allister; Julián Álvarez |

### q04

> Qual jogador francês mais vezes finalizou logo depois de receber um passe de um companheiro?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Empate entre Mbappé e Kolo Muani numa leitura.

| leitura | resposta |
|---|---|
| all passes / anything | **empate:** Kylian Mbappé Lottin; Randal Kolo Muani |
| all passes / only his carries and take-ons | Randal Kolo Muani · 2 |
| open-play passes / anything | Kylian Mbappé Lottin · 2 |
| open-play passes / only his carries and take-ons | **empate:** Adrien Rabiot; Kylian Mbappé Lottin; Randal Kolo Muani |

## play

### p01

> Quais dois jogadores argentinos mais vezes participaram juntos das mesmas jogadas que chegaram ao terço final?

Estágio: **graph** · conferência: `set` · estável: **sim**

Nota: Enzo Fernández e Messi.

| leitura | resposta |
|---|---|
| reaches the attacking third | Enzo Fernandez e Lionel Andrés Messi Cuccittini · 23 |

### p02

> Qual jogador participou de mais jogadas da Argentina que começaram no próprio campo de defesa e terminaram em finalização?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Messi.

| leitura | resposta |
|---|---|
| defensive third / last action is a shot | Lionel Andrés Messi Cuccittini · 3 |
| defensive third / a shot in the possession | Lionel Andrés Messi Cuccittini · 3 |
| own half / last action is a shot | Lionel Andrés Messi Cuccittini · 6 |
| own half / a shot in the possession | Lionel Andrés Messi Cuccittini · 6 |

### p03

> Qual jogador participou de mais jogadas da Argentina que terminaram em finalização?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Messi.

| leitura | resposta |
|---|---|
| last action is a shot | Lionel Andrés Messi Cuccittini · 12 |
| a shot in the possession | Lionel Andrés Messi Cuccittini · 12 |

### p04

> Qual jogador participou de mais jogadas da França que terminaram em finalização?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Mbappé.

| leitura | resposta |
|---|---|
| last action is a shot | Kylian Mbappé Lottin · 6 |
| a shot in the possession | Kylian Mbappé Lottin · 6 |

### p05

> Nas jogadas da Argentina que terminaram em finalização e em que Messi tocou na bola, qual companheiro mais participou junto com ele?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Enzo Fernández.

| leitura | resposta |
|---|---|
| last action is a shot | Enzo Fernandez · 6 |
| a shot in the possession | Enzo Fernandez · 6 |

### p06

> Nas jogadas da França que terminaram em finalização e em que Mbappé tocou na bola, qual companheiro mais participou junto com ele?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Rabiot.

| leitura | resposta |
|---|---|
| last action is a shot | Adrien Rabiot · 2 |
| a shot in the possession | Adrien Rabiot · 2 |

### p07

> Quais dois jogadores franceses mais vezes participaram juntos das mesmas jogadas que chegaram ao terço final?

Estágio: **removed** · conferência: `set` · estável: **não**

Nota: Empate entre Rabiot e Tchouaméni e Rabiot e Mbappé.

| leitura | resposta |
|---|---|
| reaches the attacking third | **empate:** Adrien Rabiot e Aurélien Djani Tchouaméni; Adrien Rabiot e Kylian Mbappé Lottin |

### p08

> Quem participou de mais jogadas da França que levaram a bola da defesa até o terço final no segundo tempo?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Kolo Muani se a jogada começa no terço de defesa; empate de três se começa no próprio campo.

| leitura | resposta |
|---|---|
| defensive third | Randal Kolo Muani · 4 |
| own half | **empate:** Aurélien Djani Tchouaméni; Jules Koundé; Randal Kolo Muani |

### p09

> Em quantas jogadas da França que terminaram em finalização na prorrogação Mbappé participou?

Estágio: **removed** · conferência: `value` · estável: **não**

Nota: 2.

| leitura | resposta |
|---|---|
| last action is a shot | 2 |
| a shot in the possession | 2 |
| a penalty is not a play | 1 |

### p10

> Qual jogador participou de mais jogadas da Argentina que terminaram em gol?

Estágio: **candidate** · conferência: `player` · estável: **sim**

Nota: Messi (3). Fica de reserva: as ferramentas não identificam a jogada de cada gol, e a conferência pelo grafo não tem como responder.

| leitura | resposta |
|---|---|
| every goal | Lionel Andrés Messi Cuccittini · 3 |
| penalty goals left out | Lionel Andrés Messi Cuccittini · 2 |

## substitution

### b01

> Depois que Di María foi substituído, qual trio argentino mais trocou passes entre si, com os três passando a bola uns para os outros?

Estágio: **removed** · conferência: `set` · estável: **não**

Nota: Enzo Fernández, Messi e De Paul.

| leitura | resposta |
|---|---|
| all passes / each pair in some direction / after the substitution (raw JSON) | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 34 |
| all passes / each pair in some direction / after the player's last action | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 35 |
| all passes / all six directions / after the substitution (raw JSON) | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 34 |
| all passes / all six directions / after the player's last action | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 35 |
| open-play passes / each pair in some direction / after the substitution (raw JSON) | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 33 |
| open-play passes / each pair in some direction / after the player's last action | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 34 |
| open-play passes / all six directions / after the substitution (raw JSON) | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 33 |
| open-play passes / all six directions / after the player's last action | Enzo Fernandez e Lionel Andrés Messi Cuccittini e Rodrigo Javier De Paul · 34 |
| sequence A -> B -> C / all passes / same possession / consecutive passes / after the substitution (raw JSON) | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / all passes / same possession / other passes between allowed / after the substitution (raw JSON) | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / all passes / any possession / consecutive passes / after the substitution (raw JSON) | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / all passes / any possession / other passes between allowed / after the substitution (raw JSON) | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / open-play passes / same possession / consecutive passes / after the substitution (raw JSON) | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / open-play passes / same possession / other passes between allowed / after the substitution (raw JSON) | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / open-play passes / any possession / consecutive passes / after the substitution (raw JSON) | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / open-play passes / any possession / other passes between allowed / after the substitution (raw JSON) | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / all passes / same possession / consecutive passes / after the player's last action | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / all passes / same possession / other passes between allowed / after the player's last action | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / all passes / any possession / consecutive passes / after the player's last action | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / all passes / any possession / other passes between allowed / after the player's last action | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / open-play passes / same possession / consecutive passes / after the player's last action | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / open-play passes / same possession / other passes between allowed / after the player's last action | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / open-play passes / any possession / consecutive passes / after the player's last action | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |
| sequence A -> B -> C / open-play passes / any possession / other passes between allowed / after the player's last action | **empate:** Alexis Mac Allister e Enzo Fernandez e Lionel Andrés Messi Cuccittini; Nicolás Hernán Otamendi e Cristian Gabriel Romero e Enzo Fernandez |

### b02

> Depois que Di María foi substituído, qual companheiro mais passou a bola para Messi?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Enzo Fernández.

| leitura | resposta |
|---|---|
| all passes / after the substitution (raw JSON) | Enzo Fernandez · 6 |
| all passes / after the player's last action | Enzo Fernandez · 6 |
| open-play passes / after the substitution (raw JSON) | Enzo Fernandez · 6 |
| open-play passes / after the player's last action | Enzo Fernandez · 6 |

### b03

> Depois que Dembélé foi substituído no primeiro tempo, qual companheiro mais passou a bola para Mbappé?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Rabiot. O recorte usa a saída de Dembélé, e não a de Giroud (no mesmo minuto), porque o amarelo de Giroud foi dado com ele já no banco e aparece como uma ação dele aos 95'.

| leitura | resposta |
|---|---|
| all passes / after the substitution (raw JSON) | Adrien Rabiot · 6 |
| all passes / after the player's last action | Adrien Rabiot · 6 |
| open-play passes / after the substitution (raw JSON) | Adrien Rabiot · 6 |
| open-play passes / after the player's last action | Adrien Rabiot · 6 |

### b04

> Depois que Dembélé foi substituído no primeiro tempo, qual trio francês mais trocou passes entre si, com os três passando a bola uns para os outros?

Estágio: **removed** · conferência: `set` · estável: **não**

Nota: Upamecano, Koundé e Varane.

| leitura | resposta |
|---|---|
| all passes / each pair in some direction / after the substitution (raw JSON) | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 44 |
| all passes / each pair in some direction / after the player's last action | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 46 |
| all passes / all six directions / after the substitution (raw JSON) | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 44 |
| all passes / all six directions / after the player's last action | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 46 |
| open-play passes / each pair in some direction / after the substitution (raw JSON) | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 43 |
| open-play passes / each pair in some direction / after the player's last action | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 45 |
| open-play passes / all six directions / after the substitution (raw JSON) | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 43 |
| open-play passes / all six directions / after the player's last action | Dayotchanculle Upamecano e Jules Koundé e Raphaël Varane · 45 |
| sequence A -> B -> C / all passes / same possession / consecutive passes / after the substitution (raw JSON) | **empate:** Theo Bernard François Hernández e Dayotchanculle Upamecano e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé; Aurélien Djani Tchouaméni e Jules Koundé e Raphaël Varane |
| sequence A -> B -> C / all passes / same possession / other passes between allowed / after the substitution (raw JSON) | **empate:** Theo Bernard François Hernández e Dayotchanculle Upamecano e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé; Aurélien Djani Tchouaméni e Jules Koundé e Raphaël Varane |
| sequence A -> B -> C / all passes / any possession / consecutive passes / after the substitution (raw JSON) | **empate:** Theo Bernard François Hernández e Dayotchanculle Upamecano e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé; Aurélien Djani Tchouaméni e Jules Koundé e Raphaël Varane |
| sequence A -> B -> C / all passes / any possession / other passes between allowed / after the substitution (raw JSON) | **empate:** Theo Bernard François Hernández e Dayotchanculle Upamecano e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé; Aurélien Djani Tchouaméni e Jules Koundé e Raphaël Varane |
| sequence A -> B -> C / open-play passes / same possession / consecutive passes / after the substitution (raw JSON) | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 4 |
| sequence A -> B -> C / open-play passes / same possession / other passes between allowed / after the substitution (raw JSON) | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 4 |
| sequence A -> B -> C / open-play passes / any possession / consecutive passes / after the substitution (raw JSON) | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 4 |
| sequence A -> B -> C / open-play passes / any possession / other passes between allowed / after the substitution (raw JSON) | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 4 |
| sequence A -> B -> C / all passes / same possession / consecutive passes / after the player's last action | **empate:** Theo Bernard François Hernández e Dayotchanculle Upamecano e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé; Aurélien Djani Tchouaméni e Jules Koundé e Raphaël Varane |
| sequence A -> B -> C / all passes / same possession / other passes between allowed / after the player's last action | **empate:** Theo Bernard François Hernández e Dayotchanculle Upamecano e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé; Aurélien Djani Tchouaméni e Jules Koundé e Raphaël Varane |
| sequence A -> B -> C / all passes / any possession / consecutive passes / after the player's last action | **empate:** Theo Bernard François Hernández e Dayotchanculle Upamecano e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé; Aurélien Djani Tchouaméni e Jules Koundé e Raphaël Varane |
| sequence A -> B -> C / all passes / any possession / other passes between allowed / after the player's last action | **empate:** Theo Bernard François Hernández e Dayotchanculle Upamecano e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé; Aurélien Djani Tchouaméni e Jules Koundé e Raphaël Varane |
| sequence A -> B -> C / open-play passes / same possession / consecutive passes / after the player's last action | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 4 |
| sequence A -> B -> C / open-play passes / same possession / other passes between allowed / after the player's last action | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 4 |
| sequence A -> B -> C / open-play passes / any possession / consecutive passes / after the player's last action | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 4 |
| sequence A -> B -> C / open-play passes / any possession / other passes between allowed / after the player's last action | Dayotchanculle Upamecano e Raphaël Varane e Jules Koundé · 4 |

### b05

> Depois que Dembélé foi substituído no primeiro tempo, para qual companheiro Mbappé mais passou a bola?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Kolo Muani, que entrou no lugar de Dembélé.

| leitura | resposta |
|---|---|
| all passes / after the substitution (raw JSON) | Randal Kolo Muani · 3 |
| all passes / after the player's last action | Randal Kolo Muani · 3 |
| open-play passes / after the substitution (raw JSON) | Randal Kolo Muani · 3 |
| open-play passes / after the player's last action | Randal Kolo Muani · 3 |

### b06

> Depois que Dembélé foi substituído no primeiro tempo, qual dupla francesa mais trocou passes entre si?

Estágio: **removed** · conferência: `set` · estável: **não**

Nota: Empate entre Koundé e Varane e Upamecano e Varane quando as duas direções se somam.

| leitura | resposta |
|---|---|
| all passes / directed / after the substitution (raw JSON) | Jules Koundé e Raphaël Varane · 10 |
| all passes / directed / after the player's last action | Jules Koundé e Raphaël Varane · 11 |
| all passes / undirected / after the substitution (raw JSON) | **empate:** Jules Koundé e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane |
| all passes / undirected / after the player's last action | Jules Koundé e Raphaël Varane · 20 |
| open-play passes / directed / after the substitution (raw JSON) | Jules Koundé e Raphaël Varane · 10 |
| open-play passes / directed / after the player's last action | Jules Koundé e Raphaël Varane · 11 |
| open-play passes / undirected / after the substitution (raw JSON) | **empate:** Jules Koundé e Raphaël Varane; Dayotchanculle Upamecano e Raphaël Varane |
| open-play passes / undirected / after the player's last action | Jules Koundé e Raphaël Varane · 20 |

### b07

> Depois que Di María foi substituído, qual companheiro mais recebeu passes de Messi?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Empate entre Enzo Fernández e De Paul quando só contam passes de bola rolando.

| leitura | resposta |
|---|---|
| all passes / after the substitution (raw JSON) | Enzo Fernandez · 6 |
| all passes / after the player's last action | Enzo Fernandez · 6 |
| open-play passes / after the substitution (raw JSON) | **empate:** Enzo Fernandez; Rodrigo Javier De Paul |
| open-play passes / after the player's last action | **empate:** Enzo Fernandez; Rodrigo Javier De Paul |

### b08

> Depois que Kolo Muani entrou, ele se tornou o principal parceiro de Mbappé? Com quem Mbappé mais combinou a partir dali?

Estágio: **removed** · conferência: `player` · estável: **não**

Nota: Muda com a leitura: Rabiot contando os passes para Mbappé ou as duas direções; Kolo Muani contando só os passes de Mbappé.

| leitura | resposta |
|---|---|
| all passes / after the substitution (raw JSON) / both directions | Adrien Rabiot · 6 |
| all passes / after the substitution (raw JSON) / to Mbappé | Adrien Rabiot · 6 |
| all passes / after the substitution (raw JSON) / from Mbappé | Randal Kolo Muani · 3 |
| all passes / after the player's last action / both directions | Adrien Rabiot · 7 |
| all passes / after the player's last action / to Mbappé | Adrien Rabiot · 6 |
| all passes / after the player's last action / from Mbappé | Randal Kolo Muani · 3 |
| open-play passes / after the substitution (raw JSON) / both directions | Adrien Rabiot · 6 |
| open-play passes / after the substitution (raw JSON) / to Mbappé | Adrien Rabiot · 6 |
| open-play passes / after the substitution (raw JSON) / from Mbappé | Randal Kolo Muani · 3 |
| open-play passes / after the player's last action / both directions | Adrien Rabiot · 7 |
| open-play passes / after the player's last action / to Mbappé | Adrien Rabiot · 6 |
| open-play passes / after the player's last action / from Mbappé | Randal Kolo Muani · 3 |

### b09

> Depois que Di María foi substituído, quem passou a ser o jogador da Argentina mais procurado pelos companheiros?

Estágio: **graph** · conferência: `player` · estável: **sim**

Nota: Enzo Fernández, o que mais recebeu passes.

| leitura | resposta |
|---|---|
| all passes / after the substitution (raw JSON) | Enzo Fernandez · 41 |
| all passes / after the player's last action | Enzo Fernandez · 42 |
| open-play passes / after the substitution (raw JSON) | Enzo Fernandez · 37 |
| open-play passes / after the player's last action | Enzo Fernandez · 38 |
