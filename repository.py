import sqlite3
import json

from typing import Any


class TelemetryRepository:
    def __init__(self, db_path: str = "telemetry.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    overall_band REAL NOT NULL,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def save_evaluation(self, student_id: str, overall_band: float, total_tokens: int, payload: dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO evaluations (student_id, overall_band, total_tokens, payload)
                VALUES (?, ?, ?, ?)
                """,
                (student_id, overall_band, total_tokens, json.dumps(payload, ensure_ascii=False))
            )
