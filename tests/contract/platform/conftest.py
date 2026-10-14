"""Put this directory on sys.path so the helpers import by bare name."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
