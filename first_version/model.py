import duckdb, pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

con = duckdb.connect("lastmile.duckdb", read_only=True)
df = con.execute("SELECT * FROM features").df()

cible = "service_total_s"
y = df[cible]

def evalue(colonnes_features, nom):
    X = df[colonnes_features]
    cols_texte = [c for c in colonnes_features if not pd.api.types.is_numeric_dtype(df[c])]
    X = pd.get_dummies(X, columns=cols_texte)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    m = HistGradientBoostingRegressor(random_state=42)
    m.fit(X_train, y_train)
    mae = mean_absolute_error(y_test, m.predict(X_test))
    print(f"{nom:<32} MAE : {mae:.0f} s")

evalue(["nb_colis"],                                                 "1. Baseline (nb_colis)")
evalue(["nb_colis", "volume_total_l", "visit_order", "zone_prefix"], "2. + lettre (zone_prefix)")
evalue(["nb_colis", "volume_total_l", "visit_order", "sous_zone_groupee"], "3. + sous-zone groupee")