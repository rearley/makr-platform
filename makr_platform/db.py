import contextlib
import psycopg2
import psycopg2.pool

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_db(database_url: str, minconn: int = 1, maxconn: int = 10) -> None:
    global _pool
    _pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn=database_url)


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    if _pool is None:
        raise RuntimeError("Database not initialised — call init_db() in app.py before first use.")
    return _pool


@contextlib.contextmanager
def get_conn():
    """Yield a psycopg2 connection; commit on success, rollback on exception."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def execute(sql: str, params: tuple = ()) -> list:
    """Run a query and return all rows."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def execute_one(sql: str, params: tuple = ()):
    """Run a query and return the first row, or None."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
