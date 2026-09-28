// Pestaña "Demanda y operación": filtros, KPIs y gráficos de demanda.
import {
  anchoEtiqueta, base, ejeCategoria, ejeValor, escapar, filaTooltip, filas, fmt, grafico, kpis, tabla,
  tokens, vistaTabla,
} from './util.js';

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
const DIAS_CORTOS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const TIPOS = ['Laborable', 'Fin de semana/festivo'];
const ETIQUETA_TIPO = { Laborable: 'Laborable', 'Fin de semana/festivo': 'Fin de semana y festivo' };

const METRICAS = {
  viajes: { nombre: 'Viajes por día', corto: 'viajes por día', fmt: fmt.entero, eje: fmt.compacto },
  ingreso_hora: { nombre: 'Ingreso por hora de servicio', corto: 'USD por hora de servicio', fmt: fmt.usd2, eje: (v) => `$${fmt.entero(v)}` },
  velocidad: { nombre: 'Velocidad media', corto: 'mph', fmt: (v) => `${fmt.dec1(v)} mph`, eje: fmt.entero },
};

let D; // datos de demanda
let estado = { tipo: 'Todos', franja: 'Todas', distrito: 'Todos', metrica: 'viajes' };
let zonaInfo; // id -> {zona, distrito}
let tablas; // filas pre-convertidas

export function iniciar(datos) {
  D = datos;
  zonaInfo = new Map();
  filas(D.zonas).forEach((z) => zonaInfo.set(z.id, z));
  tablas = {
    zonaHora: filas(D.zona_hora),
    dowHora: filas(D.dow_hora),
    diario: filas(D.diario),
    rutas: filas(D.rutas),
    aeropuertos: filas(D.aeropuertos),
  };
  const tipoDiaFecha = new Map(filas(D.dias.calendario).map((f) => [f.fecha, f.tipo_dia]));
  tablas.diario.forEach((f) => { f.tipo_dia = tipoDiaFecha.get(f.fecha); });
  tablas.zonaHora.forEach((f) => { f.distrito = zonaInfo.get(f.zona)?.distrito; });
  tablas.rutas.forEach((f) => { f.distrito = zonaInfo.get(f.origen)?.distrito; });

  // Opciones de filtros a partir de los datos.
  const selFranja = document.getElementById('filtro-franja');
  for (const [nombre, [a, b]] of Object.entries(D.franjas)) {
    selFranja.add(new Option(`${nombre} (${a}:00–${b}:59)`, nombre));
  }
  const selDistrito = document.getElementById('filtro-distrito');
  const volumen = new Map();
  tablas.zonaHora.forEach((f) => volumen.set(f.distrito, (volumen.get(f.distrito) || 0) + f.viajes));
  [...volumen.entries()].sort((a, b) => b[1] - a[1]).forEach(([d]) => selDistrito.add(new Option(d, d)));

  document.querySelectorAll('#filtro-tipo input').forEach((el) => el.addEventListener('change', () => {
    estado.tipo = el.value; render();
  }));
  selFranja.addEventListener('change', () => { estado.franja = selFranja.value; render(); });
  selDistrito.addEventListener('change', () => { estado.distrito = selDistrito.value; render(); });
  document.getElementById('filtro-metrica').addEventListener('change', (e) => { estado.metrica = e.target.value; render(); });
}

// ---------------------------------------------------------------------------
// Filtros y métricas
// ---------------------------------------------------------------------------
function horaOk(h) {
  if (estado.franja === 'Todas') return true;
  const [a, b] = D.franjas[estado.franja];
  return h >= a && h <= b;
}
const tipoOk = (t) => estado.tipo === 'Todos' || t === estado.tipo;
const distritoOk = (d) => estado.distrito === 'Todos' || d === estado.distrito;
const nDias = (tipo = estado.tipo) => (tipo === 'Todos' ? D.dias.total : D.dias.por_tipo[tipo]);

function sumar(lista) {
  const s = { viajes: 0, ingreso: 0, horas: 0, ingreso_t: 0, millas: 0 };
  for (const f of lista) {
    s.viajes += f.viajes; s.ingreso += f.ingreso; s.horas += f.horas; s.ingreso_t += f.ingreso_t; s.millas += f.millas;
  }
  return s;
}

function valor(s, dias, metrica = estado.metrica) {
  if (metrica === 'viajes') return s.viajes / dias;
  if (metrica === 'ingreso_hora') return s.horas > 0 ? s.ingreso_t / s.horas : null;
  return s.horas > 0 ? s.millas / s.horas : null;
}

function agrupar(lista, clave) {
  const m = new Map();
  for (const f of lista) {
    const k = clave(f);
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(f);
  }
  return m;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
export function render() {
  const t = tokens();
  const zh = tablas.zonaHora.filter((f) => tipoOk(f.tipo_dia) && horaOk(f.hora) && distritoOk(f.distrito));
  renderKpis(zh);
  renderHeatmap(t);
  renderDiario(t);
  renderPerfil(t);
  renderZonas(t, zh);
  renderRutas(t);
  renderAeropuertos();
}

function renderKpis(zh) {
  const s = sumar(zh);
  const dias = nDias();
  kpis(document.getElementById('kpis-demanda'), [
    { etiqueta: 'Viajes por día', valor: fmt.entero(s.viajes / dias), nota: `${fmt.entero(s.viajes)} en ${dias} días` },
    { etiqueta: 'Ingreso por día', valor: fmt.usdCompacto(s.ingreso / dias), nota: 'Tarifa + recargos + propina' },
    { etiqueta: 'Ingreso por hora de servicio', valor: fmt.usd2(valor(s, dias, 'ingreso_hora')), nota: 'Por hora con pasajero a bordo' },
    { etiqueta: 'Velocidad media', valor: `${fmt.dec1(valor(s, dias, 'velocidad'))} mph`, nota: 'Millas totales / horas totales' },
    { etiqueta: 'Ingreso por viaje', valor: fmt.usd2(s.ingreso / s.viajes) },
  ]);
}

function renderHeatmap(t) {
  const tarjeta = document.querySelector('[data-grafico="heatmap"]');
  const m = METRICAS[estado.metrica];
  const dows = estado.tipo === 'Laborable' ? [0, 1, 2, 3, 4] : estado.tipo === 'Todos' ? [0, 1, 2, 3, 4, 5, 6] : [5, 6];
  const horas = [...Array(24).keys()].filter(horaOk);
  const sub = tablas.dowHora.filter((f) => distritoOk(f.distrito));
  const grupos = agrupar(sub, (f) => `${f.dia_semana}|${f.hora}`);
  const celdas = [];
  const filasTabla = [];
  dows.forEach((d, yi) => {
    horas.forEach((h, xi) => {
      const s = sumar(grupos.get(`${d}|${h}`) || []);
      const v = valor(s, D.dias.por_dia_semana_sin_festivos[d]);
      celdas.push([xi, yi, v == null ? null : +v.toFixed(2)]);
      filasTabla.push({ dia: DIAS[d], hora: `${h}:00`, valor: v });
    });
  });
  const valores = celdas.map((c) => c[2]).filter((v) => v != null);
  const min = Math.min(...valores);
  const max = Math.max(...valores);

  tarjeta.querySelector('[data-subtitulo]').textContent =
    `${m.nombre} por día de la semana y hora de recogida${estado.distrito === 'Todos' ? '' : ` (origen en ${estado.distrito})`}. Excluye los festivos del 2 y 16 de enero.`;

  const g = grafico(tarjeta);
  g.setOption({
    ...base(t),
    grid: { left: 8, right: 16, top: 8, bottom: 56, containLabel: true },
    tooltip: {
      ...base(t).tooltip,
      formatter: (p) => `<div style="margin-bottom:4px">${DIAS[dows[p.value[1]]]} · ${horas[p.value[0]]}:00–${horas[p.value[0]]}:59</div>`
        + filaTooltip(null, m.nombre, m.fmt(p.value[2])),
    },
    xAxis: ejeCategoria(t, horas.map((h) => `${h}h`), { splitArea: { show: false }, axisLine: { show: false } }),
    yAxis: ejeCategoria(t, dows.map((d) => DIAS_CORTOS[d]), { inverse: true, axisLine: { show: false } }),
    visualMap: {
      min, max, calculable: false, orient: 'horizontal', left: 'center', bottom: 0, itemWidth: 12, itemHeight: 180,
      inRange: { color: t.secuencial }, text: [m.eje(max), m.eje(min)], textStyle: { color: t.eje, fontSize: 11 },
    },
    series: [{
      type: 'heatmap', data: celdas, itemStyle: { borderColor: t.superficie, borderWidth: 2, borderRadius: 3 },
      emphasis: { itemStyle: { borderColor: t.tinta, borderWidth: 1 } },
    }],
  }, true);

  vistaTabla(tarjeta, [
    { titulo: 'Día', valor: 'dia' }, { titulo: 'Hora', valor: 'hora' },
    { titulo: m.nombre, valor: 'valor', num: true, fmt: m.fmt },
  ], filasTabla);
}

function renderDiario(t) {
  const tarjeta = document.querySelector('[data-grafico="diario"]');
  const m = METRICAS[estado.metrica];
  const sub = tablas.diario.filter((f) => horaOk(horaFranja(f.franja)) && distritoOk(f.distrito));
  const grupos = agrupar(sub, (f) => f.fecha);
  const fechas = filas(D.dias.calendario);
  const porTipo = { Laborable: [], 'Fin de semana/festivo': [] };
  const filasTabla = [];
  for (const d of fechas) {
    const v = valor(sumar(grupos.get(d.fecha) || []), 1);
    for (const tipo of TIPOS) porTipo[tipo].push(d.tipo_dia === tipo ? v : null);
    filasTabla.push({ fecha: d.fecha, dia: DIAS[d.dia_semana], tipo: ETIQUETA_TIPO[d.tipo_dia], valor: v });
  }
  const colores = { Laborable: t.serie1, 'Fin de semana/festivo': t.serie2 };
  const g = grafico(tarjeta);
  g.setOption({
    ...base(t),
    grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    legend: {
      top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: t.tinta2, fontSize: 12 },
      data: TIPOS.map((tp) => ({ name: ETIQUETA_TIPO[tp] })),
    },
    tooltip: {
      ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { opacity: 0.06 } },
      formatter: (ps) => {
        const p = ps.find((x) => x.value != null);
        if (!p) return '';
        const f = fechas[p.dataIndex];
        return `<div style="margin-bottom:4px">${DIAS[f.dia_semana]} ${f.fecha.slice(8)} de enero${D.dias.festivos.includes(f.fecha) ? ' · festivo' : ''}</div>`
          + filaTooltip(p.color, m.nombre, m.fmt(p.value));
      },
    },
    xAxis: ejeCategoria(t, fechas.map((f) => String(+f.fecha.slice(8))), { axisLabel: { color: t.eje, fontSize: 11, interval: 1 } }),
    yAxis: ejeValor(t, { axisLabel: { color: t.eje, fontSize: 11, formatter: m.eje } }),
    series: TIPOS.map((tipo) => ({
      name: ETIQUETA_TIPO[tipo], type: 'bar', stack: 'dia', data: porTipo[tipo], barMaxWidth: 16,
      itemStyle: { color: colores[tipo], borderRadius: [4, 4, 0, 0], opacity: tipoOk(tipo) ? 1 : 0.25 },
    })),
  }, true);
  vistaTabla(tarjeta, [
    { titulo: 'Fecha', valor: 'fecha' }, { titulo: 'Día', valor: 'dia' }, { titulo: 'Tipo', valor: 'tipo' },
    { titulo: m.nombre, valor: 'valor', num: true, fmt: m.fmt },
  ], filasTabla);
}

// Las filas diarias vienen por franja: se usa la primera hora de la franja para
// evaluar si la franja está dentro del filtro.
function horaFranja(franja) { return D.franjas[franja][0]; }

function renderPerfil(t) {
  const tarjeta = document.querySelector('[data-grafico="perfil"]');
  const m = METRICAS[estado.metrica];
  const sub = tablas.zonaHora.filter((f) => distritoOk(f.distrito));
  const grupos = agrupar(sub, (f) => `${f.tipo_dia}|${f.hora}`);
  const horas = [...Array(24).keys()];
  const series = {};
  for (const tipo of TIPOS) {
    series[tipo] = horas.map((h) => valor(sumar(grupos.get(`${tipo}|${h}`) || []), nDias(tipo)));
  }
  const colores = { Laborable: t.serie1, 'Fin de semana/festivo': t.serie2 };
  const visibles = TIPOS.filter(tipoOk);
  let area = [];
  if (estado.franja !== 'Todas') {
    const [a, b] = D.franjas[estado.franja];
    area = [[{ xAxis: `${a}h` }, { xAxis: `${b}h` }]];
  }
  tarjeta.querySelector('[data-subtitulo]').textContent =
    `${m.nombre} según la hora de recogida${estado.distrito === 'Todos' ? '' : ` (origen en ${estado.distrito})`}. La franja seleccionada aparece sombreada.`;
  const g = grafico(tarjeta);
  g.setOption({
    ...base(t),
    grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    legend: {
      top: 0, left: 0, itemWidth: 16, itemHeight: 4, icon: 'roundRect', textStyle: { color: t.tinta2, fontSize: 12 },
      data: visibles.map((tp) => ETIQUETA_TIPO[tp]),
    },
    tooltip: {
      ...base(t).tooltip, trigger: 'axis', axisPointer: { type: 'line', lineStyle: { color: t.eje, width: 1 } },
      formatter: (ps) => `<div style="margin-bottom:4px">${ps[0].axisValue.replace('h', ':00')}</div>`
        + ps.map((p) => filaTooltip(p.color, p.seriesName, m.fmt(p.value))).join(''),
    },
    xAxis: ejeCategoria(t, horas.map((h) => `${h}h`), { boundaryGap: false, axisLabel: { color: t.eje, fontSize: 11, interval: 2 } }),
    yAxis: ejeValor(t, { axisLabel: { color: t.eje, fontSize: 11, formatter: m.eje } }),
    series: visibles.map((tipo, i) => ({
      name: ETIQUETA_TIPO[tipo], type: 'line', data: series[tipo].map((v) => (v == null ? null : +v.toFixed(2))),
      showSymbol: false, symbolSize: 8, smooth: false,
      lineStyle: { width: 2, color: colores[tipo], cap: 'round', join: 'round' },
      itemStyle: { color: colores[tipo], borderColor: t.superficie, borderWidth: 2 },
      markArea: i === 0 && area.length ? { silent: true, itemStyle: { color: t.tinta, opacity: 0.05 }, data: area } : undefined,
    })),
  }, true);
  vistaTabla(tarjeta, [
    { titulo: 'Hora', valor: 'hora' },
    ...visibles.map((tipo) => ({ titulo: ETIQUETA_TIPO[tipo], valor: tipo, num: true, fmt: m.fmt })),
  ], horas.map((h) => ({ hora: `${h}:00`, Laborable: series.Laborable[h], 'Fin de semana/festivo': series['Fin de semana/festivo'][h] })));
}

function renderZonas(t, zh) {
  const tarjeta = document.querySelector('[data-grafico="zonas"]');
  const m = METRICAS[estado.metrica];
  const dias = nDias();
  const grupos = agrupar(zh, (f) => f.zona);
  const todas = [];
  for (const [zona, lista] of grupos) {
    const s = sumar(lista);
    const info = zonaInfo.get(zona) || {};
    todas.push({
      zona: info.zona, distrito: info.distrito, viajes: s.viajes / dias, ingreso: s.ingreso / dias,
      ingreso_hora: valor(s, dias, 'ingreso_hora'), velocidad: valor(s, dias, 'velocidad'), valor: valor(s, dias),
    });
  }
  // En métricas de razón se exige un volumen mínimo para no premiar zonas con pocos viajes.
  const minimo = estado.metrica === 'viajes' ? 0 : 20;
  const top = todas.filter((z) => z.viajes >= minimo && z.valor != null)
    .sort((a, b) => b.valor - a.valor).slice(0, 15).reverse();
  tarjeta.querySelector('[data-subtitulo]').textContent = estado.metrica === 'viajes'
    ? 'Las 15 zonas de recogida con más viajes por día en el filtro actual.'
    : `Las 15 zonas con mayor ${m.nombre.toLowerCase()} entre las que tienen al menos 20 viajes por día.`;
  barrasHorizontales(t, grafico(tarjeta), top.map((z) => z.zona), top.map((z) => z.valor), m,
    (i) => `${top[i].zona} · ${top[i].distrito}`);
  vistaTabla(tarjeta, [
    { titulo: 'Zona', valor: 'zona' }, { titulo: 'Distrito', valor: 'distrito' },
    { titulo: 'Viajes por día', valor: 'viajes', num: true, fmt: fmt.entero },
    { titulo: 'Ingreso por día', valor: 'ingreso', num: true, fmt: fmt.usd },
    { titulo: 'Ingreso por hora', valor: 'ingreso_hora', num: true, fmt: fmt.usd2 },
    { titulo: 'Velocidad (mph)', valor: 'velocidad', num: true, fmt: fmt.dec1 },
  ], todas.sort((a, b) => (b.valor ?? -1) - (a.valor ?? -1)));
}

function renderRutas(t) {
  const tarjeta = document.querySelector('[data-grafico="rutas"]');
  const m = METRICAS[estado.metrica];
  const dias = nDias();
  // Las zonas 264 y 265 no son ubicaciones accionables para la operación.
  const conocida = (z) => z !== 264 && z !== 265;
  const sub = tablas.rutas.filter((f) => conocida(f.origen) && conocida(f.destino)
    && tipoOk(f.tipo_dia) && horaOk(horaFranja(f.franja)) && distritoOk(f.distrito));
  const grupos = agrupar(sub, (f) => `${f.origen}|${f.destino}`);
  const todas = [];
  for (const [clave, lista] of grupos) {
    const [o, d] = clave.split('|').map(Number);
    const s = sumar(lista);
    const origen = zonaInfo.get(o)?.zona;
    const destino = zonaInfo.get(d)?.zona;
    todas.push({
      etiqueta: o === d ? `${origen} (dentro de la zona)` : `${origen} → ${destino}`, origen, destino,
      viajes: s.viajes / dias, ingreso_viaje: s.ingreso / s.viajes, minutos: s.horas > 0 ? (s.horas * 60) / s.viajes : null,
      ingreso_hora: valor(s, dias, 'ingreso_hora'), velocidad: valor(s, dias, 'velocidad'), valor: valor(s, dias),
    });
  }
  const minimo = estado.metrica === 'viajes' ? 0 : 20;
  const top = todas.filter((r) => r.viajes >= minimo && r.valor != null).sort((a, b) => b.valor - a.valor).slice(0, 12).reverse();
  tarjeta.querySelector('[data-subtitulo]').textContent = estado.metrica === 'viajes'
    ? 'Pares origen → destino con más viajes por día en el filtro actual. Excluye zonas desconocidas.'
    : `Pares con mayor ${m.nombre.toLowerCase()} entre los que tienen al menos 20 viajes por día.`;
  barrasHorizontales(t, grafico(tarjeta), top.map((r) => r.etiqueta), top.map((r) => r.valor), m,
    (i) => top[i].etiqueta, { width: 230, overflow: 'break' });
  vistaTabla(tarjeta, [
    { titulo: 'Origen', valor: 'origen' }, { titulo: 'Destino', valor: 'destino' },
    { titulo: 'Viajes por día', valor: 'viajes', num: true, fmt: fmt.entero },
    { titulo: 'Ingreso por viaje', valor: 'ingreso_viaje', num: true, fmt: fmt.usd2 },
    { titulo: 'Ingreso por hora', valor: 'ingreso_hora', num: true, fmt: fmt.usd2 },
    { titulo: 'Velocidad (mph)', valor: 'velocidad', num: true, fmt: fmt.dec1 },
  ], todas.sort((a, b) => b.viajes - a.viajes).slice(0, 100));
}

function barrasHorizontales(t, g, categorias, valores, m, titulo, etiquetaEje = { width: 180, overflow: 'truncate' }) {
  const estrecho = g.getWidth() < 520;
  const eje = { ...etiquetaEje, width: anchoEtiqueta(g, etiquetaEje.width) };
  if (estrecho) {
    categorias = categorias.map(abreviar);
    eje.overflow = 'truncate';
  }
  g.setOption({
    ...base(t),
    grid: { left: 8, right: 64, top: 4, bottom: 8, containLabel: true },
    tooltip: {
      ...base(t).tooltip, trigger: 'item',
      formatter: (p) => `<div style="margin-bottom:4px">${escapar(titulo(p.dataIndex))}</div>` + filaTooltip(null, m.nombre, m.fmt(p.value)),
    },
    xAxis: ejeValor(t, { splitNumber: estrecho ? 2 : 4, axisLabel: { color: t.eje, fontSize: 11, formatter: m.eje } }),
    yAxis: ejeCategoria(t, categorias, {
      axisLabel: { color: t.tinta2, fontSize: estrecho ? 11 : 12, lineHeight: 14, ...eje },
      axisLine: { lineStyle: { color: t.lineaBase } },
    }),
    series: [{
      type: 'bar', data: valores.map((v) => +v.toFixed(2)), barMaxWidth: 18,
      itemStyle: { color: t.serie1, borderRadius: [0, 4, 4, 0] },
      emphasis: { itemStyle: { opacity: 0.85 } },
      label: { show: true, position: 'right', color: t.tinta2, fontSize: 11, formatter: (p) => m.fmt(p.value) },
    }],
  }, true);
}

// Abreviaturas para pantallas estrechas (solo en las etiquetas del eje).
function abreviar(texto) {
  return texto
    .replaceAll('Upper East Side', 'UES').replaceAll('Upper West Side', 'UWS')
    .replaceAll(' (dentro de la zona)', ' (interna)').replaceAll('Square', 'Sq').replaceAll('Theatre District', 'Theatre')
    .replaceAll('Penn Station/Madison Sq', 'Penn Sta')
    .replace(/ North\b/g, ' N').replace(/ South\b/g, ' S').replace(/ East\b/g, ' E').replace(/ West\b/g, ' W');
}

function renderAeropuertos() {
  const tarjeta = document.querySelector('[data-grafico="aeropuertos"]');
  const sub = tablas.aeropuertos.filter((f) => tipoOk(f.tipo_dia) && horaOk(f.hora));
  const grupos = agrupar(sub, (f) => `${f.aeropuerto}|${f.sentido}`);
  const dias = nDias();
  const filasTabla = [];
  for (const [clave, lista] of grupos) {
    const [aeropuerto, sentido] = clave.split('|');
    const s = sumar(lista);
    filasTabla.push({
      aeropuerto, sentido, viajes: s.viajes / dias, ingreso: s.ingreso / dias, ingreso_viaje: s.ingreso / s.viajes,
      ingreso_hora: valor(s, dias, 'ingreso_hora'), velocidad: valor(s, dias, 'velocidad'),
    });
  }
  filasTabla.sort((a, b) => b.viajes - a.viajes);
  tarjeta.querySelector('[data-subtitulo]').textContent = 'Viajes que salen de o llegan a JFK, LaGuardia y Newark. Responde al tipo de día y a la franja; el filtro de distrito no aplica.';
  tabla(tarjeta.querySelector('[data-tabla-fija]'), [
    { titulo: 'Aeropuerto', valor: 'aeropuerto' }, { titulo: 'Sentido', valor: 'sentido' },
    { titulo: 'Viajes por día', valor: 'viajes', num: true, fmt: fmt.entero },
    { titulo: 'Ingreso por día', valor: 'ingreso', num: true, fmt: fmt.usd },
    { titulo: 'Ingreso por viaje', valor: 'ingreso_viaje', num: true, fmt: fmt.usd2 },
    { titulo: 'Ingreso por hora de servicio', valor: 'ingreso_hora', num: true, fmt: fmt.usd2 },
    { titulo: 'Velocidad (mph)', valor: 'velocidad', num: true, fmt: fmt.dec1 },
  ], filasTabla);
}

