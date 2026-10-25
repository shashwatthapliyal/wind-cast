import json
from datetime import date, datetime, timezone
from pathlib import Path


class DataRepository:
    def __init__(self, path: Path):
        self.path = path

    def load(self, name: str) -> tuple[list[dict], datetime] | None:
        file = self.path / f"{name}.json"
        if not file.exists():
            return None
        payload = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
            raise ValueError("cache file must contain a records array")
        retrieved = datetime.fromisoformat(payload["retrievedAt"])
        if retrieved.tzinfo is None:
            raise ValueError("cache retrieval timestamp must include a timezone")
        return payload["records"], retrieved.astimezone(timezone.utc)

    def save(self, name: str, records: list[dict]) -> datetime:
        self.path.mkdir(parents=True, exist_ok=True)
        retrieved = datetime.now(timezone.utc)
        file = self.path / f"{name}.json"
        temporary_file = file.with_suffix(".json.tmp")
        temporary_file.write_text(
            json.dumps({"retrievedAt": retrieved.isoformat(), "records": records}),
            encoding="utf-8",
        )
        temporary_file.replace(file)
        return retrieved
