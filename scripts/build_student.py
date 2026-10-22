"""Build the legacy five-row synthetic student fixture in a new database.

File: scripts/build_student.py
Maintainer: sunshine-engineer
Modified: 2026-10-23

Example:
    python -m scripts.build_student --output /tmp/student-demo.db

The default output is student.db in the current working directory for compatibility
with the original script. An existing STUDENT table raises rather than appending
another copy of the fixture. The application uses the bundled database read-only.
"""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

STUDENT_ROWS = (
    ("sun", "Data Science", "A", 90),
    ("John", "Data Science", "B", 100),
    ("Mukesh", "Data Science", "A", 86),
    ("Jacob", "DEVOPS", "A", 50),
    ("Dipesh", "DEVOPS", "A", 35),
)


def main():
    """Create the legacy fixture at the explicitly selected command-line output path.

    Returns:
        int: Zero after the five rows have been committed and printed.

    Raises:
        sqlite3.Error: If the path cannot be opened or the STUDENT table already exists.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("student.db"))
    args = parser.parse_args()
    with closing(sqlite3.connect(args.output)) as connection, connection:
        connection.execute(
            "CREATE TABLE STUDENT(NAME VARCHAR(25), CLASS VARCHAR(25), "
            "SECTION VARCHAR(25), MARKS INT)"
        )
        connection.executemany("INSERT INTO STUDENT VALUES (?, ?, ?, ?)", STUDENT_ROWS)
        print("The inserted records are")
        for row in connection.execute("SELECT * FROM STUDENT"):
            print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
