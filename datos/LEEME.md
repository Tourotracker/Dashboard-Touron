# Histórico LIBRA — archivo maestro

`historico_libra.csv` contiene **todos los días con actividad del almacén** desde abril de 2019
y se amplía automáticamente cada noche (lunes a viernes, 22:15) con el correo
"Control regular de tareas y líneas por zonas, y expediciones SEUR/DHL".

Se abre directamente con Excel (separador `;`, UTF-8).

| Columna | Contenido |
|---|---|
| TEMPORADA | Año LIBRA (octubre–septiembre). 27 = temporada 2026/27 |
| SEMANA | Semana de la temporada (la S1 empieza el lunes de la semana del 1 de octubre) |
| DIA | 1L, 2M, 3X, 4J, 5V |
| FECHA | dd/mm/aaaa |
| TAREAS, LINEAS | Totales del día |
| LINEAS_ARMARIOS | Solo en el histórico del Excel |
| LINEAS_CD | Líneas de Cross-Docking (zona 7) |
| Zx_TAREAS, Zx_LINEAS | Desglose por zona (desde octubre de 2026) |
| Z5_TAREAS, Z5_LINEAS | Zona 5 completa (desde el 13/10/2026): embarcaciones + productos de gran tamaño. Las líneas suman las dos partes, como el TOTAL de LIBRA |
| Z5_EMB_TAREAS, Z5_EMB_LINEAS | Parte de EMBARCACIONES de la zona 5 (el resto de líneas son productos de gran tamaño) |
| SEUR_ESP … DHL_POR | Bultos expedidos por agencia y país (desde octubre de 2026) |
| FUENTE | Excel original o correo LIBRA |
| NOTA | Correcciones (5 fechas mal tecleadas en el Excel se corrigieron según su semana y día; días del Excel corregidos con el correo LIBRA) |

Origen hasta el 09/10/2026: Excel *Seguimiento_tareas_y_expediciones_v1.xlsx*, hoja "Datos LIBRA".

Si llega un correo de LIBRA de un día que ya estaba cargado desde el Excel, **manda el correo**: se sobrescriben
totales, zonas y expediciones y se deja constancia en NOTA de los valores que tenía el Excel.
