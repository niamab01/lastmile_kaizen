import duckdb
con = duckdb.connect("lastmile.duckdb", read_only=True)

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