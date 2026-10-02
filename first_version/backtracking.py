import duckdb
con = duckdb.connect("lastmile.duckdb", read_only=True)

# --- Indice de backtracking par tournée ---
print(con.sql("""
WITH sequence_zones AS (
    SELECT seq.route_id,
           seq.visit_order,
           COALESCE(left(s.zone_id, length(s.zone_id) - 1), 'INCONNUE') AS zone,
           LAG(COALESCE(left(s.zone_id, length(s.zone_id) - 1), 'INCONNUE'))
               OVER (PARTITION BY seq.route_id ORDER BY seq.visit_order) AS zone_precedente
    FROM sequences seq
    JOIN stops s ON s.route_id = seq.route_id AND s.stop_id = seq.stop_id
),
agg AS (
    SELECT route_id,
           COUNT(*) FILTER (WHERE zone IS DISTINCT FROM zone_precedente) AS nb_blocs,
           COUNT(DISTINCT zone)                                          AS nb_zones
    FROM sequence_zones
    GROUP BY route_id
)
SELECT
    round(AVG(nb_blocs - nb_zones), 2)  AS backtracking_moyen,
    round(MAX(nb_blocs - nb_zones), 0)  AS backtracking_max,
    COUNT(route_id)                                AS nb_routes
FROM agg
"""))

print(con.sql("""
WITH sequence_zones AS (
    SELECT seq.route_id, seq.visit_order,
           COALESCE(left(s.zone_id, length(s.zone_id) - 1), 'INCONNUE') AS zone,
           LAG(COALESCE(left(s.zone_id, length(s.zone_id) - 1), 'INCONNUE'))
               OVER (PARTITION BY seq.route_id ORDER BY seq.visit_order) AS zone_precedente
    FROM sequences seq
    JOIN stops s ON s.route_id = seq.route_id AND s.stop_id = seq.stop_id
),
agg AS (
    SELECT route_id,
           COUNT(*) FILTER (WHERE zone IS DISTINCT FROM zone_precedente) AS nb_blocs,
           COUNT(DISTINCT zone) AS nb_zones
    FROM sequence_zones GROUP BY route_id
),
bt AS (
    SELECT route_id, nb_blocs - nb_zones AS backtracking FROM agg
)
SELECT
    CASE
        WHEN backtracking <= 1 THEN 'a) 0-1  (propre)'
        WHEN backtracking <= 4 THEN 'b) 2-4  (modere)'
        WHEN backtracking <= 9 THEN 'c) 5-9  (eleve)'
        ELSE                        'd) 10+  (pathologique)'
    END                                    AS tranche,
    COUNT(*)                               AS nb_routes,
    round(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM bt
GROUP BY tranche
ORDER BY tranche
"""))
#les 16 routes zigzag
print(con.sql("""
WITH sequence_zones AS (
    SELECT seq.route_id, seq.visit_order,
           COALESCE(left(s.zone_id, length(s.zone_id) - 1), 'INCONNUE') AS zone,
           s.zone_id AS zone_brute,
           LAG(COALESCE(left(s.zone_id, length(s.zone_id) - 1), 'INCONNUE'))
               OVER (PARTITION BY seq.route_id ORDER BY seq.visit_order) AS zone_precedente
    FROM sequences seq
    JOIN stops s ON s.route_id = seq.route_id AND s.stop_id = seq.stop_id
),
agg AS (
    SELECT route_id,
           COUNT(*)                                                      AS nb_arrets,
           COUNT(*) FILTER (WHERE zone_brute IS NULL)                    AS nb_zones_nulles,
           COUNT(*) FILTER (WHERE zone IS DISTINCT FROM zone_precedente) AS nb_blocs,
           COUNT(DISTINCT zone)                                          AS nb_zones
    FROM sequence_zones GROUP BY route_id
)
SELECT route_id,
       nb_blocs - nb_zones                       AS backtracking,
       nb_arrets,
       nb_zones,
       nb_zones_nulles,
       round(100.0*nb_zones_nulles/nb_arrets, 0) AS pct_zone_nulle
FROM agg
ORDER BY backtracking DESC
LIMIT 16
"""))