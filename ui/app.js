// RECOMENDADOR · lógica de la interfaz.
// Habla con Python a través de window.pywebview.api (ver app.py).

let api = null;
let modo = "normal";
let tieneIA = false;
let sondeo = null;

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

function portada(appid, nombre) {
  const fuentes = [
    `https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/${appid}/header.jpg`,
    `https://cdn.cloudflare.steamstatic.com/steam/apps/${appid}/header.jpg`,
  ];
  const img = el("img", { clase: "portada", alt: "", loading: "lazy", src: fuentes[0] });
  img.addEventListener("error", () => {
    const siguiente = fuentes[fuentes.indexOf(img.src) + 1];
    if (siguiente) { img.src = siguiente; return; }
    const iniciales = (nombre || "?").split(/\s+/).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
    img.replaceWith(el("div", { clase: "portada sin-imagen" }, iniciales));
  });
  return img;
}

const formatoHoras = (h) => (h >= 10 ? `${Math.round(h)} h` : `${h.toLocaleString("es-ES")} h`);
const formatoPrecio = (p) => (p == null ? "Precio no disponible" : p === 0 ? "Gratis"
  : p.toLocaleString("es-ES", { style: "currency", currency: "EUR" }));

function abrir(url) { api.abrir_url(url); }

// ---------- Navegación ----------

function mostrarVista(nombre) {
  document.querySelectorAll(".vista").forEach((v) => (v.hidden = v.id !== `vista-${nombre}`));
  document.querySelectorAll(".menu-item").forEach((b) => b.classList.toggle("activo", b.dataset.vista === nombre));
  if (nombre === "perfil") cargarPerfil();
  if (nombre === "preguntas") cargarPreguntas();
  if (nombre === "ajustes") cargarAjustes();
}

// ---------- Tareas largas (sincronizar / recomendar) ----------

function pintarProgreso(p, mensaje, barra) {
  mensaje.textContent = p.total ? `${p.mensaje} · ${p.actual} de ${p.total}` : p.mensaje;
  const contenedor = barra.parentElement;
  contenedor.classList.toggle("indeterminada", !p.total);
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
    avisar("Biblioteca sincronizada");
    if (!$("#vista-perfil").hidden) cargarPerfil();
  });
}

async function recomendar() {
  const r = await api.iniciar_recomendacion(modo);
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
  const vacio = p.total === 0;
  $("#perfil-vacio").hidden = !vacio;
  $("#perfil-datos").hidden = vacio;
  if (vacio) return;

  const cifra = (valor, texto) => el("div", { clase: "cifra" }, el("strong", {}, valor.toLocaleString("es-ES")), el("span", {}, texto));
  $("#perfil-cifras").replaceChildren(
    cifra(p.total, "juegos en tu biblioteca"),
    cifra(p.horas_totales, "horas jugadas"),
    cifra(p.abandonados, "probados y dejados"),
    cifra(p.sin_jugar, "sin estrenar"),
  );

  $("#perfil-favoritos").replaceChildren(...p.favoritos.slice(0, 10).map((j) =>
    el("article", { clase: "tarjeta" }, portada(j.appid, j.nombre),
      el("div", { clase: "tarjeta-cuerpo" },
        el("p", { clase: "tarjeta-titulo" }, j.nombre),
        el("p", { clase: "tarjeta-meta" }, formatoHoras(j.horas))))));
  if (!p.favoritos.length) $("#perfil-favoritos").append(el("p", { clase: "lista-vacia" }, "Aún no hay juegos con más de 10 horas."));

  $("#perfil-etiquetas").replaceChildren(...p.etiquetas.map((e) =>
    el("div", { clase: "etiqueta" }, el("span", { title: e.nombre }, e.nombre),
      el("div", { clase: "barra" }, el("div", { style: `width:${Math.max(4, e.peso * 100)}%` })))));

  const recientes = $("#perfil-recientes");
  recientes.replaceChildren(...p.recientes.map((j) => el("li", {}, el("span", {}, j.nombre), el("span", { clase: "suave" }, formatoHoras(j.horas)))));
  recientes.nextElementSibling?.remove();
  if (!p.recientes.length) recientes.after(el("p", { clase: "lista-vacia" }, "Nada en las últimas dos semanas."));
}

// ---------- Recomendaciones ----------

function pintarRecomendaciones(lista) {
  const contenedor = $("#recomendaciones-lista");
  if (!lista.length) {
    $("#recomendaciones-vacio").hidden = false;
    return avisar("No hay recomendaciones esta vez. Prueba a cambiar las preguntas o el modo.");
  }
  contenedor.replaceChildren(...lista.map((r) => {
    const meta = [formatoPrecio(r.precio), r.valoracion ? `${r.valoracion}% reseñas positivas` : null].filter(Boolean).join(" · ");
    const tarjeta = el("article", { clase: "tarjeta" },
      portada(r.appid, r.nombre),
      el("div", { clase: "tarjeta-cuerpo" },
        el("p", { clase: "tarjeta-titulo" }, r.nombre),
        el("p", { clase: "tarjeta-meta" }, meta),
        el("p", { clase: "tarjeta-motivo" }, r.motivo),
        el("div", { clase: "tarjeta-acciones" },
          el("button", { clase: "boton secundario pequeno", onclick: () => abrir(r.url) }, "Ver en Steam"),
          el("button", {
            clase: "boton fantasma pequeno",
            onclick: async () => {
              await api.descartar(r.appid, r.nombre);
              tarjeta.classList.add("saliendo");
              setTimeout(() => tarjeta.remove(), 250);
              avisar(`«${r.nombre}» no volverá a salir`);
            },
          }, "No me interesa"))));
    return tarjeta;
  }));
}

function elegirModo(nuevo) {
  modo = nuevo;
  document.querySelectorAll(".selector-opcion").forEach((b) => {
    const activo = b.dataset.modo === nuevo;
    b.classList.toggle("activo", activo);
    b.setAttribute("aria-checked", activo);
  });
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
  $("#ajustes-perfil").placeholder = estado.steamid ? `SteamID ${estado.steamid}` : "URL del perfil, nombre o SteamID64";
  $("#ajustes-ia").placeholder = estado.tiene_ia ? "Guardada · escribe para cambiarla" : "Opcional, para el modo IA";
  $("#boton-quitar-ia").hidden = !estado.tiene_ia;
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

async function guardarAjustes(evento) {
  evento.preventDefault();
  const f = evento.target;
  const error = $("#error-ajustes");
  const r = await api.guardar_config(f.steam_key.value, f.perfil.value, f.anthropic_key.value);
  error.hidden = r.ok;
  if (!r.ok) { error.textContent = r.error; return; }
  f.reset();
  await actualizarIA();
  cargarAjustes();
  avisar("Ajustes guardados");
}

async function actualizarIA() {
  tieneIA = (await api.estado()).tiene_ia;
  const botonIA = document.querySelector('.selector-opcion[data-modo="ia"]');
  botonIA.disabled = !tieneIA;
  botonIA.title = tieneIA ? "" : "Añade tu API key de Anthropic en Ajustes";
  if (!tieneIA && modo === "ia") elegirModo("normal");
}

// ---------- Arranque ----------

async function configuracionInicial(evento) {
  evento.preventDefault();
  const f = evento.target;
  const boton = f.querySelector("button[type=submit]");
  const error = $("#error-inicio");
  boton.disabled = true;
  boton.textContent = "Comprobando…";
  const r = await api.guardar_config(f.steam_key.value, f.perfil.value, f.anthropic_key.value);
  boton.disabled = false;
  boton.textContent = "Conectar y sincronizar";
  error.hidden = r.ok;
  if (!r.ok) { error.textContent = r.error; return; }
  await entrar();
  sincronizar();
}

async function entrar() {
  $("#pantalla-inicio").hidden = true;
  $("#aplicacion").hidden = false;
  await actualizarIA();
  mostrarVista("perfil");
}

async function arrancar() {
  api = window.pywebview.api;

  document.querySelectorAll("[data-url]").forEach((a) =>
    a.addEventListener("click", (e) => { e.preventDefault(); abrir(a.dataset.url); }));
  document.querySelectorAll(".menu-item").forEach((b) => b.addEventListener("click", () => mostrarVista(b.dataset.vista)));
  document.querySelectorAll(".selector-opcion").forEach((b) => b.addEventListener("click", () => elegirModo(b.dataset.modo)));
  $("#boton-sincronizar").addEventListener("click", sincronizar);
  $("#boton-recomendar").addEventListener("click", recomendar);
  $("#form-inicio").addEventListener("submit", configuracionInicial);
  $("#form-preguntas").addEventListener("submit", guardarPreguntas);
  $("#form-ajustes").addEventListener("submit", guardarAjustes);
  $("#boton-quitar-ia").addEventListener("click", async () => {
    await api.borrar_clave_ia(); await actualizarIA(); cargarAjustes(); avisar("Clave de IA eliminada");
  });

  const estado = await api.estado();
  if (!estado.configurado) {
    $("#pantalla-inicio").hidden = false;
    return;
  }
  await entrar();
  // Si quedó una tarea en marcha (por ejemplo, al recargar), seguimos su progreso
  const p = await api.progreso();
  if (p.ocupado) seguirTarea(() => cargarPerfil());
  else if (!estado.sincronizado) sincronizar();
}

window.addEventListener("pywebviewready", arrancar);
