"""
uji_pola_malam.py

Menguji dugaan pada Subbab 4.2.3 dan 4.2.4: pada urutan sarapan, siang, malam,
persentase protein makan malam lebih rendah (dan lemak lebih tinggi) daripada
sarapan karena item yang sudah dipakai pada waktu makan sebelumnya dikecualikan.

Dasar uji: target sarapan dan makan malam identik (rho_w sama-sama 0,30 pada
rumus (9)), sehingga tanpa pengecualian keduanya memperoleh menu yang sama.
Perbedaan hasil hanya dapat berasal dari pengecualian item. Percobaan:
  1. Urutan normal (sarapan, siang, malam) dan urutan terbalik (malam, siang,
     sarapan). Bila dugaan benar, penurunan protein mengikuti POSISI ke-3,
     bukan nama waktu makan.
  2. Makan malam tanpa pengecualian item; harus sama dengan sarapan.

Alat bantu pengujian, bukan bagian sistem. Memakai metode privat
MesinRekomendasi._pilih_menu_waktu_makan agar urutan waktu makan dapat diubah.
Basis data tidak disentuh; pool bahan dibentuk dari data_makanan.csv melalui
kurasi_makanan (id_makanan 1..N sama dengan tabel makanan).

Masukan : data_uji/hasil_gizi.csv (keluaran uji_responden.py)
Keluaran: data_uji/uji_pola_malam.csv, data_uji/ringkasan_uji_pola_malam.txt
Waktu jalan: beberapa menit (47 profil x 10 pemilihan menu).
"""

import sys
from pathlib import Path
from typing import Any, Dict, Sequence, Set, Tuple

import pandas as pd

FOLDER_DATABASE = Path(__file__).resolve().parent
FOLDER_PROYEK = FOLDER_DATABASE.parent
FOLDER_DATA_UJI = FOLDER_PROYEK / "data_uji"
sys.path.insert(0, str(FOLDER_PROYEK))
sys.path.insert(0, str(FOLDER_DATABASE))

import kurasi_makanan  # noqa: E402
from kalkulator_gizi import KalkulatorGizi, ZAT_GIZI  # noqa: E402
from mesin_rekomendasi import MesinRekomendasi  # noqa: E402
from repositori_makanan import PERAN_VALID  # noqa: E402

# ---------------------------------------------------------------------------
# BERKAS DAN FORMAT
# ---------------------------------------------------------------------------
BERKAS_CSV_MAKANAN = FOLDER_DATABASE / "data_makanan.csv"
BERKAS_PROFIL = FOLDER_DATA_UJI / "hasil_gizi.csv"
BERKAS_HASIL = FOLDER_DATA_UJI / "uji_pola_malam.csv"
BERKAS_RINGKASAN = FOLDER_DATA_UJI / "ringkasan_uji_pola_malam.txt"
PEMISAH_CSV, DESIMAL_CSV, KODIFIKASI_CSV = ";", ",", "utf-8-sig"

# ---------------------------------------------------------------------------
# PERCOBAAN
# ---------------------------------------------------------------------------
URUTAN_NORMAL = ("sarapan", "siang", "malam")
URUTAN_TERBALIK = ("malam", "siang", "sarapan")
LABEL_NORMAL = "normal"
LABEL_TERBALIK = "terbalik"
LABEL_TANPA = "malam_tanpa_pengecualian"
TOLERANSI_TARGET = 1e-9
LABEL_YA, LABEL_TIDAK = "Ya", "Tidak"


def muat_pool() -> pd.DataFrame:
    """Pool bahan siap makan; id_makanan 1..N mengikuti urutan tabel makanan."""
    data = kurasi_makanan.ambil_siap_makan(str(BERKAS_CSV_MAKANAN))
    data.insert(0, "id_makanan", range(1, len(data) + 1))
    return data


def baca_profil() -> pd.DataFrame:
    if not BERKAS_PROFIL.exists():
        sys.exit(f"Berkas tidak ditemukan: {BERKAS_PROFIL}. Jalankan uji_responden.py lebih dulu.")
    return pd.read_csv(BERKAS_PROFIL, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, encoding=KODIFIKASI_CSV)


def id_menu(menu: Dict[str, Any]) -> Tuple[int, ...]:
    return tuple(int(menu["item"][p]["id_makanan"]) for p in PERAN_VALID)


def susun_berurutan(mesin: MesinRekomendasi, urutan: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Memilih menu berurutan; item waktu makan sebelumnya dikecualikan."""
    terpakai: Set[int] = set()
    hasil: Dict[str, Dict[str, Any]] = {}
    for waktu in urutan:
        menu = mesin._pilih_menu_waktu_makan(waktu, set(terpakai))
        hasil[waktu] = menu
        terpakai |= set(id_menu(menu))
    return hasil


def baris_hasil(kode: str, kelompok: str, percobaan: str, posisi: int,
                waktu: str, menu: Dict[str, Any]) -> Dict[str, Any]:
    pem = menu["pemenuhan"]
    return {
        "kode": kode, "kelompok": kelompok, "percobaan": percobaan,
        "posisi": posisi, "waktu_makan": waktu,
        **{f"{z}_persen": round(pem[z], 2) for z in ZAT_GIZI},
        "skor_rata_rata": round(menu["skor_rata_rata"], 4),
        "memenuhi": LABEL_YA if menu["memenuhi"] else LABEL_TIDAK,
        **{f"id_{p}": menu["item"][p]["id_makanan"] for p in PERAN_VALID},
    }


def ringkas(df: pd.DataFrame, periksa: Dict[str, int]) -> str:
    n = periksa["profil"]
    teks = ["UJI POLA MAKAN MALAM", "=" * 66, "", f"Jumlah profil: {n}", "",
            "Pemeriksaan validitas percobaan:",
            f"  Target sarapan = target malam (rumus 9): {periksa['target_sama']} dari {n}",
            f"  Urutan normal sama dengan susun_menu_harian(): {periksa['cocok_sistem']} dari {n}",
            f"  Malam tanpa pengecualian = menu sarapan: {periksa['tanpa_sama_sarapan']} dari {n}"]
    for percobaan, urutan in ((LABEL_NORMAL, URUTAN_NORMAL), (LABEL_TERBALIK, URUTAN_TERBALIK)):
        sub = df[df["percobaan"] == percobaan]
        teks += ["", f"Urutan {percobaan}: " + " -> ".join(urutan),
                 "Rata-rata persentase pemenuhan (%) menurut posisi:",
                 f"{'posisi':<8}{'waktu':<10}" + "".join(f"{z:>13}" for z in ZAT_GIZI) + f"{'skor':>9}"]
        for posisi, waktu in enumerate(urutan, start=1):
            s = sub[sub["posisi"] == posisi]
            teks.append(f"{posisi:<8}{waktu:<10}"
                        + "".join(f"{s[f'{z}_persen'].mean():>13.2f}" for z in ZAT_GIZI)
                        + f"{s['skor_rata_rata'].mean():>9.4f}")
        pp = sub.pivot(index="kode", columns="posisi", values="protein_persen")
        pl = sub.pivot(index="kode", columns="posisi", values="lemak_persen")
        teks += [f"Protein posisi 3 lebih rendah dari posisi 1: {int((pp[3] < pp[1]).sum())} dari {len(pp)} profil",
                 f"Lemak posisi 3 lebih tinggi dari posisi 1: {int((pl[3] > pl[1]).sum())} dari {len(pl)} profil",
                 f"Menu di luar 90-110%: {int((sub['memenuhi'] == LABEL_TIDAK).sum())} dari {len(sub)}"]
    tanpa = df[df["percobaan"] == LABEL_TANPA]
    malam = df[(df["percobaan"] == LABEL_NORMAL) & (df["waktu_makan"] == "malam")]
    teks += ["", "Makan malam: dengan pengecualian (normal) dibanding tanpa pengecualian",
             f"{'':<28}" + "".join(f"{z:>13}" for z in ZAT_GIZI) + f"{'skor':>9}"]
    for nama, s in (("dengan pengecualian", malam), ("tanpa pengecualian", tanpa)):
        teks.append(f"{nama:<28}" + "".join(f"{s[f'{z}_persen'].mean():>13.2f}" for z in ZAT_GIZI)
                    + f"{s['skor_rata_rata'].mean():>9.4f}")
    return "\n".join(teks)


def jalankan() -> None:
    pool = muat_pool()
    profil = baca_profil()
    FOLDER_DATA_UJI.mkdir(exist_ok=True)
    baris, periksa = [], dict(profil=len(profil), target_sama=0, cocok_sistem=0, tanpa_sama_sarapan=0)
    for _, p in profil.iterrows():
        kalk = KalkulatorGizi(int(p["usia"]), str(p["jenis_kelamin"]), float(p["berat_kg"]),
                              float(p["tinggi_cm"]), str(p["aktivitas"]))
        target = kalk.hitung_target_waktu_makan()
        mesin = MesinRekomendasi(pool, target)
        normal = susun_berurutan(mesin, URUTAN_NORMAL)
        terbalik = susun_berurutan(mesin, URUTAN_TERBALIK)
        tanpa = mesin._pilih_menu_waktu_makan("malam", set())
        acuan = mesin.susun_menu_harian()["menu"]

        periksa["target_sama"] += int(all(
            abs(target["sarapan"][z] - target["malam"][z]) <= TOLERANSI_TARGET for z in ZAT_GIZI))
        periksa["cocok_sistem"] += int(all(id_menu(normal[w]) == id_menu(acuan[w]) for w in URUTAN_NORMAL))
        periksa["tanpa_sama_sarapan"] += int(id_menu(tanpa) == id_menu(normal["sarapan"]))

        kode, kelompok = str(p["kode"]), str(p["kelompok"])
        for label, urutan, hasil in ((LABEL_NORMAL, URUTAN_NORMAL, normal),
                                     (LABEL_TERBALIK, URUTAN_TERBALIK, terbalik)):
            for posisi, waktu in enumerate(urutan, start=1):
                baris.append(baris_hasil(kode, kelompok, label, posisi, waktu, hasil[waktu]))
        baris.append(baris_hasil(kode, kelompok, LABEL_TANPA, 1, "malam", tanpa))
        print(f"{kode}: selesai")

    df = pd.DataFrame(baris)
    df.to_csv(BERKAS_HASIL, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, index=False, encoding=KODIFIKASI_CSV)
    ringkasan = ringkas(df, periksa)
    BERKAS_RINGKASAN.write_text(ringkasan, encoding="utf-8")
    print("\n" + ringkasan)


if __name__ == "__main__":
    jalankan()