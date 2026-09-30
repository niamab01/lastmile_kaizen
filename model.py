import duckdb
import pandas as pd
from sklearn.model_selection import train_test_split

# 1) charger la table features depuis la base
con = duckdb.connect("lastmile.duckdb", read_only=True)   # lecture seule : on ne fait que lire
df = con.execute("SELECT * FROM features").df()
print("Table chargée :", df.shape)                         # (56630, 7) attendu

# 2) séparer la CIBLE (ce qu'on prédit) des FEATURES (ce avec quoi on prédit)
cible = "service_total_s"
colonnes_features = ["nb_colis", "volume_total_l", "visit_order", "zone_prefix"]

X = df[colonnes_features]     # les features
y = df[cible]                 # la cible

# 3) séparer entraînement / test (80/20)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print("Entraînement :", X_train.shape, " | Test :", X_test.shape)

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

# --- BASELINE : prédire le service à partir du SEUL nb_colis ---
X_train_base = X_train[["nb_colis"]]     # une seule feature : le nombre de colis
X_test_base  = X_test[["nb_colis"]]

modele_base = LinearRegression()
modele_base.fit(X_train_base, y_train)                    # apprendre sur l'entraînement
pred_base = modele_base.predict(X_test_base)              # prédire sur le test

mae_base = mean_absolute_error(y_test, pred_base)
print(f"Baseline (nb_colis seul) — MAE : {mae_base:.0f} s")

from sklearn.ensemble import HistGradientBoostingRegressor

# --- transformer le texte (zone_prefix) en colonnes numériques ---
X_train_enc = pd.get_dummies(X_train, columns=["zone_prefix"])
X_test_enc  = pd.get_dummies(X_test,  columns=["zone_prefix"])

# aligner les colonnes des deux jeux (au cas où une zone rare manque d'un côté)
X_train_enc, X_test_enc = X_train_enc.align(X_test_enc, join="left", axis=1, fill_value=0)

# --- le vrai modèle, sur les 4 features ---
modele = HistGradientBoostingRegressor(random_state=42)
modele.fit(X_train_enc, y_train)
pred = modele.predict(X_test_enc)

mae = mean_absolute_error(y_test, pred)
print(f"Gradient boosting (4 features) — MAE : {mae:.0f} s")
print(f"Baseline — MAE : {mae_base:.0f} s")
print(f"Amélioration : {mae_base - mae:.0f} s ({100*(mae_base-mae)/mae_base:.0f} %)")