# Revisão das perguntas da rodada única

39 perguntas ativas, todas estáveis em todas as leituras e conferidas pelo grafo. Resposta esperada = `ground_truth.json`. Último resultado: execução 09 (perguntas antigas, ferramentas v2.4) e execução 11 (perguntas de grafo, v3.1); cada símbolo abre o trace.

| Grupo | Perguntas | `events_in_prompt` | `graph_tools` |
|---|---|---|---|
| 1. Busca e contagem | 10 | 7/10 | 9/10 |
| 2. Relações na rede de passes | 13 | 5/13 | 13/13 |
| 3. Jogadas e sequências | 7 | 0/7 | 5/7 |
| 4. Antes e depois de um momento do jogo | 4 | 1/4 | 3/4 |
| Controle: sem resposta | 5 | 5/5 | 5/5 |

## 1. Busca e contagem

O que a pergunta exige: achar um lance ou contar ações com filtro.

| id | tipo | pergunta | resposta esperada | events | graph_tools |
|---|---|---|---|---|---|
| f01 | fact | Quem recebeu o primeiro cartão amarelo da final? | Enzo Fernandez | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/d1a11e06d5ac0f81324b1ff2dcc4c2b9) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/38bd7ad620190a4e9f015bebb8953d56) |
| f02 | fact | Quem cometeu a falta que deu origem ao primeiro pênalti da final? | Ousmane Dembélé | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/8e7ce94e5abaee548bc9039b0fda58a2) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6fca8b7a948977c44aa51a55ac98aed5) |
| f03 | fact | No lance do gol de Messi na prorrogação, o goleiro francês tinha feito uma defesa instantes antes. Quem deu o chute que ele defendeu? | Lautaro Javier Martínez | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/47dffd870d5b6a37dba2d7c5165c336a) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/f04b81bbfc0eaf02b11bea2ec406c576) |
| f04 | fact | Quem deu o passe para o gol que deixou o placar em 2 a 2 no tempo normal? | Marcus Thuram | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9b5c02117d2a08fe8cd9f5782ab9969d) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9f3446a833353b1173940ab7dc32f3f5) |
| f05 | fact | Quem fez a última finalização da França na final, antes da disputa de pênaltis? | Randal Kolo Muani | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c572160cf5274883bdad9b13017adedb) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/b0860f83835980709f12332bdd478c58) |
| a01 | filtered_aggregation | Quem deu mais passes certos no terço final do campo pela Argentina? | Lionel Andrés Messi Cuccittini | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/5d5adb84313c3ebcc19e96ef6c6cfc7c) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/efbaf9611c1521b0bf82fde5c8ca6d35) |
| a03 | filtered_aggregation | Depois do gol que deixou o placar em 2 a 2 no tempo normal, quantas finalizações a Argentina fez até o fim da prorrogação? | 10 | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/eac9bfe2166cfb22a6cabe34b6d7c1d2) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/51fd3498a021311e14c86ee265ef0e9f) |
| a05 | filtered_aggregation | Enquanto a Argentina vencia por 2 a 0, qual jogador argentino acertou mais passes, e quantos? | Enzo Fernandez · 26 | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/eae12668e16ec6e417a3e471da890fee) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/fec0392eb0767e161933b8fef4ad6955) |
| a06 | filtered_aggregation | Na prorrogação, quem fez mais desarmes certos pela Argentina? | Enzo Fernandez | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9de32210b35125f7108330d9d2754879) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/fe4971ef766a95bc9680b07733512f4e) |
| a07 | filtered_aggregation | No segundo tempo, quem cometeu mais faltas? | Julián Álvarez | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/bf6384fa5748dfb7a56fec84b3fb7335) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e2f8906f9e5e21cfe8cb6ab66df05aa7) |

## 2. Relações na rede de passes

O que a pergunta exige: quem passa para quem: parcerias, quem conecta o time, o que muda sem um jogador.

| id | tipo | pergunta | resposta esperada | events | graph_tools |
|---|---|---|---|---|---|
| n03 | network | Na troca de passes da Argentina, qual jogador, se não estivesse em campo, deixaria algum companheiro sem trocar passes com ninguém do time? | Nicolás Hernán Otamendi | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6b29fbb9544d794f5335ef10b5cc84eb) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/fc16a4d053ee1956eac141e9c970e140) |
| n04 | network | Qual dupla da França mais trocou passes entre si na final? | Dayotchanculle Upamecano, Raphaël Varane | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a1ace14555ba3086df2e77ab27a939e4) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9f1e27be5920f8e976230062325c3713) |
| n05 | network | Qual dupla da Argentina mais trocou passes entre si na final? | Cristian Gabriel Romero, Nicolás Hernán Otamendi | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/2ae93099b57469034f945bedcb93c79b) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/d3c84b43efdf20115273f4df7ebbbcd7) |
| n06 | network | Qual jogador da Argentina trocou passes com o maior número de companheiros diferentes na final? | Enzo Fernandez | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/3488b096177a82e18e74c71cac50e8e8) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/013dfa0de4283c3ca46c78b16a5a5f39) |
| n09 | network | Qual sequência de três jogadores da França, com a bola passando de um para o outro, mais se repetiu na final? | Dayotchanculle Upamecano, Raphaël Varane, Jules Koundé | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c1b233a63cf6480d72c525f19d847f90) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/d88a8f85d746b1d1d5cb195d7b44b464) |
| s01 | network_slice | Na prorrogação, quem foi o principal elo da circulação de bola da França? | Jules Koundé | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/0e77e74ff4177565fb0473340fec4207) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6438e5e636d00142c8c2184143864276) |
| s03 | network_slice | Depois do gol que deixou o placar em 2 a 2 no tempo normal, qual dupla da França mais trocou passes entre si? | Jules Koundé, Raphaël Varane | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/36c83fbffb1067d602c09bb82a2d1348) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/27770d7adab6a80e5c4eb6340aee6d2b) |
| s04 | network_slice | A dupla da Argentina que mais trocou passes entre si no primeiro tempo continuou sendo a principal no segundo tempo? Qual foi a dupla que mais trocou passes no segundo tempo? | Enzo Fernandez, Rodrigo Javier De Paul | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/30faf2377bc847519712bebefc3774e8) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/995b6a3cf0950ea95825106a2e9f0f32) |
| s06 | network_slice | No segundo tempo, qual companheiro mais recebeu passes de Enzo Fernández? | Rodrigo Javier De Paul | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/66184c03e03845cf4b5d2afe085edfae) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/416514d587ea48fad781eec9a159aaee) |
| s07 | network_slice | Na prorrogação, qual sequência de três jogadores da Argentina, com a bola passando de um para o outro, mais se repetiu? | Nicolás Hernán Otamendi, Cristian Gabriel Romero, Enzo Fernandez | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a50f9464687fc2ab2fce39a40751a3a1) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/0af8964fe7fc591148a4014589065926) |
| t06 | structure | Na prorrogação, qual jogador da França, se não estivesse em campo, deixaria algum companheiro sem trocar passes com ninguém do time? | Jules Koundé | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9865a0039522f56b12287d3ea2e40aad) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e570cbc16f61d974c0214c2d906ace9d) |
| c01 | counterfactual | Se Enzo Fernández não estivesse em campo, quem passaria a ser o principal elo da circulação de bola da Argentina? | Nicolás Hernán Otamendi | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/831140e539ab0a710c346484f23a772c) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/9c700a6348a83bf937256fd47e06edae) |
| c02 | counterfactual | Sem Otamendi em campo, algum companheiro da Argentina ficaria sem trocar passes com ninguém do time? Quem? | Germán Alejandro Pezzella | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/14d9eb151deb9906e33939a240148782) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e0fe4ed85a577f5841f40b31dc7a9ee8) |

## 3. Jogadas e sequências

O que a pergunta exige: seguir a ordem das ações dentro de uma jogada até a finalização ou o gol.

| id | tipo | pergunta | resposta esperada | events | graph_tools |
|---|---|---|---|---|---|
| q01 | sequence | Qual jogador argentino mais vezes finalizou logo depois de receber um passe de um companheiro? | Lautaro Javier Martínez | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/01c182dca891f73b933e7a37ccf60369) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/df08c8a9037e94b040615264c08aee48) |
| p01 | play | Quais dois jogadores argentinos mais vezes participaram juntos das mesmas jogadas que chegaram ao terço final? | Enzo Fernandez, Lionel Andrés Messi Cuccittini | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/99917351c759e08e043d41586a2f215b) | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/bda6c39e0d47e51ccb8fc34c85fb7bc4) |
| p02 | play | Qual jogador participou de mais jogadas da Argentina que começaram no próprio campo de defesa e terminaram em finalização? | Lionel Andrés Messi Cuccittini | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/0273b34b8a8fb0b6ce3fb010c5ee2eea) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/fa73983c638302d527cb5b8e71d6d2c7) |
| p03 | play | Qual jogador participou de mais jogadas da Argentina que terminaram em finalização? | Lionel Andrés Messi Cuccittini | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/a6496476aa9287ac37b29c2a435bdf8d) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/f12ec82c4a95086f287d190145e74248) |
| p04 | play | Qual jogador participou de mais jogadas da França que terminaram em finalização? | Kylian Mbappé Lottin | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/f88ca53f26d3c382bd150580394dd5f2) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/8da94fa18a64ebfb036c27ec80b30c6f) |
| p05 | play | Nas jogadas da Argentina que terminaram em finalização e em que Messi tocou na bola, qual companheiro mais participou junto com ele? | Enzo Fernandez | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/10bbc68e998c7ab25cb8d95b65175dbb) | [⚠️](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e866f6fe2aa233197c1acc169ba6cdf9) |
| p06 | play | Nas jogadas da França que terminaram em finalização e em que Mbappé tocou na bola, qual companheiro mais participou junto com ele? | Adrien Rabiot | [❌](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/492b2b166af2540f05e0f2c0d34ce47e) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c7d5b362e68c2a6d9eb5a7d773685a17) |

## 4. Antes e depois de um momento do jogo

O que a pergunta exige: achar o momento de uma substituição e comparar a partir dele.

| id | tipo | pergunta | resposta esperada | events | graph_tools |
|---|---|---|---|---|---|
| b02 | substitution | Depois que Di María foi substituído, qual companheiro mais passou a bola para Messi? | Enzo Fernandez | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/8b4a56b22ddc87250a7b54a88e9db648) | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/7759bc7fa4cbaeac05144aaeff613ae5) |
| b03 | substitution | Depois que Dembélé foi substituído no primeiro tempo, qual companheiro mais passou a bola para Mbappé? | Adrien Rabiot | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/317107b4b5e624ffd3aa0b97a4962697) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/64b5d84cf6b83c1b2ca7bc16a973efbd) |
| b05 | substitution | Depois que Dembélé foi substituído no primeiro tempo, para qual companheiro Mbappé mais passou a bola? | Randal Kolo Muani | [🟡](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e880c4b37fc3d296dbe6ac70671e3c52) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/5479ef86869a61d1eed281108e01cd3a) |
| b09 | substitution | Depois que Di María foi substituído, quem passou a ser o jogador da Argentina mais procurado pelos companheiros? | Enzo Fernandez | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/2ec9992474b31c222e88c55732c178eb) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/059af8b86f58824ec5792f46d14fe710) |

## Controle: sem resposta

O que a pergunta exige: perceber que o dado não existe.

| id | tipo | pergunta | resposta esperada | events | graph_tools |
|---|---|---|---|---|---|
| u01 | unanswerable | Quantos minutos Messi passou no campo de ataque durante a final? | sem dados | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/f59b890dd74933eb20d515752078f530) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/6138ec8cfdbc9c59e66a5dd152c33a0c) |
| u02 | unanswerable | Qual foi a distância total percorrida por Rodrigo De Paul na final? | sem dados | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/dfd021e69ad1ef07016d49e8a131e432) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/95b927a10fd6f887bab200b4d9c88621) |
| u03 | unanswerable | Quantos piques em alta velocidade Mbappé deu na prorrogação? | sem dados | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/54f9e1ac64a489fa2246cb3b22d5bf2f) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/7a0b4542e40079da0be34f4edb370d2c) |
| u04 | unanswerable | A que velocidade saiu o chute de Mbappé no gol que deixou o placar em 2 a 2? | sem dados | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/e870ca60048402e31aba428225ba6899) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/c96b8c07bd535dc827b131bb2afbb758) |
| u05 | unanswerable | Em quantos lances Mbappé ficou em posição de impedimento sem participar da jogada? | sem dados | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/0d9041dd3de27ec689a516ec62f17e54) | [✅](https://us.cloud.langfuse.com/project/cmrnt6v8800q4ad0dlq21s2ms/traces/746634d71a2643b26efcefb3f07d65cb) |
