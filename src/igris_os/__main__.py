from __future__ import annotations

import multiprocessing

from .cli import main

multiprocessing.freeze_support()

raise SystemExit(main())
