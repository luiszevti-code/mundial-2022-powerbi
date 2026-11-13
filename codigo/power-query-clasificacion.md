# Power Query: orden de la tabla de posiciones

La tabla `Clasificacion` llega del Excel con una columna `posicion` que es un ranking general de los 32 equipos. Para mostrar una tabla de grupos (A a H, y dentro de cada grupo por posición) se agrega una columna `orden`.

Pasos agregados al final de la consulta `Clasificacion` (Editor avanzado):

```m
let
    Origen = Excel.Workbook(File.Contents("RUTA\mundial2022.xlsx"), null, true),
    tbl_Clasificacion_Table = Origen{[Item="tbl_Clasificacion",Kind="Table"]}[Data],
    #"Tipo cambiado" = Table.TransformColumnTypes(tbl_Clasificacion_Table,{{"posicion", Int64.Type}, {"equipo", type text}, {"grupo", type text}, {"puntos", Int64.Type}, {"gf", Int64.Type}, {"gc", Int64.Type}, {"dif_goles", Int64.Type}, {"pj", Int64.Type}, {"pg", Int64.Type}, {"pe", Int64.Type}, {"pp", Int64.Type}}),
    Ordenado = Table.Sort(#"Tipo cambiado", {
        {"grupo", Order.Ascending},
        {"puntos", Order.Descending},
        {"dif_goles", Order.Descending},
        {"gf", Order.Descending}
    }),
    Buffer = Table.Buffer(Ordenado),
    ConOrden = Table.AddIndexColumn(Buffer, "orden", 1, 1, Int64.Type)
in
    ConOrden
```

- `Table.Buffer` evita que el índice se numere antes de aplicar el orden.
- En el modelo, la columna `equipo` de `Clasificacion` se ordena por `orden` (Herramientas de columnas → Ordenar por columna).
- Desempate simplificado: puntos, diferencia de goles y goles a favor. La FIFA también considera el resultado entre los equipos empatados.

## Cambiar la ruta del Excel

`RUTA` debe apuntar al `mundial2022.xlsx` de tu equipo: Inicio → Transformar datos → Configuración de origen de datos → Cambiar origen.
