# Overleaf e a skill de escrita no Claude Code web

O que está verificado e o que não está, conferido em 10/10/2026 num contêiner de nuvem.

## Verificado

- **Skill:** as skills de `.claude/skills/` do repositório são carregadas numa sessão da web (as cinco do artigo
  apareceram na lista de skills da própria sessão). A `academic-writing` (MIT, de `jamditis/claude-skills-journalism`)
  foi copiada para lá sem alteração, com a licença; ver `.claude/skills/academic-writing/NOTICE.md`.
- **claudeleaf roda na nuvem:** Node 22 e npm estão no contêiner, `npx -y claudeleaf@0.2.0 mcp` sobe e expõe 17
  ferramentas (`overleaf_list_projects`, `overleaf_read_document`, `overleaf_replace_text`, `overleaf_compile`...).
  Sem sessão, ele responde "No Overleaf session found".
- **Rede:** `registry.npmjs.org` e `www.overleaf.com` responderam por HTTPS. Um WebSocket aberto contra o
  Overleaf (e contra um servidor de eco público) completou o *handshake*, mas **o README do proxy da nuvem lista
  "WebSocket upgrades" como não suportados**, e uma primeira tentativa, no mesmo endereço, devolveu 502. O
  `claudeleaf` lê e edita documentos por WebSocket (ShareJS sobre Socket.IO), então a leitura e a edição só ficam
  confirmadas com uma sessão real. A política de rede do SEU ambiente pode ser mais restrita que a deste: se
  `www.overleaf.com` for negado, acrescente o domínio em Allowed domains (menu do ambiente na barra de título da
  sessão, Edit, Network access).
- **Variáveis de ambiente:** testado numa sessão em andamento, uma variável criada depois da sessão abrir não
  aparece no contêiner (nem no `env`, nem em `/proc/*/environ`, nem em arquivo). A documentação do ambiente diz
  que uma sessão nova a recebe. Não há, de dentro da sessão, como relê-la.

## Não verificado (precisa de você)

- Uma edição real no Overleaf: exige a sua sessão, que eu não tenho. O primeiro teste é pedir
  `overleaf_list_projects` e ver o projeto do artigo.
- Se a web carrega o `.mcp.json` do repositório sozinha. O arquivo e a aprovação
  (`enabledMcpjsonServers` em `.claude/settings.json`) estão no lugar; se a sessão não mostrar as ferramentas
  `overleaf_*`, use o plano B abaixo.

## O que falta: a sessão do Overleaf

O `claudeleaf` entra no Overleaf com o cookie da sua conta, obtido por um login manual num navegador
(`npx claudeleaf login`). A nuvem não tem navegador, então o login se faz na sua máquina e o arquivo resultante
vai para o ambiente como segredo:

1. **Crie uma conta só para o agente** e convide-a no projeto do artigo (Share, Can edit). É a recomendação do
   próprio claudeleaf, e aqui pesa mais: o cookie é uma credencial da conta e vai ficar no ambiente da nuvem. Com
   uma conta separada, o agente só alcança o que foi compartilhado com ela, e o histórico do Overleaf mostra o que
   ele mudou.
2. Na sua máquina: `npx claudeleaf login`, entre com essa conta, depois `npx claudeleaf doctor`.
3. Copie o conteúdo de `~/.claudeleaf/session.json`.
4. No menu do ambiente da sessão (barra de título), Edit, acrescente a variável de ambiente
   **`CLAUDELEAF_SESSION_JSON`** com esse conteúdo. **Não cole o conteúdo no chat.**
5. Inicie uma sessão nova (variáveis e `.mcp.json` são lidos no início). O hook
   `.claude/hooks/overleaf-session.sh` recria `~/.claudeleaf/session.json` (modo 600) a partir da variável e
   avisa, sem imprimir o conteúdo, se ela faltar ou estiver malformada.
6. Teste: "liste meus projetos do Overleaf".

O cookie expira. Quando as ferramentas voltarem a dizer que o login é necessário, repita os passos 2 a 4.

## Plano B, sem MCP

Se a sessão não carregar o servidor MCP, o mesmo código roda como CLI pelo Bash, com a mesma sessão em
`~/.claudeleaf/session.json`:

```bash
npx -y claudeleaf@0.2.0 projects
npx -y claudeleaf@0.2.0 ls "Nome do projeto"
npx -y claudeleaf@0.2.0 cat "Nome do projeto" main.tex
npx -y claudeleaf@0.2.0 compile "Nome do projeto" --warnings
```

## Sobre a skill `academic-writing`

É genérica (IMRaD, bolsas, escolha de periódico, ética). Em conflito com `paper-style-pt`, vale o
`paper-style-pt` (ela usa "We found" e travessão; o artigo, não). A parte útil aqui é a seção de uso de IA e
declaração, e o aviso sobre citações fabricadas.

## O que o hook de início de sessão faz

`.claude/hooks/session-start.sh` (só na web): cria `.venv` e instala `.[dev,paper]` se faltar (não precisa de
Neo4j, Docker nem chave), de modo que `scripts/paper_numbers.py`, `scripts/figures.py` e os testes rodam. Roda
de forma síncrona: a sessão só abre depois que ele termina.
