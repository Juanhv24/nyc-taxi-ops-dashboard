<!-- Textos interpretativos que el tablero muestra al inicio de cada pestaña. -->
<!-- Cada encabezado corresponde a una pestaña; se admite **negrita** y una sección vacía no se muestra. -->

## demanda

La demanda responde a dos calendarios distintos: en los días laborables se concentra en los horarios de entrada y salida laboral, con el pico más alto a las 19:00 de los viernes, mientras que los fines de semana la actividad se traslada a la noche y la madrugada, cuando se registran en promedio más de tres veces los viajes de un día laborable a la misma hora.

Sin embargo, las horas y zonas con más viajes no son las más productivas, ya que el ingreso por hora de servicio sigue casi exactamente a la velocidad (correlación de 0.99). De esta forma, las horas congestionadas del día laboral generan cerca de **$57 por hora ocupada**, frente a cerca de $90 en la madrugada, y los aeropuertos, que representan el 6.2% de los viajes, aportan el **20.3% del ingreso**.

## integridad

El tarifario de la TLC se cumple en el 99.99% de los viajes estándar, por lo que un viaje por fuera de la banda representa una inconsistencia real y no un valor extremo legítimo. A partir de esta y otras seis reglas, se marcó el 0.67% de la base analítica.

Por un lado, los patrones más claros se concentran en un solo proveedor: el **100% de los totales que no concilian es de VeriFone**, casi siempre con una diferencia de $1.95, y las tarifas por debajo del mínimo son **8.9 veces más frecuentes en Creative Mobile Technologies**, lo que apunta a fallas técnicas más que a los conductores. Por otro lado, los 1,702 viajes dentro de la ciudad cobrados con la tarifa suburbana reproducen el patrón de sobrecobro que la TLC documentó en 2010 (NBC News, 2010), por lo que son la prioridad para una revisión caso a caso.

## calidad

El Dataset presenta problemas puntuales y bien delimitados, ya que tras excluir solo los registros que no representan un servicio prestado la base conserva el 99.62% de los viajes. Adicionalmente, los 4,544 "duplicados" del proyecto del curso resultaron ser **anulaciones** (un cargo y su reverso, que suman $0), y los viajes con distancia cero se separaron en tres situaciones con tratamientos distintos.

Finalmente, para la distancia faltante de los viajes taximetrados, la regresión sobre tarifa y duración redujo el error a **0.19 millas**, frente a 1.53 de la mediana global, dado que aprovecha que el taxímetro calcula la tarifa a partir de la distancia y del tiempo.
