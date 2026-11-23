"""
ringkasan_pemenuhan_imt.py

Membuat ringkasan persentase pemenuhan gizi HARIAN menurut kategori IMT untuk
seluruh profil uji (responden + sintetis). Isi berkas keluaran sama dengan
Tabel 4.20 pada skripsi.

Data dibaca dari dua berkas hasil uji_responden.py:
  - data_uji/hasil_gizi.csv        : kategori IMT tiap profil (klasifikasi Tabel 2.1)
  - data_uji/hasil_pemenuhan.csv   : persentase pemenuhan rumus (13), baris cakupan "harian"

Skrip ini hanya MEMBACA kedua berkas tersebut. Skrip ini tidak menjalankan sistem
rekomendasi dan tidak mengubah angka apa pun.

Cara menjalankan (dari folder database):
    python ringkasan_pemenuhan_imt.py
Keluaran: data_uji/ringkasan_pemenuhan_imt.txt
"""

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Konstanta (ketetapan pelaporan, bukan rumus baru)
# ---------------------------------------------------------------------------
# Skrip berada di folder database, data_uji berada di folder utama proyek.
FOLDER_PROYEK = Path(__file__).resolve().parent.parent
FOLDER_DATA_UJI = FOLDER_PROYEK / "data_uji"
BERKAS_GIZI = FOLDER_DATA_UJI / "hasil_gizi.csv"
BERKAS_PEMENUHAN = FOLDER_DATA_UJI / "hasil_pemenuhan.csv"
BERKAS_KELUARAN = FOLDER_DATA_UJI / "ringkasan_pemenuhan_imt.txt"

# Format CSV dari uji_responden.py: pemisah titik koma, desimal koma
PEMISAH_CSV = ";"
DESIMAL_CSV = ","
ENCODING_CSV = "utf-8-sig"

# Cakupan yang dilaporkan pada Tabel 4.20 (pemenuhan satu hari penuh)
CAKUPAN_HARIAN = "harian"

# Zat gizi dan kolomnya pada hasil_pemenuhan.csv, urutan mengikuti Tabel 4.20
ZAT_GIZI = ["energi", "protein", "lemak", "karbohidrat"]
KOLOM_PERSEN = {zat: f"{zat}_persen" for zat in ZAT_GIZI}

# Urutan kategori IMT mengikuti Tabel 2.1
URUTAN_KATEGORI = [
    "Kekurangan berat badan tingkat berat",
    "Kekurangan berat badan tingkat ringan",
    "Berat badan normal",
    "Kelebihan berat badan tingkat ringan",
    "Kelebihan berat badan tingkat berat",
]

LEBAR_KATEGORI = 40
LEBAR_KOLOM = 17
JUMLAH_DESIMAL = 2


def format_angka(nilai):
    """Menuliskan angka dengan koma desimal (gaya penulisan skripsi)."""
    return f"{nilai:.{JUMLAH_DESIMAL}f}".replace(".", ",")


def format_rentang(seri):
    """Satu angka bila hanya satu profil (atau semua nilai sama), selain itu 'min-maks'."""
    bawah, atas = seri.min(), seri.max()
    if format_angka(bawah) == format_angka(atas):
        return format_angka(bawah)
    return f"{format_angka(bawah)}-{format_angka(atas)}"


def baca_csv(jalur, kolom_wajib):
    """Membaca CSV hasil uji dan memeriksa kolom yang dibutuhkan."""
    if not jalur.exists():
        raise FileNotFoundError(
            f"Berkas {jalur} tidak ditemukan. Jalankan uji_responden.py lebih dulu."
        )
    df = pd.read_csv(jalur, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, encoding=ENCODING_CSV)
    kurang = set(kolom_wajib) - set(df.columns)
    if kurang:
        raise ValueError(f"Kolom tidak ditemukan pada {jalur.name}: {sorted(kurang)}")
    return df


def gabung_data():
    """Menggabungkan kategori IMT (hasil_gizi) dengan pemenuhan harian (hasil_pemenuhan)."""
    gizi = baca_csv(BERKAS_GIZI, ["kode", "kategori_imt"])
    pemenuhan = baca_csv(
        BERKAS_PEMENUHAN, ["kode", "cakupan", *KOLOM_PERSEN.values()]
    )
    harian = pemenuhan[pemenuhan["cakupan"] == CAKUPAN_HARIAN]
    data = harian.merge(gizi[["kode", "kategori_imt"]], on="kode", how="left")
    if data["kategori_imt"].isna().any():
        kode_hilang = data.loc[data["kategori_imt"].isna(), "kode"].tolist()
        raise ValueError(f"Kategori IMT tidak ditemukan untuk profil: {kode_hilang}")
    if data["kode"].duplicated().any():
        raise ValueError("Ada kode profil ganda pada baris cakupan harian.")
    return data


def susun_ringkasan(data):
    """Menyusun teks ringkasan Tabel 4.20."""
    baris = []
    baris.append("RINGKASAN PEMENUHAN GIZI HARIAN MENURUT KATEGORI IMT")
    baris.append("=" * 100)
    baris.append("")
    baris.append(f"Sumber data   : {BERKAS_GIZI.name} dan {BERKAS_PEMENUHAN.name}")
    baris.append(f"Jumlah profil : {len(data)}")
    baris.append("Satu angka bila kategori hanya diwakili satu profil, selain itu rentang minimum-maksimum (%).")
    baris.append("")
    baris.append("TABEL 4.20")
    baris.append("-" * 100)
    judul = f"{'Kategori IMT':<{LEBAR_KATEGORI}}{'Profil':>7}"
    for zat in ZAT_GIZI:
        judul += f"{zat.capitalize() + ' (%)':>{LEBAR_KOLOM}}"
    baris.append(judul)
    baris.append("-" * 100)

    ada = set(data["kategori_imt"])
    for kategori in URUTAN_KATEGORI:
        if kategori not in ada:
            continue
        bagian = data[data["kategori_imt"] == kategori]
        teks = f"{kategori:<{LEBAR_KATEGORI}}{len(bagian):>7}"
        for zat in ZAT_GIZI:
            teks += f"{format_rentang(bagian[KOLOM_PERSEN[zat]]):>{LEBAR_KOLOM}}"
        baris.append(teks)

    # Kategori di luar urutan Tabel 2.1 (bila ada) tetap dilaporkan agar tidak hilang
    lain = sorted(ada - set(URUTAN_KATEGORI))
    for kategori in lain:
        bagian = data[data["kategori_imt"] == kategori]
        teks = f"{kategori:<{LEBAR_KATEGORI}}{len(bagian):>7}"
        for zat in ZAT_GIZI:
            teks += f"{format_rentang(bagian[KOLOM_PERSEN[zat]]):>{LEBAR_KOLOM}}"
        baris.append(teks)

    baris.append("-" * 100)
    baris.append("")
    baris.append("Kategori tanpa profil (tidak ditampilkan pada tabel):")
    kosong = [k for k in URUTAN_KATEGORI if k not in ada]
    if kosong:
        for kategori in kosong:
            baris.append(f"  {kategori}: 0 profil")
    else:
        baris.append("  (tidak ada)")
    baris.append("")
    baris.append("Profil pada tiap kategori:")
    for kategori in URUTAN_KATEGORI + lain:
        if kategori in ada:
            kode = data.loc[data["kategori_imt"] == kategori, "kode"].tolist()
            baris.append(f"  {kategori} ({len(kode)}): {', '.join(kode)}")
    return "\n".join(baris) + "\n"


def main():
    data = gabung_data()
    teks = susun_ringkasan(data)
    BERKAS_KELUARAN.write_text(teks, encoding="utf-8")
    print(teks)
    print(f"Ringkasan disimpan ke: {BERKAS_KELUARAN}")


if __name__ == "__main__":
    main()