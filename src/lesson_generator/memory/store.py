"""Explainable SQLite run history and frequency-based failure guidance."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

class MemoryStore:
    def __init__(self, path="data/lesson_memory.sqlite3"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _initialize(self):
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, topic TEXT NOT NULL, status TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts(run_id TEXT NOT NULL, attempt INTEGER NOT NULL, lesson TEXT NOT NULL, evaluation_json TEXT NOT NULL, failed_criteria_json TEXT NOT NULL, feedback_json TEXT NOT NULL, successful_corrections_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(run_id, attempt), FOREIGN KEY(run_id) REFERENCES runs(run_id));
            """)

    @staticmethod
    def new_run_id(): return str(uuid4())

    def start_run(self, run_id, topic):
        with self._connect() as db:
            db.execute("INSERT INTO runs(run_id, topic, status, created_at) VALUES(?,?,?,?)", (run_id, topic, "running", datetime.now(timezone.utc).isoformat()))

    def record_attempt(self, run_id, attempt, lesson, evaluation, failed_criteria, feedback, successful_corrections=None):
        dump = evaluation.model_dump_json() if hasattr(evaluation, "model_dump_json") else json.dumps(evaluation)
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO attempts VALUES(?,?,?,?,?,?,?,?)", (run_id, attempt, lesson, dump, json.dumps(failed_criteria), json.dumps(feedback), json.dumps(successful_corrections or []), datetime.now(timezone.utc).isoformat()))

    def finish_run(self, run_id, status):
        with self._connect() as db: db.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))

    def history(self, run_id):
        with self._connect() as db:
            return [{"attempt": row[0], "lesson": row[1], "evaluation": json.loads(row[2]), "failed_criteria": json.loads(row[3]), "feedback": json.loads(row[4]), "successful_corrections": json.loads(row[5]), "timestamp": row[6]} for row in db.execute("SELECT attempt,lesson,evaluation_json,failed_criteria_json,feedback_json,successful_corrections_json,created_at FROM attempts WHERE run_id=? ORDER BY attempt", (run_id,))]

    def historical_guidance(self, topic, minimum_failures=2):
        """Return concise guidance for criteria failing at least twice in prior runs."""
        with self._connect() as db:
            rows = db.execute("SELECT a.failed_criteria_json,a.feedback_json FROM attempts a JOIN runs r USING(run_id) WHERE r.topic=? AND r.status IN ('approved','rejected')", (topic,)).fetchall()
        counts, instructions = {}, {}
        for failed_json, feedback_json in rows:
            for item in json.loads(failed_json):
                name = item["criterion"]
                counts[name] = counts.get(name, 0) + 1
            for line in json.loads(feedback_json):
                name = line.split(":", 1)[0]
                instructions.setdefault(name, line)
        return [f"Historical recurring issue ({counts[name]} prior failures): {instructions[name]}" for name in sorted(counts) if counts[name] >= minimum_failures and name in instructions]
