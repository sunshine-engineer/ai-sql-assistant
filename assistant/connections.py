"""Connection construction without credential interpolation or shared user caches."""
from pathlib import Path
import sqlite3
from sqlalchemy import URL, create_engine, event
from sqlalchemy.pool import NullPool


def connection_url(kind, host, port, user, password, database):
    driver = {'postgres': 'postgresql+psycopg', 'mysql': 'mysql+mysqlconnector'}[kind]
    return URL.create(driver, username=user, password=password, host=host,
                      port=int(port), database=database)


def open_engine(kind, **settings):
    if kind == 'sqlite':
        uri = Path(settings['path']).resolve().as_uri() + '?mode=ro'
        engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(uri, uri=True),
                               poolclass=NullPool)

        @event.listens_for(engine, 'connect')
        def readonly(connection, record):
            connection.execute('PRAGMA query_only=ON')
        return engine
    url = connection_url(kind, **settings)
    args = {'connect_timeout': 5} if kind == 'postgres' else {'connection_timeout': 5}
    return create_engine(url, connect_args=args, poolclass=NullPool)
