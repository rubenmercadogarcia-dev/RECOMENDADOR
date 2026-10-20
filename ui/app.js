// RECOMENDADOR · lógica de la interfaz.
// Habla con Python a través de window.pywebview.api (ver app.py).

let api = null;
let sondeo = null;
let vistaActual = "perfil";
let bibliotecaSteam = [];

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

function portada(appid, nombre) {
  const sinImagen = () => el("div", { clase: "portada sin-imagen" }, iniciales(nombre));
  if (!(appid > 0)) return sinImagen();  // juegos fuera de Steam
  const fuentes = [
    `https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/${appid}/header.jpg`,
    `https://cdn.cloudflare.steamstatic.com/steam/apps/${appid}/header.jpg`,
  ];
  let intento = 0;
  const img = el("img", { clase: "portada", alt: "", loading: "lazy", src: fuentes[0] });
  img.addEventListener("error", () => {
    intento += 1;
    if (intento < fuentes.length) img.src = fuentes[intento];
    else img.replaceWith(sinImagen());
  });
  return img;
}

const formatoHoras = (h) => (h >= 10 ? `${Math.round(h)} h` : `${h.toLocaleString("es-ES")} h`);
const formatoPrecio = (p) => (p == null ? "Precio no disponible" : p === 0 ? "Gratis"
  : p.toLocaleString("es-ES", { style: "currency", currency: "EUR" }));

function abrir(url) { api.abrir_url(url); }

// ---------- Estrellas ----------

// Componente de 5 estrellas. Pulsar la nota que ya tiene la quita.
function estrellas(juego, alCambiar) {
  const caja = el("div", { clase: "estrellas", role: "radiogroup", "aria-label": `Nota de ${juego.nombre}` });
  const pintar = () => caja.querySelectorAll(".estrella").forEach((b, i) =>
    b.classList.toggle("llena", juego.nota != null && i < juego.nota));
  for (let n = 1; n <= 5; n++) {
    const boton = el("button", {
      type: "button", clase: "estrella", title: `${n} de 5`, "aria-label": `${n} estrellas`,
      onclick: async () => {
        const nueva = juego.nota === n ? null : n;
        const anterior = juego.nota;
        juego.nota = nueva;
        pintar();
        const r = await api.puntuar(juego.appid, nueva);
        if (!r.ok) { juego.nota = anterior; pintar(); return avisar(r.error, true); }
        if (alCambiar) alCambiar(nueva);
      },
      onmouseenter: () => {
        caja.classList.add("previa");
        caja.querySelectorAll(".estrella").forEach((b, i) => b.classList.toggle("encendida", i < n));
      },
    }, "★");
    caja.append(boton);
  }
  caja.addEventListener("mouseleave", () => caja.classList.remove("previa"));
  pintar();
  return caja;
}

// Tarjeta de un juego de tu biblioteca
function tarjetaJuego(j, { quitable = false, alQuitar = null } = {}) {
  const meta = [];
  if (j.en_steam) meta.push(j.horas > 0 ? formatoHoras(j.horas) : "Sin jugar");
  else if (!(j.appid > 0)) meta.push("Fuera de Steam");
  const insignias = el("div", { clase: "insignias" },
    j.en_steam && j.en_manual ? el("span", { clase: "insignia", title: "También está en tu biblioteca manual" }, "Manual") : null);
  const tarjeta = el("article", { clase: "tarjeta" },
    portada(j.appid, j.nombre),
    el("div", { clase: "tarjeta-cuerpo" },
      el("p", { clase: "tarjeta-titulo" }, j.nombre),
      el("div", { clase: "tarjeta-meta" }, meta.join(" · ")),
      el("div", { clase: "tarjeta-pie" },
        estrellas(j),
        quitable
          ? el("button", {
            clase: "boton-icono", title: "Quitar de la biblioteca manual",
            onclick: async () => {
              await api.quitar_manual(j.appid);
              tarjeta.classList.add("saliendo");
              setTimeout(() => { tarjeta.remove(); if (alQuitar) alQuitar(); }, 250);
            },
          }, "Quitar")
          : insignias)));
  return tarjeta;
}

// ---------- Navegación ----------

function mostrarVista(nombre) {
  vistaActual = nombre;
  document.querySelectorAll(".vista").forEach((v) => (v.hidden = v.id !== `vista-${nombre}`));
  document.querySelectorAll(".menu-item").forEach((b) => b.classList.toggle("activo", b.dataset.vista === nombre));
  $(".contenido").scrollTop = 0;
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
  const vacio = p.total === 0;
  $("#perfil-vacio").hidden = !vacio;
  $("#perfil-datos").hidden = vacio;
  if (vacio) return;

  const cifra = (valor, texto) => el("div", { clase: "cifra" }, el("strong", {}, valor.toLocaleString("es-ES")), el("span", {}, texto));
  $("#perfil-cifras").replaceChildren(
    cifra(p.total, "juegos en tus bibliotecas"),
    cifra(p.puntuados, "puntuados por ti"),
    cifra(p.horas_totales, "horas jugadas en Steam"),
    cifra(p.abandonados, "dejados o mal puntuados"),
  );

  const favoritos = $("#perfil-favoritos");
  favoritos.replaceChildren(...p.favoritos.slice(0, 10).map((j) => tarjetaJuego(j)));
  if (!p.favoritos.length) favoritos.append(el("p", { clase: "lista-vacia" }, "Puntúa juegos con 4 o 5 estrellas, o juega más de 10 horas a alguno."));

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

let temporizadorBusqueda = null;
let busquedaActual = 0;
function buscarConEspera() {
  clearTimeout(temporizadorBusqueda);
  temporizadorBusqueda = setTimeout(buscar, 350);
}

async function buscar() {
  const texto = $("#buscador").value.trim();
  const lista = $("#resultados");
  if (texto.length < 2) { lista.hidden = true; return; }
  const numero = ++busquedaActual;
  lista.hidden = false;
  lista.replaceChildren(el("li", {}, el("span", { clase: "mensaje" }, "Buscando…")));
  const r = await api.buscar_juego(texto);
  if (numero !== busquedaActual) return;  // llegó una búsqueda más nueva
  if (!r.ok) { lista.replaceChildren(el("li", {}, el("span", { clase: "mensaje" }, r.error))); return; }
  if (!r.resultados.length) {
    lista.replaceChildren(el("li", {}, el("span", { clase: "mensaje" },
      "No aparece en Steam. Puedes añadirlo solo con el nombre, más abajo.")));
    return;
  }
  lista.replaceChildren(...r.resultados.map((j) => {
    const boton = el("button", {
      type: "button", clase: "boton secundario pequeno", disabled: j.anadido ? "" : false,
      onclick: async () => {
        boton.disabled = true;
        boton.textContent = "Añadiendo…";
        await api.anadir_manual(j.appid, j.nombre, null);
        boton.textContent = "Añadido";
        avisar(`«${j.nombre}» añadido. Puntúalo con las estrellas.`);
        cargarManual();
      },
    }, j.anadido ? "Añadido" : "Añadir");
    return el("li", {},
      j.imagen ? el("img", { src: j.imagen, alt: "" }) : el("span", { clase: "sin-miniatura" }),
      el("span", {}, j.nombre), boton);
  }));
}

async function anadirSinSteam(evento) {
  evento.preventDefault();
  const r = await api.anadir_sin_steam(evento.target.nombre.value, null);
  if (!r.ok) return avisar(r.error, true);
  avisar(`«${evento.target.nombre.value.trim()}» añadido`);
  evento.target.reset();
  cargarManual();
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
      el("p", { clase: "suave", style: "margin-top:6px" }, "Si desconectas, se borran la clave y los juegos importados de Steam. Lo que añadiste a mano se queda."),
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
  $("#form-sin-steam").addEventListener("submit", anadirSinSteam);
  $("#form-preguntas").addEventListener("submit", guardarPreguntas);
  $("#steam-filtro").addEventListener("input", pintarSteam);
  $("#buscador").addEventListener("input", buscarConEspera);
  $("#buscador").addEventListener("keydown", (e) => { if (e.key === "Escape") $("#resultados").hidden = true; });
  document.addEventListener("click", (e) => { if (!e.target.closest(".buscador")) $("#resultados").hidden = true; });

  mostrarVista("perfil");
  // Si quedó una tarea en marcha (por ejemplo, al recargar), seguimos su progreso
  const p = await api.progreso();
  if (p.ocupado) seguirTarea(() => mostrarVista(vistaActual));
}

window.addEventListener("pywebviewready", arrancar);
