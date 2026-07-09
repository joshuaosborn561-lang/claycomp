from __future__ import annotations

import sys
from pathlib import Path

# Vercel runs from repo root; claycomp lives in src/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claycomp.web.app import app  # noqa: E402

# Vercel Python runtime (ASGI)
# https://vercel.com/docs/functions/runtimes/python
