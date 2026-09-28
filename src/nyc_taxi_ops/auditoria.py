"""Reglas de integridad tarifaria.

Cada regla marca viajes cuyo cobro no es consistente con el tarifario de la
TLC, con la ruta o con sus propios componentes, y estima el monto en dólares
involucrado. Una marca no prueba fraude: identifica casos que un área de
fiscalización revisaría primero.
"""

import numpy as np
import pandas as pd

from . import config

# Nombre visible, qué detecta y cómo se estima el impacto en dólares.
REGLAS = {
    "a_bajo_tarifario": (
        "Tarifa por debajo del mínimo del tarifario",
        "Viajes estándar, con duración y velocidad plausibles, cobrados por debajo de "
        "$2.50 + $2.50 por milla. Indica cobro incompleto (p. ej., tarifa de $0 en "
        "efectivo) o una distancia registrada mayor a la real.",
        "Mínimo del tarifario menos la tarifa cobrada.",
    ),
    "a_sobre_tarifario": (
        "Tarifa por encima del máximo del tarifario",
        "Viajes estándar cobrados por encima de $2.50 + $2.50 por milla + $0.50 por "
        "minuto, el máximo que el taxímetro puede marcar. Indica posible sobrecobro.",
        "Tarifa cobrada menos el máximo del tarifario.",
    ),
    "a_codigo_fuera_ciudad": (
        "Tarifa suburbana en un viaje dentro de NYC",
        "Código 3 (Newark) o 4 (Nassau/Westchester) en viajes que empiezan y terminan en "
        "los cinco distritos. Es el patrón del sobrecobro que la TLC detectó en 2010.",
        "Tarifa cobrada menos el máximo de la tarifa estándar.",
    ),
    "a_jfk_distinta": (
        "Tarifa plana JFK distinta de $52",
        "Viajes con código 2 cuya tarifa no es la tarifa plana vigente.",
        "Diferencia absoluta frente a $52.",
    ),
    "a_desvio_ruta": (
        "Distancia atípica para la ruta",
        "Distancia muy superior a la habitual del mismo par origen-destino (mediana + 5 "
        "MAD y al menos 1.5 veces la mediana). Candidato a revisión por posible desvío.",
        "Millas adicionales frente a la mediana de la ruta × $2.50.",
    ),
    "a_total_no_concilia": (
        "Total que no concilia con sus componentes",
        "El total cobrado difiere de la suma de tarifa, recargos, impuestos, propina y "
        "peajes.",
        "Diferencia absoluta entre el total y la suma de componentes.",
    ),
    "a_monto_implausible": (
        "Monto implausible, mayor a $1,000",
        "Errores de digitación evidentes. Se reportan sin sumar su monto, que no "
        "corresponde a dinero real.",
        "No se estima.",
    ),
}


def limites_tarifario(distancia: pd.Series, duracion: pd.Series) -> tuple[pd.Series, pd.Series]:
    minimo = config.BANDERAZO + config.TARIFA_MILLA * distancia
    maximo = minimo + config.TARIFA_MINUTO * duracion
    return minimo, maximo


def marcar_auditoria(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas ``a_*`` (bool) e ``impacto_*`` (USD) sobre la base válida.

    Modifica el DataFrame recibido para no duplicar ~1.5 GB en memoria.
    """
    base = df["valido_demanda"]
    estandar = base & (df["RatecodeID"] == 1) & ~df["q_monto_implausible"]
    distancia_observada = df["trip_distance"].astype("float64")
    tarifa = df["fare_amount"]
    minimo, maximo = limites_tarifario(distancia_observada, df["duracion_min"].astype("float64"))

    # 1. Por debajo del mínimo (solo con distancia observada, no imputada).
    #    Se excluyen "sin cargo" y "disputa", donde un cobro menor es esperable,
    #    y los viajes con duración o velocidad imposibles: en ellos la
    #    inconsistencia ya se explica por un error de distancia o de tiempo
    #    (regla de calidad), no por un cobro incompleto.
    cobrable = ~df["payment_type"].isin([3, 4])
    bajo = (
        estandar
        & (distancia_observada > 0)
        & cobrable
        & ~df["q_tiempo_invalido"]
        & (tarifa < minimo - config.TOLERANCIA_TARIFA)
    )
    df["a_bajo_tarifario"] = bajo
    df["impacto_bajo_tarifario"] = np.where(bajo, minimo - tarifa, 0.0)

    # 2. Por encima del máximo (requiere una duración confiable).
    sobre = (
        estandar
        & (distancia_observada > 0)
        & ~df["q_tiempo_invalido"]
        & (tarifa > maximo + config.TOLERANCIA_TARIFA)
    )
    df["a_sobre_tarifario"] = sobre
    df["impacto_sobre_tarifario"] = np.where(sobre, tarifa - maximo, 0.0)

    # 3. Código suburbano dentro de la ciudad.
    dentro_nyc = df["pu_distrito"].isin(config.DISTRITOS_NYC) & df["do_distrito"].isin(config.DISTRITOS_NYC)
    codigo = base & df["RatecodeID"].isin([3, 4]) & dentro_nyc & ~df["q_monto_implausible"]
    df["a_codigo_fuera_ciudad"] = codigo
    maximo_estandar = np.where(df["q_tiempo_invalido"], minimo, maximo)
    df["impacto_codigo_fuera_ciudad"] = np.where(codigo, np.clip(tarifa - maximo_estandar, 0, None), 0.0)

    # 4. Tarifa plana JFK.
    jfk = base & (df["RatecodeID"] == 2) & ((tarifa - config.TARIFA_PLANA_JFK).abs() > 0.01)
    df["a_jfk_distinta"] = jfk
    df["impacto_jfk_distinta"] = np.where(jfk, (tarifa - config.TARIFA_PLANA_JFK).abs(), 0.0)

    # 5. Distancia atípica para la ruta (regla contextual robusta).
    df["a_desvio_ruta"], df["impacto_desvio_ruta"], df["mediana_ruta"] = _desvio_ruta(df, estandar)

    # 6. Conciliación del total.
    componentes = (
        df["fare_amount"]
        + df["extra"]
        + df["mta_tax"]
        + df["tip_amount"]
        + df["tolls_amount"]
        + df["improvement_surcharge"]
    )
    diferencia = (df["total_amount"] - componentes).round(2)
    concilia = base & (diferencia.abs() > 0.01)
    df["a_total_no_concilia"] = concilia
    df["diferencia_total"] = diferencia.astype("float32")
    df["impacto_total_no_concilia"] = np.where(concilia, diferencia.abs(), 0.0)

    # 7. Montos implausibles.
    df["a_monto_implausible"] = base & df["q_monto_implausible"]
    df["impacto_monto_implausible"] = 0.0

    df["tarifa_minima"] = minimo.astype("float32")
    df["tarifa_maxima"] = maximo.astype("float32")
    columnas = list(REGLAS)
    df["a_alguna"] = df[columnas].any(axis=1)
    for columna in [c.replace("a_", "impacto_", 1) for c in columnas]:
        df[columna] = df[columna].astype("float32")
    return df


def _desvio_ruta(df: pd.DataFrame, estandar: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Marca distancias atípicas dentro de cada par origen-destino.

    Se excluyen los viajes que empiezan y terminan en la misma zona (pueden ser
    viajes de ida y vuelta legítimos) y las zonas desconocidas. La dispersión se
    mide con la MAD escalada (1.4826 × MAD ≈ desviación estándar bajo
    normalidad), robusta al sesgo fuerte de la distancia.
    """
    elegible = (
        estandar
        & ~df["q_tiempo_invalido"]
        & (df["trip_distance"] > 0)
        & ~df["q_zona_desconocida"]
        & (df["PULocationID"] != df["DOLocationID"])
    )
    sub = df.loc[elegible, ["PULocationID", "DOLocationID", "trip_distance"]]
    grupos = sub.groupby(["PULocationID", "DOLocationID"])["trip_distance"]
    n = grupos.transform("size")
    mediana = grupos.transform("median")
    mad = (sub["trip_distance"] - mediana).abs().groupby([sub["PULocationID"], sub["DOLocationID"]]).transform(
        "median"
    ) * 1.4826
    exceso = sub["trip_distance"] - mediana
    marca = (
        (n >= config.RUTA_MIN_VIAJES)
        & (sub["trip_distance"] > mediana + config.RUTA_K_MAD * mad.clip(lower=0.1))
        & (sub["trip_distance"] > config.RUTA_FACTOR_MEDIANA * mediana)
        & (exceso >= config.RUTA_EXCESO_MIN_MILLAS)
    )
    salida_marca = pd.Series(False, index=df.index)
    salida_marca.loc[marca.index] = marca
    salida_impacto = pd.Series(0.0, index=df.index)
    salida_impacto.loc[marca.index] = np.where(marca, exceso * config.TARIFA_MILLA, 0.0)
    salida_mediana = pd.Series(np.nan, index=df.index, dtype="float32")
    salida_mediana.loc[mediana.index] = mediana.astype("float32")
    return salida_marca, salida_impacto, salida_mediana


def resumen_auditoria(df: pd.DataFrame) -> pd.DataFrame:
    """Casos, porcentaje sobre la base, impacto y tasa por proveedor para cada regla."""
    base = df["valido_demanda"]
    n_base = int(base.sum())
    viajes_proveedor = df.loc[base, "VendorID"].value_counts()
    filas = []
    for columna, (nombre, descripcion, metodo_impacto) in REGLAS.items():
        marca = df[columna]
        impacto = df[columna.replace("a_", "impacto_", 1)]
        fila = {
            "regla": nombre,
            "columna": columna,
            "descripcion": descripcion,
            "metodo_impacto": metodo_impacto,
            "viajes": int(marca.sum()),
            "pct_base": marca.sum() / n_base * 100,
            "impacto_usd": float(impacto[marca].sum()),
            "impacto_mediano_usd": float(impacto[marca].median()) if marca.any() else 0.0,
        }
        casos_proveedor = df.loc[marca, "VendorID"].value_counts()
        for vendor_id in config.PROVEEDORES:
            casos = int(casos_proveedor.get(vendor_id, 0))
            fila[f"casos_v{vendor_id}"] = casos
            fila[f"tasa_10k_v{vendor_id}"] = casos / viajes_proveedor.get(vendor_id, 1) * 10_000
        filas.append(fila)
    return pd.DataFrame(filas)
