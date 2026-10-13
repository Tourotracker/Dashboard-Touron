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
| SEUR_ESP … DHL_POR | Bultos expedidos por agencia y país (desde octubre de 2026) |
| FUENTE | Excel original o correo LIBRA |
| NOTA | Correcciones (5 fechas mal tecleadas en el Excel se corrigieron según su semana y día) |

Origen hasta el 09/10/2026: Excel *Seguimiento_tareas_y_expediciones_v1.xlsx*, hoja "Datos LIBRA".
