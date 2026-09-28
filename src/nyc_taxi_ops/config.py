"""Rutas, fuentes de datos y parámetros de negocio del proyecto.

Todos los umbrales usados por las reglas de calidad, imputación y auditoría
viven en este módulo, de modo que cualquier cambio de criterio queda en un
solo lugar y se refleja por igual en el pipeline, los notebooks y el tablero.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parents[2]
DATA_RAW = RAIZ / "data" / "raw"
DATA_PROCESSED = RAIZ / "data" / "processed"
SITIO_DATA = RAIZ / "docs" / "data"
FIGURAS = RAIZ / "reports" / "figures"

ARCHIVO_VIAJES = DATA_RAW / "yellow_tripdata_2017-01.parquet"
ARCHIVO_ZONAS = DATA_RAW / "taxi_zone_lookup.csv"
ARCHIVO_PROCESADO = DATA_PROCESSED / "viajes_marcados.parquet"

# ---------------------------------------------------------------------------
# Fuentes. La TLC es la fuente oficial; el repositorio del curso queda como
# respaldo en caso de que el CDN de la TLC no esté disponible.
# ---------------------------------------------------------------------------
FUENTES = {
    ARCHIVO_VIAJES.name: [
        "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2017-01.parquet",
        "https://media.githubusercontent.com/media/Juanhv24/taxi-demand-project/main/data/raw/yellow_tripdata_2017-01.parquet",
    ],
    ARCHIVO_ZONAS.name: [
        "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
        "https://raw.githubusercontent.com/Juanhv24/taxi-demand-project/main/data/raw/taxi_zone_lookup%20(1).csv",
    ],
}

# ---------------------------------------------------------------------------
# Periodo y calendario
# ---------------------------------------------------------------------------
PERIODO_INICIO = "2017-01-01"
PERIODO_FIN = "2017-02-01"  # exclusivo
# Festivos federales del periodo: Año Nuevo observado (lunes 2) y Martin Luther
# King Jr. Day (lunes 16). El 1 de enero cae en domingo.
FESTIVOS = ("2017-01-02", "2017-01-16")

FRANJAS = {
    "Madrugada": range(0, 5),
    "Mañana": range(5, 12),
    "Tarde": range(12, 18),
    "Noche": range(18, 24),
}

# ---------------------------------------------------------------------------
# Tarifario de la TLC vigente en 2017 (tarifa estándar, RatecodeID = 1):
# banderazo de $2.50 y $0.50 por cada 1/5 de milla por encima de 12 mph, o
# $0.50 por cada 60 segundos en tráfico lento o detenido. Como el taxímetro
# cobra por distancia o por tiempo, pero nunca por ambos a la vez, la tarifa
# queda acotada entre 2.50 + 2.50·millas y 2.50 + 2.50·millas + 0.50·minutos.
# ---------------------------------------------------------------------------
BANDERAZO = 2.50
TARIFA_MILLA = 2.50
TARIFA_MINUTO = 0.50
TARIFA_PLANA_JFK = 52.00
# Holgura equivalente a dos saltos del taxímetro ($0.50 cada uno), para no
# marcar diferencias de redondeo o de medición del odómetro.
TOLERANCIA_TARIFA = 1.00

# ---------------------------------------------------------------------------
# Umbrales de validez
# ---------------------------------------------------------------------------
DURACION_MIN_MIN = 1.0  # por debajo no hay trayecto medible
DURACION_MAX_MIN = 180.0  # por encima domina el medidor sin cerrar (~23-24 h)
VELOCIDAD_MAX_MPH = 80.0
MONTO_MAX_PLAUSIBLE = 1_000.0  # tarifas mayores son errores de digitación
PASAJEROS_MAX = 6

# Viaje no realizado probable: sin distancia, menos de un minuto y cobro
# igual o cercano al banderazo.
NO_REALIZADO_TARIFA_MAX = 3.00

# Distancia atípica para la ruta (posible desvío): regla contextual robusta
# por par origen-destino.
RUTA_MIN_VIAJES = 30
RUTA_K_MAD = 5.0
RUTA_FACTOR_MEDIANA = 1.5
RUTA_EXCESO_MIN_MILLAS = 1.0

# ---------------------------------------------------------------------------
# Catálogos (diccionario de datos de la TLC)
# ---------------------------------------------------------------------------
PROVEEDORES = {1: "Creative Mobile Technologies", 2: "VeriFone"}
CODIGOS_TARIFA = {
    1: "Estándar",
    2: "JFK (tarifa plana)",
    3: "Newark",
    4: "Nassau / Westchester",
    5: "Negociada",
    6: "Viaje compartido",
    99: "Código inválido",
}
FORMAS_PAGO = {
    1: "Tarjeta",
    2: "Efectivo",
    3: "Sin cargo",
    4: "Disputa",
    5: "Desconocido",
    6: "Anulado",
}

ZONA_EWR = 1
ZONA_JFK = 132
ZONA_LGA = 138
ZONA_DESCONOCIDA = 264
ZONA_FUERA_NYC = 265
AEROPUERTOS = {ZONA_JFK: "JFK", ZONA_LGA: "LaGuardia", ZONA_EWR: "Newark"}
DISTRITOS_NYC = ("Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island")

SEMILLA = 42
