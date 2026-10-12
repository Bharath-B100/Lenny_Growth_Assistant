import logging
from contextlib import contextmanager
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from .config import DATABASE_URL, ROOT

log = logging.getLogger('lenny')
pool = ConnectionPool(DATABASE_URL, min_size=0, max_size=8, timeout=5,
                      kwargs={'row_factory': dict_row, 'connect_timeout': 5}, open=False)

def initialize(recover_jobs=False):
    pool.open()
    with pool.connection(timeout=20) as conn:
        conn.execute((ROOT / 'backend' / 'schema.sql').read_text())
        if recover_jobs:
            conn.execute("UPDATE jobs SET status='error', error_code='SERVER_RESTARTED', error_message='The server restarted. Please try again.' WHERE status IN ('queued','running')")

@contextmanager
def connection():
    with pool.connection() as conn:
        yield conn

def one(sql, args=()):
    with connection() as conn:
        return conn.execute(sql, args).fetchone()

def all_rows(sql, args=()):
    with connection() as conn:
        return conn.execute(sql, args).fetchall()

def execute(sql, args=()):
    with connection() as conn:
        conn.execute(sql, args)
