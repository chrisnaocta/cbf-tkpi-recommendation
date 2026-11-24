from pathlib import Path
import pandas as pd

FOLDER_WEBSITE = Path(__file__).resolve().parent.parent
FOLDER_DATABASE = FOLDER_WEBSITE / "database"
FOLDER_OUTPUT = FOLDER_WEBSITE / "data_uji"

# Lokasi CSV di folder database
csv_path = FOLDER_DATABASE / "data_makanan.csv"
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

# Simpan hasil ke TXT di folder website/data_uji
FOLDER_OUTPUT.mkdir(parents=True, exist_ok=True)
output_path = FOLDER_OUTPUT / "hasil_peran_menu.txt"
output_path.write_text("\n".join(lines), encoding="utf-8")

print(f"Hasil disimpan ke: {output_path}")