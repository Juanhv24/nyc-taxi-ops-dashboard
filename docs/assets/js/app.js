// Punto de entrada: carga los datos, maneja las pestañas y el tema.
import * as calidad from './calidad.js';
import * as demanda from './demanda.js';
import * as integridad from './integridad.js';
import { fmt, redimensionar } from './util.js';

const PESTANAS = {
  demanda: { modulo: demanda, listo: false },
  integridad: { modulo: integridad, listo: false },
  calidad: { modulo: calidad, listo: false },
  metodologia: { modulo: null, listo: true },
};
let activa = 'demanda';

async function cargar(nombre) {
  const respuesta = await fetch(`data/${nombre}`);
  if (!respuesta.ok) throw new Error(`${nombre}: ${respuesta.status}`);
  return respuesta.json();
}

async function iniciar() {
  const estado = document.getElementById('estado');
  try {
    const [resumen, datosDemanda, datosAuditoria, datosCalidad, lecturas] = await Promise.all([
      cargar('resumen.json'), cargar('demanda.json'), cargar('auditoria.json'), cargar('calidad.json'),
      fetch('content/lecturas.md').then((r) => (r.ok ? r.text() : '')).catch(() => ''),
    ]);
    document.querySelectorAll('[data-kpi="viajes_originales"]').forEach((el) => {
      el.textContent = `${fmt.dec1(resumen.kpis.viajes_originales / 1e6)} millones`;
    });
    document.querySelectorAll('[data-kpi="viajes_base"]').forEach((el) => { el.textContent = fmt.entero(resumen.kpis.viajes_base); });
    document.querySelectorAll('[data-generado]').forEach((el) => { el.textContent = resumen.generado; });
    mostrarLecturas(lecturas);

    demanda.iniciar(datosDemanda);
    integridad.iniciar(datosAuditoria);
    calidad.iniciar(datosCalidad, resumen);
    estado.textContent = '';
    configurarPestanas();
    mostrar(location.hash.replace('#', '') in PESTANAS ? location.hash.replace('#', '') : 'demanda');
  } catch (error) {
    estado.classList.add('error');
    estado.textContent = `No fue posible cargar los datos (${error.message}). El tablero debe abrirse desde un servidor web (por ejemplo, uv run python -m http.server -d docs), no directamente como archivo`;
    console.error(error);
  }
}

// Las lecturas (interpretaciones) viven en content/lecturas.md, separadas por
// encabezados "## demanda", "## integridad" y "## calidad".
function mostrarLecturas(texto) {
  const secciones = {};
  let actual = null;
  for (const linea of texto.split(/\r?\n/)) {
    const m = linea.match(/^##\s+(\w+)/);
    if (m) { actual = m[1].toLowerCase(); secciones[actual] = []; continue; }
    if (actual && !linea.startsWith('<!--')) secciones[actual].push(linea);
  }
  for (const [clave, lineas] of Object.entries(secciones)) {
    const parrafos = lineas.join('\n').split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
    const aside = document.querySelector(`[data-lectura="${clave}"]`);
    if (!aside || parrafos.length === 0) continue;
    aside.replaceChildren(...parrafos.map((p) => {
      const el = document.createElement('p');
      // Solo se admite **negrita**; el resto se inserta como texto.
      p.split(/(\*\*[^*]+\*\*)/).forEach((trozo) => {
        if (trozo.startsWith('**') && trozo.endsWith('**')) {
          const b = document.createElement('strong'); b.textContent = trozo.slice(2, -2); el.appendChild(b);
        } else el.appendChild(document.createTextNode(trozo));
      });
      return el;
    }));
    aside.hidden = false;
  }
}

function configurarPestanas() {
  const botones = [...document.querySelectorAll('.pestanas [role="tab"]')];
  botones.forEach((b, i) => {
    b.addEventListener('click', () => mostrar(b.id.replace('tab-', '')));
    b.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      const siguiente = botones[(i + (e.key === 'ArrowRight' ? 1 : -1) + botones.length) % botones.length];
      siguiente.focus();
      mostrar(siguiente.id.replace('tab-', ''));
    });
  });
}

function mostrar(nombre) {
  activa = nombre;
  for (const clave of Object.keys(PESTANAS)) {
    const boton = document.getElementById(`tab-${clave}`);
    const panel = document.getElementById(`panel-${clave}`);
    const sel = clave === nombre;
    boton.setAttribute('aria-selected', String(sel));
    boton.tabIndex = sel ? 0 : -1;
    panel.hidden = !sel;
  }
  history.replaceState(null, '', `#${nombre}`);
  const p = PESTANAS[nombre];
  if (p.modulo) {
    // Se renderiza al mostrarse: ECharts necesita el contenedor visible para medirlo.
    p.modulo.render();
    p.listo = true;
    requestAnimationFrame(redimensionar);
  }
}

// Al cambiar el tema del sistema se vuelven a leer los tokens y se re-renderiza.
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  for (const p of Object.values(PESTANAS)) p.listo = false;
  mostrar(activa);
});

window.addEventListener('hashchange', () => {
  const nombre = location.hash.replace('#', '');
  if (nombre in PESTANAS && nombre !== activa) mostrar(nombre);
});

let espera;
window.addEventListener('resize', () => { clearTimeout(espera); espera = setTimeout(redimensionar, 120); });

document.addEventListener('DOMContentLoaded', iniciar);
