"""Preserve the legacy student-fixture command after moving implementation to scripts.

File: sqlite.py
Maintainer: sunshine-engineer
Modified: 2026-10-23

Run python sqlite.py --output /tmp/student-demo.db, or prefer
python -m scripts.build_student. Importing this shim does not modify a database.
"""

from scripts.build_student import main

if __name__ == "__main__":
    raise SystemExit(main())
