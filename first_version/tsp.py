import duckdb
con = duckdb.connect("lastmile.duckdb", read_only=True)

ROUTE = "RouteID_6170d139-b870-424e-9b66-c64608b12925"   # la route complète que tu viens de trouver

# les arrêts de cette route, dans l'ordre RÉEL de visite
arrets = con.execute("""
    SELECT stop_id
    FROM sequences
    WHERE route_id = ?
    ORDER BY visit_order
""", [ROUTE]).df()["stop_id"].tolist()

print("Nombre d'arrêts :", len(arrets))
print("Ordre réel (10 premiers) :", arrets[:10])
# charger tous les temps de trajet de cette route, dans un dictionnaire
lignes = con.execute("""
    SELECT from_stop, to_stop, seconds
    FROM travel_times
    WHERE route_id = ?
""", [ROUTE]).df()

# construire le dictionnaire : (depart, arrivee) -> secondes
temps = {}
for _, row in lignes.iterrows():
    temps[(row["from_stop"], row["to_stop"])] = row["seconds"]

print("Nombre de paires chargées :", len(temps))
# test : le temps entre les deux premiers arrêts réels
print("EC -> MS :", temps[("EC", "MS")], "s")

def cout_total(ordre, temps):
    total = 0
    for i in range(len(ordre) - 1):      # on s'arrête à l'avant-dernier
        depart  = ordre[i]
        arrivee = ordre[i + 1]
        total += temps[(depart, arrivee)]                   # <-- à toi : le temps de depart vers arrivee
    return total

# test : le coût de l'ordre RÉEL du chauffeur
cout_reel = cout_total(arrets, temps)
print("Temps de trajet réel (ordre chauffeur) :", round(cout_reel), "s", f"({cout_reel/3600:.2f} h)")

def plus_proche_voisin(arrets, temps):
    depart = arrets[0]                       # on part du 1er arrêt (la station)
    tournee = [depart]                       # la tournée qu'on construit
    a_visiter = set(arrets[1:])              # tous les autres, pas encore visités

    courant = depart
    while a_visiter:                         # tant qu'il reste des arrêts
        # trouver, parmi 'a_visiter', celui au temps minimal depuis 'courant'
        prochain = min(a_visiter, key=lambda candidat: temps[(courant, candidat)])
        tournee.append(prochain)             # on l'ajoute à la tournée
        a_visiter.remove(prochain)               # on le retire des restants
        courant = prochain                   # on se déplace vers lui
    return tournee

# test
tournee_ppv = plus_proche_voisin(arrets, temps)
cout_ppv = cout_total(tournee_ppv, temps)
print("Temps plus proche voisin :", round(cout_ppv), "s", f"({cout_ppv/3600:.2f} h)")
print("Temps réel (chauffeur)   :", round(cout_reel), "s", f"({cout_reel/3600:.2f} h)")

def deux_opt(ordre, temps):
    meilleur = ordre[:]                 # copie de l'ordre de départ
    cout_meilleur = cout_total(meilleur, temps)
    amelioration = True

    while amelioration:                 # on recommence tant qu'on a amélioré
        amelioration = False
        # on essaie d'inverser chaque segment possible (i, j)
        for i in range(1, len(meilleur) - 1):        # i >= 1 : on ne touche pas au départ (station)
            for j in range(i + 1, len(meilleur)):
                candidat = meilleur[:i] + meilleur[i:j+1][::-1] + meilleur[j+1:]
                cout_candidat = cout_total(candidat, temps)
                if cout_candidat < cout_meilleur:    # si c'est plus court
                    meilleur = candidat              # on adopte
                    cout_meilleur = cout_candidat
                    amelioration = True              # on a amélioré -> on refera un tour
    return meilleur, cout_meilleur


# --- test sur notre route ---
ordre_opt, cout_opt = deux_opt(arrets, temps)

print("Temps réel (chauffeur)   :", round(cout_reel), "s", f"({cout_reel/3600:.2f} h)")
print("Temps 2-opt (optimisé)   :", round(cout_opt),  "s", f"({cout_opt/3600:.2f} h)")
ecart = cout_reel - cout_opt
print(f"Écart : {round(ecart)} s ({ecart/60:.1f} min, soit {100*ecart/cout_reel:.1f} %)")

import time

# un échantillon de routes de tailles variées
echantillon = con.execute("""
    WITH tailles AS (
        SELECT route_id, COUNT(*) AS n
        FROM sequences GROUP BY route_id
    )
    SELECT route_id, n FROM tailles
    ORDER BY n
    LIMIT 5
""").df()
print("Routes les plus petites :")
print(echantillon)
def charge_route(route_id):
    arrets = con.execute(
        "SELECT stop_id FROM sequences WHERE route_id = ? ORDER BY visit_order",
        [route_id]).df()["stop_id"].tolist()
    lignes = con.execute(
        "SELECT from_stop, to_stop, seconds FROM travel_times WHERE route_id = ?",
        [route_id]).df()
    temps = {(r["from_stop"], r["to_stop"]): r["seconds"] for _, r in lignes.iterrows()}
    return arrets, temps

def chrono_route(route_id):
    arrets, temps = charge_route(route_id)
    t0 = time.time()
    _, cout_opt = deux_opt(arrets, temps)
    duree = time.time() - t0
    cout_reel = cout_total(arrets, temps)
    ecart_pct = 100 * (cout_reel - cout_opt) / cout_reel
    print(f"  {len(arrets):>3} arrêts | 2-opt en {duree:6.2f}s | écart {ecart_pct:4.1f}%")
    return duree

routes_test = [
    "RouteID_6cebaf24-0a39-4a6b-825e-df5e9002a1b1",   # 49 arrêts (petite)
    "RouteID_df379372-5387-4fa7-8928-eeae15d55db6",   # 61 arrêts (petite-moyenne)
    "RouteID_6170d139-b870-424e-9b66-c64608b12925",   # 194 arrêts (la plus grosse)
]

print("Chronométrage :")
total = 0
for rid in routes_test:
    total += chrono_route(rid)
print(f"\nEstimation grossière pour 448 routes : {total/len(routes_test)*448/60:.0f} min")

# récupérer TOUTES les routes de DLA8
toutes_routes = con.execute("SELECT DISTINCT route_id FROM sequences").df()["route_id"].tolist()
print(f"{len(toutes_routes)} routes à traiter...")

resultats = []
for n, rid in enumerate(toutes_routes, 1):
    arrets, temps = charge_route(rid)
    cout_reel = cout_total(arrets, temps)
    _, cout_opt = deux_opt(arrets, temps)
    resultats.append({
        "route_id":  rid,
        "n_arrets":  len(arrets),
        "reel_s":    cout_reel,
        "opt_s":     cout_opt,
        "ecart_s":   cout_reel - cout_opt,
        "ecart_pct": 100 * (cout_reel - cout_opt) / cout_reel,
    })
    if n % 50 == 0:                       # un point tous les 50, pour suivre l'avancement
        print(f"  {n}/{len(toutes_routes)} routes traitées")

import pandas as pd
res = pd.DataFrame(resultats)
print("\n=== Synthèse des écarts sur DLA8 ===")
print(f"Écart moyen        : {res['ecart_pct'].mean():.1f} %")
print(f"Écart médian       : {res['ecart_pct'].median():.1f} %")
print(f"Temps total récupérable : {res['ecart_s'].sum()/3600:.1f} h sur l'ensemble des tournées")