import shutil
from pathlib import Path

class BackupStore:
    def copy(self, source: str | Path, destination: str | Path) -> Path:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target
