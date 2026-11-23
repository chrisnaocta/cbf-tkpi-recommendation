"""
ringkasan_pemenuhan.py

Membuat ringkasan persentase pemenuhan gizi (rumus (13)) untuk SELURUH profil uji
(responden + sintetis) dari data_uji/hasil_pemenuhan.csv, lalu menuliskannya ke
data_uji/ringkasan_pemenuhan_47_profil.txt. Isi berkas ini sama dengan Tabel 4.19
pada skripsi (nilai minimum, rata-rata, dan maksimum per cakupan dan zat gizi).

Skrip ini hanya MEMBACA hasil_pemenuhan.csv yang dihasilkan uji_responden.py.
Skrip ini tidak menjalankan sistem rekomendasi dan tidak mengubah angka apa pun.

Cara menjalankan (dari folder database):
    python ringkasan_pemenuhan.py
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Konstanta (ketetapan pelaporan, bukan rumus baru)
# ---------------------------------------------------------------------------
# Skrip ini berada di folder database, sedangkan data_uji berada di folder utama
# proyek (satu tingkat di atasnya). Jalur dihitung dari lokasi berkas ini sehingga
# skrip dapat dijalankan dari folder mana pun.
FOLDER_PROYEK = Path(__file__).resolve().parent.parent
FOLDER_DATA_UJI = FOLDER_PROYEK / "data_uji"
BERKAS_MASUKAN = FOLDER_DATA_UJI / "hasil_pemenuhan.csv"
BERKAS_KELUARAN = FOLDER_DATA_UJI / "ringkasan_pemenuhan_47_profil.txt"

# Format berkas CSV dari uji_responden.py: pemisah titik koma, desimal koma
PEMISAH_CSV = ";"
DESIMAL_CSV = ","
ENCODING_CSV = "utf-8-sig"

# Urutan cakupan dan zat gizi mengikuti Tabel 4.19
URUTAN_CAKUPAN = ["sarapan", "siang", "malam", "harian"]
ZAT_GIZI = ["energi", "protein", "lemak", "karbohidrat"]
KOLOM_PERSEN = {zat: f"{zat}_persen" for zat in ZAT_GIZI}

# Toleransi kesesuaian pada rumus (13), Subbab 3.3.3 butir 9
TOLERANSI_BAWAH = 90.0
TOLERANSI_ATAS = 110.0

LEBAR_GARIS = 60
JUMLAH_DESIMAL = 2


def format_angka(nilai):
    """Menuliskan angka dengan koma desimal (gaya penulisan skripsi)."""
    return f"{nilai:.{JUMLAH_DESIMAL}f}".replace(".", ",")


def baca_data():
    """Membaca hasil_pemenuhan.csv dan memeriksa kolom yang dibutuhkan."""
    if not BERKAS_MASUKAN.exists():
        raise FileNotFoundError(
            f"Berkas {BERKAS_MASUKAN} tidak ditemukan. Jalankan uji_responden.py lebih dulu."
        )
    df = pd.read_csv(
        BERKAS_MASUKAN, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, encoding=ENCODING_CSV
    )
    kolom_wajib = {"kode", "kelompok", "cakupan", "memenuhi", *KOLOM_PERSEN.values()}
    kurang = kolom_wajib - set(df.columns)
    if kurang:
        raise ValueError(f"Kolom tidak ditemukan pada CSV: {sorted(kurang)}")
    return df


def susun_ringkasan(df):
    """Menyusun teks ringkasan dari seluruh baris (responden dan sintetis)."""
    jumlah_profil = df["kode"].nunique()
    jumlah_responden = df.loc[df["kelompok"] == "responden", "kode"].nunique()
    jumlah_sintetis = jumlah_profil - jumlah_responden
    jumlah_cakupan = len(df)
    jumlah_nilai = jumlah_cakupan * len(ZAT_GIZI)

    baris = []
    baris.append("RINGKASAN PEMENUHAN GIZI (rumus (13)) - SELURUH PROFIL UJI")
    baris.append("=" * LEBAR_GARIS)
    baris.append("")
    baris.append(f"Sumber data     : {BERKAS_MASUKAN.name}")
    baris.append(
        f"Jumlah profil   : {jumlah_profil} "
        f"({jumlah_responden} responden + {jumlah_sintetis} sintetis)"
    )
    baris.append(f"Jumlah cakupan  : {jumlah_cakupan} (profil x 4 cakupan)")
    baris.append(f"Jumlah nilai    : {jumlah_nilai} (cakupan x 4 zat gizi)")
    baris.append("")

    memenuhi = df["memenuhi"].astype(str).str.strip().str.lower() == "ya"
    baris.append(
        f"Cakupan memenuhi {format_angka(TOLERANSI_BAWAH)}-{format_angka(TOLERANSI_ATAS)}% "
        f"pada keempat zat gizi: {int(memenuhi.sum())} dari {jumlah_cakupan}"
    )
    baris.append("")
    baris.append("TABEL 4.19 - Persentase pemenuhan (%), minimum / rata-rata / maksimum")
    baris.append("-" * LEBAR_GARIS)
    baris.append(f"{'Cakupan':<10}{'Zat gizi':<14}{'Minimum':>10}{'Rata-rata':>12}{'Maksimum':>12}")
    baris.append("-" * LEBAR_GARIS)

    for cakupan in URUTAN_CAKUPAN:
        bagian = df[df["cakupan"] == cakupan]
        for indeks, zat in enumerate(ZAT_GIZI):
            nilai = bagian[KOLOM_PERSEN[zat]]
            nama_cakupan = cakupan if indeks == 0 else ""
            baris.append(
                f"{nama_cakupan:<10}{zat:<14}"
                f"{format_angka(nilai.min()):>10}"
                f"{format_angka(nilai.mean()):>12}"
                f"{format_angka(nilai.max()):>12}"
            )
        baris.append("")

    semua = df[list(KOLOM_PERSEN.values())].to_numpy().ravel()
    baris.append(f"Nilai terendah seluruhnya : {format_angka(semua.min())}%")
    baris.append(f"Nilai tertinggi seluruhnya: {format_angka(semua.max())}%")
    baris.append("")
    baris.append("Cakupan yang belum memenuhi:")
    belum = df[~memenuhi]
    if belum.empty:
        baris.append("  (tidak ada)")
    else:
        for _, r in belum.iterrows():
            baris.append(f"  {r['kode']} - {r['cakupan']}")
    return "\n".join(baris) + "\n"


def main():
    df = baca_data()
    teks = susun_ringkasan(df)
    BERKAS_KELUARAN.write_text(teks, encoding="utf-8")
    print(teks)
    print(f"Ringkasan disimpan ke: {BERKAS_KELUARAN}")


if __name__ == "__main__":
    main()