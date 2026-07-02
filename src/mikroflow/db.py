from importlib.resources import files

from psycopg_pool import ConnectionPool


def load_schema_sql() -> str:
    # schema.sql ships as package data, so this resolves both in an editable
    # install (source tree) and in a wheel installed into site-packages.
    return files("mikroflow").joinpath("schema.sql").read_text()


def make_pool(dsn: str) -> ConnectionPool:
    return ConnectionPool(dsn, min_size=1, max_size=10, open=True)


def apply_schema(pool: ConnectionPool, schema_sql: str | None = None) -> None:
    # No parameters -> psycopg uses the simple query protocol and runs the
    # whole multi-statement script in one call.
    sql = schema_sql if schema_sql is not None else load_schema_sql()
    with pool.connection() as conn:
        conn.execute(sql)


def ensure_partitions(pool: ConnectionPool, days_ahead: int, months_ahead: int) -> None:
    with pool.connection() as conn:
        conn.execute("SELECT ensure_partition_window(%s, %s)", (days_ahead, months_ahead))
