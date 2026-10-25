# Relatório de validação

Data: 25/10/2026

## Validado neste ambiente

- Compilação de todos os módulos Python: aprovada.
- Testes automatizados: 16 aprovados.
- Inicialização repetível e cadastro dinâmico de perfis, diretórios, SQLite e relatório: aprovada.
- Cadastro em lote validado com 12 perfis via CLI; teste automatizado validado com
  25 perfis e criação correta de `Perfil_25`.
- Fila pausada por padrão, retomada, claim exclusivo e idempotência: aprovada.
- Conversão de imagem horizontal para 3:4 sem esticar: aprovada.
- Painel local e endpoint `/api/report`: resposta HTTP e JSON aprovados.
- Smoke test completo da fila em diretório isolado: aprovado. Uma imagem sintética
  de 1200×600 foi convertida para 1200×1600 (3:4), salva com 11.538 bytes e
  registrada com SHA-256. Em seguida, uma segunda tarefa destinada ao mesmo
  perfil foi ignorada após ele ser marcado como completo com 7 publicações; o
  arquivo bloqueado não foi criado.
- Acesso Git do repositório original via proxy da plataforma: aprovado antes da
  mudança de escopo da solicitação.

## Validado na área de trabalho Windows do usuário

- Google Flow: uma imagem foi gerada e recuperada em JPEG. O original íntegro
  mede 1792×2400; a versão ajustada sem deformação mede 1800×2400, proporção
  exata 3:4. Nenhuma imagem foi publicada.
- VEM ENGAJAR BOT: `inspect-bot` encontrou a janela no PowerShell do usuário
  `ferre`, registrou 139 controles e identificou os nove cartões de conta.
- A captura real foi reproduzida nos testes do parser: contador 9/9, sete contas
  com aviso explícito de perfil pendente e duas sem o selo completo exposto pela
  UIA. As duas últimas só podem ser preservadas se já estiverem confirmadas como
  completas no banco local; nunca são promovidas pela ausência do selo.
- O `dry-run` foi validado automaticamente para não alterar bytes nem horários
  do banco, relatório ou arquivos dos perfis.

Ainda falta executar a versão corrigida do `sync-bot --dry-run` uma vez no
Windows e conferir o resumo antes da sincronização local efetiva.

## Não testado (bloqueio de ambiente)

- Instagram real: nenhuma credencial foi solicitada ou exposta; a máquina não
  dispõe da sessão do usuário nem de configuração da API oficial.
- Publicação: nenhuma postagem foi realizada.
- Avatar e biografia: nenhuma conta foi alterada.

## Próxima validação segura no Windows

1. Atualizar os arquivos do Windows para o commit informado no GitHub.
2. Executar `inspect-bot` e `sync-bot --dry-run` no PowerShell do usuário
   `ferre`; confirmar 9/9, sete `unchanged` e duas
   `skipped_complete_unconfirmed`.
3. Executar `sync-bot` para aplicar somente a associação local, sem clicar no
   VEM ENGAJAR.
4. Definir identidade, biografia, avatar, prompts e legendas do primeiro perfil
   de teste; gerar apenas os arquivos necessários para chegar a sete posts.
5. Configurar uma conta profissional de teste e a Instagram Graph API, com
   mídia pública HTTPS; confirmar a verificação de username antes de publicar.
6. Validar o fluxo completo em uma conta e somente depois ampliar a fila.

CAPTCHA, checkpoint, autenticação pendente ou bloqueio de segurança exigem
intervenção manual e não devem ser contornados.
