"""
ringkasan_margin_toleransi.py

Menghitung berapa persentase pemenuhan (rumus (13)) yang berada dalam MARGIN_POIN
dari batas toleransi 90% dan 110%. Angka ini mendukung pernyataan pada Subbab 4.2.3
bahwa sebagian cakupan memenuhi toleransi dengan margin yang tipis.

Data dibaca dari data_uji/hasil_pemenuhan.csv (hasil uji_responden.py). Batas
toleransi diambil dari TOLERANSI_BAWAH dan TOLERANSI_ATAS pada mesin_rekomendasi.py.
Skrip ini hanya MEMBACA data dan tidak mengubah angka apa pun.

Cara menjalankan (dari folder validasi):
    python ringkasan_margin_toleransi.py
Keluaran: data_uji/ringkasan_margin_toleransi.txt
"""

import sys
from pathlib import Path

import pandas as pd

# Skrip berada di folder validasi; modul program dan data_uji ada di folder utama.
FOLDER_PROYEK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FOLDER_PROYEK))

from mesin_rekomendasi import TOLERANSI_ATAS, TOLERANSI_BAWAH  # noqa: E402

# ---------------------------------------------------------------------------
# Konstanta
# ---------------------------------------------------------------------------
FOLDER_DATA_UJI = FOLDER_PROYEK / "data_uji"
BERKAS_MASUKAN = FOLDER_DATA_UJI / "hasil_pemenuhan.csv"
BERKAS_KELUARAN = FOLDER_DATA_UJI / "ringkasan_margin_toleransi.txt"

PEMISAH_CSV = ";"
DESIMAL_CSV = ","
ENCODING_CSV = "utf-8-sig"

# Ketetapan pelaporan: lebar margin dari batas toleransi (poin persen)
MARGIN_POIN = 1.0
CAKUPAN_HARIAN = "harian"
ZAT_GIZI = ["energi", "protein", "lemak", "karbohidrat"]
LEBAR_GARIS = 78


def format_angka(nilai):
    """Angka dengan koma desimal (bilangan bulat bila tidak berdesimal)."""
    return f"{nilai:g}".replace(".", ",")


def baca_data():
    """Membaca hasil_pemenuhan.csv."""
    if not BERKAS_MASUKAN.exists():
        raise FileNotFoundError(f"Berkas {BERKAS_MASUKAN} tidak ditemukan. Jalankan uji_responden.py lebih dulu.")
    return pd.read_csv(BERKAS_MASUKAN, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, encoding=ENCODING_CSV)


def susun_ringkasan(df):
    """Menyusun teks ringkasan margin per kelompok cakupan dan zat gizi."""
    ambang_rendah = TOLERANSI_BAWAH + MARGIN_POIN
    ambang_tinggi = TOLERANSI_ATAS - MARGIN_POIN
    kolom = {zat: f"{zat}_persen" for zat in ZAT_GIZI}

    b = ["RINGKASAN MARGIN TERHADAP BATAS TOLERANSI", "=" * LEBAR_GARIS, ""]
    b.append(f"Sumber data : {BERKAS_MASUKAN.name}")
    b.append(f"Toleransi   : {format_angka(TOLERANSI_BAWAH)}-{format_angka(TOLERANSI_ATAS)}% (mesin_rekomendasi.py)")
    b.append(f"Margin      : {format_angka(MARGIN_POIN)} poin, yaitu nilai di bawah {format_angka(ambang_rendah)}% "
             f"atau di atas {format_angka(ambang_tinggi)}%")
    b.append("")

    kelompok = [
        ("Waktu makan (sarapan, siang, malam)", df[df["cakupan"] != CAKUPAN_HARIAN]),
        ("Harian", df[df["cakupan"] == CAKUPAN_HARIAN]),
    ]
    total_margin = total_nilai = 0
    for nama, sub in kelompok:
        nilai = sub[list(kolom.values())]
        rendah = (nilai < ambang_rendah).sum()
        tinggi = (nilai > ambang_tinggi).sum()
        jumlah = int(rendah.sum() + tinggi.sum())
        total_margin += jumlah
        total_nilai += nilai.size
        b.append(f"{nama}: {len(sub)} cakupan, {nilai.size} nilai")
        b.append(f"  {'Zat gizi':<14}{'< ' + format_angka(ambang_rendah) + '%':>10}{'> ' + format_angka(ambang_tinggi) + '%':>10}")
        for zat in ZAT_GIZI:
            b.append(f"  {zat:<14}{int(rendah[kolom[zat]]):>10}{int(tinggi[kolom[zat]]):>10}")
        b.append(f"  Jumlah dalam margin: {jumlah}")
        b.append("")

    b.append("-" * LEBAR_GARIS)
    b.append(f"Total nilai dalam {format_angka(MARGIN_POIN)} poin dari batas: {total_margin} dari {total_nilai} nilai")
    return "\n".join(b) + "\n"


def main():
    teks = susun_ringkasan(baca_data())
    BERKAS_KELUARAN.write_text(teks, encoding="utf-8")
    print(teks)
    print(f"Ringkasan disimpan ke: {BERKAS_KELUARAN}")


if __name__ == "__main__":
    main()