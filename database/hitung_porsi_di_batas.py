"""
hitung_porsi_di_batas.py

Membuktikan angka "porsi di batas" pada Subbab 4.2.3: berapa menu waktu makan yang
porsi pokok, lauk, atau sayurnya tepat di batas bawah/atas BATAS_GRAM. Dihitung
langsung dari keluaran uji_responden.py (bukan dari ingatan atau perhitungan ulang
sistem), sehingga angkanya dapat ditelusuri baris demi baris.

Masukan : data_uji/hasil_menu.csv, data_uji/hasil_pemenuhan.csv
Keluaran: data_uji/porsi_di_batas.csv            (tabel utama per peran)
          data_uji/porsi_di_batas_per_menu.csv   (satu baris per menu waktu makan)
          data_uji/ringkasan_porsi_di_batas.txt
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

FOLDER_DATABASE = Path(__file__).resolve().parent
FOLDER_PROYEK = FOLDER_DATABASE.parent
FOLDER_DATA_UJI = FOLDER_PROYEK / "data_uji"
sys.path.insert(0, str(FOLDER_PROYEK))

from mesin_rekomendasi import BATAS_GRAM, KELIPATAN_GRAM  # noqa: E402
from repositori_makanan import PERAN_VALID  # noqa: E402

BERKAS_MENU = FOLDER_DATA_UJI / "hasil_menu.csv"
BERKAS_PEMENUHAN = FOLDER_DATA_UJI / "hasil_pemenuhan.csv"
BERKAS_TABEL = FOLDER_DATA_UJI / "porsi_di_batas.csv"
BERKAS_PER_MENU = FOLDER_DATA_UJI / "porsi_di_batas_per_menu.csv"
BERKAS_RINGKASAN = FOLDER_DATA_UJI / "ringkasan_porsi_di_batas.txt"
PEMISAH_CSV, DESIMAL_CSV, KODIFIKASI_CSV = ";", ",", "utf-8-sig"

WAKTU_MAKAN = ("sarapan", "siang", "malam")
LABEL_YA, LABEL_TIDAK = "Ya", "Tidak"
LABEL_BAWAH, LABEL_ATAS = "bawah", "atas"


def baca(berkas: Path) -> pd.DataFrame:
    if not berkas.exists():
        sys.exit(f"Berkas tidak ditemukan: {berkas}. Jalankan uji_responden.py lebih dulu.")
    return pd.read_csv(berkas, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, encoding=KODIFIKASI_CSV)


def tandai(gram: float, peran: str) -> str:
    bawah, atas = BATAS_GRAM[peran]
    if np.isclose(gram, bawah):
        return LABEL_BAWAH
    if np.isclose(gram, atas):
        return LABEL_ATAS
    return ""


def jalankan() -> None:
    menu = baca(BERKAS_MENU)
    pem = baca(BERKAS_PEMENUHAN)
    profil = menu["kode"].nunique()
    harapan = profil * len(WAKTU_MAKAN)
    teks = ["PORSI DI BATAS (dihitung dari hasil_menu.csv)", "=" * 66, "",
            f"Jumlah profil: {profil}; menu waktu makan per peran yang diharapkan: {harapan}"]

    # --- tabel utama per peran ---
    tabel = []
    for peran in PERAN_VALID:
        bawah, atas = BATAS_GRAM[peran]
        g = menu.loc[menu["peran"] == peran, "porsi_gram"].astype(float)
        sisa = g % KELIPATAN_GRAM
        di_bawah = int(np.isclose(g, bawah).sum())
        di_atas = int(np.isclose(g, atas).sum())
        tabel.append({
            "peran": peran, "batas_bawah_g": bawah, "batas_atas_g": atas, "jumlah_menu": len(g),
            "di_batas_bawah": di_bawah, "di_batas_atas": di_atas,
            "di_batas_total": di_bawah + di_atas,
            "persen_di_batas": round((di_bawah + di_atas) / len(g) * 100, 1),
            "di_luar_batas": int(((g < bawah - 1e-9) | (g > atas + 1e-9)).sum()),
            "bukan_kelipatan": int((~(np.isclose(sisa, 0) | np.isclose(sisa, KELIPATAN_GRAM))).sum()),
        })
    df_tabel = pd.DataFrame(tabel)
    df_tabel.to_csv(BERKAS_TABEL, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, index=False, encoding=KODIFIKASI_CSV)
    teks += ["", "Tabel utama:", df_tabel.to_string(index=False)]
    for t in tabel:
        if t["jumlah_menu"] != harapan:
            teks.append(f"PERINGATAN: jumlah menu peran {t['peran']} = {t['jumlah_menu']}, bukan {harapan}")
        if t["di_luar_batas"] or t["bukan_kelipatan"]:
            teks.append(f"PERINGATAN: peran {t['peran']} memiliki porsi di luar batas atau bukan kelipatan {KELIPATAN_GRAM:g} g")

    # --- satu baris per menu waktu makan ---
    lebar = menu.pivot_table(index=["kode", "kelompok", "waktu_makan"], columns="peran",
                             values="porsi_gram", aggfunc="first").reset_index()
    for peran in PERAN_VALID:
        lebar[f"{peran}_di_batas"] = [tandai(g, peran) for g in lebar[peran]]
    kolom_batas = [f"{p}_di_batas" for p in PERAN_VALID]
    lebar["jumlah_di_batas"] = (lebar[kolom_batas] != "").sum(axis=1)
    per_menu = lebar.merge(
        pem[pem["cakupan"].isin(WAKTU_MAKAN)][["kode", "cakupan", "penyimpangan_maks", "memenuhi"]],
        left_on=["kode", "waktu_makan"], right_on=["kode", "cakupan"], how="left",
    ).drop(columns="cakupan")
    per_menu.to_csv(BERKAS_PER_MENU, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, index=False, encoding=KODIFIKASI_CSV)

    # --- rincian menurut waktu makan dan kelompok ---
    teks += ["", "Menurut waktu makan (di batas bawah / di batas atas / jumlah menu):"]
    for peran in PERAN_VALID:
        for waktu in WAKTU_MAKAN:
            s = per_menu.loc[per_menu["waktu_makan"] == waktu, f"{peran}_di_batas"]
            teks.append(f"  {peran:<6} {waktu:<8} {int((s == LABEL_BAWAH).sum()):>3} / "
                        f"{int((s == LABEL_ATAS).sum()):>3} / {len(s)}")
    teks += ["", "Menurut kelompok data (jumlah menu dengan porsi di batas):"]
    for peran in PERAN_VALID:
        for kelompok in sorted(per_menu["kelompok"].unique()):
            s = per_menu.loc[per_menu["kelompok"] == kelompok, f"{peran}_di_batas"]
            teks.append(f"  {peran:<6} {kelompok:<10} {int((s != '').sum()):>3} dari {len(s)}")

    # --- banyak item di batas per menu dan kaitannya dengan penyimpangan ---
    teks += ["", "Jumlah item di batas pada satu menu waktu makan:"]
    for k in range(len(PERAN_VALID) + 1):
        teks.append(f"  {k} item di batas: {int((per_menu['jumlah_di_batas'] == k).sum())} menu")
    ada = per_menu[per_menu["jumlah_di_batas"] >= 1]
    tidak = per_menu[per_menu["jumlah_di_batas"] == 0]
    teks += ["", "Penyimpangan terbesar terhadap 100% (poin persen), rata-rata:",
             f"  Menu dengan >= 1 item di batas : {ada['penyimpangan_maks'].mean():.2f}  (n = {len(ada)})",
             f"  Menu tanpa item di batas       : "
             + (f"{tidak['penyimpangan_maks'].mean():.2f}  (n = {len(tidak)})" if len(tidak) else "(tidak ada)"),
             f"  Menu di luar 90-110%           : {int((per_menu['memenuhi'] == LABEL_TIDAK).sum())} dari {len(per_menu)}"]
    ringkasan = "\n".join(teks)
    BERKAS_RINGKASAN.write_text(ringkasan, encoding="utf-8")
    print(ringkasan)


if __name__ == "__main__":
    jalankan()