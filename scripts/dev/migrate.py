#!/usr/bin/env python3
"""Run Alembic database migrations.

Usage:
  python scripts/dev/migrate.py upgrade          # migrate to latest
  python scripts/dev/migrate.py downgrade -1     # rollback one step
  python scripts/dev/migrate.py current          # show current revision
  python scripts/dev/migrate.py history          # show migration history
  python scripts/dev/migrate.py revision -m "msg"  # create new migration
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    alembic_cmd = sys.argv[1]
    extra = sys.argv[2:]

    cmd = ["alembic", alembic_cmd] + extra
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
