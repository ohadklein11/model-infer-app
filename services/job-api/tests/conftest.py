import sys
from pathlib import Path

# Ensure the service directory (one level up from tests) is on sys.path
CURRENT_DIR = Path(__file__).resolve().parent
SERVICE_DIR = CURRENT_DIR.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))
