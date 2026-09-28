// Pestaña "Calidad de datos": embudo, reglas y validación de la imputación.
import {
  anchoEtiqueta, base, ejeCategoria, ejeValor, escapar, filaTooltip, fmt, grafico, kpis, tabla, tokens, vistaTabla,
} from './util.js';

let C;
let R;

export function iniciar(datosCalidad, resumen) {
  C = datosCalidad;
  R = resumen;
}

export function render() {
  const t = tokens();
  const k = R.kpis;
  const imp = C.imputacion;
  kpis(document.getElementById('kpis-calidad'), [
    { etiqueta: 'Registros originales', valor: fmt.entero(k.viajes_originales) },
    { etiqueta: 'Base analítica', valor: fmt.entero(k.viajes_base), nota: `${fmt.pct((k.viajes_base / k.viajes_originales) * 100, 2)} de los registros` },
    { etiqueta: 'Registros excluidos', valor: fmt.entero(k.viajes_originales - k.viajes_base), nota: 'Anulaciones, duplicados y viajes sin trayecto' },
    { etiqueta: 'Distancias imputadas', valor: fmt.entero(imp.n_imputados), nota: 'Viajes taximetrados con distancia 0' },
  ]);
  renderEmbudo(t);
  renderImputacion(t);
  renderReglas();
}

function renderEmbudo(t) {
  const tarjeta = document.querySelector('[data-grafico="embudo"]');
  const pasos = C.embudo.filter((p) => p.descontados > 0);
  const orden = [...pasos].reverse();
  const g = grafico(tarjeta);
  g.setOption({
    ...base(t),
    grid: { left: 8, right: 64, top: 4, bottom: 8, containLabel: true },
    tooltip: {
      ...base(t).tooltip, trigger: 'item',
      formatter: (p) => `<div style="margin-bottom:4px">${escapar(orden[p.dataIndex].paso)}</div>`
        + filaTooltip(null, 'Registros descontados', fmt.entero(p.value))
        + filaTooltip(null, 'Quedan', fmt.entero(orden[p.dataIndex].restantes)),
    },
    xAxis: ejeValor(t, { splitNumber: 4, axisLabel: { color: t.eje, fontSize: 11, formatter: fmt.compacto } }),
    yAxis: ejeCategoria(t, orden.map((p) => p.paso), { axisLabel: { color: t.tinta2, fontSize: 12, width: anchoEtiqueta(g, 170), overflow: 'break' } }),
    series: [{
      type: 'bar', data: orden.map((p) => p.descontados), barMaxWidth: 20,
      itemStyle: { color: t.serie1, borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: t.tinta2, fontSize: 11, formatter: (p) => fmt.entero(p.value) },
    }],
  }, true);
  vistaTabla(tarjeta, [
    { titulo: 'Paso', valor: 'paso' },
    { titulo: 'Descontados', valor: 'descontados', num: true, fmt: fmt.entero },
    { titulo: 'Restantes', valor: 'restantes', num: true, fmt: fmt.entero },
  ], C.embudo);
}

function renderImputacion(t) {
  const tarjeta = document.querySelector('[data-grafico="imputacion"]');
  const imp = C.imputacion;
  const metodos = imp.metodos;
  const c = imp.coeficientes;
  tarjeta.querySelector('[data-subtitulo]').textContent =
    `Error absoluto medio (millas) al estimar ${fmt.entero(imp.n_prueba)} distancias conocidas que se ocultaron a propósito. `
    + `El método elegido es millas = ${fmt.dec2(c.intercepto)} + ${fmt.dec2(c.tarifa)} × tarifa ${c.minutos < 0 ? '−' : '+'} ${fmt.dec2(Math.abs(c.minutos))} × minutos.`;
  const orden = [...metodos].sort((a, b) => b.mae - a.mae);
  const g = grafico(tarjeta);
  g.setOption({
    ...base(t),
    grid: { left: 8, right: 64, top: 4, bottom: 8, containLabel: true },
    tooltip: {
      ...base(t).tooltip, trigger: 'item',
      formatter: (p) => {
        const m = orden[p.dataIndex];
        return `<div style="margin-bottom:4px">${escapar(m.metodo)}</div>`
          + filaTooltip(null, 'Error absoluto medio', `${fmt.dec2(m.mae)} mi`)
          + filaTooltip(null, 'Mediana del error', `${fmt.dec2(m.mediana_error_abs)} mi`)
          + filaTooltip(null, 'Desv. estándar estimada / real', `${fmt.dec2(m.std_estimada)} / ${fmt.dec2(m.std_real)}`);
      },
    },
    xAxis: ejeValor(t, { splitNumber: 4, axisLabel: { color: t.eje, fontSize: 11, formatter: (v) => `${v} mi` } }),
    yAxis: ejeCategoria(t, orden.map((m) => m.metodo), { axisLabel: { color: t.tinta2, fontSize: 12, width: anchoEtiqueta(g, 170), overflow: 'break' } }),
    series: [{
      type: 'bar', data: orden.map((m) => m.mae), barMaxWidth: 20,
      itemStyle: { color: t.serie1, borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: t.tinta2, fontSize: 11, formatter: (p) => `${fmt.dec2(p.value)} mi` },
    }],
  }, true);
  vistaTabla(tarjeta, [
    { titulo: 'Método', valor: 'metodo' },
    { titulo: 'MAE (mi)', valor: 'mae', num: true, fmt: fmt.dec2 },
    { titulo: 'Mediana del error (mi)', valor: 'mediana_error_abs', num: true, fmt: fmt.dec2 },
    { titulo: 'RMSE (mi)', valor: 'rmse', num: true, fmt: fmt.dec2 },
    { titulo: 'Desv. estándar estimada', valor: 'std_estimada', num: true, fmt: fmt.dec2 },
    { titulo: 'Desv. estándar real', valor: 'std_real', num: true, fmt: fmt.dec2 },
  ], metodos);
}

function renderReglas() {
  tabla(document.querySelector('[data-grafico="reglas-calidad"] [data-tabla-fija]'), [
    { titulo: 'Regla', valor: 'regla' },
    { titulo: 'Registros', valor: 'viajes', num: true, fmt: fmt.entero },
    { titulo: '% del total', valor: 'pct', num: true, fmt: (v) => fmt.pct(v, 2) },
    { titulo: 'Tratamiento', valor: 'tratamiento' },
    { titulo: 'Justificación', valor: 'justificacion' },
  ], C.reglas);
}
