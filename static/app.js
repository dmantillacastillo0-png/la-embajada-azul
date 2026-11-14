/* La Embajada Azul — interacciones sin dependencias */
(() => {
  "use strict";

  /* ---------- menú móvil ---------- */
  const botonNav = document.querySelector(".nav__boton");
  const nav = document.querySelector(".nav");
  if (botonNav && nav) {
    const alternar = (abrir) => {
      const abierto = abrir ?? !nav.classList.contains("is-open");
      nav.classList.toggle("is-open", abierto);
      botonNav.setAttribute("aria-expanded", String(abierto));
    };
    botonNav.addEventListener("click", () => alternar());
    nav.addEventListener("click", (ev) => {
      if (ev.target.closest("a")) alternar(false);
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") alternar(false);
    });
  }

  /* ---------- cuenta regresiva ---------- */
  const cuenta = document.querySelector("[data-cuenta]");
  if (cuenta) {
    const objetivo = new Date(cuenta.dataset.cuenta).getTime();
    const dias = cuenta.querySelector("[data-cuenta-dias]");
    const horas = cuenta.querySelector("[data-cuenta-horas]");
    const mins = cuenta.querySelector("[data-cuenta-min]");
    const segs = cuenta.querySelector("[data-cuenta-seg]");
    const pintar = () => {
      const diff = objetivo - Date.now();
      if (!Number.isFinite(objetivo) || diff <= 0) {
        [dias, horas, mins, segs].forEach((n) => { if (n) n.textContent = "0"; });
        return;
      }
      const s = Math.floor(diff / 1000);
      if (dias) dias.textContent = String(Math.floor(s / 86400));
      if (horas) horas.textContent = String(Math.floor((s % 86400) / 3600)).padStart(2, "0");
      if (mins) mins.textContent = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
      if (segs) segs.textContent = String(s % 60).padStart(2, "0");
    };
    pintar();
    setInterval(pintar, 1000);
  }

  /* ---------- noticias: búsqueda y filtros ---------- */
  const lista = document.getElementById("lista-noticias");
  if (lista) {
    const tarjetas = Array.from(lista.querySelectorAll(".noticia"));
    const buscador = document.getElementById("buscador-noticias");
    const filtros = Array.from(document.querySelectorAll(".filtro"));
    const conteo = document.getElementById("conteo-noticias");
    const vacio = document.getElementById("sin-resultados");
    let fuente = "todas";
    let texto = "";

    const aplicar = () => {
      let visibles = 0;
      tarjetas.forEach((t) => {
        const okFuente = fuente === "todas" || t.dataset.fuente === fuente || t.dataset.medio === fuente;
        const okTexto = !texto || (t.dataset.texto || "").includes(texto);
        const mostrar = okFuente && okTexto;
        t.hidden = !mostrar;
        if (mostrar) visibles += 1;
      });
      if (conteo) conteo.textContent = `${visibles} noticia${visibles === 1 ? "" : "s"} · se muestran resúmenes con enlace al original`;
      if (vacio) vacio.hidden = visibles !== 0;
    };

    filtros.forEach((f) => {
      f.addEventListener("click", () => {
        filtros.forEach((x) => x.classList.remove("is-active"));
        f.classList.add("is-active");
        fuente = f.dataset.filtro || "todas";
        aplicar();
      });
    });

    if (buscador) {
      buscador.addEventListener("input", () => {
        texto = buscador.value.trim().toLowerCase();
        aplicar();
      });
    }
    aplicar();
  }

  /* ---------- datos de juegos ---------- */
  let datos = null;
  const nodoDatos = document.getElementById("datos-juegos");
  if (nodoDatos) {
    try { datos = JSON.parse(nodoDatos.textContent); } catch (err) { console.error("Datos de juegos inválidos", err); }
  }

  /* ---------- etiquetas del partido en juegos ---------- */
  if (datos?.partido) {
    const partidoEl = document.getElementById("pick-partido");
    if (partidoEl) partidoEl.textContent = `${datos.partido.local} vs ${datos.partido.visitante}`;
    const localEl = document.getElementById("pick-local");
    const visitanteEl = document.getElementById("pick-visitante");
    if (localEl) localEl.textContent = datos.partido.local;
    if (visitanteEl) visitanteEl.textContent = datos.partido.visitante;
  }

  /* ---------- trivia ---------- */
  const triviaApp = document.getElementById("trivia-app");
  if (triviaApp && datos?.trivia?.length) {
    const preguntas = datos.trivia;
    const elProgreso = document.getElementById("trivia-progreso");
    const elPuntaje = document.getElementById("trivia-puntaje");
    const elPregunta = document.getElementById("trivia-pregunta");
    const elOpciones = document.getElementById("trivia-opciones");
    const elDato = document.getElementById("trivia-dato");
    const btnSiguiente = document.getElementById("trivia-siguiente");
    const btnReiniciar = document.getElementById("trivia-reiniciar");
    let indice = 0;
    let aciertos = 0;
    let respondida = false;

    const pintar = () => {
      respondida = false;
      const q = preguntas[indice];
      elProgreso.textContent = `Pregunta ${indice + 1} de ${preguntas.length}`;
      elPuntaje.textContent = `${aciertos} acierto${aciertos === 1 ? "" : "s"}`;
      elPregunta.textContent = q.p;
      elDato.hidden = true;
      elDato.textContent = "";
      btnSiguiente.disabled = true;
      btnSiguiente.textContent = indice === preguntas.length - 1 ? "Ver resultado" : "Siguiente";
      elOpciones.innerHTML = "";
      q.opciones.forEach((op, i) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "opcion";
        b.textContent = op;
        b.addEventListener("click", () => responder(i, b));
        elOpciones.appendChild(b);
      });
    };

    const responder = (i, boton) => {
      if (respondida) return;
      respondida = true;
      const q = preguntas[indice];
      const botones = Array.from(elOpciones.querySelectorAll(".opcion"));
      botones.forEach((b, j) => {
        b.disabled = true;
        if (j === q.correcta) b.classList.add("is-correcta");
        if (j === i && i !== q.correcta) b.classList.add("is-incorrecta");
      });
      if (i === q.correcta) aciertos += 1;
      elPuntaje.textContent = `${aciertos} acierto${aciertos === 1 ? "" : "s"}`;
      elDato.textContent = `${i === q.correcta ? "✅ Correcto. " : "❌ Casi. "}${q.dato}`;
      elDato.hidden = false;
      btnSiguiente.disabled = false;
    };

    btnSiguiente.addEventListener("click", () => {
      if (indice < preguntas.length - 1) {
        indice += 1;
        pintar();
      } else {
        elPregunta.textContent = `Terminaste: ${aciertos} de ${preguntas.length}`;
        elOpciones.innerHTML = "";
        elDato.hidden = true;
        elProgreso.textContent = "Fin de la trivia";
        btnSiguiente.hidden = true;
        btnReiniciar.hidden = false;
      }
    });

    btnReiniciar.addEventListener("click", () => {
      indice = 0;
      aciertos = 0;
      btnSiguiente.hidden = false;
      btnReiniciar.hidden = true;
      pintar();
    });

    pintar();
  }

  /* ---------- adivina el jugador ---------- */
  const adivinaApp = document.getElementById("adivina-app");
  if (adivinaApp && datos?.convocados) {
    const grupos = datos.convocados;
    const plantilla = new Map((datos.plantilla || []).map((j) => [j.nombre, j]));
    const pool = Object.entries(grupos).flatMap(([grupo, nombres]) =>
      nombres.map((nombre) => ({ nombre, grupo, ...(plantilla.get(nombre) || {}) }))
    );
    const elPista = document.getElementById("adivina-pista");
    const elOpciones = document.getElementById("adivina-opciones");
    const elEstado = document.getElementById("adivina-estado");
    const btnOtra = document.getElementById("adivina-otra");
    let ronda = 0;
    let resuelto = false;

    const barajar = (arr) => {
      const copia = arr.slice();
      for (let i = copia.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [copia[i], copia[j]] = [copia[j], copia[i]];
      }
      return copia;
    };

    const iniciales = (nombre) => nombre.split(" ").filter(Boolean).map((p) => p[0]).join(".") + ".";

    const nuevaRonda = () => {
      if (pool.length < 4) return;
      resuelto = false;
      ronda += 1;
      elEstado.textContent = "";
      btnOtra.hidden = true;
      const elegido = pool[Math.floor(Math.random() * pool.length)];
      const otros = barajar(pool.filter((j) => j.nombre !== elegido.nombre)).slice(0, 3);
      const opciones = barajar([elegido, ...otros]);
      const pistas = [
        `Juega en la línea de ${elegido.grupo.toLowerCase()}.`,
        `Sus iniciales son ${iniciales(elegido.nombre)}.`,
        elegido.num && elegido.num !== "—" ? `Usa el número ${elegido.num}.` : `Su apellido tiene ${elegido.nombre.split(" ").slice(-1)[0].length} letras.`,
      ];
      elPista.textContent = `${pistas[0]} ${pistas[1]} ${pistas[2]}`;
      elOpciones.innerHTML = "";
      opciones.forEach((j) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "opcion";
        b.textContent = j.nombre;
        b.addEventListener("click", () => {
          if (resuelto) return;
          resuelto = true;
          const botones = Array.from(elOpciones.querySelectorAll(".opcion"));
          botones.forEach((x) => {
            x.disabled = true;
            if (x.textContent === elegido.nombre) x.classList.add("is-correcta");
          });
          if (j.nombre === elegido.nombre) {
            elEstado.textContent = "✅ Ese era. Bien ahí.";
          } else {
            b.classList.add("is-incorrecta");
            elEstado.textContent = `❌ Era ${elegido.nombre}. Otra ronda, sin vergüenza.`;
          }
          btnOtra.hidden = false;
        });
        elOpciones.appendChild(b);
      });
    };

    btnOtra.addEventListener("click", nuevaRonda);
    nuevaRonda();
  }

  /* ---------- picks (localStorage) ---------- */
  const CLAVE_PICK = "ea_pick_2481264";
  const cajas = Array.from(document.querySelectorAll(".pick"));
  if (cajas.length) {
    const leer = () => {
      try { return JSON.parse(localStorage.getItem(CLAVE_PICK) || "null"); } catch { return null; }
    };
    const nombresDe = (caja) => ({
      local: caja.dataset.local || datos?.partido?.local || "Local",
      empate: "Empate",
      visitante: caja.dataset.visitante || datos?.partido?.visitante || "Visitante",
    });

    const pintarCaja = (caja) => {
      const guardado = leer();
      const nombres = nombresDe(caja);
      const estado = caja.querySelector('[id^="pick-estado"]');
      const botones = Array.from(caja.querySelectorAll("[data-pick]"));
      botones.forEach((b) => {
        const activo = guardado?.pick === b.dataset.pick;
        b.classList.toggle("is-active", Boolean(activo));
        b.setAttribute("aria-pressed", String(Boolean(activo)));
      });
      if (estado) {
        estado.textContent = guardado
          ? `Tu pick: ${nombres[guardado.pick] || guardado.pick}. Guardado en este navegador.`
          : "Todavía no elegiste. Sin presión.";
      }
    };

    cajas.forEach((caja) => {
      const botones = Array.from(caja.querySelectorAll("[data-pick]"));
      botones.forEach((b) => {
        b.addEventListener("click", () => {
          try {
            localStorage.setItem(CLAVE_PICK, JSON.stringify({ pick: b.dataset.pick, fecha: new Date().toISOString() }));
          } catch { /* modo privado: seguimos sin guardar */ }
          cajas.forEach(pintarCaja);
        });
      });
      const limpiar = caja.querySelector('[id^="pick-limpiar"]');
      if (limpiar) {
        limpiar.addEventListener("click", () => {
          try { localStorage.removeItem(CLAVE_PICK); } catch { /* nada */ }
          cajas.forEach(pintarCaja);
        });
      }
    });
    cajas.forEach(pintarCaja);
  }
})();
