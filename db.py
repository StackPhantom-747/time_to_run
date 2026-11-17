import mysql.connector
from config import DB_CONFIG


def _conn():
    return mysql.connector.connect(**DB_CONFIG)


def query(sql, params=(), one=False):
    conn = _conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute(sql, params=()):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def execute_transaction(statements):
    conn = _conn()
    cur = None
    try:
        cur = conn.cursor()
        lastrowids = []
        for sql, params in statements:
            cur.execute(sql, params)
            lastrowids.append(cur.lastrowid)
        conn.commit()
        return lastrowids
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()