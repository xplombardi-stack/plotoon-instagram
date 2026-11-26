# Instagram do Plotoon

Fila de posts do @plotoon.app. Uma automação do GitHub publica sozinha, a cada 15 minutos, os posts aprovados que já chegaram no horário.

## Como funciona

- Cada post é uma pasta em `posts/` com a imagem (`1.jpg`; com `2.jpg`, `3.jpg`… vira carrossel) e o `post.json`.
- No `post.json`, `"aprovado": true` libera o post e `"quando"` marca o horário (ex.: `"2026-11-27T12:00:00-03:00"`). Sem horário, sai na próxima rodada.
- Depois de publicado, aparece um `publicado.json` na pasta com o link do post. Se der erro, aparece um `erro.json` com o motivo.

## Configuração

- A chave da Meta fica no segredo `IG_TOKEN` (Settings → Secrets and variables → Actions). Ela nunca vai no código.
- Pra testar se a chave funciona sem publicar nada: Actions → Publicar no Instagram → Run workflow → ação `verificar`.

Este repositório não tem nada a ver com o site nem com o banco do Plotoon.
