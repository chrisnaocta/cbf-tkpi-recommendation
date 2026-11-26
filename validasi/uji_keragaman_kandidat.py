"""
Analisis keragaman kandidat K-Nearest Neighbor (KNN) dan kombinasi menu terpilih
pada 47 profil uji (40 responden + 7 profil sintetis valid).

Menunjukkan:
1. Keidentikan 15 kandidat KNN (5 pokok, 5 lauk, 5 sayur) di seluruh 47 profil x 3 waktu makan.
2. Jumlah bahan unik yang terpilih dan jumlah kombinasi menu harian unik.
3. Peran porsi gram sebagai mekanisme personalisasi antarprofil
   (jumlah variasi kombinasi bahan dan porsi).

Keluaran:
- data_uji/uji_keragaman_kandidat.csv
- data_uji/ringkasan_keragaman_kandidat.txt

Basis data asli tidak diubah: seluruh profil diproses pada salinan sementara.
"""

from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from aplikasi_utama import AplikasiUtama  # noqa: E402
from kalkulator_gizi import KalkulatorGizi  # noqa: E402
from koneksi_database import KoneksiDatabase  # noqa: E402
from mesin_rekomendasi import MesinRekomendasi  # noqa: E402
from repositori_makanan import RepositoriMakanan  # noqa: E402


# ---------------------------------------------------------------------------
# Konstanta skrip uji
# ---------------------------------------------------------------------------
JUMLAH_PROFIL_UJI = 47          # 40 responden + 7 profil sintetis
BARIS_PER_PROFIL = 9            # 3 waktu makan x (1 pokok + 1 lauk + 1 sayur)
WAKTU_MAKAN = ("sarapan", "siang", "malam")
PERAN_MENU = ("pokok", "lauk", "sayur")
DESIMAL_SKOR = 6                # pembulatan skor untuk membandingkan himpunan kandidat

# Pagar kewajaran data responden. Hanya untuk skrip uji ini (menangkap kesalahan
# pengolahan data, mis. tanda desimal hilang); bukan aturan validasi sistem (Tabel 3.2).
BERAT_MIN_KG, BERAT_MAX_KG = 30.0, 250.0
TINGGI_MIN_CM, TINGGI_MAX_CM = 100.0, 250.0

NILAI_PRIA = ("pria", "laki-laki", "laki - laki", "l")
NILAI_WANITA = ("wanita", "perempuan", "p")

# Format berkas hasil uji: pemisah titik koma, desimal koma, terbaca di Excel (lokal Indonesia).
CSV_PEMISAH = ";"
CSV_DESIMAL = ","
CSV_ENCODING = "utf-8-sig"

PROFIL_SINTETIS_VALID = [
    {"kode": "S01", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 70.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "menetap"},
    {"kode": "S02", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 70.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "aktif"},
    {"kode": "S03", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 70.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "sangat_aktif"},
    {"kode": "S04", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 75.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "menetap"},
    {"kode": "S05", "usia": 35, "jenis_kelamin": "wanita", "berat_badan": 80.0, "tinggi_badan": 160.0, "tingkat_aktivitas": "aktif"},
    {"kode": "S06", "usia": 40, "jenis_kelamin": "pria", "berat_badan": 100.0, "tinggi_badan": 200.0, "tingkat_aktivitas": "sangat_aktif"},
    {"kode": "S07", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 50.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "menetap"},
]


# ---------------------------------------------------------------------------
# Pemuatan profil
# ---------------------------------------------------------------------------
def baca_csv_fleksibel(path_csv: Path) -> pd.DataFrame:
    """Membaca CSV dengan pemisah titik koma ';' atau koma ','."""
    df = pd.read_csv(path_csv, sep=";")
    if df.shape[1] >= 5:
        return df
    return pd.read_csv(path_csv, sep=None, engine="python")


def petakan_jenis_kelamin(nilai: str, kode: str) -> str:
    """Memetakan isian jenis kelamin ke 'pria' atau 'wanita'; nilai lain ditolak."""
    teks = str(nilai).strip().lower()
    if teks in NILAI_PRIA:
        return "pria"
    if teks in NILAI_WANITA:
        return "wanita"
    raise ValueError(f"Jenis kelamin tidak dikenali pada {kode}: {nilai!r}")


def petakan_aktivitas(nilai: str) -> str:
    """Memetakan isian tingkat aktivitas ke kunci 'menetap', 'aktif', atau 'sangat_aktif'."""
    teks = str(nilai).strip().lower()
    if "sangat" in teks:
        return "sangat_aktif"
    if "aktif" in teks and "menetap" not in teks and "ringan" not in teks:
        return "aktif"
    return "menetap"


def ubah_angka(nilai, nama: str, kode: str, batas_min: float, batas_maks: float) -> float:
    """Mengubah teks angka (koma atau titik desimal) dan memeriksa kewajarannya."""
    angka = float(str(nilai).strip().replace(",", "."))
    if not batas_min <= angka <= batas_maks:
        raise ValueError(
            f"{nama} tidak wajar pada {kode}: {angka} (batas {batas_min}-{batas_maks}). "
            "Periksa tanda desimal pada berkas responden."
        )
    return angka


def muat_47_profil(path_responden: Path) -> list[dict]:
    """Memuat 40 responden dari CSV dan menggabungkannya dengan 7 profil sintetis valid."""
    df_resp = baca_csv_fleksibel(path_responden)
    kolom_map = {c.lower().strip(): c for c in df_resp.columns}

    def ambil_kolom(kandidat_nama: list[str]) -> str:
        for k in kandidat_nama:
            if k in kolom_map:
                return kolom_map[k]
        for k in kandidat_nama:
            for col_lower, col_asli in kolom_map.items():
                if col_lower.startswith(k):
                    return col_asli
        raise KeyError(f"Kolom {kandidat_nama} tidak ditemukan pada {path_responden}: {list(df_resp.columns)}")

    c_kode = ambil_kolom(["responden", "kode", "id"])
    c_usia = ambil_kolom(["usia (tahun)", "usia"])
    c_jk = ambil_kolom(["jenis kelamin", "jenis_kelamin", "jk"])
    c_bb = ambil_kolom(["berat badan (kg)", "berat_badan", "bb"])
    c_tb = ambil_kolom(["tinggi badan (cm)", "tinggi_badan", "tb"])
    c_akt = ambil_kolom(["tingkat aktivitas fisik harian", "tingkat_aktivitas", "aktivitas"])

    profil_list = []
    for _, row in df_resp.iterrows():
        kode = str(row[c_kode]).strip()
        profil_list.append(
            {
                "kode": kode,
                "usia": int(float(str(row[c_usia]).strip())),
                "jenis_kelamin": petakan_jenis_kelamin(row[c_jk], kode),
                "berat_badan": ubah_angka(row[c_bb], "Berat badan", kode, BERAT_MIN_KG, BERAT_MAX_KG),
                "tinggi_badan": ubah_angka(row[c_tb], "Tinggi badan", kode, TINGGI_MIN_CM, TINGGI_MAX_CM),
                "tingkat_aktivitas": petakan_aktivitas(row[c_akt]),
            }
        )

    profil_list.extend(PROFIL_SINTETIS_VALID)
    return profil_list


# ---------------------------------------------------------------------------
# Kandidat KNN dan penyusunan menu
# ---------------------------------------------------------------------------
def ekstrak_kandidat(hasil: pd.DataFrame) -> list[tuple[int, float]]:
    """Mengambil pasangan (id_makanan, skor_similarity) dari luaran cari_k_tetangga_terdekat."""
    return [
        (int(i), round(float(s), DESIMAL_SKOR))
        for i, s in zip(hasil["id_makanan"], hasil["skor_similarity"])
    ]


def ambil_15_kandidat_knn(
    df_makanan: pd.DataFrame, profil: dict
) -> dict[str, list[tuple[int, float]]]:
    """Mengambil 15 kandidat KNN (5 pokok, 5 lauk, 5 sayur) untuk tiap waktu makan.

    Pencarian dilakukan tanpa item yang dikecualikan, sehingga yang diperiksa
    adalah himpunan kandidat murni dari vektor target.
    """
    kalk = KalkulatorGizi(
        profil["usia"],
        profil["jenis_kelamin"],
        profil["berat_badan"],
        profil["tinggi_badan"],
        profil["tingkat_aktivitas"],
    )
    mesin = MesinRekomendasi(df_makanan, kalk.hitung_target_waktu_makan())

    kandidat_per_waktu = {}
    for wm in WAKTU_MAKAN:
        blok_15 = []
        for peran in PERAN_MENU:
            blok_15.extend(ekstrak_kandidat(mesin.cari_k_tetangga_terdekat(wm, peran, set())))
        kandidat_per_waktu[wm] = blok_15
    return kandidat_per_waktu


def buat_aplikasi_sementara(db_sementara: Path) -> AplikasiUtama:
    """Membuat AplikasiUtama yang terhubung ke salinan basis data (basis data asli tidak diubah)."""
    return AplikasiUtama(RepositoriMakanan(KoneksiDatabase(str(db_sementara))))


def jalankan_input_awal(app: AplikasiUtama, profil: dict) -> None:
    """Memproses satu profil seperti pengguna mengisi formulir."""
    app.proses_input_pengguna(
        usia=profil["usia"],
        jenis_kelamin=profil["jenis_kelamin"],
        berat_badan=profil["berat_badan"],
        tinggi_badan=profil["tinggi_badan"],
        tingkat_aktivitas=profil["tingkat_aktivitas"],
    )


# ---------------------------------------------------------------------------
# Program utama
# ---------------------------------------------------------------------------
def main() -> None:
    db_asli = ROOT_DIR / "database" / "rekomendasi_makanan.db"
    folder_uji = ROOT_DIR / "data_uji"
    path_responden = folder_uji / "responden.csv"

    profil_47 = muat_47_profil(path_responden)
    assert len(profil_47) == JUMLAH_PROFIL_UJI, (
        f"Jumlah profil uji harus {JUMLAH_PROFIL_UJI}, ditemukan {len(profil_47)}"
    )

    conn_read = sqlite3.connect(db_asli)
    try:
        df_makanan = pd.read_sql_query("SELECT * FROM makanan ORDER BY id_makanan ASC", conn_read)
    finally:
        conn_read.close()

    # 1. Periksa keidentikan 15 kandidat KNN pada 47 profil x 3 waktu makan (141 evaluasi)
    himpunan_kandidat_unik = set()
    referensi_kandidat = None
    for p in profil_47:
        for daftar_15 in ambil_15_kandidat_knn(df_makanan, p).values():
            himpunan_kandidat_unik.add(tuple(daftar_15))
            if referensi_kandidat is None:
                referensi_kandidat = daftar_15

    # 2. Proses 47 profil pada salinan basis data untuk melihat bahan dan kombinasi aktual
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_sementara = Path(tmp_dir) / "rekomendasi_makanan_47.db"
        shutil.copy2(db_asli, db_sementara)
        app = buat_aplikasi_sementara(db_sementara)
        try:
            for p in profil_47:
                jalankan_input_awal(app, p)
        finally:
            app.repositori.koneksi.close()

        conn = sqlite3.connect(db_sementara)
        try:
            df_riwayat = pd.read_sql_query(
                """
                SELECT
                    r.id_rekomendasi,
                    r.id_sesi,
                    r.jenis_waktu_makan,
                    r.skor_similarity,
                    r.porsi_gram,
                    m.id_makanan,
                    m.kode_tkpi,
                    m.nama_bahan,
                    m.peran_menu
                FROM riwayat_rekomendasi r
                JOIN makanan m ON r.id_makanan = m.id_makanan
                ORDER BY r.id_rekomendasi ASC
                """,
                conn,
            )
        finally:
            conn.close()

    assert len(df_riwayat) == len(profil_47) * BARIS_PER_PROFIL, (
        f"Jumlah baris riwayat ({len(df_riwayat)}) tidak sesuai harapan "
        f"({len(profil_47) * BARIS_PER_PROFIL})."
    )

    frekuensi_item = df_riwayat["id_makanan"].value_counts().to_dict()
    bahan_unik_terpilih = sorted(df_riwayat["id_makanan"].unique().tolist())

    # Seluruh bahan terpilih harus berasal dari 15 kandidat; bila tidak, kalimat
    # "n dari 15 kandidat" pada keluaran tidak berlaku.
    id_kandidat = {id_m for id_m, _ in referensi_kandidat}
    assert set(bahan_unik_terpilih) <= id_kandidat, (
        f"Ada bahan terpilih di luar 15 kandidat: {sorted(set(bahan_unik_terpilih) - id_kandidat)}"
    )

    kombinasi_harian = {}
    kombinasi_dengan_porsi = set()
    for idx, p in enumerate(profil_47):
        blok = df_riwayat.iloc[idx * BARIS_PER_PROFIL : (idx + 1) * BARIS_PER_PROFIL]
        sig_bahan = tuple(int(x) for x in blok["id_makanan"])
        sig_porsi = tuple((int(r["id_makanan"]), float(r["porsi_gram"])) for _, r in blok.iterrows())
        kombinasi_harian.setdefault(sig_bahan, []).append(p["kode"])
        kombinasi_dengan_porsi.add(sig_porsi)

    map_makanan = df_makanan.set_index("id_makanan").to_dict(orient="index")
    baris_kandidat = []
    for urutan, (id_m, skor) in enumerate(referensi_kandidat, start=1):
        info = map_makanan[id_m]
        jml_pilih = int(frekuensi_item.get(id_m, 0))
        baris_kandidat.append(
            {
                "urutan_kandidat": urutan,
                "peran_menu": info["peran_menu"],
                "peringkat_per_peran": ((urutan - 1) % 5) + 1,
                "id_makanan": id_m,
                "kode_tkpi": info["kode_tkpi"],
                "nama_bahan": info["nama_bahan"],
                "skor_cosine_similarity": round(skor, DESIMAL_SKOR),
                "frekuensi_terpilih_47_profil": jml_pilih,
                "status_keterpilihan": "Terpilih" if jml_pilih > 0 else "Tidak pernah terpilih",
            }
        )

    df_kandidat = pd.DataFrame(baris_kandidat)
    path_csv = folder_uji / "uji_keragaman_kandidat.csv"
    df_kandidat.to_csv(
        path_csv, index=False, sep=CSV_PEMISAH, decimal=CSV_DESIMAL, encoding=CSV_ENCODING
    )

    tidak_terpilih = df_kandidat[df_kandidat["frekuensi_terpilih_47_profil"] == 0]["nama_bahan"].tolist()
    urut_kombinasi = sorted(kombinasi_harian.items(), key=lambda x: len(x[1]), reverse=True)

    ringkasan = [
        "RINGKASAN ANALISIS KERAGAMAN KANDIDAT KNN PADA 47 PROFIL UJI",
        "=" * 64,
        f"Jumlah profil uji               : {len(profil_47)} profil (40 responden + 7 sintetis valid)",
        f"Total evaluasi waktu makan      : {len(profil_47) * 3} waktu makan (47 x 3)",
        f"Set 15 kandidat KNN unik        : {len(himpunan_kandidat_unik)} set "
        f"(identik di seluruh {len(profil_47) * 3} waktu makan bila bernilai 1)",
        f"Total kandidat KNN per evaluasi : {len(referensi_kandidat)} bahan (5 pokok + 5 lauk + 5 sayur)",
        f"Bahan unik terpilih (423 item)  : {len(bahan_unik_terpilih)} dari {len(referensi_kandidat)} kandidat",
        f"Kandidat tidak pernah terpilih  : {', '.join(tidak_terpilih) if tidak_terpilih else '-'}",
        f"Kombinasi menu harian unik      : {len(kombinasi_harian)} kombinasi dari {len(profil_47)} profil",
        f"Kombinasi (bahan + porsi) unik  : {len(kombinasi_dengan_porsi)} variasi dari {len(profil_47)} profil",
        "",
        f"Distribusi {len(kombinasi_harian)} Kombinasi Menu Harian Unik:",
    ]
    for no_komb, (sig_9, daftar_kode) in enumerate(urut_kombinasi, start=1):
        nama_9 = [map_makanan[i]["nama_bahan"] for i in sig_9]
        ringkasan.append(
            f"  Kombinasi {no_komb} ({len(daftar_kode)} profil: {', '.join(daftar_kode[:5])}"
            f"{'...' if len(daftar_kode) > 5 else ''}):"
        )
        ringkasan.append(f"    Sarapan : {nama_9[0]} | {nama_9[1]} | {nama_9[2]}")
        ringkasan.append(f"    Siang   : {nama_9[3]} | {nama_9[4]} | {nama_9[5]}")
        ringkasan.append(f"    Malam   : {nama_9[6]} | {nama_9[7]} | {nama_9[8]}")

    teks_ringkasan = "\n".join(ringkasan)
    path_txt = folder_uji / "ringkasan_keragaman_kandidat.txt"
    path_txt.write_text(teks_ringkasan + "\n", encoding="utf-8")

    print(teks_ringkasan)
    print(f"\nBerkas disimpan ke:\n- {path_csv}\n- {path_txt}")


if __name__ == "__main__":
    main()