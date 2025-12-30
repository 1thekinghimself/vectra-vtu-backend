import json
from pathlib import Path
from typing import List, Dict, Optional


class ProgressRegister:
    """Simple local progress register persisted to a JSON file.

    Usage:
        reg = ProgressRegister('.progress.json')
        reg.add_step('Write tests')
        reg.complete_step(1)
        print(reg.list_steps())
    """

    def __init__(self, path: str = ".progress.json"):
        self.path = Path(path)
        self._data = {"steps": []}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except Exception:
                self._data = {"steps": []}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def _next_id(self) -> int:
        if not self._data["steps"]:
            return 1
        return max(s["id"] for s in self._data["steps"]) + 1

    def add_step(self, title: str, status: str = "not-started") -> Dict:
        step = {"id": self._next_id(), "title": title, "status": status}
        self._data["steps"].append(step)
        self._save()
        return step

    def list_steps(self) -> List[Dict]:
        return list(self._data["steps"])

    def get_step(self, step_id: int) -> Optional[Dict]:
        for s in self._data["steps"]:
            if s["id"] == step_id:
                return s
        return None

    def update_step(self, step_id: int, *, title: Optional[str] = None, status: Optional[str] = None) -> Optional[Dict]:
        s = self.get_step(step_id)
        if not s:
            return None
        if title is not None:
            s["title"] = title
        if status is not None:
            s["status"] = status
        self._save()
        return s

    def complete_step(self, step_id: int) -> Optional[Dict]:
        return self.update_step(step_id, status="completed")

    def remove_step(self, step_id: int) -> bool:
        before = len(self._data["steps"])
        self._data["steps"] = [s for s in self._data["steps"] if s["id"] != step_id]
        changed = len(self._data["steps"]) != before
        if changed:
            self._save()
        return changed
