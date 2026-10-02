# LastMile-Kaizen

**Where does the time go in an Amazon delivery and how can we minimize it?**

## Key findings : station DLA8
- A tour lasts **7.5h** on average: 2.26h driving + 5.26h service time
- Service time is almost entirely driven by **the number of packages** & other features only count for **6%** of predictive accuracy
- Drivers route efficiently (a greedy algorithm is **12%** worse)
- Routes are on average **6.7%** above a 2-opt optimised route

**Conclusion:** The routing problem is real but marginal: drivers are already **close to optimal** and driving is only **30%** of the day. The variables Amazon records can not explain the service time.
---

## Table of contents
1. [Context]
2. [Data]
3. [Architecture]
4. [Set Up]
5. [Phase 0: Pipeline]
6. [Measure: tour duration baseline]
7. [Analyze 1: service time]
8. [Analyze 2: backtracking index]
9. [Analyze 3: optimality gap]
10. [Limitations]
11. [Lessons learned]
12. [Roadmap]

---

## 1. Context
The Amazon Last Mile Routing Research Challenge released real delivery routes and asked participants to **reproduce the stop sequences of experienced drivers**. The winning used a local-search TSP solver from the LKH family.
This project takes a complementary angle: measure where the time actually goes, then use the same operations-research tools as a measuring instrument rather than as a route generato.
The work follows the DMAIC structure of Lean Six Sigma.

---

## 2. Data

* **Source:** `s3://amazon-last-mile-challenges/almrrc2021/`
* **Licence:** Creative Commons BY-NC 4.0
* **Coverage:** 6,112 routes from 17 stations
| `route_data.json` | 75 MB | route metadata + nested stops (coordinates, type, zone) |
| `package_data.json` | 358 MB | packages per stop: scan status, time window, planned service time, dimensions |
| `travel_times.json` | **1.7 GB** | full stop-to-stop travel-time matrix of every route |
| `actual_sequences.json` | 9 MB | visit order actually driven |

The files are **monolithic** (all routes in one JSON object) and **deeply nested** (route → stop → package → sub-dictionaries).

---

## 3.Architecture
```
lastmile-kaizen/
├── pyproject.toml
├── README.md
├── samples/                      # tiny versions of the 4 files (tracked, used by tests)
├── data/                         # real files (git-ignored)
├── src/lastmile_kaizen/
│   ├── config.py                 
│   ├── cli.py                    
│   ├── ingestion/
│   │   ├── sanitizer.py          # JsonSanitizer: streaming NaN -> null
│   │   ├── extractors.py         # BaseExtractor + one subclass per table
│   │   └── pipeline.py           # ETLPipeline: extract -> flatten -> load
│   ├── storage/
│   │   └── warehouse.py          # Warehouse: DuckDB gateway (context manager)
│   ├── analysis/
│   │   ├── tour_duration.py      # TourDurationAnalyzer (Measure)
│   │   ├── service_profile.py    # ServiceTimeProfiler (distribution, cleaning impact)
│   │   ├── features.py           # FeatureBuilder (stop-level training table)
│   │   └── backtracking.py       # BacktrackingAnalyzer (zone re-entries)
│   ├── modeling/
│   │   └── service_model.py      # ServiceTimeModel (feature-set comparison)
│   └── optimization/
│       ├── tour.py               # TravelMatrix, Tour (graph model, objective function)
│       ├── heuristics.py         # TourHeuristic -> NearestNeighbor, TwoOpt (Strategy)
│       └── gap.py                # OptimalityGapAnalyzer
└── tests/                        # 78 pytest tests
```
