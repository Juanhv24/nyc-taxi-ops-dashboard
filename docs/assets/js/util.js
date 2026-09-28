// Utilidades compartidas: formato, tokens de color, tablas y tarjetas.

const nf0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmt = {
  entero: (v) => (v == null || Number.isNaN(v) ? '—' : nf0.format(v)),
  dec1: (v) => (v == null || Number.isNaN(v) ? '—' : nf1.format(v)),
  dec2: (v) => (v == null || Number.isNaN(v) ? '—' : nf2.format(v)),
  pct: (v, d = 1) => (v == null || Number.isNaN(v) ? '—' : `${({ 0: nf0, 1: nf1, 2: nf2 })[d].format(v)}%`),
  usd: (v) => (v == null || Number.isNaN(v) ? '—' : `$${nf0.format(v)}`),
  usd2: (v) => (v == null || Number.isNaN(v) ? '—' : `$${nf2.format(v)}`),
  compacto: (v) => {
    if (v == null || Number.isNaN(v)) return '—';
    const a = Math.abs(v);
    const corto = (x) => (Number.isInteger(+x.toFixed(1)) ? nf0.format(x) : nf1.format(x));
    if (a >= 1e6) return `${corto(v / 1e6)} M`;
    if (a >= 1e4) return `${corto(v / 1e3)} mil`;
    return nf0.format(v);
  },
  usdCompacto: (v) => (v == null || Number.isNaN(v) ? '—' : `$${fmt.compacto(v)}`),
};

// Lee los tokens CSS vigentes (cambian con el modo claro/oscuro).
export function tokens() {
  const s = getComputedStyle(document.documentElement);
  const v = (n) => s.getPropertyValue(n).trim();
  return {
    superficie: v('--superficie'),
    tinta: v('--tinta'),
    tinta2: v('--tinta-2'),
    eje: v('--eje'),
    reticula: v('--reticula'),
    lineaBase: v('--linea-base'),
    serie1: v('--serie-1'),
    serie2: v('--serie-2'),
    atenuado: v('--atenuado'),
    critico: v('--critico'),
    secuencial: ['--sec-100', '--sec-200', '--sec-300', '--sec-400', '--sec-500', '--sec-600', '--sec-700'].map(v),
    fuente: v('--fuente'),
  };
}

// Opciones comunes de ECharts: retícula tenue, ejes discretos, tooltip sobrio.
export function base(t) {
  return {
    animationDuration: 300,
    textStyle: { fontFamily: t.fuente, color: t.tinta2 },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      backgroundColor: t.superficie,
      borderColor: t.reticula,
      borderWidth: 1,
      textStyle: { color: t.tinta, fontSize: 12 },
      extraCssText: 'box-shadow:0 4px 14px rgba(0,0,0,.12);border-radius:8px;',
      confine: true,
    },
  };
}

// La fuente se declara en cada etiqueta de eje: así containLabel mide el texto
// con la misma fuente con la que se dibuja y no recorta etiquetas largas.
export function ejeValor(t, extra = {}) {
  const { axisLabel = {}, ...resto } = extra;
  return {
    type: 'value',
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: t.reticula, width: 1 } },
    ...resto,
    axisLabel: { color: t.eje, fontSize: 11, fontFamily: t.fuente, hideOverlap: true, ...axisLabel },
  };
}

export function ejeCategoria(t, datos, extra = {}) {
  const { axisLabel = {}, ...resto } = extra;
  return {
    type: 'category',
    data: datos,
    axisLine: { lineStyle: { color: t.lineaBase } },
    axisTick: { show: false },
    ...resto,
    axisLabel: { color: t.eje, fontSize: 11, fontFamily: t.fuente, ...axisLabel },
  };
}

// Fila de tooltip: valor destacado primero, etiqueta después, con un trazo de color.
export function filaTooltip(color, etiqueta, valor) {
  const clave = color ? `<span style="display:inline-block;width:12px;height:2px;background:${color};margin-right:6px;vertical-align:middle"></span>` : '';
  return `<div style="display:flex;justify-content:space-between;gap:16px;align-items:center">`
    + `<span style="color:inherit;opacity:.75">${clave}${escapar(etiqueta)}</span>`
    + `<strong>${escapar(valor)}</strong></div>`;
}

export function escapar(texto) {
  return String(texto)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

// Construye una tabla HTML con textContent (los datos nunca se inyectan como HTML).
export function tabla(contenedor, columnas, filas) {
  contenedor.replaceChildren();
  const t = document.createElement('table');
  const thead = t.createTHead().insertRow();
  for (const c of columnas) {
    const th = document.createElement('th');
    th.scope = 'col';
    th.textContent = c.titulo;
    if (c.num) th.className = 'num';
    thead.appendChild(th);
  }
  const tbody = t.createTBody();
  for (const f of filas) {
    const tr = tbody.insertRow();
    for (const c of columnas) {
      const td = tr.insertCell();
      const valor = typeof c.valor === 'function' ? c.valor(f) : f[c.valor];
      td.textContent = c.fmt ? c.fmt(valor) : (valor ?? '—');
      if (c.num) td.className = 'num';
    }
  }
  contenedor.appendChild(t);
}

// Registro de gráficos: permite redimensionar y re-renderizar al cambiar el tema.
const graficos = new Map();

export function grafico(tarjeta) {
  const lienzo = tarjeta.querySelector('.lienzo');
  let instancia = graficos.get(lienzo);
  if (!instancia) {
    instancia = echarts.init(lienzo, null, { renderer: 'canvas' });
    graficos.set(lienzo, instancia);
  }
  return instancia;
}

// Ancho máximo de las etiquetas del eje de categorías según el ancho del gráfico.
export function anchoEtiqueta(g, normal) {
  const w = g.getWidth();
  return w < 520 ? Math.round(w * 0.34) : normal;
}

export function redimensionar() {
  for (const g of graficos.values()) g.resize();
}

// Agrega el botón "Tabla" que alterna entre el gráfico y su versión tabular.
export function vistaTabla(tarjeta, columnas, filas) {
  const figcaption = tarjeta.querySelector('figcaption');
  let boton = figcaption.querySelector('.alternar-tabla');
  let envoltura = tarjeta.querySelector('.tabla-envoltura[data-vista-tabla]');
  const lienzo = tarjeta.querySelector('.lienzo');
  if (!boton) {
    boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'alternar-tabla';
    boton.textContent = 'Tabla';
    boton.setAttribute('aria-pressed', 'false');
    figcaption.appendChild(boton);
    envoltura = document.createElement('div');
    envoltura.className = 'tabla-envoltura';
    envoltura.dataset.vistaTabla = '';
    envoltura.hidden = true;
    tarjeta.appendChild(envoltura);
    boton.addEventListener('click', () => {
      const activo = boton.getAttribute('aria-pressed') !== 'true';
      boton.setAttribute('aria-pressed', String(activo));
      envoltura.hidden = !activo;
      lienzo.hidden = activo;
      if (!activo) redimensionar();
    });
  }
  tabla(envoltura, columnas, filas);
}

export function kpis(contenedor, items) {
  contenedor.replaceChildren();
  for (const it of items) {
    const div = document.createElement('div');
    div.className = 'kpi';
    const e = document.createElement('p'); e.className = 'etiqueta'; e.textContent = it.etiqueta;
    const v = document.createElement('p'); v.className = 'valor'; v.textContent = it.valor;
    div.append(e, v);
    if (it.nota) { const n = document.createElement('p'); n.className = 'nota'; n.textContent = it.nota; div.append(n); }
    contenedor.appendChild(div);
  }
}

export function descargarCSV(nombre, columnas, filas) {
  const celda = (v) => {
    const s = v == null ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  const lineas = [columnas.map((c) => celda(c.titulo)).join(',')];
  for (const f of filas) lineas.push(columnas.map((c) => celda(typeof c.valor === 'function' ? c.valor(f) : f[c.valor])).join(','));
  const blob = new Blob(['﻿' + lineas.join('\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: nombre });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Convierte el formato columnar {col: [..]} en una lista de objetos.
export function filas(columnar) {
  const cols = Object.keys(columnar);
  const n = columnar[cols[0]].length;
  const salida = new Array(n);
  for (let i = 0; i < n; i++) {
    const o = {};
    for (const c of cols) o[c] = columnar[c][i];
    salida[i] = o;
  }
  return salida;
}
