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
| [s01](#s01) | network_slice | pilot | sim | 12 |
| [s02](#s02) | network_slice | removed | **não** | 24 |
| [s03](#s03) | network_slice | full | sim | 8 |
| [s04](#s04) | network_slice | pilot | sim | 4 |
| [s05](#s05) | network_slice | candidate | sim | 2 |
| [s06](#s06) | network_slice | full | sim | 2 |
| [s07](#s07) | network_slice | full | sim | 8 |
| [s08](#s08) | network_slice | removed | **não** | 6 |
| [s09](#s09) | network_slice | removed | **não** | 6 |
| [u01](#u01) | unanswerable | pilot | sim | – |
| [u02](#u02) | unanswerable | full | sim | – |
| [u03](#u03) | unanswerable | pilot | sim | – |
| [u04](#u04) | unanswerable | full | sim | – |
| [u05](#u05) | unanswerable | full | sim | – |
| [u06](#u06) | unanswerable | candidate | sim | – |

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
