import mysql.connector
from config import DB_CONFIG


class DatabaseConnectionError(Exception):
    """Raised when the application cannot connect to the configured database."""


def _conn():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as error:
        raise DatabaseConnectionError from error


def query(sql, params=(), one=False):
    conn = _conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    except (mysql.connector.InterfaceError, mysql.connector.OperationalError) as error:
        raise DatabaseConnectionError from error
    finally:
        conn.close()


def execute(sql, params=()):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    except (mysql.connector.InterfaceError, mysql.connector.OperationalError) as error:
        raise DatabaseConnectionError from error
    finally:
        conn.close()


def execute_transaction(statements):
    conn = _conn()
    try:
        cur = conn.cursor()
        for sql, params in statements:
            cur.execute(sql, params)
        conn.commit()
    except mysql.connector.Error as error:
        conn.rollback()
        if isinstance(error, (mysql.connector.InterfaceError, mysql.connector.OperationalError)):
            raise DatabaseConnectionError from error
        raise
    finally:
        conn.close()
