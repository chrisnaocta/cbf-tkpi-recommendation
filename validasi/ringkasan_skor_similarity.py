"""
ringkasan_skor_similarity.py

Meringkas skor kemiripan (Cosine Similarity, rumus (11)) item pada menu hasil uji:
jumlah item, nilai minimum, maksimum, dan rata-rata, untuk seluruh item dan per
peran. Angka ini mendukung Subbab 4.2.2 (skenario 8) dan Subbab 4.2.3.

Data dibaca dari data_uji/hasil_menu.csv (hasil uji_responden.py). Skrip ini hanya
MEMBACA data dan tidak mengubah angka apa pun.

Cara menjalankan (dari folder validasi):
    python ringkasan_skor_similarity.py
Keluaran: data_uji/ringkasan_skor_similarity.txt
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Konstanta
# ---------------------------------------------------------------------------
# Skrip berada di folder validasi, data_uji berada di folder utama proyek.
FOLDER_PROYEK = Path(__file__).resolve().parent.parent
FOLDER_DATA_UJI = FOLDER_PROYEK / "data_uji"
BERKAS_MASUKAN = FOLDER_DATA_UJI / "hasil_menu.csv"
BERKAS_KELUARAN = FOLDER_DATA_UJI / "ringkasan_skor_similarity.txt"

PEMISAH_CSV = ";"
DESIMAL_CSV = ","
ENCODING_CSV = "utf-8-sig"

KOLOM_SKOR = "skor_similarity"
URUTAN_PERAN = ["pokok", "lauk", "sayur"]
JUMLAH_DESIMAL = 4
LEBAR_GARIS = 78


def format_skor(nilai):
    """Skor dengan koma desimal."""
    return f"{nilai:.{JUMLAH_DESIMAL}f}".replace(".", ",")


def baca_data():
    """Membaca hasil_menu.csv."""
    if not BERKAS_MASUKAN.exists():
        raise FileNotFoundError(f"Berkas {BERKAS_MASUKAN} tidak ditemukan. Jalankan uji_responden.py lebih dulu.")
    return pd.read_csv(BERKAS_MASUKAN, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, encoding=ENCODING_CSV)


def baris_statistik(nama, seri):
    """Satu baris: jumlah, minimum, rata-rata, maksimum."""
    return (f"{nama:<12}{len(seri):>8}{format_skor(seri.min()):>12}"
            f"{format_skor(seri.mean()):>12}{format_skor(seri.max()):>12}")


def susun_ringkasan(df):
    """Menyusun teks ringkasan skor kemiripan."""
    skor = df[KOLOM_SKOR]
    menu = df.groupby(["kode", "waktu_makan"]).ngroups
    b = ["RINGKASAN SKOR KEMIRIPAN (Cosine Similarity, rumus (11))", "=" * LEBAR_GARIS, ""]
    b.append(f"Sumber data   : {BERKAS_MASUKAN.name}")
    b.append(f"Jumlah profil : {df['kode'].nunique()}")
    b.append(f"Jumlah menu   : {menu} waktu makan, masing-masing {len(URUTAN_PERAN)} item")
    b.append(f"Jumlah item   : {len(df)} ({menu} menu x {len(URUTAN_PERAN)} peran)")
    b.append("")
    b.append(f"{'Kelompok':<12}{'Item':>8}{'Minimum':>12}{'Rata-rata':>12}{'Maksimum':>12}")
    b.append("-" * LEBAR_GARIS)
    b.append(baris_statistik("Semua item", skor))
    for peran in URUTAN_PERAN:
        b.append(baris_statistik(peran, df.loc[df["peran"] == peran, KOLOM_SKOR]))
    return "\n".join(b) + "\n"


def main():
    teks = susun_ringkasan(baca_data())
    BERKAS_KELUARAN.write_text(teks, encoding="utf-8")
    print(teks)
    print(f"Ringkasan disimpan ke: {BERKAS_KELUARAN}")


if __name__ == "__main__":
    main()