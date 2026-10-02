from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


class Warehouse:
    """Owns the DuckDB connection. Use as a context manager so it is always closed.

    ``read_only=True`` for analysis (several readers may coexist);
    ``read_only=False`` only when a component materialises a table.
    """

    def __init__(self, db_path: str | Path, read_only: bool = False) -> None:
        self.db_path = Path(db_path)
        self.con = duckdb.connect(str(self.db_path), read_only=read_only)

    def __enter__(self) -> "Warehouse":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.con.close()

    def write_table(self, name: str, rows: list[dict]) -> None:
        """Materialise rows as a real table.

        ``register`` alone only creates a view on a Python object, which disappears
        with the process; ``CREATE TABLE ... AS SELECT`` copies the data into the file.
        """
        if not rows:
            raise ValueError(f"Refusing to write empty table '{name}'")
        frame = pd.DataFrame(rows)
        self.con.register("_staging", frame)
        try:
            self.con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM _staging')
        finally:
            self.con.unregister("_staging")

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        self.con.execute(sql, params or [])

    def query(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        return self.con.execute(sql, params or []).df()

    def fetchall(self, sql: str, params: list[Any] | None = None) -> list[tuple]:
        return self.con.execute(sql, params or []).fetchall()

    def scalar(self, sql: str, params: list[Any] | None = None) -> Any:
        return self.con.execute(sql, params or []).fetchone()[0]

    def count(self, table: str) -> int:
        return int(self.scalar(f'SELECT COUNT(*) FROM "{table}"'))
