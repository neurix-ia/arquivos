#!/usr/bin/env python3
"""Grava ofertas do catálogo Zuni a partir dos anúncios ML e da equivalência de cores.

Não reescreve MLB dentro de URL. Copia a URL da variação cujo nome de cor
está na lista explícita de equivalencia_cores.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANUNCIOS = ROOT / "catalogo-zuni" / "data" / "ml_anuncios.json"
EQUIV = ROOT / "catalogo-zuni" / "data" / "equivalencia_cores.json"
CATALOGO = ROOT / "catalogo-zuni" / "catalogo_data.json"
INDEX = ROOT / "catalogo-zuni" / "index.html"
DROP = ("qtds", "mlbs", "link")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def extract_array(text: str, marker: str) -> tuple[int, int]:
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"marcador ausente: {marker}")
    i = start + len(marker)
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] != "[":
        raise SystemExit("CATALOGO não começa com array")
    depth = 0
    in_str = False
    esc = False
    for j in range(i, len(text)):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = j + 1
                k = end
                while k < len(text) and text[k] in " \t":
                    k += 1
                if k >= len(text) or text[k] != ";":
                    raise SystemExit("CATALOGO sem ponto e vírgula")
                return i, k
    raise SystemExit("array CATALOGO não fecha")


def ofertas_do_item(item_slug: str, par: dict, anuncios: list) -> list:
    nomes = par["cores_ml"]
    if len(nomes) != len(set(nomes)):
        raise SystemExit(f"cores_ml duplicadas em {item_slug}")
    ofertas = []
    for ad in anuncios:
        if ad["formato"] != par["formato"]:
            continue
        hits = [v for v in ad["variations"] if v["cor"] in nomes]
        if not hits:
            continue
        if len(hits) > 1:
            raise SystemExit(
                f"{item_slug} mlb {ad['mlb']} casa mais de uma cor: {[h['cor'] for h in hits]}"
            )
        ofertas.append(
            {
                "qtd": ad["quantidade"],
                "mlb": ad["mlb"],
                "url": hits[0]["url"],
            }
        )
    if not ofertas:
        raise SystemExit(f"nenhuma oferta para {item_slug}")
    qtds = [o["qtd"] for o in ofertas]
    if len(qtds) != len(set(qtds)):
        raise SystemExit(f"quantidade duplicada em {item_slug}")
    ofertas.sort(key=lambda o: (o["qtd"], o["mlb"]))
    return ofertas


def aplicar(catalogo: list, pares: list, anuncios: list) -> list:
    por_slug = {}
    for par in pares:
        key = (par["formato"], par["slug"])
        if key in por_slug:
            raise SystemExit(f"equivalência duplicada: {key}")
        por_slug[key] = par
    saida = []
    for grupo in catalogo:
        novo = {k: v for k, v in grupo.items() if k != "itens"}
        itens = []
        for item in grupo["itens"]:
            key = (grupo["formato"], item["slug"])
            par = por_slug.get(key)
            if par is None:
                raise SystemExit(f"sem equivalência: {key[0]} {key[1]}")
            if par["cor_catalogo"] != item["cor_display"]:
                raise SystemExit(
                    f"cor_catalogo divergente em {item['slug']}: {par['cor_catalogo']!r} != {item['cor_display']!r}"
                )
            limpo = {k: v for k, v in item.items() if k not in DROP and k != "ofertas"}
            limpo["ofertas"] = ofertas_do_item(item["slug"], par, anuncios)
            itens.append(limpo)
        novo["itens"] = itens
        saida.append(novo)
    return saida


def main() -> int:
    anuncios = load(ANUNCIOS)["anuncios"]
    pares = load(EQUIV)["pares"]
    catalogo = aplicar(load(CATALOGO), pares, anuncios)
    texto = dump(catalogo)
    CATALOGO.write_text(texto, encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")
    ini, fim = extract_array(html, "const CATALOGO =")
    html = html[:ini] + texto.rstrip("\n") + html[fim:]
    INDEX.write_text(html, encoding="utf-8")
    n = sum(len(item["ofertas"]) for g in catalogo for item in g["itens"])
    print(f"ofertas gravadas: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
