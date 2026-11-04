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
    tls_ca = settings.pop('tls_ca', None)
    url = connection_url(kind, **settings)
    args = {'connect_timeout': 5} if kind == 'postgres' else {'connection_timeout': 5}
    if tls_ca:
        if not Path(tls_ca).is_file():
            raise ValueError('Provide an existing trusted CA certificate.')
        args.update({'sslmode':'verify-full','sslrootcert':str(tls_ca)} if kind == 'postgres' else
                    {'ssl_ca':str(tls_ca),'ssl_verify_cert':True,'ssl_verify_identity':True})
    return create_engine(url, connect_args=args, poolclass=NullPool)
