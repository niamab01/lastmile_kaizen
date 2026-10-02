import json, ijson, tracemalloc, os, random

# 1) fabriquer un travel_times synthétique de taille moyenne (pour VOIR le ratio sans souffrir)
def make(n_routes, n_stops):
    d = {}
    for r in range(n_routes):
        stops = [f"{chr(65+i//26)}{chr(65+i%26)}" for i in range(n_stops)]
        d[f"RouteID_{r:04d}"] = {a: {b: round(random.random()*300, 1) for b in stops} for a in stops}
    return d

with open("tt_big.json", "w") as f:
    json.dump(make(800, 50), f)
size_mb = os.path.getsize("tt_big.json") / 1e6
print(f"Fichier sur disque : {size_mb:.1f} Mo")

# 2) MESURE 1 — json.load : tout en mémoire d'un coup
tracemalloc.start()
with open("tt_big.json") as f:
    d = json.load(f)
peak = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
print(f"json.load     -> pic RAM = {peak/1e6:.0f} Mo  (soit x{peak/1e6/size_mb:.1f} le fichier)")

# 3) MESURE 2 — ijson en streaming : une route à la fois
tracemalloc.start()
with open("tt_big.json", "rb") as f:
    for route_id, matrix in ijson.kvitems(f, ""):      # <-- remplace data.items()
        for from_stop, dests in matrix.items():
            for to_stop, seconds in dests.items():
                pass
peak2 = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
print(f"ijson stream  -> pic RAM = {peak2/1e6:.1f} Mo  (soit {peak/peak2:.0f}x moins)")

# 4) extrapolation au VRAI fichier de 1,7 Go
print(f"\nLe vrai fichier de 1700 Mo avec json.load demanderait ~ {1700*peak/1e6/size_mb/1000:.1f} Go de RAM")