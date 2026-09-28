import ijson
import duckdb
import pandas as pd
import io

from sanitizer import JsonSanitizer

def to_float(x):
    return None if x is None else float(x)  

lignes = []
with open("routes_sample.json", "rb") as f:      # ← note le "rb" (lecture binaire)
    for route_id, src in ijson.kvitems(JsonSanitizer(f), ""):
        ligne = {}
        ligne["station_code"]   = src["station_code"]
        ligne["date"]           = src["date_YYYY_MM_DD"]
        ligne["departure_time"] = src["departure_time_utc"]
        ligne["capacity_cm3"]   = int(src["executor_capacity_cm3"])
        ligne["route_score"]    = src["route_score"]
        ligne["route_id"] = route_id
        lignes.append(ligne)
print(lignes)

stops = []
with open("routes_sample.json", "rb") as f:
    for route_id, src in ijson.kvitems(JsonSanitizer(f), ""):         # boucle extérieure : chaque route
        for stop_id, s in src["stops"].items():  # boucle intérieure : chaque arrêt de CETTE route
            ligne = {}
            ligne["route_id"]  = route_id        # vient de la boucle extérieure
            ligne["stop_id"]   = stop_id         # vient de la boucle intérieure
            ligne["lat"]       = to_float(s["lat"])
            ligne["lng"] = to_float(s["lng"])
            ligne["stop_type"] = s["type"]
            ligne["zone_id"] = s["zone_id"]
            stops.append(ligne)

print(len(stops)) 
print(stops)



travel_times = []

with open("travel_times_sample.json", "rb") as f:      # ← note le "rb" (lecture binaire)
    for route_id, matrix in ijson.kvitems(JsonSanitizer(f), ""):      # ← remplace json.load + la boucle B
        for from_stop, destinations in matrix.items():
            for to_stop, seconds in destinations.items():
                ligne = {}
                ligne["route_id"]  = route_id
                ligne["from_stop"] = from_stop
                ligne["to_stop"]   = to_stop
                ligne["seconds"]   = to_float(seconds)
                travel_times.append(ligne)

print(len(travel_times))   # toujours 13 ?



packages = []
with open("package_data_real.json", "rb") as f:
    for route_id, stops_d in ijson.kvitems(JsonSanitizer(f), ""):      # ← remplace json.load + la boucle B
        for stop_id, pkgs in stops_d.items():
            for package_id, p in pkgs.items():
                ligne = {}
                ligne["route_id"]       = route_id
                ligne["stop_id"]        = stop_id
                ligne["package_id"]     = package_id
                ligne["scan_status"]    = p["scan_status"]
                ligne["service_time_s"] = to_float(p["planned_service_time_seconds"])
            # sous-dictionnaire time_window -> DEUX colonnes :
                ligne["tw_start"]  = p["time_window"]["start_time_utc"]
                ligne["tw_end"]    = p["time_window"]["end_time_utc"]
            # sous-dictionnaire dimensions -> TROIS colonnes :
                ligne["depth_cm"]  = to_float(p["dimensions"]["depth_cm"])
                ligne["height_cm"] = to_float(p["dimensions"]["height_cm"])
                ligne["width_cm"]  = to_float(p["dimensions"]["width_cm"])
                packages.append(ligne)
print(len(packages))           
print(packages[1]["tw_start"])

sequences = []

with open("actual_sequences_sample.json", "rb") as f:      # rb + ijson, comme les autres
    for route_id, seq in ijson.kvitems(JsonSanitizer(f), ""):
        for stop_id, order in seq["actual"].items():
            ligne = {}
            ligne["route_id"] = route_id
            ligne["stop_id"] = stop_id
            ligne["visit_order"] = int(order) 
            sequences.append(ligne)


# 2) ouvrir une connexion DuckDB (en mémoire, rien sur le disque)
con = duckdb.connect()

con.register("routes",       pd.DataFrame(lignes))
con.register("stops",        pd.DataFrame(stops))
con.register("packages",     pd.DataFrame(packages))
con.register("travel_times", pd.DataFrame(travel_times))
con.register("sequences", pd.DataFrame(sequences))

# vérifie les 4 comptes d'un coup :
for t in ["routes", "stops", "packages", "travel_times", "sequences"]:
    print(t, con.sql(f"SELECT COUNT(*) FROM {t}").fetchone()[0])

#token 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
