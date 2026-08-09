import csv
from pathlib import Path
from collections.abc import Iterable, Sequence

def write_csv(path: str | Path, headers: Sequence[str], rows: Iterable[Sequence[object]]) -> Path:
    target = Path(path)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return target
