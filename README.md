# Gerador de Vale Presente — Núcleo de Incentivos

Sobe a BASE COMPLETA + as apurações do mês → devolve um ValePresente por apuração
(abas COM CADASTRO / SEM CADASTRO), e a lista consolidada de quem está sem cadastro.

## Rodar no seu computador
Duplo clique em `rodar_local.bat` (precisa de Python). Mantenha a janela preta aberta; o navegador abre sozinho em http://127.0.0.1:5000.

## Deploy no Render (mais simples)
1. Crie um repositório **privado** no GitHub e envie estes arquivos.
2. No Render: **New → Blueprint** → escolha o repositório (ele lê o `render.yaml`).
3. Quando pedir `APP_PASSWORD`, digite a senha compartilhada do Núcleo.
4. Aguarde o build. O endereço `https://vale-presente-xxxx.onrender.com` já funciona (HTTPS).

## Observações
- **Memória:** o plano gratuito (512 MB) não processa apurações de ~400 MB (ex.: Cross Selling).
  O `render.yaml` usa o plano `starter`. Alternativa: salvar a apuração só com a aba de premiação antes de enviar.
- Os arquivos enviados são apagados após o processamento; os resultados ficam 2 h no servidor.
- Cada arquivo de saída é completo (BASE COM CADASTRO + COM CADASTRO + SEM CADASTRO), um por apuração, mesmo quando não há premiados.
- "Nome aproximado": quando o nome da apuração não bate exatamente com a base, o sistema usa o mais parecido
  e lista para conferência na tela.
