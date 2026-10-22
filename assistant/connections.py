"""Connection construction without credential interpolation or shared user caches.

File: assistant/connections.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import sqlite3
from pathlib import Path

from sqlalchemy import URL, create_engine, event
from sqlalchemy.pool import NullPool

from .config import DEFAULT_CONNECT_TIMEOUT_SECONDS


def connection_url(kind, host, port, user, password, database):
    """Construct an SQLAlchemy URL without interpolating credentials into strings.

    Args:
        kind: Database kind: sqlite, postgres, or mysql.
        host: Remote database hostname.
        port: Remote database TCP port.
        user: Database login role.
        password: Database password supplied at runtime.
        database: Remote database name.

    Returns:
        sqlalchemy.URL: Driver-specific URL with safely encoded credentials.

    Raises:
        KeyError: If the remote database kind is unsupported.
        ValueError: If the port cannot be converted to an integer.
    """
    driver = {"postgres": "postgresql+psycopg", "mysql": "mysql+mysqlconnector"}[kind]
    return URL.create(
        driver, username=user, password=password, host=host, port=int(port), database=database
    )


def open_engine(kind, **settings):
    """Open an uncached engine with read-only SQLite or verified remote TLS when configured.

    Args:
        kind: Database kind: sqlite, postgres, or mysql.
        **settings: Connection keyword settings, including path for SQLite or optional tls_ca.

    Returns:
        sqlalchemy.Engine: Uncached engine; the caller must dispose it.

    Raises:
        ValueError: If a supplied trusted CA certificate does not exist.
        KeyError: If required connection settings or database kind are unsupported.
    """
    if kind == "sqlite":
        uri = Path(settings["path"]).resolve().as_uri() + "?mode=ro"
        engine = create_engine(
            "sqlite://", creator=lambda: sqlite3.connect(uri, uri=True), poolclass=NullPool
        )

        @event.listens_for(engine, "connect")
        def readonly(connection, record):
            """Enable SQLite query-only mode for each newly opened DBAPI connection.

            Args:
                connection: New SQLite DBAPI connection receiving query-only protection.
                record: SQLAlchemy connection-pool record supplied by the connect event.
            """
            connection.execute("PRAGMA query_only=ON")

        return engine
    tls_ca = settings.pop("tls_ca", None)
    url = connection_url(kind, **settings)
    args = (
        {"connect_timeout": DEFAULT_CONNECT_TIMEOUT_SECONDS}
        if kind == "postgres"
        else {"connection_timeout": DEFAULT_CONNECT_TIMEOUT_SECONDS}
    )
    if tls_ca:
        if not Path(tls_ca).is_file():
            raise ValueError("Provide an existing trusted CA certificate.")
        args.update(
            {"sslmode": "verify-full", "sslrootcert": str(tls_ca)}
            if kind == "postgres"
            else {"ssl_ca": str(tls_ca), "ssl_verify_cert": True, "ssl_verify_identity": True}
        )
    return create_engine(url, connect_args=args, poolclass=NullPool)
