
import ijson
from collections import Counter
from sanitizer import JsonSanitizer

compte = Counter()
with open("data/route_data.json", "rb") as f:
    for route_id, src in ijson.kvitems(JsonSanitizer(f), ""):
        compte[src["station_code"]] += 1

for station, n in compte.most_common():
    print(f"{station}  ->  {n} routes")