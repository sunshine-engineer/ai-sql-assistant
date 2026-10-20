"""Versioned alternate synthetic instances, generated only in a fresh directory."""
from contextlib import closing
from pathlib import Path
import sqlite3
from .demo import build_demo

INSTANCES = ('base', 'skewed', 'zero_sales')


def build_instance(directory, name):
    if name not in INSTANCES:
        raise ValueError('Unknown instance.')
    path = Path(directory) / f'{name}.db'
    if path.exists():
        raise FileExistsError('Instances must be generated fresh, never mutated in place.')
    build_demo(path)
    if name == 'base':
        return path
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('PRAGMA foreign_keys=ON')
        if name == 'skewed':
            db.executemany('INSERT INTO customers VALUES (?,?,?)',
                           [(i, f'Synthetic extra {i}', None if i % 2 else 'South') for i in range(13, 20)])
            db.execute("UPDATE customers SET region=NULL WHERE customer_id IN (1,2,3)")
            db.execute('UPDATE order_items SET quantity=quantity+2 WHERE item_id % 3=0')
            db.execute("UPDATE orders SET status='cancelled' WHERE order_id % 7=0")
            db.execute('UPDATE refunds SET amount_cents=amount_cents/2 WHERE refund_id % 2=0')
            db.execute("INSERT INTO refunds SELECT (SELECT MAX(refund_id) FROM refunds)+1, 1, '2026-01-29', 37")
            db.execute('UPDATE targets SET target_cents=0 WHERE month=\'2026-02\'')
        else:
            db.execute('DELETE FROM refunds')
            db.execute('UPDATE order_items SET unit_price_cents=0')
            db.execute('UPDATE targets SET target_cents=0')
            db.execute('UPDATE customers SET region=NULL')
            db.execute('INSERT INTO customers VALUES (20,\'Synthetic empty customer\',NULL)')
        # Rebuild semantic facts from normalized tables, aggregating refunds before
        # joining. Tests compare these facts with independent raw-table oracles.
        db.execute('DELETE FROM sales_facts')
        db.execute('''INSERT INTO sales_facts
          SELECT i.item_id,o.order_id,o.customer_id,i.product_id,o.order_date,
                 substr(o.order_date,1,7),c.region,p.category,o.status,i.quantity,
                 CASE WHEN o.status='completed' THEN i.quantity*i.unit_price_cents ELSE 0 END,
                 COALESCE(r.amount,0),
                 CASE WHEN o.status='completed' THEN i.quantity*i.unit_price_cents ELSE 0 END-COALESCE(r.amount,0)
          FROM order_items i JOIN orders o ON i.order_id=o.order_id
          JOIN customers c ON c.customer_id=o.customer_id
          JOIN products p ON p.product_id=i.product_id
          LEFT JOIN (SELECT item_id,SUM(amount_cents) amount FROM refunds GROUP BY item_id) r ON r.item_id=i.item_id''')
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    return path
