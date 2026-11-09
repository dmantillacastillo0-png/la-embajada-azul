#!/usr/bin/env python3
"""Genera el sitio estático de La Embajada Azul en dist/."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATIC = ROOT / "static"
DIST = ROOT / "dist"

SITIO = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
PARTIDO = json.loads((DATA / "partido.json").read_text(encoding="utf-8"))
CALENDARIO = json.loads((DATA / "calendario.json").read_text(encoding="utf-8"))
ALINEACION = json.loads((DATA / "alineacion.json").read_text(encoding="utf-8"))
HISTORIA = json.loads((DATA / "historia.json").read_text(encoding="utf-8"))
TRIVIA = json.loads((DATA / "trivia.json").read_text(encoding="utf-8"))
RESULTADOS = json.loads((DATA / "resultados.json").read_text(encoding="utf-8"))
PLANTILLA = json.loads((DATA / "plantilla.json").read_text(encoding="utf-8"))
NOTICIAS = json.loads((DATA / "noticias.json").read_text(encoding="utf-8"))

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
COLOMBIA = timezone(timedelta(hours=-5))


def version_asset(nombre: str) -> str:
    """Hash corto para romper la caché cuando cambia un asset estático."""
    return hashlib.sha1((STATIC / nombre).read_bytes()).hexdigest()[:8]

NAV = [
    ("index.html", "Inicio", "inicio"),
    ("noticias.html", "Noticias", "noticias"),
    ("partidos.html", "Partidos", "partidos"),
    ("alineacion.html", "Alineación", "alineacion"),
    ("pronostico.html", "Pronóstico", "pronostico"),
    ("historia.html", "Historia", "historia"),
    ("juegos.html", "Juegos", "juegos"),
]

ESCUDOS = [
    {
        "archivo": "1946.svg",
        "era": "1946",
        "nombre": "El nacimiento",
        "texto": "Homenaje a la fundación: monograma MFC, el año y el azul de la primera identidad.",
    },
    {
        "archivo": "ballet.svg",
        "era": "1950s",
        "nombre": "Ballet Azul",
        "texto": "Versión libre de la época de El Dorado, cuando el equipo bailaba en El Campín.",
    },
    {
        "archivo": "embajador.svg",
        "era": "1970s–2000s",
        "nombre": "El Embajador",
        "texto": "La banda azul y la estrella: un guiño al apodo que acompañó al club por décadas.",
    },
    {
        "archivo": "actual.svg",
        "era": "Hoy",
        "nombre": "La identidad azul",
        "texto": "Relectura moderna: monograma, estrella y el azul que no se negocia.",
    },
]

MAPA_ESCUDO = {
    "inicio": "ballet.svg",
    "noticias": "actual.svg",
    "partidos": "actual.svg",
    "alineacion": "1946.svg",
    "pronostico": "embajador.svg",
    "historia": "1946.svg",
    "juegos": "ballet.svg",
}

FUENTES = {f["url"] for f in SITIO["fuentes_generales"]}


def nombre_escudo(archivo: str) -> str:
    for escudo in ESCUDOS:
        if escudo["archivo"] == archivo:
            return escudo["nombre"]
    return "Escudo homenaje"


def e(valor) -> str:
    return escape(str(valor), quote=True)


def fecha_larga(iso: str) -> str:
    d = datetime.strptime(iso, "%Y-%m-%d").date()
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def fecha_corta(iso: str | None) -> str:
    if not iso:
        return "sin fecha"
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{d.day} {MESES[d.month - 1][:3]} · {d:%H:%M} UTC"
    except ValueError:
        return iso


def fecha_dia_mes(iso: str | None) -> tuple[str, str]:
    if not iso:
        return ("--", "---")
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (f"{d.day:02d}", MESES[d.month - 1][:3].upper())
    except ValueError:
        return ("--", "---")


def fecha_calendario(iso: str | None) -> str:
    if not iso:
        return "sin fecha"
    try:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
        return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"
    except ValueError:
        return iso


def nombre_corto(nombre: str) -> str:
    for prefijo in ("Deportes ", "Atlético ", "Club ", "Independiente "):
        if nombre.startswith(prefijo):
            return nombre[len(prefijo):]
    if nombre.startswith("Alianza de "):
        return "Alianza"
    return nombre


def iso_colombia(partido: dict) -> str:
    fecha = partido.get("fecha") or date.today().isoformat()
    hora = partido.get("hora_local") or "00:00"
    return f"{fecha}T{hora}:00-05:00"


def panel_envivo(partido: dict, modo: str = "completo") -> str:
    """Panel de marcador. El JS lo actualiza contra ESPN; sin evento, no se pinta."""
    if not partido.get("espn_id"):
        return ""
    cuando = f"{fecha_calendario(partido.get('fecha'))} · {partido.get('hora_local') or 'hora por confirmar'} (Colombia)"
    hero = modo == "hero"
    clase = "envivo envivo--hero" if hero else "envivo envivo--completo"
    hidden = " hidden" if hero else ""
    solo_vivo = ' data-solo-vivo="true"' if hero else ""
    return f"""
        <div class="{clase}" data-en-vivo data-evento="{e(partido['espn_id'])}"
             data-local="{e(partido['local'])}" data-visitante="{e(partido['visitante'])}"
             data-local-es-home="true" data-cuando="{e(cuando)}"{solo_vivo}{hidden}>
          <div class="envivo__top">
            <span class="envivo__chip" data-envivo-chip>Programado</span>
            <span class="envivo__reloj" data-envivo-reloj></span>
          </div>
          <div class="envivo__marcador">
            <span class="envivo__equipo">{e(nombre_corto(partido['local']))}</span>
            <strong class="envivo__goles" data-envivo-local>–</strong>
            <span class="envivo__sep">:</span>
            <strong class="envivo__goles" data-envivo-visitante>–</strong>
            <span class="envivo__equipo">{e(nombre_corto(partido['visitante']))}</span>
          </div>
          <p class="envivo__estado" data-envivo-estado>{e(cuando)}</p>
          <p class="envivo__nota">Marcador: ESPN · se actualiza cada 30 s</p>
        </div>"""


def tarjeta_partido(partido: dict, indice: int) -> str:
    dia, mes = fecha_dia_mes(partido.get("fecha_local") or partido.get("fecha"))
    hoy = date.today().isoformat()
    if partido.get("fecha_local") == hoy:
        etiqueta = "Hoy"
    elif indice == 0:
        etiqueta = "Siguiente"
    else:
        etiqueta = "Programado"
    hora = partido.get("hora_local") if partido.get("hora_confirmada") else "hora por confirmar"
    clase = "partido-card partido-card--siguiente" if indice == 0 else "partido-card"
    fuente = partido.get("fuente") or {}
    return f"""
      <article class="{clase}">
        <div class="partido-card__fecha"><span>{e(dia)}</span><small>{e(mes)}</small></div>
        <div class="partido-card__cuerpo">
          <p class="partido-card__meta">{e(partido.get('jornada') or 'Liga BetPlay')} · {e(partido.get('liga') or 'Liga BetPlay')}</p>
          <h3 class="partido-card__equipos">{e(partido['local'])} <span>vs</span> {e(partido['visitante'])}</h3>
          <p class="partido-card__detalle">{e(fecha_calendario(partido.get('fecha_local')))} · {e(hora)} · {e(partido.get('estadio') or 'sede por confirmar')}</p>
          <div class="partido-card__pie">
            <span class="chip chip--club">{e(etiqueta)}</span>
            <a href="{e(fuente.get('url') or '#')}" target="_blank" rel="noopener">Fuente: {e(fuente.get('nombre') or 'TheSportsDB')} ↗</a>
          </div>
        </div>
      </article>"""


def seccion_proximos(limite: int = 3) -> str:
    proximos = CALENDARIO.get("proximos", [])[:limite]
    if proximos:
        contenido = f'<div class="calendario-grid">{"".join(tarjeta_partido(p, i) for i, p in enumerate(proximos))}</div>'
    else:
        contenido = '<p class="sin-resultados">No hay fechas publicadas todavía. Cuando la Dimayor las confirme, aparecen acá. 🗓️</p>'
    contenido += '<p class="seccion__pie"><a class="boton boton--fantasma" href="partidos.html">Ver calendario y resultados</a></p>'
    return seccion("Los próximos partidos", "Calendario verificable", contenido, "seccion--partidos")


def resultado_fila(resultado: dict) -> str:
    fecha = resultado.get("fecha") or ""
    try:
        dt = datetime.fromisoformat(fecha.replace("Z", "+00:00")).astimezone(COLOMBIA)
        fecha_texto = f"{dt.day} {MESES[dt.month - 1][:3]}"
    except ValueError:
        fecha_texto = "sin fecha"
    return f"""
      <li class="resultado">
        <time class="resultado__fecha" datetime="{e(fecha)}">{e(fecha_texto)}</time>
        <span class="resultado__equipo">{e(resultado.get('local') or '')}</span>
        <strong class="resultado__marcador">{e(resultado.get('goles_local'))} <span>·</span> {e(resultado.get('goles_visitante'))}</strong>
        <span class="resultado__equipo">{e(resultado.get('visitante') or '')}</span>
      </li>"""


def marca() -> str:
    return """
    <a class="marca" href="index.html" aria-label="La Embajada Azul, inicio">
      <span class="marca__escudo" aria-hidden="true">
        <svg viewBox="0 0 48 48" role="img">
          <path d="M24 2 44 9v15c0 11-8.4 19.2-20 23C12.4 43.2 4 35 4 24V9Z" fill="#0743bf"/>
          <path d="M24 7 39 12v12c0 8.6-6.4 15-15 18.4C15.4 39 9 32.6 9 24V12Z" fill="none" stroke="#fff" stroke-width="2"/>
          <text x="24" y="31" text-anchor="middle" font-family="Arial Black, Arial, sans-serif" font-size="19" font-weight="900" fill="#fff">M</text>
        </svg>
      </span>
      <span class="marca__texto"><strong>La Embajada</strong><small>Azul · Millonarios</small></span>
    </a>"""


def layout(pagina: str, titulo: str, descripcion: str, cuerpo: str, extra_head: str = "", body_class: str = "") -> str:
    activo = pagina
    enlaces = "".join(
        f'<a class="nav__link{" is-active" if clave == activo else ""}" href="{url}"'
        f'{" aria-current=\"page\"" if clave == activo else ""}>{e(texto)}</a>'
        for url, texto, clave in NAV
    )
    anio = date.today().year
    fuentes = "".join(f'<li><a href="{e(f["url"])}" target="_blank" rel="noopener">{e(f["nombre"])}</a></li>' for f in SITIO["fuentes_generales"])
    escudo_pagina = MAPA_ESCUDO.get(pagina, "actual.svg")
    otros = [x["archivo"] for x in ESCUDOS if x["archivo"] != escudo_pagina]
    escudo_secundario = otros[0] if otros else "actual.svg"
    franja_escudos = "".join(
        f'<span class="pie__escudo"><img src="static/escudos/{x["archivo"]}" alt="" loading="lazy"><b>{e(x["era"])}</b></span>'
        for x in ESCUDOS
    )
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descripcion)}">
<meta name="theme-color" content="#04122e">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(SITIO['nombre'])}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descripcion)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="static/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="static/styles.css?v={version_asset('styles.css')}">
{extra_head}
</head>
<body class="{e(body_class)}">
<a class="skip" href="#contenido">Saltar al contenido</a>
<header class="cabecera">
  <div class="contenedor cabecera__fila">
    {marca()}
    <button class="nav__boton" type="button" aria-expanded="false" aria-controls="menu-principal">
      <span></span><span></span><span></span><span class="sr-only">Abrir menú</span>
    </button>
    <nav class="nav" id="menu-principal" aria-label="Principal">{enlaces}</nav>
  </div>
</header>
<main id="contenido">
  <div class="fondo-escudo" aria-hidden="true"><img src="static/escudos/{escudo_pagina}" alt="" loading="lazy"></div>
  <div class="fondo-escudo fondo-escudo--dos" aria-hidden="true"><img src="static/escudos/{escudo_secundario}" alt="" loading="lazy"></div>
{cuerpo}
</main>
<footer class="pie">
  <div class="contenedor pie__grid">
    <div>
      <p class="pie__marca">La Embajada Azul</p>
      <p class="pie__aviso">{e(SITIO['aviso'])}</p>
    </div>
    <div>
      <p class="pie__titulo">Fuentes</p>
      <ul class="pie__lista">{fuentes}</ul>
    </div>
    <div>
      <p class="pie__titulo">Transparencia</p>
      <p class="pie__texto">Noticias: agregadas por RSS y enlazadas al medio original. Alineación: estimación editorial, no información oficial. Pronóstico: modelo estadístico, no certeza ni consejo de apuestas.</p>
      <p class="pie__texto">© {anio} · Hecho por hinchas, para hinchas.</p>
    </div>
  </div>
  <div class="contenedor pie__franja">
    <div class="pie__escudos" aria-label="Escudos homenaje del club">{franja_escudos}</div>
    <p class="pie__nota-escudos">Escudos homenaje ilustrados para este sitio · no son emblemas oficiales.</p>
  </div>
</footer>
<script src="static/app.js?v={version_asset('app.js')}" defer></script>
<script src="static/envivo.js?v={version_asset('envivo.js')}" defer></script>
</body>
</html>"""


def tarjeta_noticia(n: dict, compacta: bool = False) -> str:
    clase = "noticia noticia--compacta" if compacta else "noticia"
    origen = "Club" if n.get("club") else "Prensa"
    resumen = f'<p class="noticia__resumen">{e(n["resumen"])}</p>' if n.get("resumen") else ""
    return f"""
    <article class="{clase}" data-fuente="{e(origen)}" data-medio="{e(n['fuente'])}" data-texto="{e((n['titulo'] + ' ' + n.get('resumen','')).lower())}">
      <div class="noticia__meta">
        <span class="chip chip--{ 'club' if n.get('club') else 'prensa' }">{origen}</span>
        <span class="noticia__fuente">{e(n['fuente'])}</span>
        <time datetime="{e(n.get('fecha') or '')}">{e(fecha_corta(n.get('fecha')))}</time>
      </div>
      <h3 class="noticia__titulo"><a href="{e(n['url'])}" target="_blank" rel="noopener">{e(n['titulo'])}</a></h3>
      {resumen}
      <a class="noticia__enlace" href="{e(n['url'])}" target="_blank" rel="noopener">Leer en {e(n['fuente'])} <span aria-hidden="true">↗</span></a>
    </article>"""


def seccion(titulo: str, eyebrow: str, contenido: str, clase: str = "") -> str:
    return f"""
    <section class="seccion {clase}">
      <div class="contenedor">
        <div class="seccion__cabecera">
          <p class="eyebrow">{e(eyebrow)}</p>
          <h2 class="seccion__titulo">{e(titulo)}</h2>
        </div>
        {contenido}
      </div>
    </section>"""


def heroe() -> str:
    fecha = fecha_larga(PARTIDO["fecha"])
    hora = PARTIDO["hora_local"] if PARTIDO.get("hora_confirmada") else "hora por confirmar"
    return f"""
    <section class="heroe">
      <div class="heroe__lineas" aria-hidden="true"></div>
      <div class="heroe__escudos" aria-hidden="true">
        <img class="heroe__escudo heroe__escudo--a" src="static/escudos/ballet.svg" alt="">
        <img class="heroe__escudo heroe__escudo--b" src="static/escudos/1946.svg" alt="">
        <img class="heroe__escudo heroe__escudo--c" src="static/escudos/embajador.svg" alt="">
      </div>
      <div class="heroe__destellos" aria-hidden="true">
        <span></span><span></span><span></span><span></span><span></span><span></span>
      </div>
      <div class="contenedor heroe__grid">
        <div class="heroe__texto">
          <p class="eyebrow">Sitio de hinchas · no oficial</p>
          <h1 class="heroe__titulo">Millonarios,<br><span>sin humo.</span></h1>
          <p class="heroe__bajada">Noticias con fuente, convocatoria real, XI probable sin inventar y un pronóstico que muestra sus números. Todo lo que un embajador quiere saber antes del pitazo.</p>
          <div class="heroe__acciones">
            <a class="boton boton--primario" href="alineacion.html">Ver XI probable</a>
            <a class="boton boton--fantasma" href="pronostico.html">Pronóstico del partido</a>
          </div>
          <p class="heroe__nota">Última actualización con fuente · marcador en vivo desde ESPN</p>
        </div>
        <aside class="partido" aria-labelledby="titulo-partido">
          <div class="partido__cabecera">
            <span class="chip chip--vivo" data-partido-chip>Próximo partido</span>
            <span class="partido__jornada">{e(PARTIDO['liga'])} · {e(PARTIDO['jornada'])}</span>
          </div>
          <h2 class="sr-only" id="titulo-partido">Próximo partido de Millonarios</h2>
          <div class="partido__equipos">
            <div class="partido__equipo"><span class="partido__inicial">{e(PARTIDO['local'][0])}</span><span>{e(PARTIDO['local'])}</span></div>
            <span class="partido__vs">vs</span>
            <div class="partido__equipo partido__equipo--millos"><span class="partido__inicial">M</span><span>{e(PARTIDO['visitante'])}</span></div>
          </div>
          <p class="partido__fecha">{e(fecha)} · {e(hora)} (Colombia)</p>
          <p class="partido__estadio">{e(PARTIDO['estadio'])}</p>
          <div class="cuenta" data-cuenta="{e(iso_colombia(PARTIDO))}" aria-live="polite">
            <div><strong data-cuenta-dias>--</strong><span>días</span></div>
            <div><strong data-cuenta-horas>--</strong><span>horas</span></div>
            <div><strong data-cuenta-min>--</strong><span>min</span></div>
            <div><strong data-cuenta-seg>--</strong><span>seg</span></div>
          </div>
          {panel_envivo(PARTIDO, "hero")}
          <p class="partido__contexto">{e(PARTIDO['contexto'])}</p>
          <a class="partido__fuente" href="{e(PARTIDO['fuentes'][0]['url'])}" target="_blank" rel="noopener">Fuente: {e(PARTIDO['fuentes'][0]['nombre'])} ↗</a>
          <p class="partido__fuente"><a href="partidos.html">Ver calendario completo →</a></p>
        </aside>
      </div>
    </section>"""


def pagina_inicio() -> str:
    destacadas = "".join(tarjeta_noticia(n) for n in NOTICIAS["noticias"][:6])
    t = RESULTADOS["total"]
    c = RESULTADOS["casa"]
    f = RESULTADOS["fuera"]
    forma = f"""
    <div class="formas">
      <div class="forma__bloque"><span class="forma__dato">{t['pj']}</span><span>partidos</span></div>
      <div class="forma__bloque"><span class="forma__dato">{t['gf']}</span><span>goles a favor</span></div>
      <div class="forma__bloque"><span class="forma__dato">{t['gc']}</span><span>goles en contra</span></div>
      <div class="forma__bloque"><span class="forma__dato">{t['pts']}</span><span>puntos</span></div>
    </div>
    <div class="formas__split">
      <div class="forma__casa">
        <p class="forma__titulo">En casa</p>
        <p class="forma__linea">{c['pg']}G · {c['pe']}E · {c['pp']}P</p>
        <p class="forma__detalle">{c['gf']} GF · {c['gc']} GC en {c['pj']} partidos</p>
      </div>
      <div class="forma__fuera">
        <p class="forma__titulo">De visitante</p>
        <p class="forma__linea">{f['pg']}G · {f['pe']}E · {f['pp']}P</p>
        <p class="forma__detalle">{f['gf']} GF · {f['gc']} GC en {f['pj']} partidos</p>
      </div>
    </div>
    <p class="fuente-inline">Corte: {e(RESULTADOS['corte'])} · <a href="{e(RESULTADOS['fuente']['url'])}" target="_blank" rel="noopener">{e(RESULTADOS['fuente']['nombre'])}</a></p>"""

    palmares = "".join(
        f'<div class="logro"><span class="logro__num">{h["cantidad"]}</span><span class="logro__titulo">{e(h["titulo"])}</span></div>'
        for h in HISTORIA["palmares"][:4]
    )

    cuerpo = heroe() + seccion(
        "Lo último del Embajador", "Noticias con fuente",
        f'<div class="noticias-grid">{destacadas}</div><p class="seccion__pie"><a class="boton boton--fantasma" href="noticias.html">Ver todas las noticias</a></p>'
    ) + seccion_proximos(3) + seccion(
        "Cómo llega el azul", "Datos, no sensaciones", forma
    ) + seccion(
        "La alineación, sin inventar", "Convocatoria real + criterio",
        f"""<div class="destacado">
          <div class="destacado__texto">
            <p class="destacado__etiqueta">XI probable · {e(ALINEACION['formacion'])}</p>
            <h3>Los 20 convocados están. Las bajas, explicadas.</h3>
            <p>Valencia (lesión muscular) y Ureña (suspensión) no están. Del Castillo y Leonai Souza vuelven a la lista. El once es una estimación editorial y así se dice, sin vender humo.</p>
            <a class="boton boton--primario" href="alineacion.html">Ver pizarra y convocados</a>
          </div>
          <div class="destacado__mini"><div class="mini-pitch" aria-hidden="true">
            <span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span>
          </div></div>
        </div>"""
    ) + seccion(
        "El club en cuatro números", "Historia verificada",
        f'<div class="logros">{palmares}</div><p class="seccion__pie"><a class="boton boton--fantasma" href="historia.html">Toda la historia</a></p>'
    ) + seccion(
        "Para el entretiempo", "Minijuegos",
        """<div class="juegos-teaser">
          <a class="juego-card" href="juegos.html#trivia"><span class="juego-card__icono">🧠</span><h3>Trivia embajadora</h3><p>10 preguntas. Si fallás, quedás en ridículo.</p></a>
          <a class="juego-card" href="juegos.html#adivina"><span class="juego-card__icono">🕵️</span><h3>Adivina el jugador</h3><p>Pistas, opciones y orgullo en juego.</p></a>
          <a class="juego-card" href="juegos.html#pick"><span class="juego-card__icono">🎯</span><h3>Tu pronóstico</h3><p>Elegí 1X2 y guardá tu pick.</p></a>
        </div>"""
    ) + seccion(
        "Qué es automático y qué es criterio", "Transparencia",
        """<div class="transparencia">
          <div><h3>🤖 Automático</h3><p>Noticias por RSS, próximo partido y calendario. El actualizador corre cuando se ejecuta (manual o programado) y el marcador en vivo se consulta desde tu navegador.</p></div>
          <div><h3>✍️ Editorial</h3><p>El XI probable y la lectura del partido. Se basan en la convocatoria oficial y se marcan como estimación.</p></div>
          <div><h3>📊 Modelo</h3><p>El pronóstico es una probabilidad, no una promesa. Muestra sus supuestos y su muestra.</p></div>
          <div><h3>🔗 Verificable</h3><p>Cada dato relevante enlaza a su fuente. Si no hay fuente, no se publica.</p></div>
        </div>"""
    )
    return layout("inicio", f"{SITIO['nombre']} · Millonarios sin humo", SITIO["descripcion"], cuerpo)


def pagina_noticias() -> str:
    tarjetas = "".join(tarjeta_noticia(n) for n in NOTICIAS["noticias"])
    fuentes = sorted({n["fuente"] for n in NOTICIAS["noticias"]})
    chips = "".join(f'<button class="filtro" type="button" data-filtro="{e(f)}">{e(f)}</button>' for f in fuentes)
    errores = ""
    if NOTICIAS.get("errores"):
        errores = '<p class="aviso aviso--error">Algunas fuentes no respondieron en la última actualización: ' + \
                  ", ".join(e(x["fuente"]) for x in NOTICIAS["errores"]) + ".</p>"
    cuerpo = f"""
    <section class="cabecera-pagina">
      <div class="contenedor">
        <p class="eyebrow">Agregador de noticias</p>
        <h1>Noticias del Embajador</h1>
        <p class="cabecera-pagina__bajada">Titulares de medios y del club, con enlace al original. Sin copiar el artículo completo, sin inventar fuentes.</p>
        <p class="cabecera-pagina__meta">Última actualización: {e(fecha_corta(NOTICIAS['actualizado']))} · {NOTICIAS['total']} noticias</p>
      </div>
    </section>
    <section class="seccion seccion--ajustada">
      <div class="contenedor">
        {errores}
        <div class="controles">
          <label class="buscador">
            <span class="sr-only">Buscar noticias</span>
            <input type="search" id="buscador-noticias" placeholder="Buscar: Tolima, convocatoria, Campín…" autocomplete="off">
          </label>
          <div class="filtros" role="group" aria-label="Filtrar por fuente">
            <button class="filtro is-active" type="button" data-filtro="todas">Todas</button>
            <button class="filtro" type="button" data-filtro="Club">Club</button>
            <button class="filtro" type="button" data-filtro="Prensa">Prensa</button>
            {chips}
          </div>
        </div>
        <p class="resultado-conteo" id="conteo-noticias" aria-live="polite"></p>
        <div class="noticias-lista" id="lista-noticias">{tarjetas}</div>
        <p class="sin-resultados" id="sin-resultados" hidden>No hay noticias que coincidan. Probá con otra palabra. 🤷</p>
        <p class="nota-legal">Los resúmenes provienen del feed RSS de cada medio y se muestran solo como adelanto. El contenido completo pertenece a sus autores: hacé clic y leelo en la fuente.</p>
      </div>
    </section>"""
    return layout("noticias", f"Noticias · {SITIO['nombre']}", "Últimas noticias de Millonarios con enlace a la fuente original.", cuerpo)


def pagina_partidos() -> str:
    proximos = CALENDARIO.get("proximos", [])
    recientes = CALENDARIO.get("recientes", [])
    tarjetas = "".join(tarjeta_partido(p, i) for i, p in enumerate(proximos))
    if not tarjetas:
        tarjetas = '<p class="sin-resultados">No hay fechas publicadas todavía. Cuando la Dimayor las confirme, aparecen acá. 🗓️</p>'
    filas = "".join(resultado_fila(r) for r in recientes)
    if not filas:
        filas = '<li class="resultado resultado--vacio">Todavía no hay resultados cerrados para mostrar.</li>'
    vivo = panel_envivo(PARTIDO, "completo")
    if not vivo:
        vivo = '<div class="aviso aviso--info">El marcador en vivo aparecerá cuando ESPN publique el evento. Mientras tanto, el calendario y la hora oficial están abajo.</div>'
    actualizado = fecha_corta(CALENDARIO.get("actualizado"))

    return layout("partidos", f"Partidos · {SITIO['nombre']}", "Próximos partidos, calendario y marcador en vivo de Millonarios.", f"""
    <section class="cabecera-pagina cabecera-pagina--partidos">
      <div class="contenedor">
        <p class="eyebrow">Calendario + marcador</p>
        <h1>Los próximos partidos</h1>
        <p class="cabecera-pagina__bajada">Fechas, sedes y horas del Embajador. Si la Dimayor no confirma una hora, se dice. Si el partido ya arrancó, el marcador se actualiza solo desde ESPN.</p>
        <p class="cabecera-pagina__meta">Calendario actualizado: {e(actualizado)} · {len(proximos)} fecha{'s' if len(proximos) != 1 else ''} por jugar</p>
      </div>
    </section>
    <section class="seccion seccion--ajustada">
      <div class="contenedor">
        <div class="seccion__cabecera"><p class="eyebrow">Ahora</p><h2 class="seccion__titulo">En vivo</h2></div>
        <div class="envivo-grid">
          {vivo}
          <aside class="panel envivo-info">
            <h3>Qué estás viendo</h3>
            <ul class="envivo-info__lista">
              <li><strong>Programado:</strong> todavía no rueda la pelota. Se muestra la hora y el marcador queda en guiones.</li>
              <li><strong>En vivo:</strong> el chip se pone verde y aparecen goles y minuto. Se consulta cada 30 segundos.</li>
              <li><strong>Final:</strong> queda el marcador definitivo, sin desaparecer la página.</li>
            </ul>
            <p class="fuente-inline">Marcador: <a href="https://www.espn.com.co/futbol/colombia/" target="_blank" rel="noopener">ESPN Colombia ↗</a></p>
          </aside>
        </div>
      </div>
    </section>
    <section class="seccion">
      <div class="contenedor">
        <div class="seccion__cabecera"><p class="eyebrow">Próximas fechas</p><h2 class="seccion__titulo">El calendario</h2></div>
        <div class="calendario-grid calendario-grid--pagina">{tarjetas}</div>
        <p class="nota-legal">Las fechas y horas pueden cambiar por decisión de la Dimayor o por copas. La columna “hora por confirmar” no es un error: es una fecha que todavía no está cerrada en las fuentes públicas.</p>
      </div>
    </section>
    <section class="seccion">
      <div class="contenedor">
        <div class="seccion__cabecera"><p class="eyebrow">Lo último jugado</p><h2 class="seccion__titulo">Últimos resultados</h2></div>
        <ol class="resultados">{filas}</ol>
        <p class="fuente-inline">Resultados: <a href="https://www.espn.com.co/futbol/colombia/" target="_blank" rel="noopener">ESPN Colombia</a> · calendario: <a href="https://www.thesportsdb.com/team/137617" target="_blank" rel="noopener">TheSportsDB</a></p>
      </div>
    </section>
    <section class="seccion">
      <div class="contenedor">
        <div class="seccion__cabecera"><p class="eyebrow">Sin humo</p><h2 class="seccion__titulo">Cómo se actualiza</h2></div>
        <div class="transparencia">
          <div><h3>🗓️ Calendario</h3><p>TheSportsDB alimenta las próximas fechas. El actualizador conserva el último calendario bueno si la fuente falla.</p></div>
          <div><h3>📡 Marcador</h3><p>El navegador consulta ESPN cada 30 segundos cuando hay partido. No hay servidor propio ni base de datos: si ESPN cae, se avisa.</p></div>
          <div><h3>🕒 Hora</h3><p>Todo se muestra en hora de Colombia (UTC-5). Las horas futuras se marcan como “por confirmar” hasta que haya una fuente que las cierre.</p></div>
          <div><h3>🔗 Fuente</h3><p>Cada partido enlaza a su ficha. Si un dato no se puede verificar, no se inventa: se deja pendiente.</p></div>
        </div>
      </div>
    </section>""")



def pagina_alineacion() -> str:
    filas = []
    for i, linea in enumerate(ALINEACION["lineas"]):
        clase = "pitch__fila pitch__fila--arco" if i == 0 else "pitch__fila"
        fichas = "".join(
            f'<div class="ficha"><span class="ficha__num">{e(j["num"])}</span><span class="ficha__nombre">{e(j["nombre"].split()[-1])}</span></div>'
            for j in linea
        )
        filas.append(f'<div class="{clase}">{fichas}</div>')
    pizarra = "".join(filas)

    bajas = "".join(f'<li><strong>{e(b["nombre"])}</strong><span>{e(b["motivo"])}</span></li>' for b in ALINEACION["bajas"])
    grupos = "".join(
        f'<div class="grupo"><h3>{e(grupo)}</h3><ul>' + "".join(f"<li>{e(jugador)}</li>" for jugador in nombres) + "</ul></div>"
        for grupo, nombres in ALINEACION["convocados"].items()
    )
    once = "".join(f'<li><span class="once__num">{e(j["num"])}</span><span class="once__nombre">{e(j["nombre"])}</span><span class="once__pos">{e(j["pos"])}</span></li>' for j in ALINEACION["xi"])

    cuerpo = f"""
    <section class="cabecera-pagina">
      <div class="contenedor">
        <p class="eyebrow">Convocatoria oficial + criterio</p>
        <h1>Alineación probable</h1>
        <p class="cabecera-pagina__bajada">20 convocados confirmados, dos bajas explicadas y un once que es estimación, no filtraciones inventadas.</p>
        <div class="aviso aviso--info"><strong>Ojo:</strong> {e(ALINEACION['nota'])}</div>
      </div>
    </section>
    <section class="seccion seccion--ajustada">
      <div class="contenedor alineacion-grid">
        <div class="pizarra-card">
          <div class="pizarra-card__cabecera"><span class="chip chip--vivo">XI probable</span><span>{e(ALINEACION['formacion'])}</span></div>
          <div class="pitch" role="img" aria-label="Pizarra con el once probable de Millonarios en formación {e(ALINEACION['formacion'])}">{pizarra}</div>
          <p class="pizarra-card__pie">Estimación editorial · no confirmada por el club</p>
        </div>
        <div class="alineacion-lado">
          <div class="panel">
            <h2>Once probable</h2>
            <ol class="once">{once}</ol>
          </div>
          <div class="panel panel--bajas">
            <h2>Bajas</h2>
            <ul class="bajas">{bajas}</ul>
          </div>
          <p class="fuente-inline">Fuente: <a href="{e(ALINEACION['fuente']['url'])}" target="_blank" rel="noopener">{e(ALINEACION['fuente']['nombre'])} ↗</a></p>
        </div>
      </div>
    </section>
    <section class="seccion">
      <div class="contenedor">
        <div class="seccion__cabecera"><p class="eyebrow">Los 20</p><h2 class="seccion__titulo">Convocados para Ibagué</h2></div>
        <div class="convocados">{grupos}</div>
        <p class="nota-legal">La alineación oficial se conoce cerca del inicio del partido. Si cambia, esta página se actualiza a mano y se avisa en la fecha de edición.</p>
      </div>
    </section>"""
    return layout("alineacion", f"Alineación probable · {SITIO['nombre']}", "XI probable de Millonarios con convocatoria oficial, bajas y formación.", cuerpo)


def poisson(lam: float, k: int) -> float:
    import math
    return math.exp(-lam) * lam ** k / math.factorial(k)


def probabilidades() -> dict:
    global_local = 1.45  # supuesto documentado: promedio de local en la liga
    lam_millos = RESULTADOS["fuera"]["gf"] / RESULTADOS["fuera"]["pj"]
    lam_rival = global_local
    p_local = p_empate = p_visit = 0.0
    over25 = btts = 0.0
    for i in range(9):
        for j in range(9):
            p = poisson(lam_rival, i) * poisson(lam_millos, j)
            if i > j:
                p_local += p
            elif i == j:
                p_empate += p
            else:
                p_visit += p
            if i + j > 2.5:
                over25 += p
            if i > 0 and j > 0:
                btts += p
    return {
        "local": p_local, "empate": p_empate, "visitante": p_visit,
        "over25": over25, "btts": btts,
        "lam_millos": lam_millos, "lam_rival": lam_rival,
    }


def pagina_pronostico() -> str:
    p = probabilidades()
    def barra(nombre: str, valor: float, clase: str) -> str:
        return f"""<div class="prob">
          <div class="prob__fila"><span>{e(nombre)}</span><strong>{valor*100:.1f}%</strong></div>
          <div class="prob__barra"><span class="{clase}" style="width:{valor*100:.1f}%"></span></div>
        </div>"""
    return layout("pronostico", f"Pronóstico · {SITIO['nombre']}", "Pronóstico probabilístico y transparente del próximo partido de Millonarios.", f"""
    <section class="cabecera-pagina">
      <div class="contenedor">
        <p class="eyebrow">Modelo Poisson · transparencia total</p>
        <h1>Pronóstico del partido</h1>
        <p class="cabecera-pagina__bajada">Una probabilidad, no una promesa. Acá están los supuestos, la muestra y el cálculo. Si el modelo se equivoca, también se va a ver.</p>
        <div class="aviso aviso--info"><strong>Esto no es consejo de apuestas.</strong> Es un ejercicio estadístico con datos incompletos. No hay "fijo", no hay link de casa de apuestas, no hay milagro.</div>
      </div>
    </section>
    <section class="seccion seccion--ajustada">
      <div class="contenedor pronostico-grid">
        <div class="panel panel--grande">
          <div class="partido-mini"><span>{e(PARTIDO['local'])}</span><strong>vs</strong><span>{e(PARTIDO['visitante'])}</span></div>
          <p class="panel__sub">{e(fecha_larga(PARTIDO['fecha']))} · {e(PARTIDO['hora_local'])} · {e(PARTIDO['estadio'])}</p>
          {barra(PARTIDO['local'] + ' gana', p['local'], 'barra--roja')}
          {barra('Empate', p['empate'], 'barra--gris')}
          {barra(PARTIDO['visitante'] + ' gana', p['visitante'], 'barra--azul')}
          <div class="prob-dobles">
            <div><span>Más de 2.5 goles</span><strong>{p['over25']*100:.0f}%</strong></div>
            <div><span>Ambos marcan</span><strong>{p['btts']*100:.0f}%</strong></div>
            <div><span>Goles esperados Millos</span><strong>{p['lam_millos']:.2f}</strong></div>
            <div><span>Goles esperados Tolima</span><strong>{p['lam_rival']:.2f}</strong></div>
          </div>
        </div>
        <aside class="panel">
          <h2>Cómo se calcula</h2>
          <ol class="pasos">
            <li>Se toma la producción ofensiva y defensiva de Millonarios como visitante en 2026: <strong>{RESULTADOS['fuera']['gf']} goles a favor y {RESULTADOS['fuera']['gc']} en contra en {RESULTADOS['fuera']['pj']} partidos</strong>.</li>
            <li>Se estima al Tolima como local con un prior de liga de <strong>1.45 goles por partido</strong>. Es un supuesto, no un dato verificado del rival.</li>
            <li>Con esos dos promedios se calcula una distribución de Poisson para cada marcador posible (0-8 goles) y se suman las probabilidades de victoria, empate y derrota.</li>
            <li>El resultado es una foto del rendimiento reciente, no una predicción del futuro. No ajusta por lesiones, clima, árbitro ni motivación.</li>
          </ol>
          <p class="fuente-inline">Datos: <a href="{e(RESULTADOS['fuente']['url'])}" target="_blank" rel="noopener">{e(RESULTADOS['fuente']['nombre'])}</a> · corte {e(RESULTADOS['corte'])}</p>
        </aside>
      </div>
    </section>
    <section class="seccion">
      <div class="contenedor">
        <div class="seccion__cabecera"><p class="eyebrow">Tu pick</p><h2 class="seccion__titulo">Jugátela, pero sin plata</h2></div>
        <div class="pick" id="pick" data-local="{e(PARTIDO['local'])}" data-visitante="{e(PARTIDO['visitante'])}">
          <p>Elegí tu resultado para Tolima vs Millonarios. Se guarda en tu navegador y nada más.</p>
          <div class="pick__botones" role="group" aria-label="Elegir resultado">
            <button type="button" class="pick__opcion" data-pick="local">{e(PARTIDO['local'])}</button>
            <button type="button" class="pick__opcion" data-pick="empate">Empate</button>
            <button type="button" class="pick__opcion" data-pick="visitante">{e(PARTIDO['visitante'])}</button>
          </div>
          <p class="pick__estado" id="pick-estado" aria-live="polite"></p>
          <button type="button" class="boton boton--fantasma boton--chico" id="pick-limpiar">Borrar mi pick</button>
        </div>
        <div class="panel panel--registro">
          <h2>Registro del modelo</h2>
          <p>Este espacio queda vacío a propósito hasta que haya partidos cerrados con pronóstico previo. Un registro honesto empieza cuando se puede verificar, no cuando conviene.</p>
          <p class="registro-vacio">0 partidos registrados · 0 aciertos · 0% de efectividad</p>
        </div>
      </div>
    </section>""")


def pagina_historia() -> str:
    palmares = "".join(
        f"""<div class="palmares__item">
          <span class="palmares__num">{h['cantidad']}</span>
          <div><h3>{e(h['titulo'])}</h3><p>{e(h['anios'])}</p>{f'<small>{e(h["nota"])}</small>' if h.get('nota') else ''}</div>
        </div>"""
        for h in HISTORIA["palmares"]
    )
    cronologia = "".join(
        f'<li><span class="linea__anio">{e(c["anio"])}</span><div class="linea__texto">{e(c["texto"])}</div></li>'
        for c in HISTORIA["cronologia"]
    )
    idolos = "".join(f'<div class="idolo"><h3>{e(i["nombre"])}</h3><p>{e(i["detalle"])}</p></div>' for i in HISTORIA["idolos"])
    rivales = "".join(f'<div class="rival"><h3>{e(r["nombre"])}</h3><p>{e(r["detalle"])}</p></div>' for r in HISTORIA["rivalidades"])
    galeria = "".join(
        f"""<figure class="escudo-card">
          <img src="static/escudos/{x['archivo']}" alt="Escudo homenaje {e(x['nombre'])}" loading="lazy">
          <figcaption><span>{e(x['era'])}</span><h3>{e(x['nombre'])}</h3><p>{e(x['texto'])}</p></figcaption>
        </figure>"""
        for x in ESCUDOS
    )

    return layout("historia", f"Historia · {SITIO['nombre']}", "Historia, palmarés, ídolos y rivalidades de Millonarios Fútbol Club.", f"""
    <section class="cabecera-pagina cabecera-pagina--historia">
      <div class="contenedor">
        <p class="eyebrow">1946 · Bogotá · El Campín</p>
        <h1>La historia del Embajador</h1>
        <p class="cabecera-pagina__bajada">{e(HISTORIA['resumen'])}</p>
        <div class="datos-club">
          <div><span>Fundación</span><strong>{e(HISTORIA['fundacion'])}</strong></div>
          <div><span>Estadio</span><strong>{e(HISTORIA['estadio'])}</strong></div>
          <div><span>Apodo</span><strong>{e(HISTORIA['apodo'])}</strong></div>
          <div><span>Colores</span><strong>{e(HISTORIA['colores'])}</strong></div>
        </div>
      </div>
    </section>
    <section class="seccion seccion--ajustada">
      <div class="contenedor">
        <div class="seccion__cabecera"><p class="eyebrow">Palmarés</p><h2 class="seccion__titulo">Lo que hay en la vitrina</h2></div>
        <div class="palmares">{palmares}</div>
        <p class="fuente-inline">Fuente: <a href="{e(HISTORIA['fuente']['url'])}" target="_blank" rel="noopener">{e(HISTORIA['fuente']['nombre'])}</a> · {e(HISTORIA['fuente']['licencia'])}</p>
      </div>
    </section>
    <section class="seccion">
      <div class="contenedor">
        <div class="seccion__cabecera"><p class="eyebrow">Identidad</p><h2 class="seccion__titulo">Escudos en el tiempo</h2></div>
        <div class="galeria-escudos">{galeria}</div>
        <p class="fuente-inline">Ilustraciones homenaje creadas para este sitio. Son versiones libres inspiradas en la historia del club, no los emblemas oficiales ni copias de ellos.</p>
      </div>
    </section>
    <section class="seccion">
      <div class="contenedor historia-grid">
        <div>
          <div class="seccion__cabecera"><p class="eyebrow">Línea de tiempo</p><h2 class="seccion__titulo">De El Dorado a hoy</h2></div>
          <ol class="linea">{cronologia}</ol>
        </div>
        <div>
          <div class="seccion__cabecera"><p class="eyebrow">Nombres</p><h2 class="seccion__titulo">Ídolos</h2></div>
          <div class="idolos">{idolos}</div>
          <div class="seccion__cabecera seccion__cabecera--separada"><p class="eyebrow">Clásicos</p><h2 class="seccion__titulo">Rivalidades</h2></div>
          <div class="rivales">{rivales}</div>
        </div>
      </div>
    </section>""")


def pagina_juegos() -> str:
    datos_js = json.dumps({
        "trivia": TRIVIA["preguntas"],
        "convocados": ALINEACION["convocados"],
        "plantilla": PLANTILLA["jugadores"],
        "partido": {"local": PARTIDO["local"], "visitante": PARTIDO["visitante"]},
    }, ensure_ascii=False)
    return layout("juegos", f"Juegos · {SITIO['nombre']}", "Trivia, adivina el jugador y pronóstico rápido de Millonarios.", f"""
    <section class="cabecera-pagina">
      <div class="contenedor">
        <p class="eyebrow">Para el entretiempo</p>
        <h1>Minijuegos embajadores</h1>
        <p class="cabecera-pagina__bajada">Tres juegos, cero plata, cero humo. Todo corre en tu navegador.</p>
      </div>
    </section>
    <section class="seccion seccion--ajustada">
      <div class="contenedor juegos">
        <article class="panel juego" id="trivia">
          <div class="juego__cabecera"><span class="juego__icono">🧠</span><div><p class="eyebrow">Juego 1</p><h2>Trivia embajadora</h2></div></div>
          <p class="juego__intro">10 preguntas de historia y datos. Sin trampa: la respuesta se explica al final de cada una.</p>
          <div class="trivia" id="trivia-app">
            <div class="trivia__barra"><span id="trivia-progreso">Pregunta 1 de 10</span><span id="trivia-puntaje">0 aciertos</span></div>
            <h3 class="trivia__pregunta" id="trivia-pregunta">Cargando…</h3>
            <div class="trivia__opciones" id="trivia-opciones"></div>
            <p class="trivia__dato" id="trivia-dato" hidden></p>
            <div class="trivia__acciones">
              <button class="boton boton--primario" type="button" id="trivia-siguiente" disabled>Siguiente</button>
              <button class="boton boton--fantasma" type="button" id="trivia-reiniciar" hidden>Reiniciar</button>
            </div>
          </div>
        </article>
        <article class="panel juego" id="adivina">
          <div class="juego__cabecera"><span class="juego__icono">🕵️</span><div><p class="eyebrow">Juego 2</p><h2>Adivina el jugador</h2></div></div>
          <p class="juego__intro">Un convocado, tres pistas y cuatro opciones. Una sola oportunidad por ronda.</p>
          <div class="adivina" id="adivina-app">
            <p class="adivina__pista" id="adivina-pista">Cargando…</p>
            <div class="adivina__opciones" id="adivina-opciones"></div>
            <p class="adivina__estado" id="adivina-estado" aria-live="polite"></p>
            <button class="boton boton--fantasma" type="button" id="adivina-otra" hidden>Otra ronda</button>
          </div>
        </article>
        <article class="panel juego" id="pick">
          <div class="juego__cabecera"><span class="juego__icono">🎯</span><div><p class="eyebrow">Juego 3</p><h2>Pronóstico rápido</h2></div></div>
          <p class="juego__intro">Elegí quién gana el próximo partido. Se guarda en tu navegador, sin registro ni promesas.</p>
          <div class="pick" id="pick-juego" data-local="{e(PARTIDO['local'])}" data-visitante="{e(PARTIDO['visitante'])}">
            <p class="pick__partido" id="pick-partido">Cargando…</p>
            <div class="pick__botones" role="group" aria-label="Elegir resultado">
              <button type="button" class="pick__opcion" data-pick="local" id="pick-local">Local</button>
              <button type="button" class="pick__opcion" data-pick="empate">Empate</button>
              <button type="button" class="pick__opcion" data-pick="visitante" id="pick-visitante">Visitante</button>
            </div>
            <p class="pick__estado" id="pick-estado-juego" aria-live="polite"></p>
            <button type="button" class="boton boton--fantasma boton--chico" id="pick-limpiar-juego">Borrar</button>
          </div>
        </article>
      </div>
    </section>
    <script type="application/json" id="datos-juegos">{datos_js}</script>""")


def sitemap() -> str:
    base = SITIO["dominio"].rstrip("/")
    urls = "".join(
        f"<url><loc>{base}/{url}</loc><changefreq>{'hourly' if url in ('index.html','noticias.html') else 'weekly'}</changefreq></url>"
        for url, _, _ in NAV
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(STATIC, DIST / "static")

    paginas = {
        "index.html": pagina_inicio(),
        "noticias.html": pagina_noticias(),
        "partidos.html": pagina_partidos(),
        "alineacion.html": pagina_alineacion(),
        "pronostico.html": pagina_pronostico(),
        "historia.html": pagina_historia(),
        "juegos.html": pagina_juegos(),
    }
    for nombre, html in paginas.items():
        (DIST / nombre).write_text(html, encoding="utf-8")

    (DIST / "sitemap.xml").write_text(sitemap(), encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITIO['dominio'].rstrip('/')}/sitemap.xml\n", encoding="utf-8")
    print(f"Listo: {len(paginas)} páginas en {DIST}")


if __name__ == "__main__":
    main()
