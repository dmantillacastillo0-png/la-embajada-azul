#!/usr/bin/env python3
"""
Actualizador de datos de La Embajada Azul.

- Noticias: lee feeds RSS de medios (con enlace al original, sin copiar el artículo).
- Próximo partido: TheSportsDB. Usa THE_SPORTSDB_KEY si existe; si no, la
  clave pública de prueba "123" (puede tener límite de peticiones).
- Calendario: próximos partidos y últimos resultados (TheSportsDB + ESPN).
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
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "LaEmbajadaAzul/1.0 (+sitio de hinchas; contacto: configurar)"
COLOMBIA = timezone(timedelta(hours=-5))
TSDB_KEY = os.environ.get("THE_SPORTSDB_KEY", "").strip() or "123"
TSDB_TEAM = "137617"
TSDB_LEAGUE = "4497"
ESPN_LIGA = "col.1"

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
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read(3_000_000)


def descargar_json(url: str):
    return json.loads(descargar(url).decode("utf-8"))


def fecha_utc(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def proximo_evento() -> dict | None:
    """Último/ próximo evento de Millonarios según TheSportsDB."""
    url = f"https://www.thesportsdb.com/api/v1/json/{TSDB_KEY}/eventsnext.php?id={TSDB_TEAM}"
    try:
        data = descargar_json(url)
        return (data.get("events") or [None])[0]
    except Exception as exc:
        print(f"[aviso] no se pudo leer el próximo partido: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None


_CACHE_ESPN: dict[str, str | None] = {}


def buscar_espn_id(evento: dict) -> str | None:
    """Busca el id de ESPN del mismo partido para el marcador en vivo."""
    clave_cache = "|".join(str(evento.get(k, "")) for k in ("dateEvent", "strHomeTeam", "strAwayTeam"))
    if clave_cache in _CACHE_ESPN:
        return _CACHE_ESPN[clave_cache]

    fecha = evento.get("dateEvent")
    if not fecha:
        _CACHE_ESPN[clave_cache] = None
        return None
    try:
        dia = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        _CACHE_ESPN[clave_cache] = None
        return None

    home = normalizar(evento.get("strHomeTeam") or "")
    away = normalizar(evento.get("strAwayTeam") or "")
    for delta in (0, 1, -1):
        fecha_busqueda = (dia + timedelta(days=delta)).strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{ESPN_LIGA}/scoreboard?dates={fecha_busqueda}"
        try:
            data = descargar_json(url)
        except Exception:
            continue
        for ev in data.get("events") or []:
            comp = (ev.get("competitions") or [{}])[0]
            nombres = [normalizar(c.get("team", {}).get("displayName") or "") for c in comp.get("competitors", [])]
            if "millonarios" not in nombres:
                continue
            if home in nombres and away in nombres:
                _CACHE_ESPN[clave_cache] = str(ev.get("id"))
                return _CACHE_ESPN[clave_cache]
    _CACHE_ESPN[clave_cache] = None
    return None


def evento_partido(evento: dict, anterior: dict | None, espn_id: str | None) -> dict:
    inicio = fecha_utc(evento.get("strTimestamp"))
    if inicio is None and evento.get("dateEvent"):
        inicio = fecha_utc(f"{evento['dateEvent']}T{evento.get('strTime') or '00:00:00'}")
    local_dt = inicio.astimezone(COLOMBIA) if inicio else None
    mismo = bool(anterior and str(anterior.get("id")) == str(evento.get("idEvent")))

    fuentes = []
    if mismo and anterior.get("fuentes"):
        fuentes = [f for f in anterior["fuentes"] if f.get("nombre") != "TheSportsDB"]
    fuentes.insert(0, {
        "nombre": "TheSportsDB",
        "url": f"https://www.thesportsdb.com/event/{evento.get('idEvent')}",
    })

    contexto = (
        anterior.get("contexto")
        if mismo and anterior.get("contexto")
        else "Próximo partido de Millonarios en la Liga BetPlay. Horario y sede según TheSportsDB; pueden cambiar."
    )
    return {
        "id": str(evento.get("idEvent") or ""),
        "local": evento.get("strHomeTeam") or "",
        "visitante": evento.get("strAwayTeam") or "",
        "fecha": local_dt.strftime("%Y-%m-%d") if local_dt else (evento.get("dateEvent") or ""),
        "hora_local": local_dt.strftime("%H:%M") if local_dt else "",
        "zona": "America/Bogota",
        "hora_utc": inicio.strftime("%H:%M") if inicio else (evento.get("strTime") or "")[:5],
        "estadio": evento.get("strVenue") or "",
        "liga": "Liga BetPlay",
        "jornada": f"Fecha {evento.get('intRound')}" if evento.get("intRound") else "",
        "temporada": evento.get("strSeason") or "2026",
        "estado": "programado",
        "contexto": contexto,
        "fuentes": fuentes,
        "espn_id": espn_id,
        "hora_confirmada": bool(espn_id),
        "actualizado": datetime.now(timezone.utc).isoformat(),
    }


def actualizar_partido(evento: dict | None = None) -> dict | None:
    """Próximo partido vía TheSportsDB. Conserva el JSON si la fuente falla."""
    if evento is None:
        return None
    destino = DATA / "partido.json"
    anterior = None
    if destino.exists():
        try:
            anterior = json.loads(destino.read_text(encoding="utf-8"))
        except Exception:
            anterior = None

    espn_id = buscar_espn_id(evento)
    if not espn_id and anterior and str(anterior.get("id")) == str(evento.get("idEvent")):
        espn_id = anterior.get("espn_id")

    partido = evento_partido(evento, anterior, espn_id)
    destino.write_text(json.dumps(partido, ensure_ascii=False, indent=2), encoding="utf-8")
    return partido


def valor_marcador(competidor: dict | None):
    score = (competidor or {}).get("score")
    if isinstance(score, dict):
        return score.get("displayValue")
    return score


def numero(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return valor


def resultados_recientes() -> list[dict]:
    """Últimos 5 partidos cerrados según el calendario público de ESPN."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{ESPN_LIGA}/teams/5484/schedule"
    try:
        data = descargar_json(url)
    except Exception as exc:
        print(f"[aviso] no se pudieron leer los resultados recientes: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    recientes = []
    for ev in data.get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        estado = (comp.get("status") or {}).get("type") or {}
        if not estado.get("completed"):
            continue
        equipos = {c.get("homeAway"): c for c in comp.get("competitors", [])}
        home, away = equipos.get("home"), equipos.get("away")
        if not home or not away:
            continue
        gl, gv = valor_marcador(home), valor_marcador(away)
        if gl is None or gv is None:
            continue
        recientes.append({
            "fecha": ev.get("date"),
            "local": (home.get("team") or {}).get("displayName") or "",
            "visitante": (away.get("team") or {}).get("displayName") or "",
            "goles_local": numero(gl),
            "goles_visitante": numero(gv),
            "estado": "Final",
            "fuente": {"nombre": "ESPN", "url": "https://www.espn.com.co/futbol/colombia/"},
        })
    recientes.sort(key=lambda x: x.get("fecha") or "", reverse=True)
    return recientes[:5]


def actualizar_calendario(evento: dict | None = None) -> dict:
    """Próximos partidos (rondas de TheSportsDB) y últimos resultados (ESPN)."""
    destino = DATA / "calendario.json"
    anterior = {}
    if destino.exists():
        try:
            anterior = json.loads(destino.read_text(encoding="utf-8"))
        except Exception:
            anterior = {}

    ahora = datetime.now(timezone.utc)
    eventos: list[dict] = []
    vistos: set[str] = set()

    if evento:
        eventos.append(evento)
        vistos.add(str(evento.get("idEvent")))

    if evento and evento.get("intRound"):
        try:
            ronda = int(evento["intRound"])
        except (TypeError, ValueError):
            ronda = 0
        for r in range(ronda, ronda + 3):
            url = (
                f"https://www.thesportsdb.com/api/v1/json/{TSDB_KEY}/eventsround.php"
                f"?id={TSDB_LEAGUE}&r={r}&s={evento.get('strSeason') or '2026'}"
            )
            try:
                data = descargar_json(url)
            except Exception as exc:
                print(f"[aviso] no se pudo leer la fecha {r}: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            for ev in data.get("events") or []:
                if "Millonarios" not in (ev.get("strEvent") or ""):
                    continue
                inicio = fecha_utc(ev.get("strTimestamp"))
                if not inicio or inicio < ahora - timedelta(hours=6):
                    continue
                eid = str(ev.get("idEvent"))
                if eid in vistos:
                    continue
                vistos.add(eid)
                eventos.append(ev)

    proximos = []
    for ev in sorted(eventos, key=lambda x: x.get("strTimestamp") or ""):
        inicio = fecha_utc(ev.get("strTimestamp"))
        if not inicio:
            continue
        local_dt = inicio.astimezone(COLOMBIA)
        espn_id = None
        if inicio <= ahora + timedelta(days=3):
            espn_id = buscar_espn_id(ev)
        proximos.append({
            "id": str(ev.get("idEvent") or ""),
            "fecha": inicio.isoformat().replace("+00:00", "Z"),
            "fecha_local": local_dt.strftime("%Y-%m-%d"),
            "hora_local": local_dt.strftime("%H:%M"),
            "local": ev.get("strHomeTeam") or "",
            "visitante": ev.get("strAwayTeam") or "",
            "estadio": ev.get("strVenue") or "",
            "liga": "Liga BetPlay",
            "jornada": f"Fecha {ev.get('intRound')}" if ev.get("intRound") else "",
            "estado": "programado",
            "espn_id": espn_id,
            "hora_confirmada": bool(espn_id),
            "fuente": {
                "nombre": "TheSportsDB",
                "url": f"https://www.thesportsdb.com/event/{ev.get('idEvent')}",
            },
        })

    if not proximos:
        proximos = anterior.get("proximos", [])
    recientes = resultados_recientes() or anterior.get("recientes", [])

    payload = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "proximos": proximos,
        "recientes": recientes,
    }
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    noticias = actualizar_noticias()
    evento = proximo_evento()
    partido = actualizar_partido(evento)
    calendario = actualizar_calendario(evento)
    print(f"Noticias: {noticias['total']} · fuentes con error: {len(noticias['errores'])}")
    if partido:
        print(f"Próximo partido: {partido['local']} vs {partido['visitante']} ({partido['fecha']} {partido['hora_local']})")
    else:
        print("Próximo partido: sin cambios (TheSportsDB no devolvió eventos)")
    print(f"Calendario: {len(calendario['proximos'])} próximos · {len(calendario['recientes'])} recientes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
