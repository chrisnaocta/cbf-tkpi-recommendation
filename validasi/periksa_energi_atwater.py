"""
periksa_energi_atwater.py

Membandingkan nilai energi TKPI (kolom energi) dengan energi hasil faktor Atwater
(4 x protein + 9 x lemak + 4 x karbohidrat) untuk 256 bahan pada pool, dan
menghitung berapa item pada menu uji yang terdampak. Untuk pembahasan keterbatasan
pada Subbab 4.2.4. Penyebab selisih (mis. cara perhitungan TKPI atau salah cetak)
tidak diselidiki di sini; skrip hanya mengukur besarnya selisih.

Masukan : database/data_makanan.csv (melalui kurasi_makanan), data_uji/hasil_menu.csv (opsional)
Keluaran: data_uji/selisih_energi_atwater.csv, data_uji/ringkasan_selisih_energi_atwater.txt
"""

import sys
from pathlib import Path

import pandas as pd

FOLDER_VALIDASI = Path(__file__).resolve().parent
FOLDER_PROYEK = FOLDER_VALIDASI.parent
FOLDER_DATABASE = FOLDER_PROYEK / "database"
FOLDER_DATA_UJI = FOLDER_PROYEK / "data_uji"
sys.path.insert(0, str(FOLDER_PROYEK))
sys.path.insert(0, str(FOLDER_DATABASE))

import kurasi_makanan  # noqa: E402
from kalkulator_gizi import KKAL_PER_GRAM  # noqa: E402

BERKAS_CSV_MAKANAN = FOLDER_DATABASE / "data_makanan.csv"
BERKAS_MENU = FOLDER_DATA_UJI / "hasil_menu.csv"
BERKAS_HASIL = FOLDER_DATA_UJI / "selisih_energi_atwater.csv"
BERKAS_RINGKASAN = FOLDER_DATA_UJI / "ringkasan_selisih_energi_atwater.txt"
PEMISAH_CSV, DESIMAL_CSV, KODIFIKASI_CSV = ";", ",", "utf-8-sig"

AMBANG_PERSEN = (10.0, 20.0, 50.0)   # ambang selisih relatif yang dilaporkan (ditetapkan penguji)
JUMLAH_CONTOH = 10


def jalankan() -> None:
    pool = kurasi_makanan.ambil_siap_makan(str(BERKAS_CSV_MAKANAN))
    pool["energi_atwater"] = (KKAL_PER_GRAM["protein"] * pool["protein"]
                              + KKAL_PER_GRAM["lemak"] * pool["lemak"]
                              + KKAL_PER_GRAM["karbohidrat"] * pool["karbohidrat"])
    pool["selisih_kkal"] = pool["energi"] - pool["energi_atwater"]
    pool["selisih_persen"] = pool["selisih_kkal"] / pool["energi_atwater"] * 100
    FOLDER_DATA_UJI.mkdir(exist_ok=True)
    pool.round(2).to_csv(BERKAS_HASIL, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, index=False, encoding=KODIFIKASI_CSV)

    n = len(pool)
    mutlak = pool["selisih_persen"].abs()
    teks = ["SELISIH ENERGI TKPI TERHADAP FAKTOR ATWATER (pool siap makan)", "=" * 66, "",
            f"Jumlah bahan: {n}",
            f"Median |selisih|: {mutlak.median():.1f}%   Rata-rata |selisih|: {mutlak.mean():.1f}%",
            f"Energi TKPI lebih rendah dari Atwater: {int((pool['selisih_kkal'] < 0).sum())} bahan; "
            f"lebih tinggi: {int((pool['selisih_kkal'] > 0).sum())} bahan", ""]
    for a in AMBANG_PERSEN:
        teks.append(f"Bahan dengan |selisih| > {a:g}%: {int((mutlak > a).sum())} dari {n} ({(mutlak > a).mean() * 100:.1f}%)")
    teks += ["", "Menurut peran (jumlah bahan dengan |selisih| > 10%):"]
    for peran, sub in pool.groupby("peran_menu"):
        teks.append(f"  {peran:<6} {int((sub['selisih_persen'].abs() > AMBANG_PERSEN[0]).sum()):>3} dari {len(sub)}")
    ekstrem = pool.reindex(mutlak.sort_values(ascending=False).index).head(JUMLAH_CONTOH)
    teks += ["", f"{JUMLAH_CONTOH} selisih terbesar:"]
    for r in ekstrem.itertuples():
        teks.append(f"  {r.kode_tkpi:<7}{r.nama_bahan[:34]:<36} TKPI {r.energi:>6.0f}  Atwater {r.energi_atwater:>6.1f}  ({r.selisih_persen:+.0f}%)")

    if BERKAS_MENU.exists():
        menu = pd.read_csv(BERKAS_MENU, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, encoding=KODIFIKASI_CSV)
        gabung = menu.merge(pool[["kode_tkpi", "selisih_persen"]], on="kode_tkpi", how="left")
        besar = gabung["selisih_persen"].abs() > AMBANG_PERSEN[0]
        teks += ["", f"Item pada menu uji dengan |selisih| > {AMBANG_PERSEN[0]:g}%: {int(besar.sum())} dari {len(gabung)}",
                 f"  Menurut peran: " + ", ".join(
                     f"{p} {int((besar & (gabung['peran'] == p)).sum())}" for p in sorted(gabung['peran'].unique()))]
    ringkasan = "\n".join(teks)
    BERKAS_RINGKASAN.write_text(ringkasan, encoding="utf-8")
    print(ringkasan)


if __name__ == "__main__":
    jalankan()