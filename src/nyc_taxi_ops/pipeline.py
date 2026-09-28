"""Orquestación: datos crudos → base marcada → agregados del tablero."""

import time

import pandas as pd
import pyarrow.parquet as pq

from . import auditoria, calidad, config, datos, imputacion


def construir_base(guardar: bool = True) -> pd.DataFrame:
    """Carga, marca calidad, imputa distancia y aplica las reglas de auditoría."""
    inicio = time.time()
    viajes = datos.cargar_viajes()
    zonas = datos.cargar_zonas()
    viajes = datos.unir_zonas(viajes, zonas)
    print(f"[1/4] {len(viajes):,} viajes cargados ({time.time() - inicio:.0f} s)")

    viajes = calidad.marcar_calidad(viajes)
    print(f"[2/4] reglas de calidad aplicadas ({time.time() - inicio:.0f} s)")

    viajes, coeficientes = imputacion.imputar_distancia(viajes)
    print(
        f"[3/4] {int(viajes['distancia_imputada'].sum()):,} distancias imputadas "
        f"(millas = {coeficientes[0]:.3f} + {coeficientes[1]:.3f}·tarifa "
        f"{coeficientes[2]:+.3f}·minutos) ({time.time() - inicio:.0f} s)"
    )

    viajes = auditoria.marcar_auditoria(viajes)
    viajes["ingreso"] = calidad.ingreso_servicio(viajes)
    print(f"[4/4] {int(viajes['a_alguna'].sum()):,} viajes marcados por auditoría ({time.time() - inicio:.0f} s)")

    if guardar:
        config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        viajes.to_parquet(config.ARCHIVO_PROCESADO, index=False)
        print(f"[ok] base guardada en {config.ARCHIVO_PROCESADO.relative_to(config.RAIZ)}")
    return viajes


def cargar_base(columnas: list[str] | None = None) -> pd.DataFrame:
    """Lee la base procesada (o solo algunas columnas); la construye si no existe."""
    if not config.ARCHIVO_PROCESADO.exists():
        base = construir_base()
        return base if columnas is None else base[columnas]
    tabla = pq.read_table(config.ARCHIVO_PROCESADO, columns=columnas)
    return tabla.to_pandas(self_destruct=True)
