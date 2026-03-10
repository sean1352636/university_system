# refactored/utils/report_palette.py
from __future__ import annotations
from typing import List, Optional

DEFAULT_PALETTE: List[str] = [
    "#4C78A8", "#F58518", "#E45756", "#72B7B2", "#54A24B",
    "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
]

def get_report_palette(n: Optional[int] = None) -> List[str]:
    """
    Returns a color list. Uses matplotlib cycle if available, otherwise defaults.
    If n is given, repeats/truncates to length n.
    """
    palette = DEFAULT_PALETTE
    try:
        import matplotlib.pyplot as plt  # type: ignore
        cyc = plt.rcParams.get("axes.prop_cycle")
        if cyc:
            pal = cyc.by_key().get("color", [])
            if pal:
                palette = pal
    except Exception:
        pass

    if n and n > 0:
        k = len(palette)
        if k == 0:
            palette = DEFAULT_PALETTE
            k = len(palette)
        repeats = (n + k - 1) // k
        palette = (palette * repeats)[:n]
    return list(palette)

def color_at(idx: int, palette: Optional[List[str]] = None) -> str:
    pal = palette or DEFAULT_PALETTE
    if not pal:
        pal = DEFAULT_PALETTE
    return pal[idx % len(pal)]
