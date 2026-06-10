"""Migrate data from local SQLite to PostgreSQL (NeonDB).
Usage: DATABASE_URL=<postgres_url> python migrate_to_pg.py
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))
from db import Database

SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'pgc.db')

def migrate():
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite DB not found: {SQLITE_PATH}")
        sys.exit(1)

    # Connect to SQLite
    sl = sqlite3.connect(SQLITE_PATH)
    sl.row_factory = sqlite3.Row

    # Connect to PostgreSQL via our Database wrapper
    pg = Database()
    # Initialize tables (idempotent)
    print("Initializing PostgreSQL tables...")
    pg.executescript('''
        CREATE TABLE IF NOT EXISTS residents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blok TEXT NOT NULL,
            no_rumah TEXT NOT NULL,
            nama TEXT DEFAULT '',
            status TEXT DEFAULT 'Belum Huni',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resident_id INTEGER NOT NULL,
            bulan TEXT NOT NULL,
            tahun INTEGER NOT NULL,
            jumlah INTEGER DEFAULT 0,
            paid_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (resident_id) REFERENCES residents(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tahun INTEGER NOT NULL,
            bulan TEXT NOT NULL,
            kategori TEXT NOT NULL,
            tanggal TEXT,
            keterangan TEXT DEFAULT '',
            jumlah INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            bukti TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS iuran_kategori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tahun INTEGER NOT NULL,
            nama TEXT NOT NULL,
            jumlah INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_resident_blok_no ON residents(blok, no_rumah);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_unique ON payments(resident_id, bulan, tahun);
    ''')
    # Add missing columns (if table existed before)
    try:
        pg.execute("ALTER TABLE expenses ADD COLUMN bukti TEXT DEFAULT ''")
        pg.commit()
    except Exception:
        pg.rollback()

    tables = [
        ('residents', 'blok, no_rumah, nama, status, created_at, updated_at'),
        ('payments', 'resident_id, bulan, tahun, jumlah, paid_at'),
        ('expenses', 'tahun, bulan, kategori, tanggal, keterangan, jumlah, created_at, bukti'),
        ('iuran_kategori', 'tahun, nama, jumlah, created_at'),
    ]

    for table, cols in tables:
        print(f"Migrating {table}...")
        rows_sl = sl.execute(f"SELECT * FROM {table}").fetchall()
        if not rows_sl:
            print(f"  No data in {table}, skipping")
            continue

        # Check if PG already has data
        existing_row = pg.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
        existing = existing_row['cnt'] if existing_row else 0
        if existing > 0:
            print(f"  PostgreSQL already has {existing} rows, clearing...")
            pg.execute(f"DELETE FROM {table}")
            pg.commit()

        # Get column names from first row
        first_row = sl.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
        if not first_row:
            print(f"  No data in {table}, skipping")
            continue
        col_names = [d['name'] for d in sl.execute(f"PRAGMA table_info({table})").fetchall()]
        placeholders = ','.join(['?' for _ in col_names])
        col_str = ','.join(col_names)

        count = 0
        for row in sl.execute(f"SELECT * FROM {table}").fetchall():
            values = [row[c] for c in col_names]
            pg.execute(f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})", values)
            count += 1
            if count % 100 == 0:
                pg.commit()

        pg.commit()
        print(f"  {count} rows migrated")

    sl.close()
    pg.close()
    print("\nMigration complete!")

if __name__ == '__main__':
    if not os.environ.get('DATABASE_URL'):
        print("Set DATABASE_URL environment variable first!")
        sys.exit(1)
    migrate()
