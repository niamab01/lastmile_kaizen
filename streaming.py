import ijson
import duckdb
import pandas as pd
import io

from sanitizer import JsonSanitizer


def to_float(x):
    return None if x is None else float(x)  

Stations = {"DLA8"}

keep = set()
lignes = []
with open("data/route_data.json", "rb") as f:      # ← note le "rb" (lecture binaire)
    for route_id, src in ijson.kvitems(JsonSanitizer(f), ""):
        if src["station_code"] not in Stations:
            continue                       # route d'une autre station -> on l'ignore
        keep.add(route_id)
        ligne = {}
        ligne["station_code"]   = src["station_code"]
        ligne["date"]           = src["date_YYYY_MM_DD"]
        ligne["departure_time"] = src["departure_time_utc"]
        ligne["capacity_cm3"]   = int(src["executor_capacity_cm3"])
        ligne["route_score"]    = src["route_score"]
        ligne["route_id"] = route_id
        lignes.append(ligne)

stops = []
with open("data/route_data.json", "rb") as f:
    for route_id, src in ijson.kvitems(JsonSanitizer(f), ""): 
        if route_id not in keep:
            continue        
        for stop_id, s in src["stops"].items():  # boucle intérieure : chaque arrêt de CETTE route
            ligne = {}
            ligne["route_id"]  = route_id        # vient de la boucle extérieure
            ligne["stop_id"]   = stop_id         # vient de la boucle intérieure
            ligne["lat"]       = to_float(s["lat"])
            ligne["lng"] = to_float(s["lng"])
            ligne["stop_type"] = s["type"]
            ligne["zone_id"] = s["zone_id"]
            stops.append(ligne)


travel_times = []

with open("data/travel_times.json", "rb") as f:      # ← note le "rb" (lecture binaire)
    for route_id, matrix in ijson.kvitems(JsonSanitizer(f), ""):
        if route_id not in keep:
            continue      
        for from_stop, destinations in matrix.items():
            for to_stop, seconds in destinations.items():
                ligne = {}
                ligne["route_id"]  = route_id
                ligne["from_stop"] = from_stop
                ligne["to_stop"]   = to_stop
                ligne["seconds"]   = to_float(seconds)
                travel_times.append(ligne)


packages = []
with open("data/package_data.json", "rb") as f:
    for route_id, stops_d in ijson.kvitems(JsonSanitizer(f), ""):
        if route_id not in keep:
            continue     
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

sequences = []

with open("data/actual_sequences.json", "rb") as f:      # rb + ijson, comme les autres
    for route_id, seq in ijson.kvitems(JsonSanitizer(f), ""):
        if route_id not in keep:
            continue
        for stop_id, order in seq["actual"].items():
            ligne = {}
            ligne["route_id"] = route_id
            ligne["stop_id"] = stop_id
            ligne["visit_order"] = int(order) 
            sequences.append(ligne)


# 2) ouvrir une connexion DuckDB (en mémoire, rien sur le disque)
con = duckdb.connect("lastmile.duckdb")

con.register("routes_df",       pd.DataFrame(lignes))
con.register("stops_df",        pd.DataFrame(stops))
con.register("packages_df",     pd.DataFrame(packages))
con.register("travel_times_df", pd.DataFrame(travel_times))
con.register("sequences_df", pd.DataFrame(sequences))

# vérifie les 4 comptes d'un coup :
for t in ["routes", "stops", "packages", "travel_times", "sequences"]:
    con.execute(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM {t}_df")

print(con.sql("""
    SELECT a.route_id, SUM(tt.seconds) AS duree_s
    FROM sequences a
    JOIN sequences b ON a.route_id = b.route_id AND b.visit_order = a.visit_order + 1
    JOIN travel_times tt ON tt.route_id = a.route_id AND tt.from_stop = a.stop_id AND tt.to_stop = b.stop_id
    GROUP BY a.route_id
    ORDER BY duree_s DESC
    LIMIT 5
"""))

# et un résumé sur toute la station :
print(con.sql("""
    WITH d AS (
        SELECT a.route_id, SUM(tt.seconds) AS duree_s
        FROM sequences a
        JOIN sequences b ON a.route_id=b.route_id AND b.visit_order=a.visit_order+1
        JOIN travel_times tt ON tt.route_id=a.route_id AND tt.from_stop=a.stop_id AND tt.to_stop=b.stop_id
        GROUP BY a.route_id
    )
    SELECT count(*) AS nb_routes,
           round(avg(duree_s)/3600, 2) AS duree_moyenne_h,
           round(min(duree_s)/3600, 2) AS min_h,
           round(max(duree_s)/3600, 2) AS max_h
    FROM d
"""))
con.close()
#token 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
