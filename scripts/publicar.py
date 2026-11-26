"""Publica no Instagram do Plotoon (@plotoon.app) os posts aprovados da pasta posts/.

Cada post é uma pasta em posts/ com:
  - 1.jpg (e 2.jpg, 3.jpg... vira carrossel)
  - post.json: {"titulo", "legenda", "aprovado": true/false, "quando": "2026-11-27T12:00:00-03:00" ou null}
Quando publica, grava publicado.json na pasta e não mexe mais nela.

Modos:
  python scripts/publicar.py            -> publica o que estiver aprovado e no horário
  python scripts/publicar.py verificar  -> só confere se a chave funciona (não publica nada)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GRAPH = "https://graph.facebook.com/v25.0"
PAGINA = os.environ.get("IG_PAGE_ID", "1507688999086201")  # Página do Facebook "Plotoon"
RAIZ = Path(__file__).resolve().parent.parent
POSTS = RAIZ / "posts"
LIMITE_POR_RODADA = 3


def token():
    t = os.environ.get("IG_TOKEN", "").strip()
    if not t:
        sys.exit("Falta o segredo IG_TOKEN no repositório (Settings > Secrets and variables > Actions).")
    return t


def graph(caminho, params=None, metodo="GET"):
    params = dict(params or {})
    params["access_token"] = token()
    dados = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        req = urllib.request.Request(f"{GRAPH}{caminho}?{dados.decode()}")
    else:
        req = urllib.request.Request(f"{GRAPH}{caminho}", data=dados, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors="replace")
        try:
            msg = json.loads(corpo)["error"]["message"]
        except Exception:
            msg = corpo[:300]
        raise RuntimeError(f"Meta respondeu {e.code}: {msg}") from None


def conta_instagram():
    p = graph(f"/{PAGINA}", {"fields": "instagram_business_account"})
    ig = (p.get("instagram_business_account") or {}).get("id")
    if not ig:
        raise RuntimeError("A Página Plotoon não tem conta do Instagram ligada.")
    return ig


def esperar_pronto(container):
    for _ in range(30):
        s = graph(f"/{container}", {"fields": "status_code"}).get("status_code")
        if s == "FINISHED":
            return
        if s in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"A Meta recusou a mídia ({s}).")
        time.sleep(3)
    raise RuntimeError("A Meta demorou demais pra processar a imagem.")


def url_publica(arquivo):
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ.get("GITHUB_SHA", "main")
    rel = arquivo.relative_to(RAIZ).as_posix()
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{urllib.parse.quote(rel)}"


def publicar_post(ig, pasta, info):
    imagens = sorted(pasta.glob("*.jpg"), key=lambda p: int(p.stem) if p.stem.isdigit() else 999)
    if not imagens:
        raise RuntimeError("Pasta sem imagem .jpg")
    legenda = info.get("legenda", "")
    if len(imagens) == 1:
        criacao = graph(f"/{ig}/media", {"image_url": url_publica(imagens[0]), "caption": legenda}, "POST")["id"]
    else:
        filhos = []
        for img in imagens[:10]:
            filho = graph(f"/{ig}/media", {"image_url": url_publica(img), "is_carousel_item": "true"}, "POST")["id"]
            esperar_pronto(filho)
            filhos.append(filho)
        criacao = graph(f"/{ig}/media", {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda}, "POST")["id"]
    esperar_pronto(criacao)
    media = graph(f"/{ig}/media_publish", {"creation_id": criacao}, "POST")["id"]
    try:
        link = graph(f"/{media}", {"fields": "permalink"}).get("permalink")
    except RuntimeError:
        link = None
    return media, link


def na_hora(info, agora):
    if not info.get("aprovado"):
        return False
    quando = info.get("quando")
    if not quando:
        return True
    return datetime.fromisoformat(quando) <= agora


def main():
    ig = conta_instagram()
    if len(sys.argv) > 1 and sys.argv[1] == "verificar":
        c = graph(f"/{ig}", {"fields": "username,followers_count,media_count"})
        print(f"Chave OK: @{c.get('username')} · {c.get('media_count')} posts · {c.get('followers_count')} seguidores")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "testar":
        # prepara cada imagem na Meta sem publicar (o rascunho some sozinho em 24h)
        for pasta in sorted(p for p in POSTS.iterdir() if p.is_dir()):
            img = sorted(pasta.glob("*.jpg"))[0]
            c = graph(f"/{ig}/media", {"image_url": url_publica(img), "caption": "teste"}, "POST")["id"]
            esperar_pronto(c)
            print(f"  {pasta.name}: imagem aceita pela Meta (nada publicado)")
        return
    agora = datetime.now(timezone.utc)
    feitos = 0
    for pasta in sorted(p for p in POSTS.iterdir() if p.is_dir()):
        if (pasta / "publicado.json").exists():
            continue
        info = json.loads((pasta / "post.json").read_text(encoding="utf-8"))
        if not na_hora(info, agora):
            continue
        if feitos >= LIMITE_POR_RODADA:
            break
        print(f"Publicando {pasta.name}…")
        try:
            media, link = publicar_post(ig, pasta, info)
        except RuntimeError as e:
            print(f"  erro: {e}")
            (pasta / "erro.json").write_text(json.dumps({"erro": str(e), "em": agora.isoformat()}, ensure_ascii=False, indent=2), encoding="utf-8")
            break
        (pasta / "erro.json").unlink(missing_ok=True)
        (pasta / "publicado.json").write_text(json.dumps({"media_id": media, "permalink": link, "em": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  publicado: {link or media}")
        feitos += 1
        time.sleep(20)
    print(f"{feitos} post(s) publicado(s) nesta rodada.")


if __name__ == "__main__":
    main()
