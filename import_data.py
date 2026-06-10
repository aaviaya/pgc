"""Import data from CSV (Google Sheet export) into PGC database.
Usage:
  python import_data.py data_2025.csv 2025
  python import_data.py data_2026.csv 2026
"""
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from app import get_db, BULAN_LIST

def import_csv(csv_path, tahun):
    conn = get_db()
    cur = conn.cursor()

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))

    # Find header row
    data_start = None
    for i, row in enumerate(rows):
        if len(row) >= 2 and row[1].strip() == 'No.':
            data_start = i + 1
            break

    if data_start is None:
        print("Header 'No.' not found. First 10 rows:")
        for r in rows[:10]:
            print(r)
        return

    # Detect column layout from header row
    # For 2025: [empty, No, empty, Blok, No, Nama, Huni, empty, 2025, ...]
    # For 2026: [empty, No, Blok, No.Rumah, Nama, Status Huni, empty, empty, 2026, ...]
    sample = rows[data_start] if data_start < len(rows) else []
    header = rows[data_start - 2] if data_start >= 2 else []

    # Determine which columns to use based on the CSV structure
    # Default 2025 layout
    col_blok = 3
    col_no_rumah = 4
    col_nama = 5
    col_status = 6
    col_payment_start = 8

    # Check if this is 2026 format (different column layout)
    if tahun >= 2026:
        col_blok = 2
        col_no_rumah = 3
        col_nama = 4
        col_status = 5
        col_payment_start = 8

    count_residents = 0
    count_payments = 0
    current_blok = ''

    for row in rows[data_start:]:
        if len(row) < 6:
            continue
        no = row[1].strip()
        if not no or not no.isdigit():
            continue

        blok_raw = row[col_blok].strip() if len(row) > col_blok else ''
        no_rumah = row[col_no_rumah].strip() if len(row) > col_no_rumah else ''
        nama = row[col_nama].strip() if len(row) > col_nama else ''
        status_raw = row[col_status].strip().lower() if len(row) > col_status else ''

        if blok_raw and blok_raw not in ('', ',', 'Blok', 'Total'):
            current_blok = blok_raw.upper().strip()

        if not nama or nama in ('Total', 'Kekurangan', 'Jml'):
            continue

        # Determine status
        if status_raw in ('huni', 'sudah', 'huni ', 'sudah '):
            status = 'Huni'
        elif status_raw in ('sementara',):
            status = 'Huni'
        else:
            status = 'Belum Huni'

        # Try to find existing resident by blok+no_rumah
        existing = cur.execute(
            "SELECT id FROM residents WHERE blok=? AND no_rumah=?",
            (current_blok, no_rumah)
        ).fetchone()

        if existing:
            resident_id = existing['id']
            # Update name if different
            cur.execute("UPDATE residents SET nama=?, status=? WHERE id=?",
                       (nama, status, resident_id))
        else:
            cur.execute(
                "INSERT INTO residents (blok, no_rumah, nama, status) VALUES (?,?,?,?)",
                (current_blok, no_rumah, nama, status)
            )
            resident_id = cur.lastrowid
            count_residents += 1

        # Parse payments - columns after payment start
        months_for_year = BULAN_LIST  # All 12 months
        for ci, bulan in enumerate(months_for_year):
            col_idx = col_payment_start + ci
            if col_idx < len(row):
                val = row[col_idx].strip()
                if val and val not in ('', ',-', '-', ',', '0'):
                    try:
                        cleaned = val.replace('.', '').replace(',', '').strip()
                        if cleaned and cleaned.replace('-', '').lstrip('-').isdigit():
                            amount = int(cleaned)
                            if amount > 0:
                                try:
                                    cur.execute(
                                        "INSERT INTO payments (resident_id, bulan, tahun, jumlah) VALUES (?,?,?,?)",
                                        (resident_id, bulan, tahun, amount)
                                    )
                                    count_payments += 1
                                except Exception:
                                    # Payment already exists - skip
                                    pass
                    except (ValueError, IndexError):
                        pass

    conn.commit()
    print(f"Imported {count_residents} new residents, {count_payments} payments for {tahun}.")
    conn.close()

def import_expenses(csv_path, tahun):
    """Import expenses data from CSV.
    CSV columns: [empty, section_no, no, description, date, amount, source]
    """
    conn = get_db()
    cur = conn.cursor()

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))

    count = 0
    current_bulan = None
    seen = set()

    for row in rows:
        if len(row) < 5:
            continue

        col2 = row[2].strip() if len(row) > 2 else ''
        col3 = row[3].strip() if len(row) > 3 else ''

        # Detect bulan header: col2 = "Bulan", col3 = "Januari 2026"
        if col2 == 'Bulan':
            for b in BULAN_LIST:
                if b in col3:
                    current_bulan = b
                    break
            continue

        # Skip header rows (No, Pengeluaran, Hari/Tanggal, Total, Sumber)
        if col2 == 'No' and col3 == 'Pengeluaran ':
            continue

        # Skip summary/label rows
        if col2 in ('Total Iuran', 'Total Pengeluaran', 'Sisa Iuran Total', 'Kas',
                     'Keamanan', 'Sampah', 'Fee Wifi', 'Bulan', 'No'):
            continue

        # Skip empty rows and non-numbered rows
        if not col2.isdigit():
            continue

        # Extract data - column layout:
        # col2=no, col3=keterangan, col4=tanggal, col5=jumlah, col6=sumber
        no = col2
        keterangan = col3
        tanggal = row[4].strip() if len(row) > 4 else ''
        jumlah_raw = row[5].strip() if len(row) > 5 else ''
        sumber = row[6].strip() if len(row) > 6 else ''

        if not keterangan or not jumlah_raw or jumlah_raw == 'Total':
            continue

        try:
            jumlah = int(jumlah_raw.replace('.', ''))
        except ValueError:
            continue

        # Use sumber as kategori (preserve custom categories)
        kategori = sumber

        if not current_bulan:
            continue

        # Deduplicate
        key = (keterangan, tanggal, jumlah)
        if key in seen:
            continue
        seen.add(key)

        cur.execute(
            "INSERT INTO expenses (tahun, bulan, kategori, tanggal, keterangan, jumlah) VALUES (?,?,?,?,?,?)",
            (tahun, current_bulan, kategori, tanggal, keterangan, jumlah)
        )
        count += 1

    conn.commit()
    print(f"Imported {count} expenses for {tahun}.")
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python import_data.py iuran <csv_path> <tahun>")
        print("  python import_data.py pengeluaran <csv_path> <tahun>")
        sys.exit(1)

    mode = sys.argv[1]
    csv_path = sys.argv[2]
    tahun = int(sys.argv[3]) if len(sys.argv) > 3 else 2026

    if mode == 'iuran':
        import_csv(csv_path, tahun)
    elif mode == 'pengeluaran':
        import_expenses(csv_path, tahun)
    else:
        print(f"Unknown mode: {mode}")
