import os
import sys
from pathlib import Path

# Add project root and src directory to python search path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "src"))

from src.api import app
