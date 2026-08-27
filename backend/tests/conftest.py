"""Shared pytest configuration."""
import sys
from pathlib import Path

# Ensure backend/ is on the path so `import app...` works.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
