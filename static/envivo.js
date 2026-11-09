/* Marcador en vivo desde la API pública de ESPN. Sin dependencias. */
(() => {
  "use strict";

  const paneles = Array.from(document.querySelectorAll("[data-en-vivo]"));
  if (!paneles.length) return;

  const API = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/col.1/summary?event=";
  const porEvento = new Map();
  paneles.forEach((panel) => {
    const id = panel.dataset.evento;
    if (!id) return;
    if (!porEvento.has(id)) porEvento.set(id, []);
    porEvento.get(id).push(panel);
  });
  if (!porEvento.size) return;

  const cuenta = document.querySelector("[data-cuenta]");

  const texto = (nodo, valor) => {
    if (nodo) nodo.textContent = valor;
  };

  const pintar = (panel, data) => {
    const comp = data?.header?.competitions?.[0];
    if (!comp) throw new Error("Respuesta de ESPN sin competencia");

    const estado = comp.status?.type || {};
    const state = estado.state || "pre";
    const competidores = comp.competitors || [];
    const home = competidores.find((c) => c.homeAway === "home");
    const away = competidores.find((c) => c.homeAway === "away");
    const localEsHome = panel.dataset.localEsHome !== "false";
    const local = localEsHome ? home : away;
    const visitante = localEsHome ? away : home;
    const marcador = (c) => (c && c.score != null ? String(c.score) : "–");
    const cuando = panel.dataset.cuando || "Programado";

    panel.classList.toggle("is-vivo", state === "in");
    panel.classList.toggle("is-final", state === "post");
    panel.classList.toggle("is-programado", state === "pre");

    const chip = panel.querySelector("[data-envivo-chip]");
    const reloj = panel.querySelector("[data-envivo-reloj]");
    const elLocal = panel.querySelector("[data-envivo-local]");
    const elVisitante = panel.querySelector("[data-envivo-visitante]");
    const elEstado = panel.querySelector("[data-envivo-estado]");

    texto(chip, state === "in" ? "En vivo" : state === "post" ? "Final" : "Programado");
    if (reloj) {
      if (state === "in") {
        reloj.textContent = estado.description === "Halftime"
          ? "ET"
          : (comp.status?.displayClock || "");
      } else if (state === "post") {
        reloj.textContent = "90'";
      } else {
        reloj.textContent = "";
      }
    }
    texto(elLocal, marcador(local));
    texto(elVisitante, marcador(visitante));
    if (elEstado) {
      if (state === "in") {
        elEstado.textContent = estado.description === "Halftime"
          ? "Entretiempo"
          : (comp.status?.period === 2 ? "Segundo tiempo" : "Primer tiempo");
      } else if (state === "post") {
        elEstado.textContent = "Finalizado";
      } else {
        elEstado.textContent = cuando;
      }
    }

    if (panel.dataset.soloVivo === "true") {
      const mostrar = state !== "pre";
      panel.hidden = !mostrar;
      if (cuenta) cuenta.hidden = mostrar;
    } else {
      panel.hidden = false;
    }
    return state;
  };

  const fallo = (panel) => {
    if (panel.dataset.soloVivo === "true") return;
    panel.hidden = false;
    const chip = panel.querySelector("[data-envivo-chip]");
    const estado = panel.querySelector("[data-envivo-estado]");
    texto(chip, "Sin datos");
    texto(estado, "No se pudo consultar ESPN. El calendario y las fuentes siguen disponibles.");
  };

  let temporizador = null;
  let cargando = false;

  const programar = (ms) => {
    clearTimeout(temporizador);
    temporizador = setTimeout(cargarTodo, ms);
  };

  const cargar = async (id, grupo) => {
    try {
      const resp = await fetch(API + encodeURIComponent(id), { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      const estados = grupo.map((panel) => pintar(panel, data));
      if (estados.includes("in")) return "in";
      if (estados.includes("pre")) return "pre";
      return "post";
    } catch (err) {
      grupo.forEach(fallo);
      return "error";
    }
  };

  const cargarTodo = async () => {
    if (cargando || document.hidden) return;
    cargando = true;
    const estados = await Promise.all(
      Array.from(porEvento.entries()).map(([id, grupo]) => cargar(id, grupo))
    );
    cargando = false;
    if (estados.includes("in")) programar(30000);
    else if (estados.includes("pre")) programar(60000);
    else if (estados.includes("error")) programar(120000);
  };

  cargarTodo();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) cargarTodo();
  });
})();
