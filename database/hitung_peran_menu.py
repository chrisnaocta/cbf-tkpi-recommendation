
import pandas as pd
from pathlib import Path

# Lokasi CSV
csv_path = Path(__file__).parent / "data_makanan.csv"
df = pd.read_csv(csv_path)

if "peran_menu" not in df.columns:
    raise ValueError("Kolom 'peran_menu' tidak ditemukan.")

# Hitung jumlah data per peran_menu
counts = df["peran_menu"].fillna("(kosong)").value_counts(dropna=False)
jumlah_jenis = df["peran_menu"].nunique(dropna=True)

# Susun hasil
lines = [
    "HASIL PERHITUNGAN PERAN_MENU",
    "=" * 32,
    f"Jumlah jenis peran_menu: {jumlah_jenis}",
    f"Jumlah total baris data: {len(df)}",
    "",
    "Jumlah baris per peran_menu:",
    "-" * 32,
]

for role, count in counts.items():
    lines.append(f"{role}: {count} baris")

# Simpan hasil ke TXT
output_path = Path(__file__).parent / "hasil_peran_menu.txt"
output_path.write_text("\n".join(lines), encoding="utf-8")

print(f"Hasil disimpan ke: {output_path}")