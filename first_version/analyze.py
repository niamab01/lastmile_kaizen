import duckdb
con = duckdb.connect("lastmile.duckdb")

print(con.sql("""
WITH trajet AS (
    SELECT a.route_id, SUM(tt.seconds) AS travel_s
    FROM sequences a
    JOIN sequences b ON a.route_id=b.route_id AND b.visit_order=a.visit_order+1
    JOIN travel_times tt ON tt.route_id=a.route_id AND tt.from_stop=a.stop_id AND tt.to_stop=b.stop_id
    GROUP BY a.route_id
),
service AS (
    SELECT route_id, SUM(service_time_s) AS service_s
    FROM packages
    GROUP BY route_id
)
SELECT t.route_id,
       t.travel_s,
       s.service_s,
       t.travel_s + s.service_s AS total_s
FROM trajet t
JOIN service s ON t.route_id = s.route_id      -- relier les deux CTE par route
ORDER BY total_s DESC
LIMIT 5
"""))

print(con.sql("""
WITH trajet AS (
    SELECT a.route_id, SUM(tt.seconds) AS travel_s
    FROM sequences a
    JOIN sequences b ON a.route_id=b.route_id AND b.visit_order=a.visit_order+1
    JOIN travel_times tt ON tt.route_id=a.route_id AND tt.from_stop=a.stop_id AND tt.to_stop=b.stop_id
    GROUP BY a.route_id
),
service AS (
    SELECT route_id, SUM(service_time_s) AS service_s
    FROM packages GROUP BY route_id
),
par_route AS (
    SELECT t.route_id, t.travel_s, s.service_s, t.travel_s + s.service_s AS total_s
    FROM trajet t JOIN service s ON t.route_id = s.route_id
)
SELECT
    COUNT(route_id)                                        AS nb_routes,      -- compte les routes
    round(avg(travel_s)/3600, 2)                AS trajet_h,
    round(avg(service_s)/3600, 2)                    AS service_h,      -- moyenne du service
    round(avg(total_s)/3600, 2)                 AS total_h,
    round(100 * avg(service_s) / avg(total_s), 1) AS pct_service   -- part du service en %
FROM par_route
"""))

print(con.sql("""
    SELECT
        COUNT(*)                          AS n_colis,
        COUNT(DISTINCT service_time_s)    AS nb_valeurs_distinctes,   -- LA question clé
        round(MIN(service_time_s), 1)     AS min_s,
        round(MAX(service_time_s), 1)     AS max_s,
        round(AVG(service_time_s), 1)     AS moy_s,
        round(MEDIAN(service_time_s), 1)  AS median_s
    FROM packages
"""))

#valeurs aberrantes aux requetes précédentes: regarder les extrêmes
#les plus lents services
print(con.sql("""
    SELECT scan_status,
           round(service_time_s, 1)                       AS service_s,
           round(depth_cm*height_cm*width_cm/1000, 1)     AS volume_l
    FROM packages
    ORDER BY service_time_s DESC
    LIMIT 10
"""))
print(con.sql("""
    SELECT
        count(*)                                                   AS total,
        count(*) FILTER (WHERE scan_status = 'DELIVERED')          AS livres,
        count(*) FILTER (WHERE scan_status = 'DELIVERED'
                          AND service_time_s BETWEEN 5 AND 900)    AS livres_plausibles
    FROM packages
"""))
#les plus rapides services
print(con.sql("""
    SELECT scan_status, count(*) AS n, round(avg(service_time_s),1) AS moy_s
    FROM packages
    WHERE service_time_s < 5
    GROUP BY scan_status
"""))
#Périmètre d'analyse du temps de service : on ne retient que les colis effectivement livrés (scan_status = DELIVERED) avec un temps de service physiquement plausible (entre 5 s et 15 min). Cela écarte 1,7 % des colis — les tentatives de livraison (dont le temps ne reflète pas une livraison) et de rares valeurs aberrantes. 98,3 % des données sont conservées.

#Une ligne par arrêt: cible + deux features évidentes
print(con.sql("""
    SELECT
        route_id,
        stop_id,
        SUM(service_time_s)                          AS service_total_s,   -- la CIBLE
        COUNT(*)                                     AS nb_colis,          -- feature 1
        SUM(depth_cm*height_cm*width_cm)/1000        AS volume_total_l     -- feature 2
    FROM packages
    WHERE scan_status = 'DELIVERED'
      AND service_time_s BETWEEN 5 AND 900
    GROUP BY route_id, stop_id
    ORDER BY service_total_s DESC
    LIMIT 10
"""))


print(con.sql("""
    WITH par_arret AS (
        SELECT route_id, stop_id, SUM(service_time_s) AS service_total_s, COUNT(*) AS nb_colis
        FROM packages
        WHERE scan_status = 'DELIVERED' AND service_time_s BETWEEN 5 AND 900
        GROUP BY route_id, stop_id
    )
    SELECT a.route_id, a.stop_id,
       s.zone_id,
       split_part(s.zone_id, '-', 1)  AS zone_prefix,
       seq.visit_order,                         -- la nouvelle feature
       a.service_total_s, a.nb_colis
    FROM par_arret a
    JOIN stops s     ON a.route_id = s.route_id   AND a.stop_id = s.stop_id
    JOIN sequences seq ON seq.route_id = a.route_id AND seq.stop_id = a.stop_id 
    ORDER BY a.service_total_s DESC
    LIMIT 10
"""))

#valeur distincte de préfixes de zones
print(con.sql("""
    SELECT COUNT(DISTINCT zone_id)                    AS zones_completes,
           COUNT(DISTINCT split_part(zone_id, '-', 1)) AS grandes_zones
    FROM stops
"""))

#service en fonction de la zone
print(con.sql("""
    WITH par_arret AS (
        SELECT route_id, stop_id, SUM(service_time_s) AS service_total_s
        FROM packages
        WHERE scan_status = 'DELIVERED' AND service_time_s BETWEEN 5 AND 900
        GROUP BY route_id, stop_id
    )
    SELECT split_part(s.zone_id, '-', 1)        AS grande_zone,
           COUNT(*)                             AS nb_arrets,
           round(AVG(a.service_total_s), 0)     AS service_moyen_s
    FROM par_arret a
    JOIN stops s ON a.route_id = s.route_id AND a.stop_id = s.stop_id
    GROUP BY grande_zone
    ORDER BY service_moyen_s DESC
"""))
#mesurer la table actuelle: 56630
print(con.sql("""
WITH par_arret AS (
    SELECT route_id, stop_id, SUM(service_time_s) AS service_total_s, COUNT(*) AS nb_colis
    FROM packages
    WHERE scan_status = 'DELIVERED' AND service_time_s BETWEEN 5 AND 900
    GROUP BY route_id, stop_id
)
SELECT COUNT(*)
FROM par_arret a
JOIN stops s ON a.route_id = s.route_id AND a.stop_id = s.stop_id
"""))

#Construction de la table features
con.execute("""
CREATE OR REPLACE TABLE features AS
WITH par_arret AS (
    SELECT route_id, stop_id,
           SUM(service_time_s)                        AS service_total_s,   -- la CIBLE
           COUNT(*)                                   AS nb_colis,
           SUM(depth_cm * height_cm * width_cm)/1000  AS volume_total_l
    FROM packages
    WHERE scan_status = 'DELIVERED' AND service_time_s BETWEEN 5 AND 900
    GROUP BY route_id, stop_id
)
SELECT
    a.route_id,
    a.stop_id,
    a.service_total_s,                                              -- cible
    a.nb_colis,                                                     -- feature
    a.volume_total_l,                                               -- feature
    seq.visit_order,                                               -- feature
    COALESCE(NULLIF(split_part(s.zone_id, '-', 1), ''), 'INCONNUE') AS zone_prefix,  -- feature
    COALESCE(NULLIF(split_part(s.zone_id, '.', 1), ''), 'INCONNUE') AS sous_zone   -- 'G-13.2D' -> 'G-13'
FROM par_arret a
JOIN stops s       ON a.route_id = s.route_id   AND a.stop_id = s.stop_id
JOIN sequences seq ON seq.route_id = a.route_id AND seq.stop_id = a.stop_id  
""")

# vérification : le compte doit toujours être 56 630
print("Lignes dans features :", con.execute("SELECT COUNT(*) FROM features").fetchone()[0])
print(con.sql("SELECT * FROM features ORDER BY service_total_s DESC LIMIT 5"))
print(con.sql("SELECT stop_id, zone_prefix, sous_zone, nb_colis, service_total_s FROM features LIMIT 5"))

print("Lignes dans features :", con.execute("SELECT COUNT(*) FROM features").fetchone()[0])
print("Sous-zones distinctes :", con.execute("SELECT COUNT(DISTINCT sous_zone) FROM features").fetchone()[0])

con.execute("""
CREATE OR REPLACE TABLE features AS
WITH freq AS (
    SELECT sous_zone, COUNT(*) AS n
    FROM features
    GROUP BY sous_zone
)
SELECT
    f.*,                                                    -- toutes les colonnes existantes
    CASE WHEN fr.n >= 100 THEN f.sous_zone ELSE 'AUTRE' END AS sous_zone_groupee
FROM features f
JOIN freq fr ON f.sous_zone = fr.sous_zone
""")

print("Sous-zones groupées :", con.execute("SELECT COUNT(DISTINCT sous_zone_groupee) FROM features").fetchone()[0])
print(con.sql("SELECT sous_zone, sous_zone_groupee, COUNT(*) AS n FROM features GROUP BY 1,2 ORDER BY n LIMIT 5"))

#nombre de sous-zones fréquentes: définir si le seul est validé pour avoir des données exploitables 
print(con.sql("""
    WITH comptes AS (
        SELECT sous_zone, COUNT(*) AS n
        FROM features
        GROUP BY sous_zone
    )
    SELECT
        COUNT(*)                                   AS total_sous_zones,
        COUNT(*) FILTER (WHERE n >= 100)           AS frequentes,
        SUM(n)  FILTER (WHERE n >= 100)            AS arrets_couverts,
        round(100.0 * SUM(n) FILTER (WHERE n >= 100) / SUM(n), 1) AS pct_couverts
    FROM comptes
"""))
