import os

DATABASE_URL = os.environ.get('DATABASE_URL', '')

class Database:
    """Unified wrapper for SQLite and PostgreSQL."""

    def __init__(self):
        if DATABASE_URL:
            self._init_pg()
        else:
            self._init_sqlite()

    def _init_pg(self):
        import psycopg2
        import psycopg2.extras
        self._pg = True
        self._conn = psycopg2.connect(DATABASE_URL)
        self._conn.autocommit = False
        self._real_dict = psycopg2.extras.RealDictCursor

    def _init_sqlite(self):
        import sqlite3
        import app as _app
        self._pg = False
        self._conn = sqlite3.connect(_app.DB_PATH)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def _fix_sql(self, sql):
        if not self._pg:
            return sql
        sql = sql.replace('?', '%s')
        sql = sql.replace("datetime('now','localtime')", 'NOW()')
        return sql

    def execute(self, sql, params=None):
        sql = self._fix_sql(sql)
        if self._pg:
            cur = self._conn.cursor(cursor_factory=self._real_dict)
            cur.execute(sql, params or ())
            return cur
        else:
            return self._conn.execute(sql, params or [])

    def scalar(self, sql, params=None):
        cur = self.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        if self._pg:
            return row[list(row.keys())[0]]
        return row[0]

    def executescript(self, sql):
        if self._pg:
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for stmt in statements:
                stmt = stmt.rstrip(';').strip()
                if not stmt:
                    continue
                if stmt.upper().startswith('PRAGMA'):
                    continue
                stmt = stmt.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
                stmt = stmt.replace("datetime('now','localtime')", 'NOW()')
                stmt = self._fix_sql(stmt)
                cur = self._conn.cursor()
                try:
                    cur.execute(stmt)
                except Exception as e:
                    if 'already exists' in str(e):
                        self._conn.rollback()
                        cur.close()
                        continue
                    raise
                cur.close()
            self._conn.commit()
        else:
            self._conn.executescript(sql)

    def commit(self):
        self._conn.commit()

    def close(self):
        try:
            self._conn.commit()
        except Exception:
            self._conn.rollback()
        self._conn.close()

    @property
    def IntegrityError(self):
        if self._pg:
            import psycopg2
            return psycopg2.errors.UniqueViolation
        else:
            import sqlite3
            return sqlite3.IntegrityError
