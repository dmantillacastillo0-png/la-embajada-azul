# La Embajada Azul 🟦⬜

Sitio de hinchas de **Millonarios Fútbol Club**: noticias con fuente, convocatoria y XI probable, pronóstico probabilístico, próximos partidos, marcador en vivo, historia y minijuegos.

> ⚠️ **Sitio no oficial.** No tiene relación con Millonarios FC, la Dimayor ni los medios citados. Es un proyecto de hinchas.

**En vivo:** <https://dmantillacastillo0-png.github.io/la-embajada-azul/>

## Qué incluye

| Sección | Qué hace | Cómo se actualiza |
|---|---|---|
| `index.html` | Portada: próximo partido, cuenta regresiva, últimas noticias, calendario y datos de forma | Automático + build |
| `noticias.html` | Agregador con búsqueda y filtros por medio | RSS al ejecutar el actualizador |
| `partidos.html` | Próximos partidos, calendario, marcador en vivo y últimos resultados | TheSportsDB + ESPN |
| `alineacion.html` | Pizarra con XI probable, convocados y bajas | Editorial (JSON) |
| `pronostico.html` | Modelo Poisson con supuestos a la vista y registro vacío | Automático |
| `historia.html` | Palmarés, cronología, ídolos y rivalidades | Estático, con fuente |
| `juegos.html` | Trivia, adivina el jugador y pick 1X2 | 100 % navegador |

## Cómo correrlo local

No tiene dependencias: solo Python 3.10+ y su biblioteca estándar.

```bash
python3 scripts/update.py     # baja noticias RSS (y partido si hay clave)
python3 scripts/build.py      # genera dist/
python3 -m http.server 8177 --directory dist
```

Abrí `http://localhost:8177`.

## Cómo publicarlo (gratis)

### Opción A — GitHub Pages (incluido)

1. Creá un repositorio y subí esta carpeta a la rama `main`.
2. En **Settings → Pages**, elegí *Source: GitHub Actions*.
3. En **Settings → Secrets and variables → Actions**, agregá `THE_SPORTSDB_KEY` (ver abajo).
4. El workflow `Actualizar datos y publicar` ya está activo y corre cada 30 minutos (`:00` y `:30` UTC): actualiza datos, rebuilds y publica en `gh-pages`.

### Opción B — Cloudflare Pages

- Build command: `python3 scripts/update.py && python3 scripts/build.py`
- Output directory: `dist`
- Programá un cron externo (Cloudflare Cron Trigger o un GitHub Action que dispare un deploy hook) para la actualización cada 30 minutos.

## Claves y fuentes

### Noticias
Se leen feeds RSS de:

- Millonarios FC (sitio oficial)
- ESPN Colombia
- Marca Colombia
- El Tiempo · Deportes

Solo se publican titulares y un resumen corto del feed, **siempre enlazando al artículo original**. No se copia el contenido completo.

> **Google News RSS no se usa** a propósito: sus términos limitan el feed a uso personal y no comercial. Si el sitio es público, esa fuente queda afuera.

### Próximo partido y calendario
`update.py` usa [TheSportsDB](https://www.thesportsdb.com/) para el próximo partido y las rondas. Si existe `THE_SPORTSDB_KEY`, la usa; si no, cae en la clave pública de prueba `123` (puede tener límite de peticiones). Sin respuesta, el script **no borra** el último `data/partido.json` ni el `data/calendario.json` bueno.

### Marcador en vivo
La página de partidos consulta la API pública de ESPN desde el navegador:

`https://site.web.api.espn.com/apis/site/v2/sports/soccer/col.1/summary?event={id}`

- Estado programado, en vivo y final.
- Goles y minuto cada 30 segundos mientras el partido está en juego.
- Si ESPN falla o no hay evento, se muestra un aviso y se mantiene el calendario.
- No hay backend ni base de datos: es `fetch` del lado del cliente.

### Alineación
No existe API gratuita de "XI probable" para la Liga BetPlay. El once es una **estimación editorial** basada en la convocatoria oficial; se edita a mano en `data/alineacion.json` y se marca como no confirmada en la página.

### Pronóstico
Modelo Poisson simple:

- Ataque/defensa de Millonarios como visitante en 2026 (`data/resultados.json`).
- Prior de local para el rival: 1.45 goles (supuesto explícito, no dato verificado).
- Se muestran los supuestos, la muestra y se aclara que no es consejo de apuestas.

## Editar contenido a mano

- **Partido**: `data/partido.json`
- **Calendario y resultados**: `data/calendario.json`
- **XI, convocados y bajas**: `data/alineacion.json`
- **Palmarés, cronología, ídolos**: `data/historia.json`
- **Preguntas de trivia**: `data/trivia.json`
- **Datos de forma**: `data/resultados.json`
- **Fuentes y aviso legal**: `data/site.json`

Después de editar: `python3 scripts/build.py`.

## Estructura

```
.
├── data/                  # datos editables y generados
├── scripts/
│   ├── update.py          # RSS + TheSportsDB
│   └── build.py           # generador estático (sin dependencias)
├── static/                # CSS, JS (incluye envivo.js) y favicon
├── dist/                  # salida generada (no editar)
└── .github/workflows/     # actualización + deploy
```

## Pendientes honestos

- [ ] Clave propia de TheSportsDB para producción.
- [ ] Resultados históricos completos para que el modelo tenga más muestra.
- [ ] Registro público de aciertos del pronóstico (requiere backend o JSON versionado).
- [ ] Dominio propio y analítica sin cookies si se quiere medir audiencia.
- [ ] Revisar permisos de marca antes de usar escudos oficiales: acá se usa un escudo genérico propio.

## Licencia y créditos

- Código: uso libre para el proyecto, con atribución.
- Contenido de Wikipedia: **CC BY-SA 4.0**, citado en las páginas correspondientes.
- Noticias: © de cada medio; se enlazan, no se copian.
- Datos deportivos: TheSportsDB (atribución requerida).
