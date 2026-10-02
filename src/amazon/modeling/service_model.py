from __future__ import annotations

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split


class ServiceTimeModel:
    """Evaluates several feature sets on the SAME train/test split."""

    TARGET = "service_total_s"
    FEATURE_SETS: dict[str, list[str]] = {
        "1. baseline (n_packages)": ["n_packages"],
        "2. + zone letter": ["n_packages", "volume_total_l", "visit_order", "zone_prefix"],
        "3. + grouped sub-zone": ["n_packages", "volume_total_l", "visit_order", "sub_zone_grouped"],
    }

    def __init__(self, features: pd.DataFrame, test_size: float = 0.2,
                 random_state: int = 42) -> None:
        self.features = features
        self.test_size = test_size
        self.random_state = random_state

    def _encode(self, columns: list[str]) -> pd.DataFrame:
        X = self.features[columns]
        # Detect text columns by "not numeric" (object AND pandas 'string' dtypes).
        text_cols = [c for c in columns if not pd.api.types.is_numeric_dtype(X[c])]
        return pd.get_dummies(X, columns=text_cols)

    def evaluate(self, columns: list[str]) -> float:
        X = self._encode(columns)
        y = self.features[self.TARGET]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, random_state=self.random_state
        )
        model = HistGradientBoostingRegressor(random_state=self.random_state)
        model.fit(X_train, y_train)
        return float(mean_absolute_error(y_test, model.predict(X_test)))

    def compare(self, feature_sets: dict[str, list[str]] | None = None) -> pd.DataFrame:
        sets = feature_sets or self.FEATURE_SETS
        rows = [{"model": name, "mae_s": self.evaluate(cols)} for name, cols in sets.items()]
        result = pd.DataFrame(rows)
        baseline = result["mae_s"].iloc[0]
        result["gain_vs_baseline_pct"] = (100 * (baseline - result["mae_s"]) / baseline).round(1)
        return result
