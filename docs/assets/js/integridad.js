// Pestaña "Integridad tarifaria": reglas de auditoría, proveedores y casos.
import {
  anchoEtiqueta, base, descargarCSV, ejeCategoria, ejeValor, escapar, filaTooltip, filas, fmt, grafico, kpis, tabla,
  tokens, vistaTabla,
} from './util.js';

let A;
let casos;

// Vista en pantalla: compacta. La descarga CSV incluye todas las columnas.
const COLUMNAS_CASOS = [
  { titulo: 'Regla', valor: 'regla' },
  { titulo: 'Recogida', valor: 'recogida' },
  { titulo: 'Proveedor', valor: (c) => (c.proveedor === 'Creative Mobile Technologies' ? 'CMT' : c.proveedor) },
  { titulo: 'Pago', valor: 'forma_pago' },
  { titulo: 'Origen → destino', valor: (c) => `${c.origen} → ${c.destino}` },
  { titulo: 'Millas', valor: 'millas', num: true, fmt: fmt.dec2 },
  { titulo: 'Minutos', valor: 'minutos', num: true, fmt: fmt.dec1 },
  { titulo: 'Tarifa', valor: 'tarifa', num: true, fmt: fmt.usd2 },
  { titulo: 'Referencia', valor: 'referencia' },
  { titulo: 'Impacto', valor: 'impacto', num: true, fmt: fmt.usd2 },
];

const COLUMNAS_CSV = [
  { titulo: 'regla', valor: 'regla' },
  { titulo: 'recogida', valor: 'recogida' },
  { titulo: 'proveedor', valor: 'proveedor' },
  { titulo: 'codigo_tarifa', valor: 'codigo_tarifa' },
  { titulo: 'forma_pago', valor: 'forma_pago' },
  { titulo: 'origen', valor: 'origen' },
  { titulo: 'destino', valor: 'destino' },
  { titulo: 'millas', valor: 'millas' },
  { titulo: 'minutos', valor: 'minutos' },
  { titulo: 'tarifa', valor: 'tarifa' },
  { titulo: 'total', valor: 'total' },
  { titulo: 'tarifa_minima', valor: 'tarifa_minima' },
  { titulo: 'tarifa_maxima', valor: 'tarifa_maxima' },
  { titulo: 'mediana_ruta_millas', valor: 'mediana_ruta' },
  { titulo: 'diferencia_total', valor: 'diferencia_total' },
  { titulo: 'referencia', valor: 'referencia' },
  { titulo: 'impacto_usd', valor: 'impacto' },
];

export function iniciar(datos) {
  A = datos;
  casos = filas(A.casos);
  const sel = document.getElementById('filtro-regla');
  sel.add(new Option('Todas las reglas', 'Todas'));
  for (const r of A.reglas) sel.add(new Option(`${r.regla} (${fmt.entero(r.viajes)})`, r.regla));
  sel.addEventListener('change', renderCasos);
  document.getElementById('descargar-casos').addEventListener('click', () => {
    descargarCSV('casos_auditoria_taxis_nyc_2017-01.csv', COLUMNAS_CSV, casosFiltrados());
  });
}

export function render() {
  const t = tokens();
  renderKpis();
  renderReglas(t);
  renderProveedores(t);
  renderDispersion(t);
  renderCasos();
  renderDefiniciones();
}

function renderKpis() {
  const k = A.kpis;
  const an = A.anulaciones;
  const conc = A.reglas.find((r) => r.columna === 'a_total_no_concilia');
  kpis(document.getElementById('kpis-integridad'), [
    { etiqueta: 'Viajes con alguna marca', valor: fmt.entero(k.viajes_marcados), nota: `${fmt.pct(k.pct_base, 2)} de la base analítica` },
    { etiqueta: 'Monto involucrado estimado', valor: fmt.usdCompacto(k.impacto_usd), nota: 'Suma del impacto de las reglas' },
    { etiqueta: 'Cargos anulados', valor: fmt.usdCompacto(an.monto_reversado), nota: `${fmt.entero(an.pares)} pares cargo + reverso` },
    { etiqueta: 'Totales que no concilian', valor: fmt.entero(conc.viajes), nota: `${fmt.pct(conc.casos_v2 / conc.viajes * 100, 0)} de VeriFone` },
  ]);
}

function barras(t, tarjeta, datos, clave, formato, eje) {
  const orden = [...datos].sort((a, b) => a[clave] - b[clave]);
  const g = grafico(tarjeta);
  const estrecho = g.getWidth() < 520;
  g.setOption({
    ...base(t),
    grid: { left: 8, right: 72, top: 4, bottom: 8, containLabel: true },
    tooltip: {
      ...base(t).tooltip, trigger: 'item',
      formatter: (p) => `<div style="margin-bottom:4px">${escapar(orden[p.dataIndex].regla)}</div>` + filaTooltip(null, 'Valor', formato(p.value)),
    },
    xAxis: ejeValor(t, { splitNumber: estrecho ? 2 : 4, axisLabel: { color: t.eje, fontSize: 11, formatter: eje } }),
    yAxis: ejeCategoria(t, orden.map((r) => r.regla), {
      axisLabel: { color: t.tinta2, fontSize: 12, width: anchoEtiqueta(g, 190), overflow: 'break', lineHeight: 14 },
    }),
    series: [{
      type: 'bar', data: orden.map((r) => r[clave]), barMaxWidth: 18,
      itemStyle: { color: t.serie1, borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: t.tinta2, fontSize: 11, formatter: (p) => formato(p.value) },
    }],
  }, true);
}

function renderReglas(t) {
  const tCasos = document.querySelector('[data-grafico="reglas-casos"]');
  barras(t, tCasos, A.reglas, 'viajes', fmt.entero, fmt.compacto);
  vistaTabla(tCasos, [
    { titulo: 'Regla', valor: 'regla' },
    { titulo: 'Viajes', valor: 'viajes', num: true, fmt: fmt.entero },
    { titulo: '% de la base', valor: 'pct_base', num: true, fmt: (v) => fmt.pct(v, 2) },
  ], [...A.reglas].sort((a, b) => b.viajes - a.viajes));

  const tImp = document.querySelector('[data-grafico="reglas-impacto"]');
  const conMonto = A.reglas.filter((r) => r.columna !== 'a_monto_implausible');
  barras(t, tImp, conMonto, 'impacto_usd', fmt.usd, (v) => `$${fmt.compacto(v)}`);
  vistaTabla(tImp, [
    { titulo: 'Regla', valor: 'regla' },
    { titulo: 'Impacto total', valor: 'impacto_usd', num: true, fmt: fmt.usd },
    { titulo: 'Impacto mediano por viaje', valor: 'impacto_mediano_usd', num: true, fmt: fmt.usd2 },
    { titulo: 'Cómo se estima', valor: 'metodo_impacto' },
  ], [...conMonto].sort((a, b) => b.impacto_usd - a.impacto_usd));
}

function renderProveedores(t) {
  const tarjeta = document.querySelector('[data-grafico="proveedores"]');
  const orden = [...A.reglas].sort((a, b) => (a.tasa_10k_v1 + a.tasa_10k_v2) - (b.tasa_10k_v1 + b.tasa_10k_v2));
  const nombres = A.proveedores;
  const colores = [t.serie1, t.serie2];
  const g = grafico(tarjeta);
  g.setOption({
    ...base(t),
    grid: { left: 8, right: 56, top: 36, bottom: 8, containLabel: true },
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: t.tinta2, fontSize: 12 } },
    tooltip: {
      ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { opacity: 0.06 } },
      formatter: (ps) => `<div style="margin-bottom:4px">${escapar(ps[0].axisValue)}</div>`
        + ps.map((p) => filaTooltip(p.color, p.seriesName, `${fmt.dec1(p.value)} por 10 mil`)).join(''),
    },
    xAxis: ejeValor(t, { axisLabel: { color: t.eje, fontSize: 11 } }),
    yAxis: ejeCategoria(t, orden.map((r) => r.regla), {
      axisLabel: { color: t.tinta2, fontSize: 12, width: anchoEtiqueta(g, 190), overflow: 'break', lineHeight: 14 },
    }),
    series: ['1', '2'].map((id, i) => ({
      name: nombres[id], type: 'bar', data: orden.map((r) => +r[`tasa_10k_v${id}`].toFixed(2)), barMaxWidth: 12, barGap: '20%',
      itemStyle: { color: colores[i], borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: t.tinta2, fontSize: 10, formatter: (p) => (p.value >= 0.05 ? fmt.dec1(p.value) : '') },
    })),
  }, true);
  vistaTabla(tarjeta, [
    { titulo: 'Regla', valor: 'regla' },
    { titulo: `${nombres['1']} (casos)`, valor: 'casos_v1', num: true, fmt: fmt.entero },
    { titulo: `${nombres['1']} (por 10 mil)`, valor: 'tasa_10k_v1', num: true, fmt: fmt.dec2 },
    { titulo: `${nombres['2']} (casos)`, valor: 'casos_v2', num: true, fmt: fmt.entero },
    { titulo: `${nombres['2']} (por 10 mil)`, valor: 'tasa_10k_v2', num: true, fmt: fmt.dec2 },
  ], [...orden].reverse());
}

function renderDispersion(t) {
  const tarjeta = document.querySelector('[data-grafico="dispersion"]');
  const puntos = filas(A.dispersion);
  const grupos = ['Sin marca', 'Por debajo del mínimo', 'Por encima del máximo'];
  const colores = { 'Sin marca': t.atenuado, 'Por debajo del mínimo': t.serie1, 'Por encima del máximo': t.serie2 };
  const MAX_X = 30;
  const MAX_Y = 120;
  const L = A.limites;
  const g = grafico(tarjeta);
  g.setOption({
    ...base(t),
    grid: { left: 8, right: 20, top: 36, bottom: 28, containLabel: true },
    legend: { top: 0, left: 0, itemWidth: 12, itemHeight: 9, textStyle: { color: t.tinta2, fontSize: 12 }, data: [...grupos.map((name) => ({ name, icon: 'circle' })), { name: 'Mínimo del tarifario', icon: 'path://M0,4 L12,4 L12,5 L0,5 Z' }] },
    tooltip: {
      ...base(t).tooltip, trigger: 'item',
      formatter: (p) => (p.seriesType === 'line' ? '' : `<div style="margin-bottom:4px">${escapar(p.seriesName)}</div>`
        + filaTooltip(null, 'Tarifa', fmt.usd2(p.value[1])) + filaTooltip(null, 'Distancia', `${fmt.dec2(p.value[0])} mi`)),
    },
    xAxis: ejeValor(t, { max: MAX_X, name: 'Millas', nameLocation: 'middle', nameGap: 24, nameTextStyle: { color: t.eje, fontSize: 11 }, axisLabel: { color: t.eje, fontSize: 11 } }),
    yAxis: ejeValor(t, { max: MAX_Y, axisLabel: { color: t.eje, fontSize: 11, formatter: (v) => `$${v}` } }),
    series: [
      ...grupos.map((grupo) => ({
        name: grupo, type: 'scatter', symbolSize: grupo === 'Sin marca' ? 5 : 7, large: false,
        data: puntos.filter((p) => p.grupo === grupo && p.millas <= MAX_X && p.tarifa <= MAX_Y).map((p) => [p.millas, p.tarifa]),
        itemStyle: { color: colores[grupo], opacity: grupo === 'Sin marca' ? 0.55 : 0.85, borderColor: t.superficie, borderWidth: grupo === 'Sin marca' ? 0 : 1 },
        emphasis: { scale: 1.6 },
      })),
      {
        name: 'Mínimo del tarifario', type: 'line', silent: true, showSymbol: false,
        data: [[0, L.banderazo], [MAX_X, L.banderazo + L.tarifa_milla * MAX_X]],
        lineStyle: { color: t.tinta2, width: 1.5 }, itemStyle: { color: t.tinta2 }, z: 5,
      },
    ],
  }, true);
  const resumen = grupos.map((grupo) => {
    const sub = puntos.filter((p) => p.grupo === grupo);
    return { grupo, n: sub.length, fuera: sub.filter((p) => p.millas > MAX_X || p.tarifa > MAX_Y).length };
  });
  vistaTabla(tarjeta, [
    { titulo: 'Grupo', valor: 'grupo' },
    { titulo: 'Puntos en la muestra', valor: 'n', num: true, fmt: fmt.entero },
    { titulo: 'Fuera del área visible', valor: 'fuera', num: true, fmt: fmt.entero },
  ], resumen);
}

function casosFiltrados() {
  const regla = document.getElementById('filtro-regla').value;
  return regla === 'Todas' ? casos : casos.filter((c) => c.regla === regla);
}

function renderCasos() {
  const contenedor = document.querySelector('[data-grafico="casos"] [data-tabla-fija]');
  const todas = document.getElementById('filtro-regla').value === 'Todas';
  tabla(contenedor, todas ? COLUMNAS_CASOS : COLUMNAS_CASOS.slice(1), casosFiltrados());
  contenedor.classList.add('tabla-compacta');
}

function renderDefiniciones() {
  const contenedor = document.querySelector('[data-grafico="definiciones"] [data-tabla-fija]');
  tabla(contenedor, [
    { titulo: 'Regla', valor: 'regla' },
    { titulo: 'Qué detecta', valor: 'descripcion' },
    { titulo: 'Cómo se estima el impacto', valor: 'metodo_impacto' },
    { titulo: 'Viajes', valor: 'viajes', num: true, fmt: fmt.entero },
  ], A.reglas);
}
