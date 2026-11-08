#!/usr/bin/env python3
"""
Actualizador de datos de La Embajada Azul.

- Noticias: lee feeds RSS de medios (con enlace al original, sin copiar el artículo).
- Próximo partido: TheSportsDB (opcional, si hay THE_SPORTSDB_KEY).
- Estado: deja registro de qué fuente falló y cuándo se actualizó.

Uso:
    python3 scripts/update.py
    THE_SPORTSDB_KEY=tu_clave python3 scripts/update.py
"""

from __future__ import annotations

import email.utils
import html
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "LaEmbajadaAzul/1.0 (+sitio de hinchas; contacto: configurar)"

# Feeds de medios. El feed del club se toma completo; el resto se filtra
# por palabras clave para no publicar noticias que no tengan que ver.
FEEDS = [
    {"nombre": "Millonarios FC", "url": "https://millonarios.com.co/feed/", "club": True},
    {"nombre": "Marca Colombia", "url": "https://www.marca.com/rss/futbol/colombia.xml", "club": False},
    {"nombre": "El Tiempo · Deportes", "url": "https://www.eltiempo.com/rss/deportes.xml", "club": False},
    {"nombre": "ESPN Colombia", "url": "https://www.espn.com.co/espn/rss/news", "club": False},
]

KEYWORDS = [
    "millonarios", "embajador", "ballet azul", "el campin", "campin",
    "azul y blanco", "millos",
]

MAX_NOTICIAS = 60
TIMEOUT = 20


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def limpiar(texto: str) -> str:
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = html.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def fecha_iso(valor: str) -> str | None:
    if not valor:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(valor)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def descargar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read(2_000_000)


def texto_hijo(item: ET.Element, etiquetas: tuple[str, ...]) -> str:
    for etiqueta in etiquetas:
        for hijo in item.iter():
            if hijo.tag.split("}")[-1].lower() == etiqueta and (hijo.text or "").strip():
                return hijo.text.strip()
    return ""


def enlace_item(item: ET.Element) -> str:
    enlace = texto_hijo(item, ("link",))
    if enlace:
        return enlace
    for hijo in item.iter():
        if hijo.tag.split("}")[-1].lower() == "link":
            href = hijo.attrib.get("href")
            if href:
                return href
    return ""


def leer_feed(fuente: dict) -> list[dict]:
    cuerpo = descargar(fuente["url"])
    raiz = ET.fromstring(cuerpo)
    noticias = []
    for item in raiz.iter():
        if item.tag.split("}")[-1].lower() not in ("item", "entry"):
            continue
        titulo = limpiar(texto_hijo(item, ("title",)))
        enlace = enlace_item(item)
        if not titulo or not enlace:
            continue
        resumen = limpiar(texto_hijo(item, ("description", "summary", "content")))
        resumen = resumen[:220].rsplit(" ", 1)[0] + "…" if len(resumen) > 220 else resumen
        fecha = fecha_iso(texto_hijo(item, ("pubdate", "published", "updated", "date")))
        noticias.append({
            "titulo": titulo,
            "url": enlace,
            "resumen": resumen,
            "fecha": fecha,
            "fuente": fuente["nombre"],
            "club": fuente["club"],
        })
    return noticias


def relevante(noticia: dict) -> bool:
    if noticia["club"]:
        return True
    texto = normalizar(noticia["titulo"] + " " + noticia["resumen"])
    return any(k in texto for k in KEYWORDS)


def clave(noticia: dict) -> str:
    titulo = re.sub(r"[^a-z0-9 ]", "", normalizar(noticia["titulo"]))
    return re.sub(r"\s+", " ", titulo).strip()[:90]


def actualizar_noticias() -> dict:
    todas, errores = [], []
    for fuente in FEEDS:
        try:
            leidas = leer_feed(fuente)
            todas.extend(n for n in leidas if relevante(n))
        except Exception as exc:  # una fuente caída no rompe el resto
            errores.append({"fuente": fuente["nombre"], "error": f"{type(exc).__name__}: {exc}"})

    vistas, unicas = set(), []
    for n in sorted(todas, key=lambda x: x["fecha"] or "", reverse=True):
        k = clave(n)
        if k and k not in vistas:
            vistas.add(k)
            unicas.append(n)

    payload = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "total": len(unicas[:MAX_NOTICIAS]),
        "errores": errores,
        "noticias": unicas[:MAX_NOTICIAS],
    }
    (DATA / "noticias.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def actualizar_partido() -> dict | None:
    """Próximo partido vía TheSportsDB. Sin clave, conserva el JSON existente."""
    key = os.environ.get("THE_SPORTSDB_KEY", "").strip()
    destino = DATA / "partido.json"
    if not key:
        return None
    url = f"https://www.thesportsdb.com/api/v1/json/{key}/eventsnext.php?id=137617"
    try:
        data = json.loads(descargar(url).decode("utf-8"))
        evento = (data.get("events") or [None])[0]
        if not evento:
            return None
        partido = {
            "id": evento.get("idEvent"),
            "local": evento.get("strHomeTeam"),
            "visitante": evento.get("strAwayTeam"),
            "fecha": evento.get("dateEvent"),
            "hora_utc": evento.get("strTime"),
            "estadio": evento.get("strVenue"),
            "liga": evento.get("strLeague"),
            "temporada": evento.get("strSeason"),
            "fuente": {"nombre": "TheSportsDB", "url": f"https://www.thesportsdb.com/event/{evento.get('idEvent')}"},
            "actualizado": datetime.now(timezone.utc).isoformat(),
        }
        destino.write_text(json.dumps(partido, ensure_ascii=False, indent=2), encoding="utf-8")
        return partido
    except Exception as exc:
        print(f"[aviso] no se pudo actualizar el partido: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    noticias = actualizar_noticias()
    partido = actualizar_partido()
    print(f"Noticias: {noticias['total']} · fuentes con error: {len(noticias['errores'])}")
    if partido:
        print(f"Próximo partido: {partido['local']} vs {partido['visitante']} ({partido['fecha']})")
    else:
        print("Próximo partido: sin cambios (falta THE_SPORTSDB_KEY)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
