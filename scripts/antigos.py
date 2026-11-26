"""Posts antigos do @plotoon.app (de antes do Plotoon).

  python scripts/antigos.py listar  -> grava antigos/lista.json com todos os posts antigos (não apaga nada)
  python scripts/antigos.py apagar  -> apaga até N posts por rodada, SÓ se antigos/autorizacao.json disser "autorizado": true

Nunca apaga posts publicados por esta fila (posts/*/publicado.json) nem nada publicado depois da data de corte.
"""
import json
import random
import sys
import time
from datetime import timedelta
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publicar import RAIZ, conta_instagram, graph  # noqa: E402

PASTA = RAIZ / "antigos"
LISTA = PASTA / "lista.json"
AUTORIZACAO = PASTA / "autorizacao.json"
APAGADOS = PASTA / "apagados.json"


def ids_da_fila():
    ids = set()
    for f in (RAIZ / "posts").glob("*/publicado.json"):
        ids.add(json.loads(f.read_text(encoding="utf-8")).get("media_id"))
    return ids


def listar(ig):
    itens, depois = [], None
    while True:
        params = {"fields": "id,timestamp,media_type,caption,permalink", "limit": "100"}
        if depois:
            params["after"] = depois
        r = graph(f"/{ig}/media", params)
        for m in r.get("data", []):
            itens.append({
                "id": m["id"],
                "data": m.get("timestamp"),
                "tipo": m.get("media_type"),
                "legenda": (m.get("caption") or "")[:140],
                "link": m.get("permalink"),
            })
        depois = (r.get("paging") or {}).get("cursors", {}).get("after")
        if not (r.get("paging") or {}).get("next"):
            break
    fila = ids_da_fila()
    itens = [i for i in itens if i["id"] not in fila]
    PASTA.mkdir(exist_ok=True)
    LISTA.write_text(json.dumps({"atualizado": datetime.now(timezone.utc).isoformat(), "total": len(itens), "posts": itens}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(itens)} posts antigos listados em antigos/lista.json")


def apagar(ig):
    if not AUTORIZACAO.exists():
        print("Sem autorizacao.json: nada apagado.")
        return
    aut = json.loads(AUTORIZACAO.read_text(encoding="utf-8"))
    if not aut.get("autorizado"):
        print("Apagar não autorizado: nada apagado.")
        return
    corte = datetime.fromisoformat(aut["antes_de"])
    por_dia = int(aut.get("por_dia", 20))
    feitos = json.loads(APAGADOS.read_text(encoding="utf-8")) if APAGADOS.exists() else []
    agora = datetime.now(timezone.utc)
    nas_24h = sum(1 for f in feitos if datetime.fromisoformat(f["apagado_em"]) > agora - timedelta(hours=24))
    por_rodada = min(int(aut.get("por_rodada", 5)), max(0, por_dia - nas_24h))
    if not por_rodada:
        print(f"Limite do dia atingido ({nas_24h} apagados nas últimas 24h).")
        return
    ja = {f["id"] for f in feitos}
    fila = ids_da_fila()
    lista = json.loads(LISTA.read_text(encoding="utf-8"))["posts"]
    # do mais recente pro mais antigo: limpa primeiro o que aparece logo abaixo dos posts novos
    candidatos = sorted(
        (p for p in lista if p["id"] not in ja and p["id"] not in fila and p["data"] and datetime.fromisoformat(p["data"].replace("+0000", "+00:00")) < corte),
        key=lambda p: p["data"], reverse=True,
    )
    n = 0
    for p in candidatos[:por_rodada]:
        if n:
            time.sleep(random.randint(60, 120))  # ritmo de gente, pra não parecer robô
        try:
            graph(f"/{p['id']}", {}, "DELETE")
        except RuntimeError as e:
            print(f"  erro ao apagar {p['id']}: {e}")
            break
        feitos.append({**p, "apagado_em": datetime.now(timezone.utc).isoformat()})
        n += 1
    APAGADOS.write_text(json.dumps(feitos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{n} post(s) antigo(s) apagado(s). Faltam {len(candidatos) - n}.")


if __name__ == "__main__":
    ig = conta_instagram()
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo == "listar":
        listar(ig)
    elif modo == "apagar":
        apagar(ig)
    else:
        sys.exit("use: listar | apagar")
