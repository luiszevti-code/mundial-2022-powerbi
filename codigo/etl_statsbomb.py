"""
ETL: StatsBomb Open Data (JSON)  ->  Excel con 4 tablas para Power BI
Competición por defecto: Mundial 2022 (competition_id=43, season_id=106)

Para usar otra competición cambia COMPETITION_ID y SEASON_ID
(los encuentras en data/competitions.json del repositorio).
"""
import json
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------
# PASO 0. Configuración
# ---------------------------------------------------------------
COMPETITION_ID = 43
SEASON_ID = 106
BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
CACHE = Path("cache_statsbomb")      # aquí guardamos los JSON descargados
CACHE.mkdir(exist_ok=True)
SALIDA = "mundial2022.xlsx"

# Código ISO de cada selección, solo para armar la URL de la bandera
# (en una liga de clubes aquí iría la URL del escudo de Transfermarkt)
ISO = {
    "Argentina": "ar", "Australia": "au", "Belgium": "be", "Brazil": "br",
    "Cameroon": "cm", "Canada": "ca", "Costa Rica": "cr", "Croatia": "hr",
    "Denmark": "dk", "Ecuador": "ec", "England": "gb-eng", "France": "fr",
    "Germany": "de", "Ghana": "gh", "Iran": "ir", "Japan": "jp",
    "Mexico": "mx", "Morocco": "ma", "Netherlands": "nl", "Poland": "pl",
    "Portugal": "pt", "Qatar": "qa", "Saudi Arabia": "sa", "Senegal": "sn",
    "Serbia": "rs", "South Korea": "kr", "Spain": "es", "Switzerland": "ch",
    "Tunisia": "tn", "United States": "us", "Uruguay": "uy", "Wales": "gb-wls",
}


# ---------------------------------------------------------------
# PASO 1. Función para leer un JSON (lo descarga una sola vez)
# ---------------------------------------------------------------
def leer_json(ruta_relativa):
    """Descarga data/<ruta_relativa> si no está en caché y devuelve el JSON."""
    archivo = CACHE / ruta_relativa.replace("/", "_")
    if not archivo.exists():
        r = requests.get(f"{BASE}/{ruta_relativa}", timeout=60)
        r.raise_for_status()
        archivo.write_bytes(r.content)
    return json.loads(archivo.read_text(encoding="utf-8"))


def a_minutos(reloj):
    """Convierte '64:10' en 64.17 minutos."""
    m, s = reloj.split(":")
    return int(m) + int(s) / 60


# ---------------------------------------------------------------
# PASO 2. Partidos: los JSON anidados se "aplanan" a una fila por partido
# ---------------------------------------------------------------
partidos_json = leer_json(f"matches/{COMPETITION_ID}/{SEASON_ID}.json")

filas = []
for m in partidos_json:
    filas.append({
        "match_id": m["match_id"],
        "fase": m["competition_stage"]["name"],
        "jornada": m["match_week"],
        "grupo": m["home_team"].get("home_team_group"),   # solo fase de grupos
        "fecha_hora": f'{m["match_date"]} {m["kick_off"][:8]}',
        "local": m["home_team"]["home_team_name"],
        "visitante": m["away_team"]["away_team_name"],
        "goles_local": m["home_score"],
        "goles_visitante": m["away_score"],
    })
base = pd.DataFrame(filas)

# ---------------------------------------------------------------
# PASO 3. Tabla PARTIDOS: pasamos de "una fila por partido" a
#         "una fila por equipo y partido" (como en el taller)
# ---------------------------------------------------------------
local = base.rename(columns={
    "local": "equipo", "visitante": "rival",
    "goles_local": "goles_equipo", "goles_visitante": "goles_rival"})
local["condicion"] = "Local"

visita = base.rename(columns={
    "visitante": "equipo", "local": "rival",
    "goles_visitante": "goles_equipo", "goles_local": "goles_rival"})
visita["condicion"] = "Visitante"

partidos = pd.concat([local, visita], ignore_index=True)

# Resultado y puntos (se calculan con condiciones vectorizadas)
partidos["resultado"] = "Empate"
partidos.loc[partidos.goles_equipo > partidos.goles_rival, "resultado"] = "Victoria"
partidos.loc[partidos.goles_equipo < partidos.goles_rival, "resultado"] = "Derrota"

# OJO: en algunos partidos StatsBomb deja el grupo vacío (p. ej. Marruecos-Croacia).
# Solución: armamos un diccionario equipo -> grupo con los datos que sí vienen
# y rellenamos el grupo de todos los partidos de fase de grupos.
grupo_de = (partidos.dropna(subset=["grupo"])
            .drop_duplicates("equipo").set_index("equipo")["grupo"])
es_grupos = partidos["fase"] == "Group Stage"
partidos.loc[es_grupos, "grupo"] = partidos.loc[es_grupos, "equipo"].map(grupo_de)

partidos = partidos[["match_id", "fase", "grupo", "jornada", "condicion",
                     "equipo", "rival", "fecha_hora",
                     "goles_equipo", "goles_rival", "resultado"]]
partidos = partidos.sort_values(["fecha_hora", "match_id", "condicion"]).reset_index(drop=True)

# ---------------------------------------------------------------
# PASO 4. Tabla EQUIPOS
# ---------------------------------------------------------------
equipos = pd.DataFrame({"equipo": sorted(partidos["equipo"].unique())})
equipos["escudo"] = equipos["equipo"].map(
    lambda e: f"https://flagcdn.com/w320/{ISO[e]}.png")

# ---------------------------------------------------------------
# PASO 5. Tabla CLASIFICACIÓN (solo fase de grupos)
# ---------------------------------------------------------------
g = partidos[partidos["fase"] == "Group Stage"].copy()
g["pts"] = g["resultado"].map({"Victoria": 3, "Empate": 1, "Derrota": 0})

clasif = g.groupby(["grupo", "equipo"]).agg(
    pj=("match_id", "count"),
    pg=("resultado", lambda s: (s == "Victoria").sum()),
    pe=("resultado", lambda s: (s == "Empate").sum()),
    pp=("resultado", lambda s: (s == "Derrota").sum()),
    gf=("goles_equipo", "sum"),
    gc=("goles_rival", "sum"),
    puntos=("pts", "sum"),
).reset_index()
clasif["dif_goles"] = clasif["gf"] - clasif["gc"]

# Orden: puntos, diferencia de goles, goles a favor (criterio simplificado)
clasif = clasif.sort_values(["puntos", "dif_goles", "gf"], ascending=False)
clasif.insert(0, "posicion", range(1, len(clasif) + 1))
clasif = clasif[["posicion", "equipo", "grupo", "puntos", "gf", "gc",
                 "dif_goles", "pj", "pg", "pe", "pp"]]

# ---------------------------------------------------------------
# PASO 6. Tabla ESTADÍSTICAS DE JUGADORES
#         Aquí hay que recorrer 64 archivos de alineaciones y 64 de eventos
# ---------------------------------------------------------------
reg = {}   # (jugador, equipo) -> acumulador de estadísticas


def jugador(nombre, equipo):
    return reg.setdefault((nombre, equipo), dict(
        partidos=0, titular=0, minutos=0.0, goles=0, asistencias=0))


for match_id in base["match_id"]:
    eventos = leer_json(f"events/{match_id}.json")
    alineaciones = leer_json(f"lineups/{match_id}.json")

    # Duración real del partido (incluye prórroga). Ignoramos la tanda
    # de penales (periodo 5) porque no cuenta como tiempo de juego.
    fin = max(e["minute"] + e["second"] / 60
              for e in eventos if e["period"] <= 4)

    # 6a. Minutos, partidos jugados y titularidades (de lineups)
    for equipo in alineaciones:
        for p in equipo["lineup"]:
            if not p["positions"]:        # estuvo en la lista pero no jugó
                continue
            r = jugador(p["player_name"], equipo["team_name"])
            r["partidos"] += 1
            if p["positions"][0]["start_reason"] == "Starting XI":
                r["titular"] += 1
            for pos in p["positions"]:
                desde = a_minutos(pos["from"])
                hasta = a_minutos(pos["to"]) if pos["to"] else fin
                r["minutos"] += hasta - desde

    # 6b. Goles y asistencias (de events)
    for e in eventos:
        if e["period"] == 5:               # tanda de penales: no cuenta
            continue
        tipo = e["type"]["name"]
        if tipo == "Shot" and e["shot"]["outcome"]["name"] == "Goal":
            jugador(e["player"]["name"], e["team"]["name"])["goles"] += 1
        elif tipo == "Pass" and e["pass"].get("goal_assist"):
            jugador(e["player"]["name"], e["team"]["name"])["asistencias"] += 1

estadisticas = (
    pd.DataFrame([{"jugador": j, "equipo": t, **v} for (j, t), v in reg.items()])
    .assign(minutos=lambda d: d["minutos"].round().astype(int))
)
estadisticas["goles_asistencias"] = estadisticas["goles"] + estadisticas["asistencias"]
estadisticas = estadisticas.rename(columns={"partidos": "partidos_jugados",
                                            "titular": "titularidades"})
estadisticas = estadisticas[["jugador", "equipo", "partidos_jugados",
                             "titularidades", "minutos", "goles",
                             "asistencias", "goles_asistencias"]]
estadisticas = estadisticas.sort_values(["goles_asistencias", "goles"],
                                        ascending=False).reset_index(drop=True)

# ---------------------------------------------------------------
# PASO 7. Exportar a Excel (una hoja por tabla)
# ---------------------------------------------------------------
with pd.ExcelWriter(SALIDA, engine="openpyxl") as xl:
    equipos.to_excel(xl, sheet_name="Equipos", index=False)
    partidos.to_excel(xl, sheet_name="Partidos", index=False)
    estadisticas.to_excel(xl, sheet_name="Estadisticas", index=False)
    clasif.to_excel(xl, sheet_name="Clasificacion", index=False)

print(f"Listo: {SALIDA}")
print(equipos.shape, partidos.shape, estadisticas.shape, clasif.shape)

# ---------------------------------------------------------------
# PASO 8. Dar formato de "Tabla de Excel" (Power BI las lista por nombre)
# ---------------------------------------------------------------
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.worksheet.table import Table, TableStyleInfo

wb = load_workbook(SALIDA)
for ws in wb.worksheets:
    ultima = f"{ws.cell(ws.max_row, ws.max_column).coordinate}"
    tabla = Table(displayName=f"tbl_{ws.title}", ref=f"A1:{ultima}")
    tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tabla)
    for col in ws.columns:                      # ancho de columna automático
        ancho = max(len(str(c.value)) for c in col if c.value is not None)
        ws.column_dimensions[col[0].column_letter].width = min(ancho + 3, 60)
    for fila in ws.iter_rows():
        for c in fila:
            c.font = Font(name="Arial", size=10, bold=c.row == 1,
                          color="FFFFFF" if c.row == 1 else "000000")
wb.save(SALIDA)
print("Formato de tablas aplicado")
