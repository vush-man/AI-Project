"""In-memory notifications and CSV event/path logging."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Notification:
    t: float
    type: str
    priority: int | None
    vehicle_id: str | None
    incident_id: str | None
    message: str


class NotificationLog:
    def __init__(self, log_dir: str | Path | None = None):
        self.items: list[Notification] = []
        self.path_rows: list[dict] = []
        self.log_dir = Path(log_dir) if log_dir else None
        self._written_notifications = 0
        self._written_paths = 0
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self._initialize_csv("notifications.csv", list(Notification.__dataclass_fields__))
            self._initialize_csv("path_log.csv", ["t", "vehicle_id", "incident_id", "mode", "algorithm", "edge", "from_node", "to_node", "traffic_level", "action", "cost_so_far", "eta_remaining"])

    def _initialize_csv(self, name: str, fields: list[str]) -> None:
        with (self.log_dir / name).open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()

    def add(self, t: float, kind: str, message: str, priority=None, vehicle_id=None, incident_id=None) -> Notification:
        item = Notification(t, kind, priority, vehicle_id, incident_id, message)
        self.items.append(item)
        return item

    def path(self, **row) -> None:
        self.path_rows.append(row)

    def flush(self) -> None:
        if not self.log_dir:
            return
        for name, rows, fields, written in (
            ("notifications.csv", [asdict(x) for x in self.items], list(Notification.__dataclass_fields__), self._written_notifications),
            ("path_log.csv", self.path_rows, ["t", "vehicle_id", "incident_id", "mode", "algorithm", "edge", "from_node", "to_node", "traffic_level", "action", "cost_so_far", "eta_remaining"], self._written_paths),
        ):
            with (self.log_dir / name).open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                writer.writerows(rows[written:])
            if name == "notifications.csv":
                self._written_notifications = len(rows)
            else:
                self._written_paths = len(rows)

