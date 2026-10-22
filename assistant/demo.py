"""Deterministic retail fixture. All people, transactions and targets are synthetic.

File: assistant/demo.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import argparse
import calendar
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

DEMO_VERSION = "retail-v1"
AS_OF_DATE = "2026-05-01"
TABLES = ["customers", "products", "orders", "order_items", "refunds", "targets", "sales_facts"]
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE customers(customer_id INTEGER PRIMARY KEY, customer_name TEXT NOT NULL, region TEXT);
CREATE TABLE products(product_id INTEGER PRIMARY KEY, product_name TEXT NOT NULL, category TEXT NOT NULL, list_price_cents INTEGER NOT NULL);
CREATE TABLE orders(order_id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers, order_date TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE order_items(item_id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders, product_id INTEGER REFERENCES products, quantity INTEGER NOT NULL, unit_price_cents INTEGER NOT NULL);
CREATE TABLE refunds(refund_id INTEGER PRIMARY KEY, item_id INTEGER REFERENCES order_items, refund_date TEXT NOT NULL, amount_cents INTEGER NOT NULL);
CREATE TABLE targets(month TEXT NOT NULL, category TEXT NOT NULL, target_cents INTEGER NOT NULL, PRIMARY KEY(month,category));
CREATE TABLE sales_facts(item_id INTEGER PRIMARY KEY REFERENCES order_items, order_id INTEGER REFERENCES orders, customer_id INTEGER REFERENCES customers, product_id INTEGER REFERENCES products, order_date TEXT NOT NULL, month TEXT NOT NULL, region TEXT, category TEXT NOT NULL, status TEXT NOT NULL, quantity INTEGER NOT NULL, gross_sales_cents INTEGER NOT NULL, refund_cents INTEGER NOT NULL, net_revenue_cents INTEGER NOT NULL);
CREATE INDEX sales_date ON sales_facts(order_date);
CREATE INDEX sales_category ON sales_facts(category);
"""


def build_demo(path):
    """Create the versioned synthetic retail fixture, leaving an existing database untouched.

    Args:
        path: Output database path. An existing file is returned without version validation.

    Returns:
        Path: Location of the reproducible retail database.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    handle, temporary = tempfile.mkstemp(prefix="retail-", suffix=".db", dir=path.parent)
    os.close(handle)
    try:
        with closing(sqlite3.connect(temporary)) as db, db:
            db.executescript(SCHEMA)
            db.executemany(
                "INSERT INTO customers VALUES (?,?,?)",
                [
                    (
                        i,
                        f"Customer {i:03}",
                        None if i == 7 else ["North", "South", "East", "West"][(i - 1) % 4],
                    )
                    for i in range(1, 13)
                ],
            )
            products = [
                (1, "Keyboard", "Hardware", 5000),
                (2, "Monitor", "Hardware", 20000),
                (3, "Editor license", "Software", 12000),
                (4, "Backup license", "Software", 7000),
                (5, "Cable", "Accessories", 1000),
                (6, "Stand", "Accessories", 3000),
                (7, "Unused adapter", "Accessories", 2000),
            ]
            db.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
            order_id = item_id = refund_id = 0
            for month in range(1, 5):
                for category in ["Hardware", "Software", "Accessories"]:
                    target = {"Hardware": 650000, "Software": 500000, "Accessories": 160000}[
                        category
                    ]
                    db.execute(
                        "INSERT INTO targets VALUES (?,?,?)", (f"2026-{month:02}", category, target)
                    )
                for index in range(36):
                    order_id += 1
                    date = f"2026-{month:02}-{2 + index % 25:02}"
                    customer = 1 + index % 11  # Customer 12 deliberately has no orders.
                    status = "cancelled" if order_id % 10 == 0 else "completed"
                    db.execute(
                        "INSERT INTO orders VALUES (?,?,?,?)", (order_id, customer, date, status)
                    )
                    for offset in range(2):
                        item_id += 1
                        product = products[(index + offset + month) % 6]
                        quantity = 1 + (index + offset) % 3
                        price = product[3] + (month - 1) * 100
                        db.execute(
                            "INSERT INTO order_items VALUES (?,?,?,?,?)",
                            (item_id, order_id, product[0], quantity, price),
                        )
                        gross = quantity * price if status == "completed" else 0
                        refund = gross // 2 if gross and item_id % 11 == 0 else 0
                        if refund:
                            # Split refunds expose accidental fan-out in raw joins.
                            for amount in [refund // 2, refund - refund // 2]:
                                refund_id += 1
                                db.execute(
                                    "INSERT INTO refunds VALUES (?,?,?,?)",
                                    (refund_id, item_id, f"2026-{month:02}-28", amount),
                                )
                        region = (
                            None
                            if customer == 7
                            else ["North", "South", "East", "West"][(customer - 1) % 4]
                        )
                        db.execute(
                            "INSERT INTO sales_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                item_id,
                                order_id,
                                customer,
                                product[0],
                                date,
                                date[:7],
                                region,
                                product[2],
                                status,
                                quantity,
                                gross,
                                refund,
                                gross - refund,
                            ),
                        )
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        # Atomic publication without overwriting another process's completed fixture.
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def previous_month(month):
    """Return the calendar month immediately before the supplied ISO month.

    Args:
        month: Calendar month formatted as YYYY-MM.

    Returns:
        str: Prior calendar month formatted as YYYY-MM.
    """
    year, number = map(int, month.split("-"))
    return f"{year - (number == 1):04}-{12 if number == 1 else number - 1:02}"


def next_month(month):
    """Return the calendar month immediately after the supplied ISO month.

    Args:
        month: Calendar month formatted as YYYY-MM.

    Returns:
        str: Next calendar month formatted as YYYY-MM.
    """
    year, number = map(int, month.split("-"))
    calendar.monthrange(year, number)  # Reject invalid months.
    return f"{year + (number == 12):04}-{1 if number == 12 else number + 1:02}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/retail-v1.db"))
    print(build_demo(parser.parse_args().output))
