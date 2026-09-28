"""Agregados livianos que alimentan el tablero estático (docs/).

El tablero no carga los 9.7 millones de viajes: recibe tablas pre-agregadas
(en formato columnar para reducir el peso del JSON) y aplica los filtros en
el navegador sumando numeradores y denominadores, de modo que las razones
(ingreso por hora, velocidad) siempre se recalculan correctamente.
"""

import json
from datetime import datetime

import numpy as np
import pandas as pd

from . import auditoria, calidad, config, datos, imputacion


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _columnar(df: pd.DataFrame, redondeo: dict | None = None) -> dict:
    """Convierte un DataFrame en {columna: lista}, con redondeo opcional."""
    redondeo = redondeo or {}
    salida = {}
    for columna in df.columns:
        serie = df[columna]
        if columna in redondeo:
            serie = serie.round(redondeo[columna])
        if isinstance(serie.dtype, pd.CategoricalDtype) or pd.api.types.is_string_dtype(serie) or serie.dtype == object:
            salida[columna] = serie.astype(str).tolist()
        elif pd.api.types.is_integer_dtype(serie) or (
            pd.api.types.is_float_dtype(serie) and columna in redondeo and redondeo[columna] == 0
        ):
            salida[columna] = serie.astype("int64").tolist()
        else:
            salida[columna] = [None if pd.isna(v) else float(v) for v in serie]
    return salida


def _metricas(grupos) -> pd.DataFrame:
    """Numeradores y denominadores comunes a todas las tablas de demanda."""
    return grupos.agg(
        viajes=("ingreso", "size"),
        ingreso=("ingreso", "sum"),
        horas=("horas_t", "sum"),
        ingreso_t=("ingreso_t", "sum"),
        millas=("millas_t", "sum"),
    ).reset_index()


def preparar_demanda(df: pd.DataFrame) -> pd.DataFrame:
    """Subconjunto válido para demanda con columnas auxiliares de tiempo."""
    base = df.loc[
        df["valido_demanda"],
        [
            "fecha",
            "hora",
            "dia_semana",
            "tipo_dia",
            "franja",
            "PULocationID",
            "DOLocationID",
            "pu_distrito",
            "ingreso",
            "valido_ingreso",
            "valido_tiempo",
            "duracion_min",
            "distancia_final",
            "fare_amount",
            "tip_amount",
            "payment_type",
        ],
    ].copy()
    base.loc[~base["valido_ingreso"], "ingreso"] = 0.0
    tiempo = base["valido_tiempo"]
    base["horas_t"] = np.where(tiempo, base["duracion_min"] / 60, 0.0)
    base["ingreso_t"] = np.where(tiempo, base["ingreso"], 0.0)
    base["millas_t"] = np.where(tiempo, base["distancia_final"], 0.0)
    return base


# ---------------------------------------------------------------------------
# Tablas del tablero
# ---------------------------------------------------------------------------
def tablas_demanda(df: pd.DataFrame, zonas: pd.DataFrame) -> dict:
    base = preparar_demanda(df)
    redondeo = {"ingreso": 0, "horas": 1, "ingreso_t": 0, "millas": 1}

    dias = base.drop_duplicates("fecha")[["fecha", "tipo_dia", "dia_semana"]].sort_values("fecha")
    festivos = pd.to_datetime(list(config.FESTIVOS))
    dias_por_dow = dias.loc[~dias["fecha"].isin(festivos), "dia_semana"].value_counts().sort_index()

    zona_hora = _metricas(
        base.groupby(["PULocationID", "hora", "tipo_dia"], observed=True)
    ).rename(columns={"PULocationID": "zona"})

    no_festivo = base.loc[~base["fecha"].isin(festivos)]
    dow_hora = _metricas(
        no_festivo.groupby(["dia_semana", "hora", "pu_distrito"], observed=True)
    ).rename(columns={"pu_distrito": "distrito"})

    diario = _metricas(base.groupby(["fecha", "pu_distrito", "franja"], observed=True)).rename(
        columns={"pu_distrito": "distrito"}
    )
    diario["fecha"] = diario["fecha"].dt.strftime("%Y-%m-%d")

    # Rutas: se preseleccionan los 400 pares con más viajes en el mes y se
    # desagregan por tipo de día, franja y distrito de origen para filtrar.
    pares = base.groupby(["PULocationID", "DOLocationID"]).size().nlargest(400).index
    en_pares = base.set_index(["PULocationID", "DOLocationID"]).index.isin(pares)
    rutas = _metricas(
        base.loc[en_pares].groupby(["PULocationID", "DOLocationID", "tipo_dia", "franja"], observed=True)
    ).rename(columns={"PULocationID": "origen", "DOLocationID": "destino"})

    # Aeropuertos: viajes que salen de o llegan a JFK, LaGuardia o Newark.
    filas = []
    for zona_id, nombre in config.AEROPUERTOS.items():
        for sentido, columna in (("Desde", "PULocationID"), ("Hacia", "DOLocationID")):
            sub = base.loc[base[columna] == zona_id]
            agregado = _metricas(sub.groupby(["hora", "tipo_dia"], observed=True))
            agregado.insert(0, "sentido", sentido)
            agregado.insert(0, "aeropuerto", nombre)
            filas.append(agregado)
    aeropuertos = pd.concat(filas, ignore_index=True)

    catalogo = zonas.rename(columns={"LocationID": "id"})[["id", "zona", "distrito", "tipo_servicio"]]
    return {
        "dias": {
            "por_tipo": dias["tipo_dia"].astype(str).value_counts().to_dict(),
            "total": int(len(dias)),
            "por_dia_semana_sin_festivos": {int(k): int(v) for k, v in dias_por_dow.items()},
            "calendario": _columnar(
                dias.assign(fecha=dias["fecha"].dt.strftime("%Y-%m-%d"))[["fecha", "tipo_dia", "dia_semana"]]
            ),
            "festivos": list(config.FESTIVOS),
        },
        "franjas": {k: [min(v), max(v)] for k, v in config.FRANJAS.items()},
        "zonas": _columnar(catalogo),
        "zona_hora": _columnar(zona_hora, redondeo),
        "dow_hora": _columnar(dow_hora, redondeo),
        "diario": _columnar(diario, redondeo),
        "rutas": _columnar(rutas, redondeo),
        "aeropuertos": _columnar(aeropuertos, redondeo),
    }


def tabla_kpis(df: pd.DataFrame) -> dict:
    base = preparar_demanda(df)
    tarjeta = base["payment_type"] == 1
    tiempo = base["valido_tiempo"]
    return {
        "viajes_originales": int(len(df)),
        "viajes_base": int(len(base)),
        "ingreso": float(base["ingreso"].sum()),
        "ingreso_por_viaje": float(base["ingreso"].sum() / len(base)),
        "duracion_mediana_min": float(base.loc[tiempo, "duracion_min"].median()),
        "velocidad_mph": float(base["millas_t"].sum() / base["horas_t"].sum()),
        "ingreso_por_hora": float(base["ingreso_t"].sum() / base["horas_t"].sum()),
        "pct_tarjeta": float(tarjeta.mean() * 100),
        "propina_pct_tarjeta": float(
            base.loc[tarjeta, "tip_amount"].sum() / base.loc[tarjeta, "fare_amount"].sum() * 100
        ),
    }


def tablas_auditoria(df: pd.DataFrame, zonas: pd.DataFrame) -> dict:
    resumen = auditoria.resumen_auditoria(df)
    reglas = list(auditoria.REGLAS)
    base = df["valido_demanda"]

    # Anulaciones: se toma el cargo positivo de cada par para estimar el monto
    # que se reversó.
    anuladas = df.loc[df["q_anulacion"]]
    positivos = anuladas.loc[anuladas["total_amount"] > 0]
    negativos = anuladas.loc[anuladas["total_amount"] < 0]
    anulaciones = {
        "filas": int(len(anuladas)),
        "pares": int(len(positivos)),
        "monto_reversado": float(positivos["total_amount"].sum()),
        "por_forma_pago_reverso": {
            config.FORMAS_PAGO.get(int(k), str(k)): int(v)
            for k, v in negativos["payment_type"].value_counts().items()
        },
        "por_proveedor": {
            config.PROVEEDORES[int(k)]: int(v) for k, v in anuladas["VendorID"].value_counts().items()
        },
    }

    # Conciliación: valores de diferencia más frecuentes.
    no_concilia = df.loc[df["a_total_no_concilia"], "diferencia_total"].round(2)
    conciliacion = {
        "top_diferencias": [
            {"diferencia": round(float(k), 2), "viajes": int(v)} for k, v in no_concilia.value_counts().head(6).items()
        ]
    }

    # Dispersión tarifa vs distancia (viajes estándar): muestra de viajes
    # normales más todos los casos de las reglas de tarifario (con tope).
    rng = np.random.default_rng(config.SEMILLA)
    estandar = base & (df["RatecodeID"] == 1) & (df["trip_distance"] > 0) & ~df["q_monto_implausible"]
    normales = df.loc[estandar & ~df["a_alguna"], ["trip_distance", "fare_amount"]]
    normales = normales.sample(n=min(5_000, len(normales)), random_state=config.SEMILLA)
    normales["grupo"] = "Sin marca"
    marcados = []
    for columna, etiqueta in (
        ("a_bajo_tarifario", "Por debajo del mínimo"),
        ("a_sobre_tarifario", "Por encima del máximo"),
    ):
        sub = df.loc[df[columna] & (df["trip_distance"] > 0), ["trip_distance", "fare_amount"]]
        if len(sub) > 1_500:
            sub = sub.iloc[rng.choice(len(sub), 1_500, replace=False)]
        marcados.append(sub.assign(grupo=etiqueta))
    dispersion = pd.concat([normales, *marcados]).rename(columns={"trip_distance": "millas", "fare_amount": "tarifa"})

    # Casos para revisión: los de mayor impacto por regla.
    nombres = zonas.set_index("LocationID")["zona"]
    columnas_caso = [
        "tpep_pickup_datetime",
        "VendorID",
        "RatecodeID",
        "payment_type",
        "PULocationID",
        "DOLocationID",
        "trip_distance",
        "duracion_min",
        "fare_amount",
        "total_amount",
        "tarifa_minima",
        "tarifa_maxima",
        "mediana_ruta",
        "diferencia_total",
    ]
    casos = []
    for columna in reglas:
        impacto = columna.replace("a_", "impacto_", 1)
        orden = "fare_amount" if columna == "a_monto_implausible" else impacto
        sub = df.loc[df[columna], columnas_caso + [impacto]].nlargest(60, orden)
        sub = sub.rename(columns={impacto: "impacto"})
        sub.insert(0, "regla", auditoria.REGLAS[columna][0])
        casos.append(sub)
    casos = pd.concat(casos, ignore_index=True)
    casos["tpep_pickup_datetime"] = casos["tpep_pickup_datetime"].dt.strftime("%Y-%m-%d %H:%M")
    casos["VendorID"] = casos["VendorID"].map(config.PROVEEDORES)
    casos["RatecodeID"] = casos["RatecodeID"].map(config.CODIGOS_TARIFA)
    casos["payment_type"] = casos["payment_type"].map(config.FORMAS_PAGO)
    casos["PULocationID"] = casos["PULocationID"].map(nombres)
    casos["DOLocationID"] = casos["DOLocationID"].map(nombres)
    casos["referencia"] = _referencia_caso(casos)
    casos = casos.rename(
        columns={
            "tpep_pickup_datetime": "recogida",
            "VendorID": "proveedor",
            "RatecodeID": "codigo_tarifa",
            "payment_type": "forma_pago",
            "PULocationID": "origen",
            "DOLocationID": "destino",
            "trip_distance": "millas",
            "duracion_min": "minutos",
            "fare_amount": "tarifa",
            "total_amount": "total",
        }
    )

    # Tasa de casos por hora de recogida para las dos reglas más frecuentes.
    por_hora = (
        df.loc[base].groupby("hora")[["a_desvio_ruta", "a_bajo_tarifario", "a_total_no_concilia"]].mean() * 10_000
    ).reset_index()

    marcados_unicos = df["a_alguna"] & base
    return {
        "kpis": {
            "viajes_marcados": int(marcados_unicos.sum()),
            "pct_base": float(marcados_unicos.sum() / base.sum() * 100),
            "impacto_usd": float(resumen["impacto_usd"].sum()),
            "reglas": len(reglas),
        },
        "reglas": resumen.round(4).to_dict(orient="records"),
        "proveedores": {str(k): v for k, v in config.PROVEEDORES.items()},
        "viajes_por_proveedor": {
            str(k): int(v) for k, v in df.loc[base, "VendorID"].value_counts().sort_index().items()
        },
        "anulaciones": anulaciones,
        "conciliacion": conciliacion,
        "dispersion": _columnar(dispersion, {"millas": 2, "tarifa": 2}),
        "limites": {
            "banderazo": config.BANDERAZO,
            "tarifa_milla": config.TARIFA_MILLA,
            "tarifa_minuto": config.TARIFA_MINUTO,
            "tolerancia": config.TOLERANCIA_TARIFA,
        },
        "por_hora": _columnar(por_hora, {"a_desvio_ruta": 2, "a_bajo_tarifario": 2, "a_total_no_concilia": 2}),
        "casos": _columnar(
            casos,
            {
                "millas": 2,
                "minutos": 1,
                "tarifa": 2,
                "total": 2,
                "tarifa_minima": 2,
                "tarifa_maxima": 2,
                "mediana_ruta": 2,
                "diferencia_total": 2,
                "impacto": 2,
            },
        ),
    }


def _referencia_caso(casos: pd.DataFrame) -> pd.Series:
    """Texto corto con el valor contra el que se compara cada caso."""
    nombres = {columna: datos[0] for columna, datos in auditoria.REGLAS.items()}
    salida = []
    for _, c in casos.iterrows():
        regla = c["regla"]
        if regla in (nombres["a_bajo_tarifario"], nombres["a_sobre_tarifario"]):
            texto = f"Tarifario: ${c['tarifa_minima']:,.2f} – ${c['tarifa_maxima']:,.2f}"
        elif regla == nombres["a_codigo_fuera_ciudad"]:
            texto = f"Código {c['RatecodeID']}; estándar hasta ${c['tarifa_maxima']:,.2f}"
        elif regla == nombres["a_jfk_distinta"]:
            texto = f"Tarifa plana ${config.TARIFA_PLANA_JFK:,.2f}"
        elif regla == nombres["a_desvio_ruta"]:
            texto = f"Mediana de la ruta: {c['mediana_ruta']:,.2f} mi"
        elif regla == nombres["a_total_no_concilia"]:
            texto = f"Total ${c['total_amount']:,.2f}; diferencia ${c['diferencia_total']:,.2f}"
        else:
            texto = f"Total ${c['total_amount']:,.2f}"
        salida.append(texto)
    return pd.Series(salida, index=casos.index)


def tablas_calidad(df: pd.DataFrame) -> dict:
    reglas = calidad.resumen_calidad(df)
    comparacion, _ = imputacion.comparar_metodos(df)
    coeficientes = imputacion.ajustar_regresion(imputacion.base_entrenamiento(df))
    return {
        "reglas": reglas.round(4).to_dict(orient="records"),
        "embudo": calidad.embudo(df).to_dict(orient="records"),
        "imputacion": {
            "metodos": comparacion.round(4).to_dict(orient="records"),
            "n_entrenamiento": comparacion.attrs["n_entrenamiento"],
            "n_prueba": comparacion.attrs["n_prueba"],
            "n_imputados": int(df["distancia_imputada"].sum()),
            "coeficientes": {
                "intercepto": round(float(coeficientes[0]), 4),
                "tarifa": round(float(coeficientes[1]), 4),
                "minutos": round(float(coeficientes[2]), 4),
            },
        },
        "zonas_especiales": {
            "origen_desconocido": int(df["PULocationID"].eq(config.ZONA_DESCONOCIDA).sum()),
            "origen_fuera_nyc": int(df["PULocationID"].eq(config.ZONA_FUERA_NYC).sum()),
            "destino_desconocido": int(df["DOLocationID"].eq(config.ZONA_DESCONOCIDA).sum()),
            "destino_fuera_nyc": int(df["DOLocationID"].eq(config.ZONA_FUERA_NYC).sum()),
        },
    }


# ---------------------------------------------------------------------------
# Exportación
# ---------------------------------------------------------------------------
def exportar_sitio(df: pd.DataFrame) -> None:
    """Escribe los JSON del tablero en docs/data."""
    zonas = datos.cargar_zonas()
    config.SITIO_DATA.mkdir(parents=True, exist_ok=True)
    paquetes = {
        "resumen.json": {
            "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "periodo": "Enero de 2017",
            "kpis": tabla_kpis(df),
        },
        "demanda.json": tablas_demanda(df, zonas),
        "auditoria.json": tablas_auditoria(df, zonas),
        "calidad.json": tablas_calidad(df),
    }
    for nombre, contenido in paquetes.items():
        ruta = config.SITIO_DATA / nombre
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(contenido, archivo, ensure_ascii=False, separators=(",", ":"), default=_serializar)
        print(f"[ok] {ruta.relative_to(config.RAIZ)} ({ruta.stat().st_size / 1e3:,.0f} KB)")


def _serializar(valor):
    if isinstance(valor, (np.integer,)):
        return int(valor)
    if isinstance(valor, (np.floating,)):
        return None if np.isnan(valor) else float(valor)
    if isinstance(valor, (pd.Timestamp, datetime)):
        return valor.isoformat()
    raise TypeError(f"Tipo no serializable: {type(valor)}")
