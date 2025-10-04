import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBS = ROOT / "libs"

for package in ["calculator_core", "calculator_logic"]:
    package_src = LIBS / package / "src"
    if package_src.exists() and str(package_src) not in sys.path:
        sys.path.insert(0, str(package_src))
