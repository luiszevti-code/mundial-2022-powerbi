# Medidas y columnas calculadas (DAX)

Todas las medidas se evalúan con el contexto del segmentador **equipo** (`Equipos[equipo]`), que filtra `Partidos` y `Estadisticas`.

## Medidas de las tarjetas

```DAX
Partidos jugados = DISTINCTCOUNT(Partidos[match_id])

Victorias = CALCULATE(COUNTROWS(Partidos), Partidos[resultado] = "Victoria")

% Victorias = DIVIDE([Victorias], COUNTROWS(Partidos))

Goles a favor = SUM(Partidos[goles_equipo])

Goles en contra = SUM(Partidos[goles_rival])

Goles por partido = DIVIDE([Goles a favor], [Partidos jugados])

Vallas invictas = CALCULATE(COUNTROWS(Partidos), Partidos[goles_rival] = 0)

Puntos grupos =
CALCULATE(
    SUMX(
        Partidos,
        SWITCH(Partidos[resultado], "Victoria", 3, "Empate", 1, 0)
    ),
    Partidos[fase] = "Group Stage"
)

Goleador =
CONCATENATEX(
    TOPN(1, Estadisticas, Estadisticas[goles], DESC),
    Estadisticas[jugador],
    ", "
)
```

| Medida | Qué calcula |
|---|---|
| Partidos jugados | Cuenta partidos distintos del equipo seleccionado |
| % Victorias | Victorias entre partidos jugados (los penales cuentan como empate) |
| Vallas invictas | Partidos en los que el rival no marcó (tiempo reglamentario y prórroga) |
| Puntos grupos | 3 por victoria, 1 por empate, solo en la fase de grupos |
| Goleador | Jugador con más goles del equipo (si hay empate, los concatena) |

## Columnas calculadas

```DAX
-- En Partidos: etiqueta del eje del gráfico de goles por partido
Etiqueta = FORMAT(Partidos[fecha], "dd/mm") & " vs " & Partidos[rival]

-- En Clasificacion: posición dentro del grupo (1 a 4), apoyada en la columna "orden"
Pos. =
VAR o = Clasificacion[orden]
RETURN
CALCULATE(
    COUNTROWS(Clasificacion),
    ALLEXCEPT(Clasificacion, Clasificacion[grupo]),
    Clasificacion[orden] <= o
)
```
