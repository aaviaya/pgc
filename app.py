import os
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from db import Database

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'pgc-secret-key-2025')

@app.context_processor
def inject_globals():
    conn = get_db()
    tahun_list = [r['tahun'] for r in conn.execute("SELECT DISTINCT tahun FROM payments UNION SELECT DISTINCT tahun FROM expenses UNION SELECT DISTINCT tahun FROM iuran_kategori ORDER BY tahun").fetchall()]
    conn.close()
    if not tahun_list:
        tahun_list = [2025]
    return dict(tahun_list=tahun_list, tahun_range=f"{min(tahun_list)}-{max(tahun_list)}")
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'pgc123')

IS_VERCEL = os.environ.get('VERCEL', '') == '1'
BASE_DIR = '/tmp' if IS_VERCEL else os.path.dirname(__file__)

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DB_PATH = os.path.join(BASE_DIR, 'pgc.db')

BLOK_LIST = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'B4', 'C1', 'C2', 'C3', 'D1', 'D2', 'D3', 'D4', 'D5']
BULAN_LIST = ['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember']
KATEGORI_LIST = ['Kas', 'Keamanan', 'Sampah', 'Fee Wifi']

_db_initialized = False

def get_db():
    global _db_initialized
    conn = Database()
    if not _db_initialized:
        conn.executescript('''
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
                created_at TEXT DEFAULT (datetime('now','localtime'))
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

        # Seed iuran_kategori defaults if empty
        ada = conn.scalar("SELECT COUNT(*) FROM iuran_kategori")
        if ada == 0:
            for t in [2025, 2026]:
                if t == 2025:
                    conn.execute("INSERT INTO iuran_kategori (tahun, nama, jumlah) VALUES (?,?,?)", (t, 'Kas', 30000))
                else:
                    conn.execute("INSERT INTO iuran_kategori (tahun, nama, jumlah) VALUES (?,?,?)", (t, 'Sampah', 20000))
                    conn.execute("INSERT INTO iuran_kategori (tahun, nama, jumlah) VALUES (?,?,?)", (t, 'Kas', 10000))
                    conn.execute("INSERT INTO iuran_kategori (tahun, nama, jumlah) VALUES (?,?,?)", (t, 'Keamanan', 15000))
        _db_initialized = True
    return conn

def tahun_aktif():
    return request.args.get('tahun', type=int) or 2026

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Password salah!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('dashboard'))

@app.route('/')
def dashboard():
    conn = get_db()
    tahun = request.args.get('tahun', type=int)
    if not tahun:
        tahun = 2026

    total_warga = conn.scalar("SELECT COUNT(*) FROM residents")
    total_huni = conn.scalar("SELECT COUNT(*) FROM residents WHERE status='Huni'")
    total_belum = conn.scalar("SELECT COUNT(*) FROM residents WHERE status='Belum Huni' OR status='Belum'")
    total_iuran = conn.scalar("SELECT COALESCE(SUM(jumlah),0) FROM payments WHERE tahun=?", (tahun,))
    total_pengeluaran = conn.scalar("SELECT COALESCE(SUM(jumlah),0) FROM expenses WHERE tahun=?", (tahun,))

    per_bulan = {}
    for b in BULAN_LIST:
        total = conn.scalar("SELECT COALESCE(SUM(jumlah),0) FROM payments WHERE tahun=? AND bulan=?", (tahun, b))
        per_bulan[b] = total

    pengeluaran_per_bulan = {}
    for b in BULAN_LIST:
        total = conn.scalar("SELECT COALESCE(SUM(jumlah),0) FROM expenses WHERE tahun=? AND bulan=?", (tahun, b))
        pengeluaran_per_bulan[b] = total

    recent = conn.execute('''
        SELECT r.blok, r.no_rumah, r.nama, p.bulan, p.jumlah, p.paid_at, p.tahun
        FROM payments p JOIN residents r ON p.resident_id = r.id
        WHERE p.tahun=?
        ORDER BY p.paid_at DESC LIMIT 10
    ''', (tahun,)).fetchall()

    by_blok = []
    for b in BLOK_LIST:
        cnt = conn.scalar("SELECT COUNT(*) FROM residents WHERE blok=?", (b,))
        cnt_huni = conn.scalar("SELECT COUNT(*) FROM residents WHERE blok=? AND status='Huni'", (b,))
        if cnt > 0:
            by_blok.append({'blok': b, 'total': cnt, 'huni': cnt_huni})

    # Recent expenses
    recent_expenses = conn.execute('''
        SELECT * FROM expenses WHERE tahun=? ORDER BY created_at DESC LIMIT 5
    ''', (tahun,)).fetchall()

    # Payment rate per bulan (% warga huni yang sudah bayar)
    payment_rate = {}
    for b in BULAN_LIST:
        paid = conn.scalar("SELECT COUNT(DISTINCT p.resident_id) FROM payments p JOIN residents r ON p.resident_id=r.id WHERE p.tahun=? AND p.bulan=? AND r.status='Huni' AND p.jumlah>0", (tahun, b))
        payment_rate[b] = paid

    conn.close()
    return render_template('dashboard.html',
        tahun=tahun, total_warga=total_warga, total_huni=total_huni, total_belum=total_belum,
        total_iuran=total_iuran, total_pengeluaran=total_pengeluaran,
        per_bulan=per_bulan, pengeluaran_per_bulan=pengeluaran_per_bulan,
        recent=recent, recent_expenses=recent_expenses, by_blok=by_blok,
        payment_rate=payment_rate)

@app.route('/warga')
def warga_list():
    conn = get_db()
    tahun = request.args.get('tahun', type=int) or 2026
    blok_filter = request.args.get('blok', '')
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'blok')
    order = request.args.get('order', 'asc')

    per_page = 50
    allowed_sort = {'blok': 'r.blok', 'no_rumah': "CAST(r.no_rumah AS INTEGER)", 'nama': 'r.nama', 'status': 'r.status', 'total': 'total_dibayar'}
    sort_col = allowed_sort.get(sort, 'r.blok')
    sort_dir = 'DESC' if order == 'desc' else 'ASC'

    count_params = []
    if blok_filter:
        count_params.append(blok_filter)
    count_row = conn.scalar(
        f"SELECT COUNT(*) FROM residents WHERE 1=1" + (" AND blok=?" if blok_filter else ""),
        count_params
    )

    total_pages = max(1, (count_row + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    sql_params = [tahun]
    where_clause = ""
    if blok_filter:
        where_clause = "AND r.blok=?"
        sql_params.append(blok_filter)
    sql_params.extend([per_page, offset])

    sql = f"""
        SELECT r.*, COALESCE(SUM(p.jumlah),0) as total_dibayar
        FROM residents r
        LEFT JOIN payments p ON r.id = p.resident_id AND p.tahun=?
        WHERE 1=1 {where_clause}
        GROUP BY r.id
        ORDER BY {sort_col} {sort_dir}
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(sql, sql_params).fetchall()

    conn.close()
    return render_template('warga_list.html', rows=rows, blok_filter=blok_filter,
        blok_list=BLOK_LIST, tahun=tahun,
        page=page, total_pages=total_pages, sort=sort, order=order)

@app.route('/warga/tambah', methods=['GET', 'POST'])
@login_required
def warga_tambah():
    if request.method == 'POST':
        blok = request.form['blok']
        no_rumah = request.form['no_rumah']
        nama = request.form['nama']
        status = request.form['status']
        conn = get_db()

        existing = conn.execute(
            "SELECT id, nama, status FROM residents WHERE blok=? AND no_rumah=?",
            (blok, no_rumah)).fetchone()
        if existing:
            if existing['status'] in ('Huni', 'Sudah'):
                flash(f'Blok {blok} No {no_rumah} sudah dihuni {existing["nama"]}!', 'danger')
            else:
                flash(f'Blok {blok} No {no_rumah} sudah terdaftar atas nama {existing["nama"]}!', 'danger')
            conn.close()
            return redirect(url_for('warga_list'))

        try:
            conn.execute("INSERT INTO residents (blok, no_rumah, nama, status) VALUES (?,?,?,?)",
                         (blok, no_rumah, nama, status))
            conn.commit()
            flash('Warga berhasil ditambahkan', 'success')
        except conn.IntegrityError as e:
            flash('Data warga sudah ada!', 'danger')
        conn.close()
        return redirect(url_for('warga_list'))
    return render_template('warga_form.html', warga=None, blok_list=BLOK_LIST, tahun=request.args.get('tahun', 2026))

@app.route('/warga/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def warga_edit(id):
    conn = get_db()
    warga = conn.execute("SELECT * FROM residents WHERE id=?", (id,)).fetchone()
    if not warga:
        conn.close()
        flash('Warga tidak ditemukan', 'danger')
        return redirect(url_for('warga_list'))
    if request.method == 'POST':
        blok = request.form['blok']
        no_rumah = request.form['no_rumah']
        nama = request.form['nama']
        status = request.form['status']

        existing = conn.execute(
            "SELECT id, nama, status FROM residents WHERE blok=? AND no_rumah=? AND id!=?",
            (blok, no_rumah, id)).fetchone()
        if existing:
            if existing['status'] in ('Huni', 'Sudah'):
                flash(f'Blok {blok} No {no_rumah} sudah dihuni {existing["nama"]}!', 'danger')
            else:
                flash(f'Blok {blok} No {no_rumah} sudah terdaftar atas nama {existing["nama"]}!', 'danger')
            conn.close()
            return redirect(url_for('warga_list'))

        try:
            conn.execute("UPDATE residents SET blok=?, no_rumah=?, nama=?, status=?, updated_at=datetime('now','localtime') WHERE id=?",
                         (blok, no_rumah, nama, status, id))
            conn.commit()
            flash('Data warga berhasil diupdate', 'success')
        except conn.IntegrityError as e:
            flash('Data sudah ada!', 'danger')
        conn.close()
        return redirect(url_for('warga_list'))
    conn.close()
    return render_template('warga_form.html', warga=warga, blok_list=BLOK_LIST, tahun=request.args.get('tahun', 2026))

@app.route('/warga/<int:id>/hapus', methods=['POST'])
@login_required
def warga_hapus(id):
    conn = get_db()
    conn.execute("DELETE FROM residents WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Warga berhasil dihapus', 'success')
    return redirect(url_for('warga_list'))

@app.route('/warga/<int:id>/bayar')
@login_required
def warga_bayar(id):
    conn = get_db()
    tahun = request.args.get('tahun', type=int) or 2026
    warga = conn.execute("SELECT * FROM residents WHERE id=?", (id,)).fetchone()
    payments = conn.execute("SELECT * FROM payments WHERE resident_id=? AND tahun=? ORDER BY id", (id, tahun)).fetchall()
    iuran_kats = conn.execute("SELECT * FROM iuran_kategori WHERE tahun=? ORDER BY id", (tahun,)).fetchall()
    iuran_total = sum(r['jumlah'] for r in iuran_kats)
    conn.close()
    return render_template('warga_bayar.html', warga=warga, payments=payments, bulan_list=BULAN_LIST, tahun=tahun, iuran_kats=iuran_kats, iuran_total=iuran_total)

@app.route('/warga/<int:id>/bayar/tambah', methods=['POST'])
@login_required
def bayar_tambah(id):
    tahun = int(request.form.get('tahun', 2026))
    bulan = request.form['bulan']
    jumlah = int(request.form['jumlah'])
    conn = get_db()
    try:
        conn.execute("INSERT INTO payments (resident_id, bulan, tahun, jumlah) VALUES (?,?,?,?)",
                     (id, bulan, tahun, jumlah))
        conn.commit()
        flash(f'Pembayaran {bulan} {tahun} berhasil dicatat', 'success')
    except conn.IntegrityError as e:
        flash(f'Pembayaran {bulan} {tahun} sudah ada!', 'danger')
    conn.close()
    return redirect(url_for('warga_bayar', id=id, tahun=tahun))

@app.route('/bayar/<int:id>/edit', methods=['POST'])
@login_required
def bayar_edit(id):
    jumlah = int(request.form['jumlah'])
    conn = get_db()
    conn.execute("UPDATE payments SET jumlah=?, paid_at=datetime('now','localtime') WHERE id=?", (jumlah, id))
    conn.commit()
    flash('Pembayaran berhasil diupdate', 'success')
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/bayar/<int:id>/hapus', methods=['POST'])
@login_required
def bayar_hapus(id):
    conn = get_db()
    bayar = conn.execute("SELECT resident_id, tahun FROM payments WHERE id=?", (id,)).fetchone()
    if bayar:
        conn.execute("DELETE FROM payments WHERE id=?", (id,))
        conn.commit()
        flash('Pembayaran berhasil dihapus', 'success')
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/pengaturan')
@login_required
def pengaturan():
    tahun = request.args.get('tahun', type=int) or 2026
    return render_template('pengaturan.html', tahun=tahun)

@app.route('/iuran-kategori')
@login_required
def iuran_kategori_list():
    tahun = request.args.get('tahun', type=int) or 2026
    conn = get_db()
    rows = conn.execute("SELECT * FROM iuran_kategori WHERE tahun=? ORDER BY id", (tahun,)).fetchall()
    total = sum(r['jumlah'] for r in rows)
    conn.close()
    return render_template('iuran_kategori.html', rows=rows, total=total, tahun=tahun)

@app.route('/iuran-kategori/tambah', methods=['POST'])
@login_required
def iuran_kategori_tambah():
    tahun = int(request.form['tahun'])
    nama = request.form['nama'].strip()
    jumlah = int(request.form['jumlah'])
    if nama:
        conn = get_db()
        conn.execute("INSERT INTO iuran_kategori (tahun, nama, jumlah) VALUES (?,?,?)", (tahun, nama, jumlah))
        conn.commit()
        conn.close()
        flash(f'Kategori iuran "{nama}" berhasil ditambahkan', 'success')
    return redirect(url_for('iuran_kategori_list', tahun=tahun))

@app.route('/iuran-kategori/<int:id>/edit', methods=['POST'])
@login_required
def iuran_kategori_edit(id):
    nama = request.form['nama'].strip()
    jumlah = int(request.form['jumlah'])
    conn = get_db()
    conn.execute("UPDATE iuran_kategori SET nama=?, jumlah=? WHERE id=?", (nama, jumlah, id))
    conn.commit()
    conn.close()
    flash('Kategori iuran berhasil diupdate', 'success')
    return redirect(request.referrer or url_for('iuran_kategori_list'))

@app.route('/iuran-kategori/<int:id>/hapus', methods=['POST'])
@login_required
def iuran_kategori_hapus(id):
    conn = get_db()
    conn.execute("DELETE FROM iuran_kategori WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Kategori iuran berhasil dihapus', 'success')
    return redirect(request.referrer or url_for('iuran_kategori_list'))

@app.route('/pengeluaran')
def pengeluaran_list():
    conn = get_db()
    tahun = request.args.get('tahun', type=int) or 2026
    page = request.args.get('page', 1, type=int)
    per_page = 50
    total = conn.scalar("SELECT COUNT(*) FROM expenses WHERE tahun=?", (tahun,))
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    rows = conn.execute("SELECT * FROM expenses WHERE tahun=? ORDER BY id LIMIT ? OFFSET ?", (tahun, per_page, offset)).fetchall()

    per_bulan = {}
    for b in BULAN_LIST:
        total = conn.scalar("SELECT COALESCE(SUM(jumlah),0) FROM expenses WHERE tahun=? AND bulan=?", (tahun, b))
        per_bulan[b] = total

    # Sisa kas per kategori (dynamic from DB)
    sisa_kas = {}
    total_iuran = conn.scalar("SELECT COALESCE(SUM(jumlah),0) FROM payments WHERE tahun=?", (tahun,))
    kategori_db_raw = [r['kategori'] for r in conn.execute("SELECT DISTINCT kategori FROM expenses WHERE tahun=? ORDER BY kategori", (tahun,)).fetchall()]
    kategori_db = list(dict.fromkeys(kategori_db_raw + KATEGORI_LIST))
    for k in kategori_db:
        pengeluaran = conn.scalar("SELECT COALESCE(SUM(jumlah),0) FROM expenses WHERE tahun=? AND kategori=?", (tahun, k))
        sisa_kas[k] = pengeluaran

    conn.close()
    return render_template('pengeluaran_list.html', rows=rows, per_bulan=per_bulan,
        sisa_kas=sisa_kas, total_iuran=total_iuran, tahun=tahun,
        bulan_list=BULAN_LIST, kategori_list=kategori_db, page=page, total_pages=total_pages, total=total, offset=offset)

@app.route('/pengeluaran/tambah', methods=['GET', 'POST'])
@login_required
def pengeluaran_tambah():
    if request.method == 'POST':
        tahun = int(request.form['tahun'])
        bulan = request.form['bulan']
        kategori = request.form['kategori']
        tanggal = request.form['tanggal']
        keterangan = request.form['keterangan']
        jumlah = int(request.form['jumlah'])
        bukti = ''
        file = request.files.get('bukti')
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            bukti = filename
        conn = get_db()
        conn.execute("INSERT INTO expenses (tahun, bulan, kategori, tanggal, keterangan, jumlah, bukti) VALUES (?,?,?,?,?,?,?)",
                     (tahun, bulan, kategori, tanggal, keterangan, jumlah, bukti))
        conn.commit()
        conn.close()
        flash('Pengeluaran berhasil dicatat', 'success')
        return redirect(url_for('pengeluaran_list', tahun=tahun))
    conng = get_db()
    kategori_db_raw = [r['kategori'] for r in conng.execute("SELECT DISTINCT kategori FROM expenses ORDER BY kategori").fetchall()]
    conng.close()
    kategori_db = list(dict.fromkeys(kategori_db_raw + KATEGORI_LIST))
    return render_template('pengeluaran_form.html', tahun=request.args.get('tahun', 2026),
        bulan_list=BULAN_LIST, kategori_list=kategori_db)

@app.route('/pengeluaran/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def pengeluaran_edit(id):
    conn = get_db()
    exp = conn.execute("SELECT * FROM expenses WHERE id=?", (id,)).fetchone()
    if not exp:
        conn.close()
        flash('Data tidak ditemukan', 'danger')
        return redirect(url_for('pengeluaran_list'))
    if request.method == 'POST':
        tahun = int(request.form['tahun'])
        bulan = request.form['bulan']
        kategori = request.form['kategori']
        tanggal = request.form['tanggal']
        keterangan = request.form['keterangan']
        jumlah = int(request.form['jumlah'])
        bukti = exp['bukti'] or ''
        file = request.files.get('bukti')
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            bukti = filename
        conn.execute("UPDATE expenses SET tahun=?, bulan=?, kategori=?, tanggal=?, keterangan=?, jumlah=?, bukti=? WHERE id=?",
                     (tahun, bulan, kategori, tanggal, keterangan, jumlah, bukti, id))
        conn.commit()
        conn.close()
        flash('Pengeluaran berhasil diupdate', 'success')
        return redirect(url_for('pengeluaran_list', tahun=tahun))
    kategori_db_raw = [r['kategori'] for r in conn.execute("SELECT DISTINCT kategori FROM expenses ORDER BY kategori").fetchall()]
    kategori_db = list(dict.fromkeys(kategori_db_raw + KATEGORI_LIST))
    conn.close()
    return render_template('pengeluaran_form.html', exp=exp, tahun=exp['tahun'],
        bulan_list=BULAN_LIST, kategori_list=kategori_db)

@app.route('/pengeluaran/<int:id>/hapus', methods=['POST'])
@login_required
def pengeluaran_hapus(id):
    conn = get_db()
    exp = conn.execute("SELECT bukti FROM expenses WHERE id=?", (id,)).fetchone()
    if exp and exp['bukti']:
        path = os.path.join(app.config['UPLOAD_FOLDER'], exp['bukti'])
        if os.path.exists(path):
            os.remove(path)
    conn.execute("DELETE FROM expenses WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Pengeluaran berhasil dihapus', 'success')
    return redirect(request.referrer or url_for('pengeluaran_list'))

@app.route('/laporan')
def laporan():
    conn = get_db()
    tahun = request.args.get('tahun', type=int) or 2026
    blok = request.args.get('blok') or ''
    page = request.args.get('page', 1, type=int)
    per_page = 50

    blok_list = [r['blok'] for r in conn.execute("SELECT DISTINCT blok FROM residents ORDER BY blok").fetchall()]

    # Count total residents (respect blok filter)
    count_params = []
    count_where = ""
    if blok:
        count_where = "WHERE blok=?"
        count_params.append(blok)
    total_rows = conn.scalar(f"SELECT COUNT(*) FROM residents {count_where}", count_params)
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    # Dynamic CASE columns for each month
    case_cols = []
    for m in BULAN_LIST:
        case_cols.append(f"COALESCE(SUM(CASE WHEN p.bulan='{m}' THEN p.jumlah ELSE 0 END),0) as \"{m}\"")

    where_clause = ""
    params = [tahun]
    if blok:
        where_clause = "AND r.blok=?"
        params.append(blok)

    sql = f'''
        SELECT r.blok, r.no_rumah, r.nama, r.status,
            {','.join(case_cols)}
        FROM residents r
        LEFT JOIN payments p ON r.id = p.resident_id AND p.tahun=?
        {where_clause}
        GROUP BY r.id ORDER BY r.blok, CAST(r.no_rumah AS INTEGER)
        LIMIT ? OFFSET ?
    '''
    data = conn.execute(sql, params + [per_page, offset]).fetchall()

    # Total iuran per bulan (respects blok filter, for all residents not just page)
    total_per_bulan = {}
    for b in BULAN_LIST:
        sql_tpb = "SELECT COALESCE(SUM(p.jumlah),0) FROM payments p JOIN residents r ON p.resident_id=r.id WHERE p.tahun=? AND p.bulan=?"
        params_tpb = [tahun, b]
        if blok:
            sql_tpb += " AND r.blok=?"
            params_tpb.append(blok)
        t = conn.scalar(sql_tpb, params_tpb)
        total_per_bulan[b] = t

    conn.close()
    return render_template('laporan.html', data=data, tahun=tahun,
        bulan_list=BULAN_LIST, active_months=BULAN_LIST,
        total_per_bulan=total_per_bulan,
        blok=blok, blok_list=blok_list,
        page=page, total_pages=total_pages, total_rows=total_rows)

@app.route('/laporan/pengeluaran')
def laporan_pengeluaran():
    conn = get_db()
    tahun = request.args.get('tahun', type=int) or 2026
    page = request.args.get('page', 1, type=int)
    per_page = 50

    total_rows = conn.scalar("SELECT COUNT(*) FROM expenses WHERE tahun=?", (tahun,))
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    expenses = conn.execute("SELECT * FROM expenses WHERE tahun=? ORDER BY id LIMIT ? OFFSET ?", (tahun, per_page, offset)).fetchall()
    total_pengeluaran = conn.scalar("SELECT COALESCE(SUM(jumlah),0) FROM expenses WHERE tahun=?", (tahun,))
    per_bulan = {}
    for b in BULAN_LIST:
        per_bulan[b] = conn.scalar("SELECT COALESCE(SUM(jumlah),0) FROM expenses WHERE tahun=? AND bulan=?", (tahun, b))
    conn.close()
    return render_template('laporan_pengeluaran.html', expenses=expenses,
        total_pengeluaran=total_pengeluaran, per_bulan=per_bulan,
        tahun=tahun, bulan_list=BULAN_LIST,
        page=page, total_pages=total_pages, total_rows=total_rows)

@app.template_global()
def format_rupiah(n):
    if n is None or n == 0:
        return '-'
    return f"{n:,}"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
