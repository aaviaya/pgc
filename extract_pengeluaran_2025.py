import csv
from pathlib import Path

OUTPUT_CSV = Path(__file__).parent / "pengeluaran_2025.csv"

EXPENSES = [
    ("Mei", "Pak Dody",                      170_000, "Kas"),
    ("Mei", "Pembayaran sampah",             300_000, "Sampah"),
    ("Juni", "Cable",                         10_000, "Kas"),
    ("Juni", "Konsumsi musyawarah",          150_000, "Kas"),
    ("Juni", "Berkas kelurahan+tips pak erdi",120_000, "Kas"),
    ("Juni", "Bayar sampah Juni 2025",       860_000, "Sampah"),
    ("Juli", "Konsumsi",                     350_000, "Kas"),
    ("Juli", "pembayaran sampah",          1_320_000, "Sampah"),
    ("Juli", "Photo Copy",                   150_000, "Kas"),
    ("Juli", "umbul-umbul",                   76_820, "Kas"),
    ("Juli", "sticker",                       31_850, "Kas"),
    ("Juli", "pengajian, umbul & tali",      488_500, "Kas"),
    ("Juli", "alat lomba & kado",          1_000_000, "Kas"),
    ("Juli", "Konsumsi+Lain lain lomba",     420_000, "Kas"),
    ("Juli", "lainnya",                        2_830, "Kas"),
    ("Agustus", "Bansos",                    150_000, "Kas"),
    ("Agustus", "pembayaran sampah agst",  1_400_000, "Sampah"),
    ("September", "pembayaran sampah sept",1_480_000, "Sampah"),
    ("Oktober", "Pemb. Sampah",            1_680_000, "Sampah"),
    ("Oktober", "Bansos",                    400_000, "Kas"),
    ("Oktober", "Pilok + snack Developer",   190_000, "Kas"),
    ("November", "konsumsi rapat",           400_000, "Kas"),
    ("November", "Stempel & Print Copy",     120_000, "Kas"),
    ("November", "Damkar",                    50_000, "Kas"),
    ("Desember", "Pemb. Sampah Nov",       2_280_000, "Sampah"),
    ("Desember", "Bansos",                   100_000, "Kas"),
    ("Desember", "Matrial utk Musholla",     255_000, "Kas"),
    ("Desember", "Bensin alat potong token mushola", 75_000, "Kas"),
    ("Desember", "Operasional",              355_000, "Kas"),
    ("Desember", "Token Mushola",             52_600, "Kas"),
    ("Desember", "lampu reimburst",          400_000, "Kas"),
    ("Desember", "Isra Miraj Masjid Cibogo", 200_000, "Kas"),
    ("Desember", "Pemb. Sampah Des",       2_480_000, "Sampah"),
]

MONTHS = ["Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

def write_output():
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["", "", "", "PENGELUARAN 2025", "", "", ""])
        writer.writerow([])
        counter = 0
        for month in MONTHS:
            items = [(b, d, a, k) for b, d, a, k in EXPENSES if b == month]
            if not items:
                continue
            writer.writerow(["", "", "Bulan", month, "", "", ""])
            writer.writerow(["", "", "No", "Pengeluaran ", "Hari/Tanggal", "Total", "Sumber"])
            for _, desc, amount, kategori in items:
                counter += 1
                amount_str = f"{amount:,}".replace(",", ".")
                writer.writerow(["", "", str(counter), desc, "", amount_str, kategori])
            writer.writerow([])
    print(f"Total: {len(EXPENSES)} expenses written to {OUTPUT_CSV}")
    for month in MONTHS:
        vals = [a for b, d, a, k in EXPENSES if b == month]
        if vals:
            print(f"  {month}: {len(vals)} items, Rp{sum(vals):,}".replace(",", "."))

if __name__ == "__main__":
    write_output()
