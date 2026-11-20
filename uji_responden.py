"""
uji_responden.py

Menjalankan alur sistem (AplikasiUtama.proses_input_pengguna) untuk data responden
dan data sintetis valid, lalu menyimpan hasilnya ke CSV sebagai bahan Subbab 4.2.

Skrip ini alat bantu pengujian, bukan bagian sistem. Basis data yang dipakai adalah
berkas sementara yang dibuat dengan setup_db.py (pool bahan sama dengan basis data
skripsi), sehingga rekomendasi_makanan.db tidak tertulis.

Masukan : data_uji/responden.csv (pemisah titik koma; kolom pada KOLOM_* di bawah)
Keluaran: data_uji/hasil_gizi.csv, hasil_menu.csv, hasil_pemenuhan.csv, ringkasan_uji.txt

Jalankan dari folder utama:  python uji_responden.py
"""

import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))
sys.path.insert(0, str(FOLDER / "database"))

import setup_db  # noqa: E402
from aplikasi_utama import AplikasiUtama  # noqa: E402
from kalkulator_gizi import ZAT_GIZI  # noqa: E402
from koneksi_database import KoneksiDatabase  # noqa: E402
from repositori_makanan import PERAN_VALID, RepositoriMakanan  # noqa: E402

# ---------------------------------------------------------------------------
# BERKAS
# ---------------------------------------------------------------------------
FOLDER_DATA_UJI = FOLDER / "data_uji"
BERKAS_RESPONDEN = FOLDER_DATA_UJI / "responden.csv"
BERKAS_CSV_MAKANAN = FOLDER / "database" / "data_makanan.csv"
BERKAS_HASIL_GIZI = FOLDER_DATA_UJI / "hasil_gizi.csv"
BERKAS_HASIL_MENU = FOLDER_DATA_UJI / "hasil_menu.csv"
BERKAS_HASIL_PEMENUHAN = FOLDER_DATA_UJI / "hasil_pemenuhan.csv"
BERKAS_RINGKASAN = FOLDER_DATA_UJI / "ringkasan_uji.txt"

# Format CSV (Excel berbahasa Indonesia: pemisah titik koma, desimal koma)
PEMISAH_CSV = ";"
DESIMAL_CSV = ","
KODIFIKASI_CSV = "utf-8-sig"

# Nama kolom pada responden.csv
KOLOM_KODE = "Responden"
KOLOM_USIA = "Usia (Tahun)"
KOLOM_JENIS_KELAMIN = "Jenis Kelamin"
KOLOM_BERAT = "Berat Badan (kg)"
KOLOM_TINGGI = "Tinggi Badan (cm)"
KOLOM_AKTIVITAS = "Tingkat Aktivitas Fisik Harian"

# Pemetaan isian Google Form ke nilai yang dikenal sistem (dicocokkan dari awal teks)
AWALAN_AKTIVITAS = (("menetap", "menetap"), ("aktif", "aktif"), ("sangat", "sangat_aktif"))
PEMETAAN_JENIS_KELAMIN = {
    "pria": "pria", "laki-laki": "pria", "wanita": "wanita", "perempuan": "wanita",
}

# Pemeriksaan kewajaran oleh penguji (BUKAN bagian sistem): IMT di luar rentang ini
# dianggap salah ketik dan skrip berhenti.
IMT_WAJAR_MIN = 13.0
IMT_WAJAR_MAX = 60.0

# Kelompok umur AKG (Tabel 2.3)
BATAS_KELOMPOK_USIA = 29
LABEL_USIA_BAWAH = "19-29 tahun"
LABEL_USIA_ATAS = "30-49 tahun"

PERSEN_SEMPURNA = 100.0
LABEL_YA, LABEL_TIDAK = "Ya", "Tidak"

# ---------------------------------------------------------------------------
# NILAI ACUAN PERHITUNGAN MANUAL (ditulis ulang dari Bab 3, tidak mengimpor
# kalkulator_gizi agar menjadi pembanding yang berdiri sendiri)
# ---------------------------------------------------------------------------
MANUAL_FA = {"menetap": 1.55, "aktif": 1.85, "sangat_aktif": 2.20}   # Tabel 3.1
MANUAL_BMR_BERAT, MANUAL_BMR_TINGGI, MANUAL_BMR_USIA = 10.0, 6.25, 5.0  # rumus (2), (3)
MANUAL_BMR_PRIA, MANUAL_BMR_WANITA = 5.0, -161.0
MANUAL_BATAS_IMT, MANUAL_DEFISIT = 25.0, 500.0                         # rumus (5)
MANUAL_PERSEN = {"protein": 0.15, "lemak": 0.25, "karbohidrat": 0.60}  # rumus (6)-(8)
MANUAL_ATWATER = {"protein": 4.0, "lemak": 9.0, "karbohidrat": 4.0}
TOLERANSI_MANUAL = 1e-6

# ---------------------------------------------------------------------------
# DATA SINTETIS VALID (Tabel data sintetis pada Subbab 4.2.1)
# (kode, usia, jenis_kelamin, berat, tinggi, aktivitas)
# ---------------------------------------------------------------------------
SINTETIS_VALID = (
    ("S01", 30, "pria", 70.0, 170.0, "menetap"),
    ("S02", 30, "pria", 70.0, 170.0, "aktif"),
    ("S03", 30, "pria", 70.0, 170.0, "sangat_aktif"),
    ("S04", 30, "pria", 75.0, 170.0, "menetap"),
    ("S05", 35, "wanita", 80.0, 160.0, "aktif"),
    ("S06", 40, "pria", 100.0, 200.0, "sangat_aktif"),
    ("S07", 30, "pria", 50.0, 170.0, "menetap"),
)


# ---------------------------------------------------------------------------
# Pembacaan dan pemeriksaan data
# ---------------------------------------------------------------------------
def _angka(teks: Any) -> float:
    return float(str(teks).strip().replace(",", "."))


def _petakan_aktivitas(teks: Any) -> str:
    awal = str(teks).strip().lower()
    for awalan, nilai in AWALAN_AKTIVITAS:
        if awal.startswith(awalan):
            return nilai
    raise ValueError(f"Tingkat aktivitas tidak dikenal: {str(teks)[:40]!r}")


def baca_responden() -> List[Dict[str, Any]]:
    if not BERKAS_RESPONDEN.exists():
        sys.exit(f"Berkas tidak ditemukan: {BERKAS_RESPONDEN}")
    df = pd.read_csv(BERKAS_RESPONDEN, sep=PEMISAH_CSV, encoding=KODIFIKASI_CSV, dtype=str)
    daftar = []
    for _, b in df.iterrows():
        jk = str(b[KOLOM_JENIS_KELAMIN]).strip().lower()
        daftar.append(dict(
            kode=str(b[KOLOM_KODE]).strip(), kelompok="responden",
            usia=int(_angka(b[KOLOM_USIA])), jenis_kelamin=PEMETAAN_JENIS_KELAMIN[jk],
            berat=_angka(b[KOLOM_BERAT]), tinggi=_angka(b[KOLOM_TINGGI]),
            aktivitas=_petakan_aktivitas(b[KOLOM_AKTIVITAS]),
        ))
    return daftar


def periksa_kewajaran(daftar: List[Dict[str, Any]]) -> None:
    curiga = []
    for d in daftar:
        imt = d["berat"] / (d["tinggi"] / 100.0) ** 2
        if not IMT_WAJAR_MIN <= imt <= IMT_WAJAR_MAX:
            curiga.append(f"  {d['kode']}: berat {d['berat']} kg, tinggi {d['tinggi']} cm (IMT {imt:.1f})")
    if curiga:
        print("Data berikut tidak wajar (kemungkinan salah ketik). Perbaiki responden.csv lalu jalankan ulang:")
        print("\n".join(curiga))
        sys.exit(1)


def hitung_manual(d: Dict[str, Any]) -> Dict[str, float]:
    """Rumus (1)-(8) ditulis ulang secara mandiri."""
    imt = d["berat"] / (d["tinggi"] / 100.0) ** 2
    konstanta = MANUAL_BMR_PRIA if d["jenis_kelamin"] == "pria" else MANUAL_BMR_WANITA
    bmr = (MANUAL_BMR_BERAT * d["berat"] + MANUAL_BMR_TINGGI * d["tinggi"]
           - MANUAL_BMR_USIA * d["usia"] + konstanta)
    tee = bmr * MANUAL_FA[d["aktivitas"]]
    energi = tee - MANUAL_DEFISIT if imt > MANUAL_BATAS_IMT else tee
    hasil = {"imt": imt, "bmr": bmr, "tee": tee, "energi": energi}
    for zat, persen in MANUAL_PERSEN.items():
        hasil[zat] = persen * energi / MANUAL_ATWATER[zat]
    return hasil


# ---------------------------------------------------------------------------
# Penyusunan baris hasil
# ---------------------------------------------------------------------------
def baris_pemenuhan(d: Dict[str, Any], cakupan: str, pemenuhan, memenuhi: bool) -> Dict[str, Any]:
    baris: Dict[str, Any] = {"kode": d["kode"], "kelompok": d["kelompok"], "cakupan": cakupan}
    for zat in ZAT_GIZI:
        baris[f"{zat}_persen"] = round(pemenuhan[zat], 2)
    baris["penyimpangan_maks"] = round(max(abs(pemenuhan[z] - PERSEN_SEMPURNA) for z in ZAT_GIZI), 2)
    baris["memenuhi"] = LABEL_YA if memenuhi else LABEL_TIDAK
    return baris


def susun_ringkasan(df_gizi: pd.DataFrame, df_pem: pd.DataFrame) -> str:
    resp = df_gizi[df_gizi["kelompok"] == "responden"]
    pem = df_pem[df_pem["kelompok"] == "responden"]
    baris = ["RINGKASAN UJI (responden saja, kecuali dinyatakan lain)", "=" * 60, ""]
    baris.append(f"Jumlah responden: {len(resp)}")
    for judul, kolom in (("Jenis kelamin", "jenis_kelamin"), ("Kelompok usia", "kelompok_usia"),
                         ("Tingkat aktivitas", "aktivitas"), ("Kategori IMT", "kategori_imt")):
        baris += ["", f"{judul}:"] + [f"  {k}: {v}" for k, v in resp[kolom].value_counts().items()]

    semua = df_gizi
    baris += ["", "Verifikasi (responden dan sintetis):",
              f"  Cocok dengan hitung manual (IMT, BMR, TEE, target harian): "
              f"{int((semua['cocok_manual'] == LABEL_YA).sum())} dari {len(semua)}",
              f"  Hasil identik pada dua kali pemrosesan: "
              f"{int((semua['konsisten'] == LABEL_YA).sum())} dari {len(semua)}",
              f"  Waktu proses (detik): rata-rata {semua['waktu_proses_detik'].mean():.2f}, "
              f"maksimum {semua['waktu_proses_detik'].max():.2f}"]

    baris += ["", "Kesesuaian gizi (rentang 90-110% pada keempat zat gizi):"]
    for cakupan in ("sarapan", "siang", "malam", "harian"):
        sub = pem[pem["cakupan"] == cakupan]
        ok = int((sub["memenuhi"] == LABEL_YA).sum())
        baris.append(f"  {cakupan}: {ok} dari {len(sub)} memenuhi ({ok / len(sub) * 100:.1f}%)")
        for zat in ZAT_GIZI:
            kol = sub[f"{zat}_persen"]
            baris.append(f"      {zat}: min {kol.min():.2f}  rata-rata {kol.mean():.2f}  maks {kol.max():.2f}")
    tidak = pem[pem["memenuhi"] == LABEL_TIDAK]
    baris += ["", "Responden dan cakupan yang belum memenuhi:"]
    baris += [f"  {r.kode} - {r.cakupan} (penyimpangan maks {r.penyimpangan_maks:.2f} poin)"
              for r in tidak.itertuples()] or ["  (tidak ada)"]
    sint = df_pem[(df_pem["kelompok"] == "sintetis") & (df_pem["memenuhi"] == LABEL_TIDAK)]
    baris += ["", "Data sintetis yang belum memenuhi:"]
    baris += [f"  {r.kode} - {r.cakupan} (penyimpangan maks {r.penyimpangan_maks:.2f} poin)"
              for r in sint.itertuples()] or ["  (tidak ada)"]
    return "\n".join(baris)


# ---------------------------------------------------------------------------
# Program utama
# ---------------------------------------------------------------------------
def jalankan() -> None:
    daftar = baca_responden() + [
        dict(kode=k, kelompok="sintetis", usia=u, jenis_kelamin=jk, berat=b, tinggi=t, aktivitas=a)
        for k, u, jk, b, t, a in SINTETIS_VALID
    ]
    periksa_kewajaran(daftar)
    FOLDER_DATA_UJI.mkdir(exist_ok=True)

    gizi, menu, pemenuhan = [], [], []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        jalur_db = str(Path(tmp) / "uji.db")
        setup_db.DB_NAME = jalur_db
        setup_db.create_tables()
        setup_db.import_csv_to_db(str(BERKAS_CSV_MAKANAN))
        koneksi = KoneksiDatabase(jalur_db)
        try:
            repositori = RepositoriMakanan(koneksi)
            makanan = repositori.get_all_makanan()
            if makanan.empty:
                sys.exit("Tabel makanan kosong; periksa keluaran setup_db di atas.")
            print(f"Pool bahan: {len(makanan)} ({makanan['peran_menu'].value_counts().to_dict()})")
            kode_tkpi = makanan.set_index("id_makanan")["kode_tkpi"]

            for d in daftar:
                masukan = (d["usia"], d["jenis_kelamin"], d["berat"], d["tinggi"], d["aktivitas"])
                aplikasi = AplikasiUtama(repositori)
                mulai = time.perf_counter()
                hasil = aplikasi.proses_input_pengguna(*masukan)
                waktu = time.perf_counter() - mulai
                rek = aplikasi.sesi.rekomendasi_saat_ini

                ulang = AplikasiUtama(repositori)
                ulang.proses_input_pengguna(*masukan)
                konsisten = rek == ulang.sesi.rekomendasi_saat_ini

                man = hitung_manual(d)
                harian = hasil["target_harian"]
                pasangan = [(hasil["imt"], man["imt"]), (hasil["bmr"], man["bmr"]), (hasil["tee"], man["tee"])]
                pasangan += [(harian[z], man[z]) for z in ZAT_GIZI]
                cocok = all(abs(a - b) <= TOLERANSI_MANUAL for a, b in pasangan)

                jumlah_ok = sum(m["memenuhi"] for m in rek["menu"].values())
                gizi.append({
                    "kode": d["kode"], "kelompok": d["kelompok"], "usia": d["usia"],
                    "kelompok_usia": LABEL_USIA_BAWAH if d["usia"] <= BATAS_KELOMPOK_USIA else LABEL_USIA_ATAS,
                    "jenis_kelamin": d["jenis_kelamin"], "berat_kg": d["berat"], "tinggi_cm": d["tinggi"],
                    "aktivitas": d["aktivitas"], "imt": round(hasil["imt"], 2),
                    "kategori_imt": hasil["klasifikasi"], "bmr": round(hasil["bmr"], 1),
                    "tee": round(hasil["tee"], 1),
                    **{f"target_{z}": round(harian[z], 1) for z in ZAT_GIZI},
                    "waktu_makan_memenuhi": jumlah_ok,
                    "harian_memenuhi": LABEL_YA if rek["harian"]["memenuhi"] else LABEL_TIDAK,
                    "cocok_manual": LABEL_YA if cocok else LABEL_TIDAK,
                    "konsisten": LABEL_YA if konsisten else LABEL_TIDAK,
                    "waktu_proses_detik": round(waktu, 3),
                })
                for waktu_makan, isi in rek["menu"].items():
                    for peran in PERAN_VALID:
                        b = isi["item"][peran]
                        menu.append({
                            "kode": d["kode"], "kelompok": d["kelompok"], "waktu_makan": waktu_makan,
                            "peran": peran, "id_makanan": b["id_makanan"],
                            "kode_tkpi": kode_tkpi[b["id_makanan"]], "nama_bahan": b["nama_bahan"],
                            "porsi_gram": b["porsi_gram"],
                            **{z: round(b[z], 1) for z in ZAT_GIZI},
                            "skor_similarity": round(b["skor_similarity"], 4),
                        })
                    pemenuhan.append(baris_pemenuhan(d, waktu_makan, isi["pemenuhan"], isi["memenuhi"]))
                pemenuhan.append(baris_pemenuhan(d, "harian", rek["harian"]["pemenuhan"], rek["harian"]["memenuhi"]))
                print(f"{d['kode']}: selesai ({waktu:.2f} detik)")
        finally:
            koneksi.close()

    df_gizi, df_menu, df_pem = pd.DataFrame(gizi), pd.DataFrame(menu), pd.DataFrame(pemenuhan)
    for df, berkas in ((df_gizi, BERKAS_HASIL_GIZI), (df_menu, BERKAS_HASIL_MENU), (df_pem, BERKAS_HASIL_PEMENUHAN)):
        df.to_csv(berkas, sep=PEMISAH_CSV, decimal=DESIMAL_CSV, index=False, encoding=KODIFIKASI_CSV)
    ringkasan = susun_ringkasan(df_gizi, df_pem)
    BERKAS_RINGKASAN.write_text(ringkasan, encoding="utf-8")
    print("\n" + ringkasan)
    print(f"\nHasil disimpan di folder: {FOLDER_DATA_UJI}")


if __name__ == "__main__":
    jalankan()