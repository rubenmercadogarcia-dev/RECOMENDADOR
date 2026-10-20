// RECOMENDADOR · lógica de la interfaz.
// Habla con Python a través de window.pywebview.api (ver app.py).

let api = null;
let sondeo = null;
let vistaActual = "perfil";
let bibliotecaSteam = [];
let carpetasCache = { pendientes: [], completados: [] };

const COLECCIONES = {
  pendientes: {
    titulo: "Pendientes",
    subtitulo: "Tu lista de juegos por jugar. Organízala en carpetas como quieras.",
    vacio: "No tienes juegos pendientes. Búscalos arriba o añádelos desde las recomendaciones.",
  },
  completados: {
    titulo: "Completados",
    subtitulo: "Los juegos que te has pasado. Cuentan como juegos que te gustan, salvo que les pongas otra nota.",
    vacio: "Aún no has marcado ningún juego como completado.",
  },
  platinos: {
    titulo: "Platinos",
    subtitulo: "Juegos completados al 100 %. Los platinos también aparecen en Completados.",
    vacio: "Aún no tienes ningún platino.",
  },
};

// ---------- Utilidades ----------

const $ = (selector) => document.querySelector(selector);

// Crea elementos sin usar innerHTML con datos externos (evita inyectar HTML)
function el(etiqueta, atributos = {}, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(atributos)) {
    if (clave === "clase") nodo.className = valor;
    else if (clave.startsWith("on")) nodo.addEventListener(clave.slice(2), valor);
    else if (valor !== false && valor != null) nodo.setAttribute(clave, valor);
  }
  for (const hijo of hijos.flat()) {
    if (hijo != null && hijo !== false) nodo.append(hijo instanceof Node ? hijo : String(hijo));
  }
  return nodo;
}

let temporizadorAviso = null;
function avisar(texto, esError = false) {
  const aviso = $("#aviso");
  aviso.textContent = texto;
  aviso.classList.toggle("error", esError);
  aviso.hidden = false;
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => (aviso.hidden = true), esError ? 5000 : 2600);
}

function iniciales(nombre) {
  return (nombre || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}

const CDN = ["https://shared.akamai.steamstatic.com/store_item_assets/steam/apps",
             "https://cdn.cloudflare.steamstatic.com/steam/apps"];

// Imagen que prueba varias direcciones en orden y, si fallan todas, muestra las iniciales
function imagenEnCadena(fuentes, nombre, clase) {
  const sinImagen = () => el("div", { clase: `${clase} sin-imagen` }, iniciales(nombre));
  if (!fuentes.length) return sinImagen();
  let intento = 0;
  const img = el("img", { clase: fuentes[0].clase ? `${clase} ${fuentes[0].clase}` : clase, alt: "", loading: "lazy", src: fuentes[0].url });
  img.addEventListener("error", () => {
    intento += 1;
    if (intento >= fuentes.length) { img.replaceWith(sinImagen()); return; }
    img.className = fuentes[intento].clase ? `${clase} ${fuentes[intento].clase}` : clase;
    img.src = fuentes[intento].url;
  });
  return img;
}

// Portada horizontal (tarjetas de biblioteca y recomendaciones)
function portada(appid, nombre) {
  const fuentes = appid > 0 ? CDN.map((b) => ({ url: `${b}/${appid}/header.jpg` })) : [];
  return imagenEnCadena(fuentes, nombre, "portada");
}

// Portada vertical, como en la biblioteca de Steam; si el juego no la tiene, usa la horizontal
function portadaVertical(appid, nombre) {
  const fuentes = appid > 0 ? [
    ...CDN.map((b) => ({ url: `${b}/${appid}/library_600x900.jpg` })),
    ...CDN.map((b) => ({ url: `${b}/${appid}/header.jpg`, clase: "horizontal" })),
  ] : [];
  return imagenEnCadena(fuentes, nombre, "");
}

const formatoHoras = (h) => (h >= 10 ? `${Math.round(h)} h` : `${h.toLocaleString("es-ES")} h`);
const formatoPrecio = (p) => (p == null ? "Precio no disponible" : p === 0 ? "Gratis"
  : p.toLocaleString("es-ES", { style: "currency", currency: "EUR" }));
const urlTienda = (appid) => `https://store.steampowered.com/app/${appid}`;

function abrir(url) { api.abrir_url(url); }

// ---------- Menú flotante de acciones (⋯) ----------

let menuAbierto = null;

function cerrarMenu() {
  if (!menuAbierto) return;
  menuAbierto.ancla.setAttribute("aria-expanded", "false");
  menuAbierto.nodo.remove();
  menuAbierto = null;
}

// items: {texto, accion, peligro, actual, deshabilitado} · {titulo} · {separador}
function abrirMenu(ancla, items) {
  const yaAbierto = menuAbierto?.ancla === ancla;
  cerrarMenu();
  if (yaAbierto) return;
  const nodo = el("div", { clase: "menu-flotante", role: "menu" }, ...items.filter(Boolean).map((it) => {
    if (it.separador) return el("hr");
    if (it.titulo) return el("p", { clase: "titulo-menu" }, it.titulo);
    return el("button", {
      type: "button", role: "menuitem",
      clase: [it.peligro ? "peligro" : "", it.actual ? "marca-actual" : ""].join(" ").trim() || null,
      disabled: it.deshabilitado ? "" : false,
      onclick: async (e) => {
        e.stopPropagation();
        if (it.confirmar && e.currentTarget.dataset.confirmar !== "1") {
          e.currentTarget.dataset.confirmar = "1";
          e.currentTarget.firstChild.textContent = it.confirmar;
          return;
        }
        cerrarMenu();
        await it.accion();
      },
    }, el("span", {}, it.texto), it.actual ? el("span", {}, "✓") : null);
  }));
  document.body.append(nodo);
  const r = ancla.getBoundingClientRect();
  const ancho = nodo.offsetWidth, alto = nodo.offsetHeight;
  // Los botones ⋯ abren el menú hacia la izquierda; los botones con texto, alineado con ellos
  const base = ancla.classList.contains("boton-menu") ? r.right - ancho : r.left;
  const izquierda = Math.min(Math.max(8, base), window.innerWidth - ancho - 8);
  const arriba = r.bottom + 6 + alto > window.innerHeight ? Math.max(8, r.top - alto - 6) : r.bottom + 6;
  nodo.style.left = `${izquierda}px`;
  nodo.style.top = `${arriba}px`;
  ancla.setAttribute("aria-expanded", "true");
  menuAbierto = { ancla, nodo, desde: performance.now() };
  nodo.querySelector("button:not(:disabled)")?.focus({ preventScroll: true });
}

function botonMenu(titulo, items) {
  const boton = el("button", {
    type: "button", clase: "boton-menu", title: titulo, "aria-label": titulo,
    "aria-haspopup": "menu", "aria-expanded": "false",
    onclick: async (e) => { e.stopPropagation(); abrirMenu(boton, await items()); },
  }, "⋯");
  return boton;
}

// ---------- Colecciones: acciones comunes ----------

async function refrescarCarpetas() {
  for (const seccion of ["pendientes", "completados"]) {
    carpetasCache[seccion] = (await api.coleccion(seccion)).carpetas;
  }
}

async function actualizarCuentas() {
  const totales = await api.colecciones_resumen();
  document.querySelectorAll("[data-cuenta]").forEach((s) => {
    const n = totales[s.dataset.cuenta];
    s.textContent = n ? n.toLocaleString("es-ES") : "";
  });
}

async function anadirA(seccion, juego, carpetaId = null) {
  const r = await api.anadir_a_coleccion(seccion, juego.appid, juego.nombre, carpetaId);
  if (!r.ok) return avisar(r.error, true), false;
  const carpeta = carpetasCache[seccion]?.find((c) => c.id === carpetaId);
  const destino = { pendientes: "pendientes", completados: "completados", platinos: "platinos" }[seccion];
  avisar(`«${juego.nombre}» añadido a ${destino}${carpeta ? ` · ${carpeta.nombre}` : ""}`);
  await actualizarCuentas();
  return true;
}

// Opciones "Añadir a colecciones" para un juego (bibliotecas y recomendaciones)
function itemsParaColecciones(juego, alTerminar = () => {}) {
  const items = [{ titulo: "Añadir a pendientes" }];
  items.push({ texto: "Sin carpeta", accion: async () => { if (await anadirA("pendientes", juego)) alTerminar("pendientes"); } });
  for (const c of carpetasCache.pendientes) {
    items.push({ texto: c.nombre, accion: async () => { if (await anadirA("pendientes", juego, c.id)) alTerminar("pendientes"); } });
  }
  items.push({ separador: true },
    { texto: "Marcar como completado", accion: async () => { if (await anadirA("completados", juego)) alTerminar("completados"); } },
    { texto: "Marcar como platino", accion: async () => { if (await anadirA("platinos", juego)) alTerminar("platinos"); } });
  return items;
}

// ---------- Estrellas ----------

// Componente de 5 estrellas. Pulsar la nota que ya tiene la quita.
function estrellas(juego, alCambiar) {
  const caja = el("div", { clase: "estrellas", role: "radiogroup", "aria-label": `Nota de ${juego.nombre}` });
  const pintar = () => caja.querySelectorAll(".estrella").forEach((b, i) =>
    b.classList.toggle("llena", juego.nota != null && i < juego.nota));
  for (let n = 1; n <= 5; n++) {
    caja.append(el("button", {
      type: "button", clase: "estrella", title: `${n} de 5`, "aria-label": `${n} estrellas`,
      onclick: async (e) => {
        e.stopPropagation();
        const nueva = juego.nota === n ? null : n;
        const anterior = juego.nota;
        juego.nota = nueva;
        pintar();
        const r = await api.puntuar(juego.appid, nueva, juego.nombre);
        if (!r.ok) { juego.nota = anterior; pintar(); return avisar(r.error, true); }
        if (alCambiar) alCambiar(nueva);
      },
      onmouseenter: () => {
        caja.classList.add("previa");
        caja.querySelectorAll(".estrella").forEach((b, i) => b.classList.toggle("encendida", i < n));
      },
    }, "★"));
  }
  caja.addEventListener("mouseleave", () => caja.classList.remove("previa"));
  pintar();
  return caja;
}

// Tarjeta horizontal de un juego de tus bibliotecas
function tarjetaJuego(j, { quitable = false, alQuitar = null } = {}) {
  const meta = [];
  if (j.en_steam) meta.push(j.horas > 0 ? formatoHoras(j.horas) : "Sin jugar");
  else if (!(j.appid > 0)) meta.push("Fuera de Steam");
  const tarjeta = el("article", { clase: "tarjeta" });
  const menu = botonMenu("Más acciones", async () => [
    ...itemsParaColecciones(j),
    j.appid > 0 ? { separador: true } : null,
    j.appid > 0 ? { texto: "Ver en Steam", accion: () => abrir(urlTienda(j.appid)) } : null,
    quitable ? { separador: true } : null,
    quitable ? {
      texto: "Quitar de la biblioteca manual", peligro: true,
      accion: async () => {
        await api.quitar_manual(j.appid);
        tarjeta.classList.add("saliendo");
        setTimeout(() => { tarjeta.remove(); if (alQuitar) alQuitar(); }, 250);
      },
    } : null,
  ]);
  tarjeta.append(
    portada(j.appid, j.nombre),
    el("div", { clase: "tarjeta-cuerpo" },
      el("p", { clase: "tarjeta-titulo" }, j.nombre),
      el("div", { clase: "tarjeta-meta" }, meta.join(" · ")),
      el("div", { clase: "tarjeta-pie" },
        estrellas(j),
        el("div", { clase: "derecha" },
          j.en_steam && j.en_manual ? el("span", { clase: "insignia", title: "También está en tu biblioteca manual" }, "Manual") : null,
          menu))));
  return tarjeta;
}

// ---------- Buscador reutilizable (biblioteca manual y colecciones) ----------

// opciones: { seccion, placeholder, alElegir(juego) -> Promise<bool>, alAnadirSinSteam(nombre) -> Promise<bool>, destino() -> texto }
function crearBuscador(contenedor, opciones) {
  const input = el("input", { placeholder: opciones.placeholder, spellcheck: "false", autocomplete: "off" });
  const lista = el("ul", { clase: "resultados", hidden: "" });
  const destino = el("p", { clase: "destino" });
  const formSinSteam = el("form", { clase: "fila-formulario", autocomplete: "off" },
    el("input", { name: "nombre", placeholder: "Nombre del juego", spellcheck: "false", required: "" }),
    el("button", { clase: "boton secundario", type: "submit" }, "Añadir"));
  contenedor.replaceChildren(
    el("div", { clase: "buscador" }, input, lista),
    destino,
    el("details", { clase: "sin-steam" },
      el("summary", {}, "¿No está en Steam? Añádelo solo con el nombre"),
      formSinSteam,
      el("small", { clase: "suave" }, "Sin portada ni etiquetas: cuenta menos para el recomendador, pero no te lo volverá a sugerir.")));

  const pintarDestino = () => {
    const texto = opciones.destino?.();
    destino.hidden = !texto;
    destino.replaceChildren("Se añadirá a ", el("strong", {}, texto || ""));
  };
  pintarDestino();

  let temporizador = null, numero = 0;
  const mensaje = (texto) => lista.replaceChildren(el("li", {}, el("span", { clase: "mensaje" }, texto)));

  async function buscar() {
    const texto = input.value.trim();
    if (texto.length < 2) { lista.hidden = true; return; }
    const actual = ++numero;
    lista.hidden = false;
    mensaje("Buscando…");
    const r = await api.buscar_juego(texto, opciones.seccion);
    if (actual !== numero) return;  // llegó una búsqueda más nueva
    if (!r.ok) return mensaje(r.error);
    if (!r.resultados.length) return mensaje("No aparece en Steam. Puedes añadirlo solo con el nombre, más abajo.");
    lista.replaceChildren(...r.resultados.map((j) => {
      const boton = el("button", {
        type: "button", clase: "boton secundario pequeno", disabled: j.anadido ? "" : false,
        onclick: async () => {
          boton.disabled = true;
          boton.textContent = "Añadiendo…";
          const ok = await opciones.alElegir(j);
          boton.textContent = ok ? "Añadido" : "Añadir";
          boton.disabled = ok;
        },
      }, j.anadido ? "Ya está" : "Añadir");
      return el("li", {},
        j.imagen ? el("img", { src: j.imagen, alt: "" }) : el("span", { clase: "sin-miniatura" }),
        el("span", {}, j.nombre), boton);
    }));
  }

  input.addEventListener("input", () => { clearTimeout(temporizador); temporizador = setTimeout(buscar, 350); });
  input.addEventListener("keydown", (e) => { if (e.key === "Escape") lista.hidden = true; });
  input.addEventListener("focus", () => { if (input.value.trim().length >= 2 && lista.childElementCount) lista.hidden = false; });
  formSinSteam.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (await opciones.alAnadirSinSteam(formSinSteam.nombre.value.trim())) formSinSteam.reset();
  });
  return { pintarDestino };
}

// ---------- Navegación ----------

function mostrarVista(nombre) {
  cerrarMenu();
  vistaActual = nombre;
  const seccion = COLECCIONES[nombre] ? "coleccion" : nombre;
  document.querySelectorAll(".vista").forEach((v) => (v.hidden = v.id !== `vista-${seccion}`));
  document.querySelectorAll(".menu-item").forEach((b) => b.classList.toggle("activo", b.dataset.vista === nombre));
  $(".contenido").scrollTop = 0;
  if (COLECCIONES[nombre]) return abrirColeccion(nombre);
  ({ perfil: cargarPerfil, steam: cargarSteam, manual: cargarManual,
     preguntas: cargarPreguntas, ajustes: cargarAjustes })[nombre]?.();
}

// ---------- Tareas largas (sincronizar / recomendar) ----------

function pintarProgreso(p, mensaje, barra) {
  mensaje.textContent = p.total ? `${p.mensaje} · ${p.actual} de ${p.total}` : p.mensaje;
  barra.parentElement.classList.toggle("indeterminada", !p.total);
  barra.style.width = p.total ? `${Math.round((p.actual / p.total) * 100)}%` : "";
}

function seguirTarea(alTerminar) {
  clearInterval(sondeo);
  bloquearBotones(true);
  $("#estado-tarea").hidden = false;
  sondeo = setInterval(async () => {
    const p = await api.progreso();
    pintarProgreso(p, $("#estado-mensaje"), $("#estado-barra"));
    if (p.tipo === "recomendar") pintarProgreso(p, $("#recomendaciones-mensaje"), $("#recomendaciones-barra"));
    if (!p.ocupado) {
      clearInterval(sondeo);
      $("#estado-tarea").hidden = true;
      bloquearBotones(false);
      alTerminar(p);
    }
  }, 400);
}

function bloquearBotones(bloquear) {
  $("#boton-sincronizar").disabled = bloquear;
  $("#boton-recomendar").disabled = bloquear;
}

async function sincronizar() {
  const r = await api.iniciar_sincronizacion();
  if (!r.ok) return avisar(r.error, true);
  seguirTarea((p) => {
    if (p.error) return avisar(`No se pudo sincronizar: ${p.error}`, true);
    avisar("Biblioteca de Steam sincronizada");
    if (vistaActual === "steam") cargarSteam();
    if (vistaActual === "perfil") cargarPerfil();
  });
}

async function recomendar() {
  const r = await api.iniciar_recomendacion();
  if (!r.ok) return avisar(r.error, true);
  $("#recomendaciones-vacio").hidden = true;
  $("#recomendaciones-lista").replaceChildren();
  $("#recomendaciones-progreso").hidden = false;
  seguirTarea((p) => {
    $("#recomendaciones-progreso").hidden = true;
    if (p.error) {
      $("#recomendaciones-vacio").hidden = false;
      return avisar(p.error, true);
    }
    pintarRecomendaciones(p.resultado || []);
  });
}

// ---------- Perfil ----------

async function cargarPerfil() {
  const p = await api.perfil();
  const vacio = p.total === 0 && p.completados === 0;
  $("#perfil-vacio").hidden = !vacio;
  $("#perfil-datos").hidden = vacio;
  if (vacio) return;

  const cifra = (valor, texto) => el("div", { clase: "cifra" }, el("strong", {}, valor.toLocaleString("es-ES")), el("span", {}, texto));
  $("#perfil-cifras").replaceChildren(
    cifra(p.total, "juegos en tus bibliotecas"),
    cifra(p.puntuados, "puntuados por ti"),
    cifra(p.completados, p.platinos ? `completados · ${p.platinos} platinos` : "completados"),
    cifra(p.horas_totales, "horas jugadas en Steam"),
  );

  const favoritos = $("#perfil-favoritos");
  favoritos.replaceChildren(...p.favoritos.slice(0, 10).map((j) => tarjetaJuego(j)));
  if (!p.favoritos.length) favoritos.append(el("p", { clase: "lista-vacia" }, "Puntúa juegos con 4 o 5 estrellas, márcalos como completados o juega más de 10 horas a alguno."));

  const etiquetas = $("#perfil-etiquetas");
  etiquetas.replaceChildren(...p.etiquetas.map((e) =>
    el("div", { clase: "etiqueta" }, el("span", { title: e.nombre }, e.nombre),
      el("div", { clase: "barra" }, el("div", { style: `width:${Math.max(4, e.peso * 100)}%` })))));
  if (!p.etiquetas.length) etiquetas.append(el("p", { clase: "lista-vacia" }, "Aún no hay suficientes datos."));

  const recientes = $("#perfil-recientes");
  recientes.replaceChildren(...p.recientes.map((j) => el("li", {}, el("span", {}, j.nombre), el("span", { clase: "suave" }, formatoHoras(j.horas)))));
  recientes.nextElementSibling?.remove();
  if (!p.recientes.length) recientes.after(el("p", { clase: "lista-vacia" }, "Nada en Steam en las últimas dos semanas."));
}

// ---------- Biblioteca de Steam ----------

async function cargarSteam() {
  const estado = await api.estado();
  $("#steam-desconectado").hidden = estado.steam_conectado;
  $("#steam-acciones").hidden = !estado.steam_conectado;
  $("#steam-recuento").hidden = !estado.steam_conectado;
  $("#steam-subtitulo").textContent = estado.steam_conectado
    ? "Tus juegos y horas, importados de tu cuenta. Puntúalos para afinar las recomendaciones."
    : "Importa automáticamente tus juegos y las horas que les has echado.";
  if (!estado.steam_conectado) { $("#steam-lista").replaceChildren(); return; }
  bibliotecaSteam = await api.biblioteca("steam");
  pintarSteam();
}

function pintarSteam() {
  const filtro = $("#steam-filtro").value.trim().toLowerCase();
  const visibles = bibliotecaSteam.filter((j) => j.nombre.toLowerCase().includes(filtro));
  const puntuados = bibliotecaSteam.filter((j) => j.nota).length;
  $("#steam-recuento").textContent = filtro
    ? `${visibles.length} de ${bibliotecaSteam.length} juegos`
    : `${bibliotecaSteam.length} juegos · ${puntuados} puntuados`;
  // Pintamos como mucho 300 para que la ventana vaya fluida con bibliotecas enormes
  $("#steam-lista").replaceChildren(...visibles.slice(0, 300).map((j) => tarjetaJuego(j)));
  if (visibles.length > 300) $("#steam-lista").append(el("p", { clase: "lista-vacia" }, "Usa el filtro para encontrar el resto."));
}

async function conectarSteam(evento) {
  evento.preventDefault();
  const f = evento.target;
  const boton = f.querySelector("button[type=submit]");
  const error = $("#error-steam");
  boton.disabled = true;
  boton.textContent = "Comprobando…";
  const r = await api.conectar_steam(f.steam_key.value, f.perfil.value);
  boton.disabled = false;
  boton.textContent = "Conectar y sincronizar";
  error.hidden = r.ok;
  if (!r.ok) { error.textContent = r.error; return; }
  f.reset();
  await cargarSteam();
  sincronizar();
}

// ---------- Biblioteca manual ----------

async function cargarManual() {
  const juegos = await api.biblioteca("manual");
  $("#manual-vacio").hidden = juegos.length > 0;
  $("#manual-recuento").hidden = juegos.length === 0;
  $("#manual-recuento").textContent = `${juegos.length} juegos · ${juegos.filter((j) => j.nota).length} puntuados`;
  $("#manual-lista").replaceChildren(...juegos.map((j) => tarjetaJuego(j, { quitable: true, alQuitar: cargarManual })));
}

function prepararBuscadorManual() {
  crearBuscador($("#manual-buscador"), {
    seccion: "manual",
    placeholder: "Busca un juego en Steam para añadirlo…",
    alElegir: async (j) => {
      await api.anadir_manual(j.appid, j.nombre, null);
      avisar(`«${j.nombre}» añadido. Puntúalo con las estrellas.`);
      cargarManual();
      return true;
    },
    alAnadirSinSteam: async (nombre) => {
      const r = await api.anadir_sin_steam(nombre, null);
      if (!r.ok) return avisar(r.error, true), false;
      avisar(`«${nombre}» añadido`);
      cargarManual();
      return true;
    },
  });
}

// ---------- Colecciones ----------

const estadoColeccion = { seccion: null, carpeta: "todas", datos: null, buscador: null };

function nombreCarpetaActual() {
  const { carpeta, datos } = estadoColeccion;
  if (!datos?.con_carpetas || carpeta === "todas" || carpeta === "sin") return "";
  return datos.carpetas.find((c) => c.id === carpeta)?.nombre || "";
}

function carpetaDestino() {
  const c = estadoColeccion.carpeta;
  return typeof c === "number" ? c : null;
}

async function abrirColeccion(seccion) {
  const cambio = estadoColeccion.seccion !== seccion;
  estadoColeccion.seccion = seccion;
  if (cambio) estadoColeccion.carpeta = "todas";
  const info = COLECCIONES[seccion];
  $("#coleccion-titulo").textContent = info.titulo;
  $("#coleccion-subtitulo").textContent = info.subtitulo;
  if (cambio || !estadoColeccion.buscador) {
    estadoColeccion.buscador = crearBuscador($("#coleccion-buscador"), {
      seccion,
      placeholder: `Busca un juego en Steam para añadirlo a ${info.titulo.toLowerCase()}…`,
      destino: () => {
        if (!estadoColeccion.datos?.con_carpetas) return "";
        return nombreCarpetaActual() ? `${info.titulo} · ${nombreCarpetaActual()}` : `${info.titulo} · sin carpeta`;
      },
      alElegir: async (j) => {
        const ok = await anadirA(seccion, j, carpetaDestino());
        if (ok) await cargarColeccion();
        return ok;
      },
      alAnadirSinSteam: async (nombre) => {
        const r = await api.anadir_sin_steam_a_coleccion(seccion, nombre, carpetaDestino());
        if (!r.ok) return avisar(r.error, true), false;
        avisar(`«${nombre}» añadido`);
        await actualizarCuentas();
        await cargarColeccion();
        return true;
      },
    });
  }
  await cargarColeccion();
}

async function cargarColeccion() {
  const { seccion } = estadoColeccion;
  const datos = await api.coleccion(seccion);
  estadoColeccion.datos = datos;
  if (datos.con_carpetas) carpetasCache[seccion] = datos.carpetas;
  // Si la carpeta seleccionada ya no existe, volvemos a "Todas"
  const c = estadoColeccion.carpeta;
  if (typeof c === "number" && !datos.carpetas.some((x) => x.id === c)) estadoColeccion.carpeta = "todas";
  pintarCarpetas();
  pintarColeccion();
  estadoColeccion.buscador?.pintarDestino();
}

function pintarCarpetas() {
  const { datos, carpeta } = estadoColeccion;
  const caja = $("#coleccion-carpetas");
  if (!datos.con_carpetas) { caja.replaceChildren(); return; }
  const sinCarpeta = datos.juegos.filter((j) => j.carpeta_id == null).length;
  const chip = (clave, texto, total) => el("button", {
    type: "button", clase: `chip${carpeta === clave ? " activo" : ""}`,
    onclick: () => { estadoColeccion.carpeta = clave; pintarCarpetas(); pintarColeccion(); estadoColeccion.buscador?.pintarDestino(); },
  }, texto, el("span", { clase: "cuenta" }, total));

  const chips = [chip("todas", "Todas", datos.juegos.length)];
  if (datos.carpetas.length) chips.push(chip("sin", "Sin carpeta", sinCarpeta));
  for (const c of datos.carpetas) chips.push(chip(c.id, c.nombre, c.total));

  const actual = datos.carpetas.find((c) => c.id === carpeta);
  if (actual) {
    chips.push(botonMenu(`Opciones de «${actual.nombre}»`, async () => [
      { texto: "Cambiar nombre", accion: () => editarCarpeta(actual) },
      { texto: "Borrar carpeta", peligro: true, confirmar: "Pulsa otra vez: los juegos no se borran",
        accion: async () => {
          const r = await api.borrar_carpeta(actual.id);
          if (!r.ok) return avisar(r.error, true);
          estadoColeccion.carpeta = "todas";
          avisar(`Carpeta «${actual.nombre}» borrada. Sus juegos siguen en la colección.`);
          cargarColeccion();
        } },
    ]));
  }
  chips.push(el("button", { type: "button", clase: "chip nueva", onclick: (e) => nuevaCarpeta(e.currentTarget) }, "+ Nueva carpeta"));
  caja.replaceChildren(...chips);
}

// Pide un nombre en línea (sin ventanas emergentes) y llama a guardar(nombre)
function pedirNombre(reemplazar, valorInicial, guardar) {
  const input = el("input", { clase: "chip-input", value: valorInicial, placeholder: "Nombre de la carpeta", spellcheck: "false" });
  let terminado = false;
  const terminar = async (aceptar) => {
    if (terminado) return;
    terminado = true;
    const nombre = input.value.trim();
    if (aceptar && nombre && nombre !== valorInicial) {
      const ok = await guardar(nombre);
      if (!ok) { terminado = false; input.focus(); return; }
    }
    pintarCarpetas();
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); terminar(true); }
    if (e.key === "Escape") terminar(false);
  });
  input.addEventListener("blur", () => terminar(true));
  reemplazar.replaceWith(input);
  input.focus();
  input.select();
}

function nuevaCarpeta(boton) {
  pedirNombre(boton, "", async (nombre) => {
    const r = await api.crear_carpeta(estadoColeccion.seccion, nombre);
    if (!r.ok) return avisar(r.error, true), false;
    estadoColeccion.carpeta = r.id;
    await cargarColeccion();
    avisar(`Carpeta «${nombre}» creada. Lo que añadas ahora irá aquí.`);
    return true;
  });
}

function editarCarpeta(carpeta) {
  const chip = [...document.querySelectorAll("#coleccion-carpetas .chip")].find((c) => c.classList.contains("activo"));
  if (!chip) return;
  pedirNombre(chip, carpeta.nombre, async (nombre) => {
    const r = await api.renombrar_carpeta(carpeta.id, nombre);
    if (!r.ok) return avisar(r.error, true), false;
    await cargarColeccion();
    return true;
  });
}

function pintarColeccion() {
  const { seccion, datos, carpeta } = estadoColeccion;
  let juegos = datos.juegos;
  if (carpeta === "sin") juegos = juegos.filter((j) => j.carpeta_id == null);
  else if (typeof carpeta === "number") juegos = juegos.filter((j) => j.carpeta_id === carpeta);

  const vacio = $("#coleccion-vacio");
  vacio.hidden = juegos.length > 0;
  vacio.replaceChildren(el("p", {}, datos.juegos.length && !juegos.length
    ? "Esta carpeta está vacía. Busca un juego arriba para añadirlo aquí."
    : COLECCIONES[seccion].vacio));
  const nombres = Object.fromEntries(datos.carpetas.map((c) => [c.id, c.nombre]));
  $("#coleccion-lista").replaceChildren(...juegos.map((j) => capsula(j, seccion, carpeta === "todas" ? nombres[j.carpeta_id] : null)));
}

function capsula(j, seccion, nombreCarpeta) {
  const nodo = el("article", { clase: "capsula" });
  const quitar = async (seccionAQuitar, mensaje) => {
    const r = await api.quitar_de_coleccion(seccionAQuitar, j.appid);
    if (!r.ok) return avisar(r.error, true);
    avisar(mensaje);
    await actualizarCuentas();
    if (seccionAQuitar === seccion) {
      nodo.classList.add("saliendo");
      setTimeout(cargarColeccion, 250);
    } else cargarColeccion();
  };

  const menu = botonMenu("Más acciones", async () => {
    const items = [];
    if (estadoColeccion.datos.con_carpetas) {
      items.push({ titulo: "Mover a carpeta" },
        { texto: "Sin carpeta", actual: j.carpeta_id == null, accion: () => mover(j, null) },
        ...estadoColeccion.datos.carpetas.map((c) => ({ texto: c.nombre, actual: j.carpeta_id === c.id, accion: () => mover(j, c.id) })),
        { separador: true });
    }
    if (seccion === "pendientes") {
      items.push({ texto: "Marcar como completado", accion: async () => {
        if (await anadirA("completados", j)) { nodo.classList.add("saliendo"); setTimeout(cargarColeccion, 250); }
      } });
    }
    if (seccion === "completados") {
      items.push(j.platino
        ? { texto: "Quitar platino", accion: () => quitar("platinos", `«${j.nombre}» ya no es platino`) }
        : { texto: "Marcar como platino", accion: async () => { if (await anadirA("platinos", j)) cargarColeccion(); } });
    }
    if (j.appid > 0) items.push({ texto: "Ver en Steam", accion: () => abrir(urlTienda(j.appid)) });
    items.push({ separador: true }, {
      texto: { pendientes: "Quitar de pendientes", completados: "Quitar de completados", platinos: "Quitar platino" }[seccion],
      peligro: true,
      accion: () => quitar(seccion, `«${j.nombre}» quitado de ${COLECCIONES[seccion].titulo.toLowerCase()}`),
    });
    return items;
  });

  const meta = [];
  if (nombreCarpeta) meta.push(nombreCarpeta);
  if (!(j.appid > 0)) meta.push("Fuera de Steam");
  // append() del navegador convertiría null en el texto "null": filtramos los huecos
  nodo.append(...[
    el("div", { clase: "capsula-imagen" },
      portadaVertical(j.appid, j.nombre),
      seccion === "completados" && j.platino ? el("span", { clase: "sello" }, "Platino") : null,
      menu),
    el("p", { clase: "capsula-titulo", title: j.nombre }, j.nombre),
    meta.length ? el("p", { clase: "capsula-meta" }, meta.join(" · ")) : null,
    seccion !== "pendientes" ? estrellas(j) : null,
  ].filter(Boolean));
  return nodo;
}

async function mover(j, carpetaId) {
  const r = await api.mover_a_carpeta(estadoColeccion.seccion, j.appid, carpetaId);
  if (!r.ok) return avisar(r.error, true);
  const destino = estadoColeccion.datos.carpetas.find((c) => c.id === carpetaId)?.nombre || "sin carpeta";
  avisar(`«${j.nombre}» movido a ${destino}`);
  cargarColeccion();
}

// ---------- Recomendaciones ----------

function pintarRecomendaciones(lista) {
  const contenedor = $("#recomendaciones-lista");
  if (!lista.length) {
    $("#recomendaciones-vacio").hidden = false;
    return avisar("No hay recomendaciones. Añade o puntúa más juegos, o cambia las preguntas.");
  }
  contenedor.replaceChildren(...lista.map((r) => {
    const meta = [formatoPrecio(r.precio), r.valoracion ? `${r.valoracion}% reseñas positivas` : null].filter(Boolean).join(" · ");
    const tarjeta = el("article", { clase: "tarjeta" });
    const salir = () => { tarjeta.classList.add("saliendo"); setTimeout(() => tarjeta.remove(), 250); };
    const pendiente = el("button", {
      type: "button", clase: "boton secundario pequeno", "aria-haspopup": "menu", "aria-expanded": "false",
      onclick: (e) => {
        e.stopPropagation();
        const juego = { appid: r.appid, nombre: r.nombre };
        const items = [{ titulo: "Añadir a pendientes" },
          { texto: "Sin carpeta", accion: async () => { if (await anadirA("pendientes", juego)) salir(); } },
          ...carpetasCache.pendientes.map((c) => ({ texto: c.nombre, accion: async () => { if (await anadirA("pendientes", juego, c.id)) salir(); } }))];
        abrirMenu(pendiente, items);
      },
    }, "Pendiente");
    tarjeta.append(
      portada(r.appid, r.nombre),
      el("div", { clase: "tarjeta-cuerpo" },
        el("p", { clase: "tarjeta-titulo" }, r.nombre),
        el("p", { clase: "tarjeta-meta" }, meta),
        el("p", { clase: "tarjeta-motivo" }, r.motivo),
        el("div", { clase: "tarjeta-acciones" },
          pendiente,
          el("button", { clase: "boton secundario pequeno", onclick: () => abrir(r.url) }, "Ver en Steam"),
          el("button", {
            clase: "boton fantasma pequeno",
            onclick: async () => {
              await api.descartar(r.appid, r.nombre);
              salir();
              avisar(`«${r.nombre}» no volverá a salir`);
            },
          }, "No me interesa"))));
    return tarjeta;
  }));
}

// ---------- Preguntas ----------

async function cargarPreguntas() {
  const preguntas = await api.preguntas();
  const form = $("#form-preguntas");
  form.replaceChildren(...preguntas.map((q) => {
    let control;
    if (q.opciones) {
      control = el("div", { clase: "opciones", "data-clave": q.clave },
        ...q.opciones.map((o) => el("button", {
          type: "button", clase: `opcion${o === q.valor ? " activo" : ""}`, "data-valor": o,
          onclick: (e) => {
            e.currentTarget.parentElement.querySelectorAll(".opcion").forEach((b) => b.classList.remove("activo"));
            e.currentTarget.classList.add("activo");
          },
        }, o)));
    } else {
      control = el("input", { "data-clave": q.clave, value: q.valor, spellcheck: "false" });
    }
    return el("div", { clase: "pregunta" }, el("p", {}, q.texto), control,
      q.ayuda ? el("small", { clase: "ayuda" }, q.ayuda) : null);
  }), el("div", {}, el("button", { clase: "boton primario", type: "submit" }, "Guardar respuestas")));
}

async function guardarPreguntas(evento) {
  evento.preventDefault();
  const respuestas = {};
  document.querySelectorAll("#form-preguntas [data-clave]").forEach((nodo) => {
    if (nodo.tagName === "INPUT") respuestas[nodo.dataset.clave] = nodo.value;
    else {
      const activa = nodo.querySelector(".opcion.activo");
      if (activa) respuestas[nodo.dataset.clave] = activa.dataset.valor;
    }
  });
  await api.guardar_preferencias(respuestas);
  avisar("Respuestas guardadas");
}

// ---------- Ajustes ----------

async function cargarAjustes() {
  const estado = await api.estado();
  const panel = $("#ajustes-steam");
  if (estado.steam_conectado) {
    panel.replaceChildren(
      el("p", {}, "Conectado · SteamID ", el("code", {}, estado.steamid)),
      el("p", { clase: "suave", style: "margin-top:6px" }, "Si desconectas, se borran la clave y los juegos importados de Steam. Lo que añadiste a mano y tus colecciones se quedan."),
      el("div", { clase: "fila-botones", style: "margin-top:16px" },
        el("button", { clase: "boton secundario", onclick: () => mostrarVista("steam") }, "Ir a la biblioteca"),
        el("button", {
          clase: "boton fantasma",
          onclick: async (e) => {
            const boton = e.currentTarget;
            if (boton.dataset.confirmar !== "1") {
              boton.dataset.confirmar = "1";
              boton.textContent = "Pulsa otra vez para confirmar";
              return;
            }
            await api.desconectar_steam();
            avisar("Steam desconectado");
            cargarAjustes();
          },
        }, "Desconectar Steam")));
  } else {
    panel.replaceChildren(
      el("p", {}, "No hay ninguna cuenta de Steam conectada."),
      el("div", { clase: "fila-botones", style: "margin-top:16px" },
        el("button", { clase: "boton primario", onclick: () => mostrarVista("steam") }, "Conectar Steam")));
  }

  const lista = await api.descartados();
  const ul = $("#lista-descartados");
  ul.replaceChildren(...lista.map((d) => el("li", {}, el("span", {}, d.nombre),
    el("button", {
      clase: "boton fantasma pequeno",
      onclick: async () => { await api.recuperar(d.appid); cargarAjustes(); avisar(`«${d.nombre}» puede volver a salir`); },
    }, "Recuperar"))));
  ul.nextElementSibling?.remove();
  if (!lista.length) ul.after(el("p", { clase: "lista-vacia" }, "No has descartado ningún juego."));
}

// ---------- Arranque ----------

async function arrancar() {
  api = window.pywebview.api;

  document.querySelectorAll("[data-url]").forEach((a) =>
    a.addEventListener("click", (e) => { e.preventDefault(); abrir(a.dataset.url); }));
  document.querySelectorAll("[data-ir]").forEach((b) => b.addEventListener("click", () => mostrarVista(b.dataset.ir)));
  document.querySelectorAll(".menu-item").forEach((b) => b.addEventListener("click", () => mostrarVista(b.dataset.vista)));
  $("#boton-sincronizar").addEventListener("click", sincronizar);
  $("#boton-recomendar").addEventListener("click", recomendar);
  $("#form-steam").addEventListener("submit", conectarSteam);
  $("#form-preguntas").addEventListener("submit", guardarPreguntas);
  $("#steam-filtro").addEventListener("input", pintarSteam);
  prepararBuscadorManual();

  // Cerrar menús y listas de resultados al pulsar fuera, con Escape o al hacer scroll
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".menu-flotante")) cerrarMenu();
    if (!e.target.closest(".buscador")) document.querySelectorAll(".resultados").forEach((l) => (l.hidden = true));
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarMenu(); });
  // Al hacer scroll se cierra el menú, salvo el scroll que llega justo al abrirlo
  $(".contenido").addEventListener("scroll", () => {
    if (menuAbierto && performance.now() - menuAbierto.desde > 250) cerrarMenu();
  }, { passive: true });
  window.addEventListener("resize", cerrarMenu);

  await Promise.all([refrescarCarpetas(), actualizarCuentas()]);
  mostrarVista("perfil");
  // Si quedó una tarea en marcha (por ejemplo, al recargar), seguimos su progreso
  const p = await api.progreso();
  if (p.ocupado) seguirTarea(() => mostrarVista(vistaActual));
}

window.addEventListener("pywebviewready", arrancar);
