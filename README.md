# PGC Dashboard — Iuran Warga

Sistem manajemen iuran warga untuk **Puri Griasadi Cibogo**. Dibangun dengan Flask + SQLite + Tailwind CSS.

## Fitur

- **Dashboard** — ringkasan total warga, iuran masuk, pengeluaran, tingkat pembayaran per bulan (slider), grafik per bulan, statistik per blok, aktivitas terbaru
- **Data Warga** — CRUD warga dengan pagination (50/halaman), sort, filter blok; validasi duplikat (blok + no_rumah unique)
- **Pembayaran** — catat bayar per warga per bulan; riwayat lunas/belum; import massal dari Google Sheets
- **Pengeluaran** — CRUD pengeluaran dengan upload bukti (foto/PDF); ringkasan per kategori dan per bulan
- **Kategori Iuran** — atur rincian iuran per tahun (misal: Sampah Rp20.000, Kas Rp10.000, Keamanan Rp15.000)
- **Laporan** — tabel matrix pembayaran per warga x bulan, rekap pengeluaran, filter blok, siap cetak
- **Multi Tahun** — dukungan 2025+, pilih tahun di setiap halaman
- **Login Admin** — session-based, password dari environment variable

## Persyaratan

- Python 3.10+
- Flask (`pip install flask`)

## Instalasi & Menjalankan

```bash
pip install flask
cd pgc
python app.py
```

Akses di `http://localhost:5000`.

## Konfigurasi

| Environment Variable | Default | Keterangan |
|---|---|---|
| `ADMIN_PASSWORD` | `pgc123` | Password login admin |
| `SECRET_KEY` | `pgc-secret-key-2025` | Secret key Flask session |

## Import Data

### Iuran warga dari CSV (export Google Sheets)

```bash
python import_data.py iuran data_2026.csv 2026
```

### Pengeluaran dari CSV

```bash
python import_data.py pengeluaran pengeluaran_2026.csv 2026
```

### Format CSV Iuran

Kolom: `blok, no_rumah, nama, status, [12 bulan: Januari–Desember]`

Nilai status: `huni`, `sudah`, `sementara` → **Huni**; lainnya → **Belum Huni**

### Format CSV Pengeluaran

Header `Bulan` diikuti nama bulan (misal `Januari 2026`) untuk menandai bulan. Kolom: `no, keterangan, tanggal, jumlah, sumber`

## Struktur Database

4 tabel utama: `residents`, `payments`, `expenses`, `iuran_kategori` — dibuat otomatis saat pertama kali jalan.

## Stuktur Folder

```
pgc/
├── app.py                     # Aplikasi Flask utama
├── import_data.py             # Script import CSV
├── templates/                 # Template Jinja2
│   ├── layout.html
│   ├── dashboard.html
│   ├── warga_list.html
│   ├── warga_form.html
│   ├── warga_bayar.html
│   ├── pengeluaran_list.html
│   ├── pengeluaran_form.html
│   ├── iuran_kategori.html
│   ├── laporan.html
│   ├── pengaturan.html
│   └── login.html
├── uploads/                   # File bukti upload
├── pgc.db                     # Database SQLite
└── data_2026.csv              # Contoh data iuran
```
