# Instagram Automação

Base local para Windows que organiza nove personagens virtuais, mantém uma fila
recuperável e auditável, evita duplicidades e publica somente por integrações
oficiais disponíveis. Ela não lê nem exporta cookies, senhas ou tokens.

## Executar em um comando

No PowerShell, dentro desta pasta:

```powershell
.\iniciar.ps1
```

O comando cria `.venv`, instala as dependências, inicializa `Perfil_01` a
`Perfil_09`, `logs`, `state.sqlite3` e `relatorio.json`, e abre o painel em
`http://127.0.0.1:8765`.

## Segurança e limites

- A fila nasce **pausada**. Use `instagram-automacao resume` só depois de revisar
  a conta de teste e os prompts.
- Perfis completos devem ser marcados como `complete`; tarefas não são criadas
  para eles. Cada publicação terá uma chave de idempotência e um hash do arquivo.
- CAPTCHA, checkpoint, login ou bloqueio deixam a tarefa como `blocked`. O sistema
  não tenta contornar esses controles.
- O Instagram é publicado somente pela Instagram Graph API. Ela exige conta
  profissional compatível, ativo público via HTTPS e permissões Meta válidas.
  Configure `META_IG_USER_ID` e `META_ACCESS_TOKEN` como variáveis do Windows;
  nunca salve o token neste projeto.
- Alteração de avatar/biografia não é implementada por automação clandestina de
  navegador. Sem API oficial disponível, fica como etapa assistida e verificada.

## Google Flow

O módulo `flow.py` usa um perfil Chrome dedicado e não extrai a sessão. Como a
interface do Flow muda, os seletores devem ser capturados na máquina Windows:

```powershell
.\.venv\Scripts\playwright.exe codegen https://labs.google/fx/tools/flow
```

Depois, registre em `config.toml` os seletores reais para: modo de imagem,
proporção, prompt, gerar, resultado e download. A automação exige exatamente um
resultado, aguarda o elemento final e confirma que o download não está vazio.
Se o Flow não oferecer 3:4, use:

```powershell
instagram-automacao fit-image entrada.png saida.jpg --mode pad
```

`pad` preserva o personagem sem deformação usando preenchimento desfocado;
`crop` faz recorte central.

## VEM ENGAJAR BOT

Não foi fornecida documentação de API. `instagram-automacao inspect-bot` procura
a janela via Windows UI Automation e faz somente leitura. A árvore de controles
precisa ser calibrada localmente antes de autorizar botões como “Abrir navegador”
ou “Verificar perfil”. A captura fornecida indica:

- `@gabrielmartins826392`: perfil completo, 7 posts — não alterar.
- `@dailysar_inha3836`: faltam biografia e 7 posts.
- `@lorenaalves9394`: faltam biografia e 7 posts.

Os demais perfis não ficaram totalmente visíveis e não são inferidos.

## Comandos úteis

```powershell
instagram-automacao status
instagram-automacao pause
instagram-automacao resume
instagram-automacao dashboard
instagram-automacao inspect-bot
instagram-automacao run
pytest
```

Cadastre o estado confirmado de uma conta antes de criar tarefas. Exemplo para
uma conta já completa (assim o worker nunca a modifica):

```powershell
instagram-automacao set-profile 1 gabrielmartins826392 --avatar-complete --biography-complete --posts 7 --complete
```

Tarefas são incluídas com payload JSON e chave única. O worker processa uma de
cada vez e bloqueia erros externos sem repetição cega:

```powershell
instagram-automacao enqueue 2 fit_image '{"source":"C:/Downloads/foto.png","destination":"C:/Instagram_Automacao/Perfil_02/publicacoes/001.jpg","mode":"pad"}' perfil02-fit-001
instagram-automacao resume
instagram-automacao run --once
```

## Estado da validação

Os componentes portáveis (estrutura, banco, retomada, idempotência, relatório e
conversão 3:4) possuem testes. Google Flow, VEM ENGAJAR BOT e Instagram real só
podem ser validados na área de trabalho Windows que contém essas sessões.
