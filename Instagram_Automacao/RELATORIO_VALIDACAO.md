# Relatório de validação

Data: 24/10/2026

## Validado neste ambiente

- Compilação de todos os módulos Python: aprovada.
- Testes automatizados: 2 aprovados.
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

## Observado nas capturas fornecidas

- `@gabrielmartins826392`: perfil completo e 7 publicações; deve ser preservado.
- `@dailysar_inha3836`: aplicativo indica falta de biografia e 0/7 publicações.
- `@lorenaalves9394`: aplicativo indica falta de biografia e 0/7 publicações.
- O VEM ENGAJAR BOT mostra 9 contas, mas as demais não estão totalmente visíveis.

Essas observações não foram gravadas nos slots porque não existe uma associação
confirmada entre usernames e os slots locais.

## Não testado (bloqueio de ambiente)

- Google Flow e download real: a máquina atual é Linux em nuvem, sem a sessão
  Chrome do usuário e sem prompts fornecidos.
- VEM ENGAJAR BOT: aplicativo Windows não está instalado/acessível nesta máquina.
- Instagram real: nenhuma credencial foi solicitada ou exposta; a máquina não
  dispõe da sessão do usuário nem de configuração da API oficial.
- Publicação: nenhuma postagem foi realizada.
- Avatar e biografia: nenhuma conta foi alterada.

## Próxima validação segura no Windows

1. Copiar esta pasta para o Windows e executar `iniciar.ps1`.
2. Associar cada username ao slot correto com `set-profile`, marcando contas
   completas antes de liberar a fila.
3. Calibrar os seletores atuais do Google Flow via Playwright Codegen.
4. Preencher `prompts.txt` do perfil de teste e gerar apenas uma imagem.
5. Confirmar arquivo 3:4 e hash no relatório.
6. Inspecionar a árvore UIA do VEM ENGAJAR BOT em modo somente leitura.
7. Para publicar, usar uma conta profissional de teste e a Graph API; confirmar
   que a verificação de username bloqueia qualquer divergência.

CAPTCHA, checkpoint, autenticação pendente ou bloqueio de segurança exigem
intervenção manual e não devem ser contornados.
