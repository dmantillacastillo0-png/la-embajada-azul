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


SENALES_PATRONES = {
    "Baja": (r"\bbaja", r"\blesion", r"\bsuspendid", r"\bsuspension\b",
             r"\bno juega\b", r"\bno jugara\b", r"\bse pierde\b",
             r"\bdescartad", r"\bfuera de\b"),
    "Duda": (r"\bduda", r"\bincierto\b", r"\ba ultima hora\b",
             r"\bpodria jugar\b", r"\ben duda\b", r"\brecupera",
             r"\breporte medico\b", r"\bactualidad medica\b",
             r"\bsobrecarga\b", r"\bmolestia"),
    "Alta": (r"\bvuelve\b", r"\bregresa\b", r"\balta\b",
             r"\bde vuelta\b", r"\breincorpora"),
}

TITULAR_PATRONES = (
    r"\bconvocad", r"\balineac", r"\bonce\b", r"\breporte medico\b",
    r"\bactualidad medica\b", r"\bbaja", r"\blesion", r"\bsuspendid",
    r"\bvuelve\b", r"\bduda",
)


def actualizar_senales_alineacion(noticias: list[dict]) -> dict:
    """Detecta señales de bajas/dudas/altas en titulares y resúmenes RSS.

    Es una ayuda, no una verdad: cada señal guarda el titular y el link
    original para que el lector pueda contrastarla.
    """
    destino = DATA / "alineacion_noticias.json"
    plantilla_path = DATA / "plantilla.json"
    try:
        jugadores = [j.get("nombre", "") for j in json.loads(
            plantilla_path.read_text(encoding="utf-8")).get("jugadores", [])]
    except Exception:
        jugadores = []

    senales: dict[tuple[str, str], dict] = {}
    titulares = []

    for noticia in noticias:
        titulo = noticia.get("titulo") or ""
        resumen = noticia.get("resumen") or ""
        slug = (noticia.get("url") or "").rsplit("/", 1)[-1].replace("-", " ")
        texto = normalizar(f"{titulo} {resumen} {slug}")
        if not texto:
            continue

        if any(re.search(p, texto) for p in TITULAR_PATRONES):
            titulares.append({
                "titulo": titulo,
                "url": noticia.get("url"),
                "fuente": noticia.get("fuente"),
                "fecha": noticia.get("fecha"),
            })

        for nombre in jugadores:
            nom_norm = normalizar(nombre)
            if not nom_norm:
                continue
            coincide = re.search(r"\b" + re.escape(nom_norm) + r"\b", texto)
            if not coincide:
                tokens = sorted((t for t in re.split(r"\W+", nom_norm) if len(t) >= 4),
                                key=len, reverse=True)
                for token in tokens:
                    coincide = re.search(r"\b" + re.escape(token) + r"\b", texto)
                    if coincide:
                        break
            if not coincide:
                continue

            ctx = texto[max(0, coincide.start() - 140):min(len(texto), coincide.end() + 180)]
            tipo = next((t for t, patrones in SENALES_PATRONES.items()
                         if any(re.search(p, ctx) for p in patrones)), None)
            if not tipo:
                continue

            clave = (nombre, tipo)
            anterior = senales.get(clave)
            if anterior and (anterior.get("fecha") or "") > (noticia.get("fecha") or ""):
                continue
            senales[clave] = {
                "nombre": nombre,
                "tipo": tipo,
                "detalle": titulo,
                "fuente": noticia.get("fuente"),
                "url": noticia.get("url"),
                "fecha": noticia.get("fecha"),
            }

    lista = []
    for tipo in ("Baja", "Duda", "Alta"):
        grupo = [s for s in senales.values() if s["tipo"] == tipo]
        grupo.sort(key=lambda s: s.get("fecha") or "", reverse=True)
        lista.extend(grupo)

    payload = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "revisadas": len(noticias),
        "senales": lista[:8],
        "titulares": titulares[:5],
    }
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


ESPN_EQUIPO_ID = "5484"
ESPN_SCHEDULE = (
    f"https://site.web.api.espn.com/apis/site/v2/sports/soccer/"
    f"{ESPN_LIGA}/teams/{ESPN_EQUIPO_ID}/schedule"
)
ESPN_SUMMARY = (
    "https://site.web.api.espn.com/apis/site/v2/sports/soccer/"
    f"{ESPN_LIGA}/summary?event={{}}"
)

ALIAS_JUGADORES = {
    "carlos d quintero": "Darwin Quintero",
    "leonai": "Leonai Souza",
    "jaine barreiro": "Stiven Barreiro",
    "leonardo castro": "Leonardo Castro",
}

SECCIONES_CONVOCATORIA = {
    "arqueros": "Arqueros",
    "defensas": "Defensores",
    "defensores": "Defensores",
    "volantes": "Mediocampistas",
    "mediocampistas": "Mediocampistas",
    "delanteros": "Delanteros",
}


def texto_nota(url: str) -> str:
    """Texto legible de un artículo, sin scripts ni etiquetas."""
    crudo = descargar(url).decode("utf-8", "ignore")
    crudo = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", crudo, flags=re.I | re.S)
    crudo = re.sub(r"</(p|div|h\d|li|br)\s*/?>", "\n", crudo, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", crudo))


def indice_plantilla() -> tuple[dict[str, str], dict[str, list[str]]]:
    try:
        jugadores = json.loads((DATA / "plantilla.json").read_text(encoding="utf-8")).get("jugadores", [])
    except Exception:
        jugadores = []
    nombres = [(j.get("nombre") or "").strip() for j in jugadores]
    # La plantilla puede ir detrás de la convocatoria; el JSON anterior también cuenta.
    try:
        anterior = json.loads((DATA / "alineacion.json").read_text(encoding="utf-8"))
        nombres += [j.get("nombre", "") for j in anterior.get("xi", [])]
        nombres += [j.get("nombre", "") for j in anterior.get("bajas", [])]
        for grupo in (anterior.get("convocados") or {}).values():
            nombres += list(grupo)
    except Exception:
        pass
    nombres += list(ALIAS_JUGADORES.values())

    por_norm, por_token = {}, {}
    for nombre in nombres:
        if not nombre:
            continue
        por_norm.setdefault(normalizar(nombre).replace(".", " ").replace("  ", " ").strip(), nombre)
        for token in re.split(r"\W+", normalizar(nombre)):
            if len(token) >= 4:
                lista = por_token.setdefault(token, [])
                if nombre not in lista:
                    lista.append(nombre)
    return por_norm, por_token


def canon_jugador(nombre: str, por_norm: dict, por_token: dict) -> str | None:
    n = normalizar(nombre).replace(".", " ").replace("  ", " ").strip()
    if n in ALIAS_JUGADORES:
        return ALIAS_JUGADORES[n]
    if n in por_norm:
        return por_norm[n]
    for token in sorted(n.split(), key=len, reverse=True):
        if len(token) >= 4 and len(por_token.get(token, [])) == 1:
            return por_token[token][0]
    return None


def nombres_en(fragmento: str, por_norm: dict, por_token: dict) -> list[str]:
    texto = normalizar(fragmento)
    encontrados = []
    for n, nombre in list(por_norm.items()) + list(ALIAS_JUGADORES.items()):
        if re.search(r"\b" + re.escape(n) + r"\b", texto):
            canon = canon_jugador(nombre, por_norm, por_token) or nombre
            if canon not in encontrados:
                encontrados.append(canon)
    return encontrados


def parsear_convocatoria(texto: str, por_norm: dict, por_token: dict) -> dict | None:
    inicio = texto.lower().find("los 20 convocados")
    if inicio < 0:
        return None
    bloque = texto[inicio:inicio + 6000]
    conv = {clave: [] for clave in ("Arqueros", "Defensores", "Mediocampistas", "Delanteros")}
    actual = None
    for linea in bloque.splitlines():
        lin = limpiar(linea)
        if not lin:
            continue
        cabecera = normalizar(lin).strip(" :")
        if cabecera in SECCIONES_CONVOCATORIA:
            actual = SECCIONES_CONVOCATORIA[cabecera]
            continue
        partido_num = re.match(r"^(\d{1,2})\.\s*(.+)$", lin)
        if not partido_num or not actual:
            continue
        nombre = canon_jugador(partido_num.group(2), por_norm, por_token)
        if nombre and nombre not in conv[actual]:
            conv[actual].append(nombre)
    if sum(len(v) for v in conv.values()) < 15:
        return None
    return conv


def parsear_bajas(texto: str, por_norm: dict, por_token: dict) -> list[dict]:
    inicio = texto.lower().find("por lesión")
    if inicio < 0:
        return []
    fin = texto.find(".", inicio)
    frase = texto[inicio:(fin + 1) if fin > 0 else inicio + 400]
    partes = re.split(r"además por decisión técnica tampoco está", frase, flags=re.I)
    bajas = []
    for i, parte in enumerate(partes[:2]):
        motivo = "Lesión" if i == 0 else "Decisión técnica"
        for nombre in nombres_en(parte, por_norm, por_token):
            bajas.append({"nombre": nombre, "motivo": motivo})
    return bajas


def posicion_es(pos: str) -> str:
    pos = pos or ""
    if pos.startswith("G"):
        return "POR"
    if pos.startswith("CD"):
        return "DFC"
    if pos == "LB":
        return "LI"
    if pos == "RB":
        return "LD"
    if pos.startswith("CM"):
        return "MC"
    if pos.startswith("LM"):
        return "MI"
    if pos.startswith("RM"):
        return "MD"
    if pos.startswith(("CF", "ST")):
        return "DC"
    return pos


def once_de_espn(event_id: str, por_norm: dict, por_token: dict) -> dict | None:
    try:
        data = descargar_json(ESPN_SUMMARY.format(event_id))
    except Exception as exc:
        print(f"[aviso] no se pudo leer once de ESPN {event_id}: {type(exc).__name__}", file=sys.stderr)
        return None
    for equipo in data.get("rosters") or []:
        if not nombres_equivalentes("millonarios", (equipo.get("team") or {}).get("displayName", "")):
            continue
        titulares = [p for p in (equipo.get("roster") or []) if p.get("starter")]
        if not titulares:
            return None
        filas = {0: [], 1: [], 2: [], 3: []}
        for p in titulares:
            nombre = canon_jugador((p.get("athlete") or {}).get("displayName", ""), por_norm, por_token)
            if not nombre:
                continue
            pos = (p.get("position") or {}).get("abbreviation", "")
            if pos.startswith("G"):
                fila = 0
            elif pos.startswith(("CD", "D")) or pos in ("LB", "RB"):
                fila = 1
            elif pos.startswith(("CM", "LM", "RM", "M")):
                fila = 2
            else:
                fila = 3
            filas[fila].append({
                "nombre": nombre,
                "num": p.get("jersey") or "—",
                "pos": posicion_es(pos),
                "_lugar": str(p.get("formationPlace") or ""),
            })
        orden = {"1": 0, "6": 1, "5": 2, "3": 3, "2": 4,
                 "8": 5, "4": 6, "11": 7, "7": 8, "9": 9, "10": 10}
        for fila in filas.values():
            fila.sort(key=lambda x: orden.get(x["_lugar"], 99))
        lineas = [[{k: v for k, v in p.items() if k != "_lugar"} for p in filas[i]] for i in range(4)]
        return {"formacion": equipo.get("formation") or "4-4-2", "lineas": lineas}
    return None


def ultimo_once_oficial(por_norm: dict, por_token: dict, excluir: str | None = None) -> dict | None:
    try:
        data = descargar_json(ESPN_SCHEDULE)
    except Exception as exc:
        print(f"[aviso] no se pudo leer calendario de ESPN: {type(exc).__name__}", file=sys.stderr)
        return None
    for ev in data.get("events") or []:
        eid = str(ev.get("id") or "")
        if excluir and eid == str(excluir):
            continue
        if ((ev.get("status") or {}).get("type") or {}).get("state") == "pre":
            continue
        once = once_de_espn(eid, por_norm, por_token)
        if once:
            return once
    return None


def completar_once(once: dict, conv: dict, bajas: list[dict], por_norm: dict, por_token: dict) -> dict:
    convocados = {n for grupo in conv.values() for n in grupo}
    fuera = {b["nombre"] for b in bajas}
    try:
        plantilla = {j["nombre"]: j for j in json.loads(
            (DATA / "plantilla.json").read_text(encoding="utf-8")).get("jugadores", [])}
    except Exception:
        plantilla = {}

    grupos = [conv["Arqueros"], conv["Defensores"], conv["Mediocampistas"], conv["Delanteros"]]
    lineas = [list(fila) for fila in once.get("lineas", [[] for _ in range(4)])]
    while len(lineas) < 4:
        lineas.append([])
    for i, grupo in enumerate(grupos):
        lineas[i] = [p for p in lineas[i] if p.get("nombre") in convocados and p.get("nombre") not in fuera]
        objetos = len(lineas[i])
        for nombre in grupo:
            if nombre in fuera or any(p["nombre"] == nombre for p in lineas[i]):
                continue
            if objetos >= (1 if i == 0 else 4 if i in (1, 2) else 2):
                break
            info = plantilla.get(nombre, {})
            lineas[i].append({
                "nombre": nombre,
                "num": info.get("num", "—"),
                "pos": info.get("pos", ""),
            })
            objetos += 1

    xi = []
    for fila in lineas:
        for p in fila:
            xi.append({"num": p.get("num", "—"), "nombre": p["nombre"], "pos": p.get("pos", "")})
    return {"formacion": once.get("formacion", "4-4-2"), "lineas": lineas, "xi": xi}


def actualizar_alineacion(noticias: list[dict], partido: dict | None) -> dict:
    """Reescribe alineación.json con convocatoria, bajas y once del rival actual."""
    destino = DATA / "alineacion.json"
    try:
        anterior = json.loads(destino.read_text(encoding="utf-8"))
    except Exception:
        anterior = {}

    por_norm, por_token = indice_plantilla()
    rival = (partido or {}).get("visitante") or ""
    nota = None
    for n in noticias:
        titulo = n.get("titulo") or ""
        if not re.search(r"\bconvocad", normalizar(titulo)):
            continue
        if rival and normalizar(rival) not in normalizar(titulo):
            continue
        nota = n
        break

    if not nota or not nota.get("url"):
        print("[aviso] sin convocatoria para el rival actual; se conserva la alineación anterior")
        return anterior

    try:
        texto = texto_nota(nota["url"])
    except Exception as exc:
        print(f"[aviso] no se pudo leer la convocatoria: {type(exc).__name__}: {exc}", file=sys.stderr)
        return anterior

    conv = parsear_convocatoria(texto, por_norm, por_token)
    if not conv:
        print("[aviso] no se pudo parsear la convocatoria; se conserva la alineación anterior")
        return anterior
    bajas = parsear_bajas(texto, por_norm, por_token)

    origen = "XI probable · continuidad del último once oficial"
    confirmada = False
    once = None
    espn_actual = (partido or {}).get("espn_id")
    if espn_actual:
        once = once_de_espn(str(espn_actual), por_norm, por_token)
        if once:
            origen = "XI oficial · ESPN"
            confirmada = True
    if not once:
        once = ultimo_once_oficial(por_norm, por_token, excluir=espn_actual)
    if not once:
        once = {"formacion": anterior.get("formacion", "4-4-2"),
                "lineas": anterior.get("lineas", []), "xi": anterior.get("xi", [])}
    once = completar_once(once, conv, bajas, por_norm, por_token)

    payload = {
        "formacion": once["formacion"],
        "xi": once["xi"],
        "lineas": once["lineas"],
        "convocados": conv,
        "bajas": bajas or anterior.get("bajas", []),
        "nota": (
            "Once actualizado desde la convocatoria oficial "
            + ("y la alineación confirmada por ESPN." if confirmada else "y el último once oficial del equipo.")
            + " La alineación puede cambiar hasta el pitazo inicial."
        ),
        "fuente": {
            "nombre": f"{nota.get('fuente') or 'ESPN Colombia'} · convocatoria oficial",
            "url": nota["url"],
        },
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "origen_xi": origen,
        "confirmada": confirmada,
        "rival": rival,
        "partido": (partido or {}).get("fecha", ""),
    }
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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

ALIAS_EQUIPOS = {
    "alianza de valledupar": {"alianza fc", "alianza valledupar", "alianza"},
    "millonarios": {"millonarios fc"},
}


def nombres_equivalentes(a: str, b: str) -> bool:
    """Compara nombres de equipos entre fuentes (ESPN vs TheSportsDB)."""
    a, b = normalizar(a), normalizar(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if b in ALIAS_EQUIPOS.get(a, set()) or a in ALIAS_EQUIPOS.get(b, set()):
        return True
    ignorar = {"de", "del", "la", "el", "fc", "club", "cd", "atletico", "deportivo", "independiente"}
    ta = {t for t in re.split(r"\W+", a) if t and t not in ignorar}
    tb = {t for t in re.split(r"\W+", b) if t and t not in ignorar}
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


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
            if not any(nombres_equivalentes("millonarios", n) for n in nombres):
                continue
            if any(nombres_equivalentes(home, n) for n in nombres) and any(nombres_equivalentes(away, n) for n in nombres):
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
    # ESPN a veces deja de devolver un partido recién terminado; conservamos
    # los resultados anteriores y evitamos duplicados por fecha y equipos.
    fusion = {}
    for item in resultados_recientes() + anterior.get("recientes", []):
        clave = (item.get("fecha"), item.get("local"), item.get("visitante"))
        fusion[clave] = item
    recientes = sorted(fusion.values(), key=lambda x: x.get("fecha") or "", reverse=True)[:5]

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
    senales = actualizar_senales_alineacion(noticias["noticias"])
    evento = proximo_evento()
    partido = actualizar_partido(evento)
    alineacion = actualizar_alineacion(noticias["noticias"], partido)
    calendario = actualizar_calendario(evento)
    print(f"Noticias: {noticias['total']} · fuentes con error: {len(noticias['errores'])}")
    print(f"Alineación · señales en noticias: {len(senales['senales'])}")
    print(
        f"Alineación · {alineacion.get('origen_xi', 'sin cambios')} · "
        f"{sum(len(v) for v in alineacion.get('convocados', {}).values())} convocados · "
        f"{len(alineacion.get('bajas', []))} bajas"
    )
    if partido:
        print(f"Próximo partido: {partido['local']} vs {partido['visitante']} ({partido['fecha']} {partido['hora_local']})")
    else:
        print("Próximo partido: sin cambios (TheSportsDB no devolvió eventos)")
    print(f"Calendario: {len(calendario['proximos'])} próximos · {len(calendario['recientes'])} recientes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
