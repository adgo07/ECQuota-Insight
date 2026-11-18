"""焦炭完整主应用开发入口。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from uebench.coke_candidate import main
if __name__ == "__main__":
    raise SystemExit(main())
