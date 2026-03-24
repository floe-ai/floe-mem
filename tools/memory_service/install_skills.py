from __future__ import annotations

import sys
from pathlib import Path

if __package__:
    from .installer import main
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.memory_service.installer import main


if __name__ == "__main__":
    raise SystemExit(main())
