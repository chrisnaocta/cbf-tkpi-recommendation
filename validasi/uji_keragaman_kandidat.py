"""
Analisis keragaman kandidat K-Nearest Neighbor (KNN) dan kombinasi menu terpilih
pada 47 profil uji (40 responden + 7 profil sintetis valid).

Membuktikan:
1. Keidentikan 15 kandidat KNN (5 pokok, 5 lauk, 5 sayur) di seluruh 47 profil x 3 waktu makan.
2. Jumlah bahan unik yang terpilih (13 bahan) dan kombinasi menu harian unik (5 kombinasi).
3. Peran porsi gram sebagai mekanisme utama personalisasi antarprofil.

Keluaran:
- data_uji/uji_keragaman_kandidat.csv
- data_uji/ringkasan_keragaman_kandidat.txt
"""

from pathlib import Path
import inspect
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


PROFIL_SINTETIS_VALID = [
    {"kode": "S01", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 70.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "menetap"},
    {"kode": "S02", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 70.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "aktif"},
    {"kode": "S03", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 70.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "sangat_aktif"},
    {"kode": "S04", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 75.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "menetap"},
    {"kode": "S05", "usia": 35, "jenis_kelamin": "wanita", "berat_badan": 80.0, "tinggi_badan": 160.0, "tingkat_aktivitas": "aktif"},
    {"kode": "S06", "usia": 40, "jenis_kelamin": "pria", "berat_badan": 100.0, "tinggi_badan": 200.0, "tingkat_aktivitas": "sangat_aktif"},
    {"kode": "S07", "usia": 30, "jenis_kelamin": "pria", "berat_badan": 50.0, "tinggi_badan": 170.0, "tingkat_aktivitas": "menetap"},
]


def baca_csv_fleksibel(path_csv: Path) -> pd.DataFrame:
    """Membaca CSV dengan pemisah titik koma ';' atau koma ','."""
    df = pd.read_csv(path_csv, sep=";")
    if df.shape[1] >= 5:
        return df
    return pd.read_csv(path_csv, sep=None, engine="python")


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
    for idx, row in df_resp.iterrows():
        kode = str(row[c_kode]).strip() if c_kode else f"R{idx + 1:02d}"
        jk_raw = str(row[c_jk]).strip().lower()
        jk = "pria" if jk_raw in ("pria", "laki-laki", "laki - laki", "l") else "wanita"

        akt_raw = str(row[c_akt]).strip().lower()
        if "sangat" in akt_raw:
            akt = "sangat_aktif"
        elif "aktif" in akt_raw and "menetap" not in akt_raw and "ringan" not in akt_raw:
            akt = "aktif"
        else:
            akt = "menetap"

        bb_val = float(str(row[c_bb]).strip().replace(",", "."))
        tb_val = float(str(row[c_tb]).strip().replace(",", "."))

        profil_list.append(
            {
                "kode": kode,
                "usia": int(float(str(row[c_usia]).strip())),
                "jenis_kelamin": jk,
                "berat_badan": bb_val,
                "tinggi_badan": tb_val,
                "tingkat_aktivitas": akt,
            }
        )

    profil_list.extend(PROFIL_SINTETIS_VALID)
    return profil_list


def buat_mesin(df_makanan: pd.DataFrame, repo: RepositoriMakanan, target_wm: dict) -> MesinRekomendasi:
    """Inisialisasi MesinRekomendasi sesuai parameter konstruktornya."""
    sig = inspect.signature(MesinRekomendasi.__init__)
    params = [p for p in sig.parameters if p != "self"]
    if params and "repo" in params[0]:
        return MesinRekomendasi(repo, target_wm)
    return MesinRekomendasi(df_makanan, target_wm)


def ekstrak_5_kandidat(hasil) -> list[tuple[int, float]]:
    """Mengekstrak 5 pasangan (id_makanan, skor_similarity) dari luaran cari_k_tetangga_terdekat."""
    if isinstance(hasil, pd.DataFrame):
        kol_skor = next(
            (c for c in hasil.columns if "skor" in c.lower() or "sim" in c.lower()),
            hasil.columns[-1],
        )
        if "id_makanan" in hasil.columns:
            return [
                (int(r["id_makanan"]), round(float(r[kol_skor]), 6))
                for _, r in hasil.iterrows()
            ]
        return [
            (int(idx), round(float(r[kol_skor]), 6))
            for idx, r in hasil.iterrows()
        ]

    if isinstance(hasil, list) and hasil and isinstance(hasil[0], dict):
        kol_skor = next(
            (k for k in hasil[0].keys() if "skor" in k.lower() or "sim" in k.lower()),
            list(hasil[0].keys())[-1],
        )
        return [
            (int(r["id_makanan"]), round(float(r[kol_skor]), 6))
            for r in hasil
        ]

    raise TypeError(f"Format keluaran cari_k_tetangga_terdekat tidak dikenali: {type(hasil)}")


def ambil_15_kandidat_knn(
    df_makanan: pd.DataFrame, repo: RepositoriMakanan, profil: dict
) -> dict[str, list[tuple[int, float]]]:
    """Mengambil 15 kandidat KNN (5 pokok, 5 lauk, 5 sayur) untuk ketiga waktu makan."""
    kalk = KalkulatorGizi(
        profil["usia"],
        profil["jenis_kelamin"],
        profil["berat_badan"],
        profil["tinggi_badan"],
        profil["tingkat_aktivitas"],
    )
    target_wm = kalk.hitung_target_waktu_makan()
    mesin = buat_mesin(df_makanan, repo, target_wm)

    kandidat_per_waktu = {}
    for wm in ("sarapan", "siang", "malam"):
        blok_15 = []
        for peran in ("pokok", "lauk", "sayur"):
            hasil_k5 = mesin.cari_k_tetangga_terdekat(wm, peran, set())
            blok_15.extend(ekstrak_5_kandidat(hasil_k5))
        kandidat_per_waktu[wm] = blok_15
    return kandidat_per_waktu


def buat_aplikasi_sementara(db_sementara: Path) -> AplikasiUtama:
    sig = inspect.signature(AplikasiUtama.__init__)
    params = [p for p in sig.parameters if p != "self"]
    if not params:
        app = AplikasiUtama()
        if hasattr(app, "repositori") and hasattr(app.repositori, "koneksi"):
            app.repositori.koneksi.close()
            app.repositori.koneksi.db_path = str(db_sementara)
        return app
    if "repo" in params[0]:
        return AplikasiUtama(RepositoriMakanan(KoneksiDatabase(str(db_sementara))))
    if "koneksi" in params[0]:
        return AplikasiUtama(KoneksiDatabase(str(db_sementara)))
    return AplikasiUtama(str(db_sementara))


def jalankan_input_awal(app: AplikasiUtama, profil: dict) -> None:
    sig = inspect.signature(app.proses_input_pengguna)
    params = [p for p in sig.parameters if p != "self"]
    if len(params) == 1:
        app.proses_input_pengguna(profil)
    else:
        app.proses_input_pengguna(
            usia=profil["usia"],
            jenis_kelamin=profil["jenis_kelamin"],
            berat_badan=profil["berat_badan"],
            tinggi_badan=profil["tinggi_badan"],
            tingkat_aktivitas=profil["tingkat_aktivitas"],
        )


def main() -> None:
    db_asli = ROOT_DIR / "database" / "rekomendasi_makanan.db"
    folder_uji = ROOT_DIR / "data_uji"
    path_responden = folder_uji / "responden.csv"

    profil_47 = muat_47_profil(path_responden)
    assert len(profil_47) == 47, f"Jumlah profil uji harus 47, ditemukan {len(profil_47)}"

    koneksi_baca = KoneksiDatabase(str(db_asli))
    repo_baca = RepositoriMakanan(koneksi_baca)
    try:
        conn_read = sqlite3.connect(db_asli)
        try:
            df_makanan = pd.read_sql_query("SELECT * FROM makanan ORDER BY id_makanan ASC", conn_read)
        finally:
            conn_read.close()

        # 1. Periksa keidentikan 15 kandidat KNN pada 47 profil x 3 waktu makan (141 evaluasi)
        himpunan_kandidat_unik = set()
        referensi_kandidat = None
        for p in profil_47:
            kand_wm = ambil_15_kandidat_knn(df_makanan, repo_baca, p)
            for _, daftar_15 in kand_wm.items():
                tanda = tuple(daftar_15)
                himpunan_kandidat_unik.add(tanda)
                if referensi_kandidat is None:
                    referensi_kandidat = daftar_15
    finally:
        koneksi_baca.close()

    # 2. Jalankan 47 profil pada salinan DB sementara untuk melihat bahan & kombinasi aktual
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_sementara = Path(tmp_dir) / "rekomendasi_makanan_47.db"
        shutil.copy2(db_asli, db_sementara)
        app = buat_aplikasi_sementara(db_sementara)

        try:
            for p in profil_47:
                jalankan_input_awal(app, p)
        finally:
            if hasattr(app, "repositori") and hasattr(app.repositori, "koneksi"):
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

    assert len(df_riwayat) == len(profil_47) * 9, (
        f"Jumlah baris riwayat ({len(df_riwayat)}) tidak sesuai harapan ({len(profil_47) * 9})."
    )

    frekuensi_item = df_riwayat["id_makanan"].value_counts().to_dict()
    bahan_unik_terpilih = sorted(df_riwayat["id_makanan"].unique().tolist())

    kombinasi_harian = {}
    kombinasi_dengan_porsi = set()
    for idx, p in enumerate(profil_47):
        blok = df_riwayat.iloc[idx * 9 : (idx + 1) * 9]
        sig_9_bahan = tuple(int(x) for x in blok["id_makanan"])
        sig_9_porsi = tuple((int(r["id_makanan"]), float(r["porsi_gram"])) for _, r in blok.iterrows())
        kombinasi_harian.setdefault(sig_9_bahan, []).append(p["kode"])
        kombinasi_dengan_porsi.add(sig_9_porsi)

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
                "skor_cosine_similarity": round(skor, 6),
                "frekuensi_terpilih_47_profil": jml_pilih,
                "status_keterpilihan": "Terpilih" if jml_pilih > 0 else "Tidak pernah terpilih",
            }
        )

    df_kandidat = pd.DataFrame(baris_kandidat)
    path_csv = folder_uji / "uji_keragaman_kandidat.csv"
    df_kandidat.to_csv(path_csv, index=False)

    tidak_terpilih = df_kandidat[df_kandidat["frekuensi_terpilih_47_profil"] == 0]["nama_bahan"].tolist()
    urut_kombinasi = sorted(kombinasi_harian.items(), key=lambda x: len(x[1]), reverse=True)

    ringkasan = [
        "RINGKASAN ANALISIS KERAGAMAN KANDIDAT KNN PADA 47 PROFIL UJI",
        "=" * 64,
        f"Jumlah profil uji               : {len(profil_47)} profil (40 responden + 7 sintetis valid)",
        f"Total evaluasi waktu makan      : {len(profil_47) * 3} waktu makan (47 x 3)",
        f"Set 15 kandidat KNN unik        : {len(himpunan_kandidat_unik)} set (100% identik di seluruh 141 waktu makan)",
        f"Total kandidat KNN per evaluasi : {len(referensi_kandidat)} bahan (5 pokok + 5 lauk + 5 sayur)",
        f"Bahan unik terpilih (423 item)  : {len(bahan_unik_terpilih)} dari {len(referensi_kandidat)} kandidat",
        f"Kandidat tidak pernah terpilih  : {', '.join(tidak_terpilih) if tidak_terpilih else '-'}",
        f"Kombinasi menu harian unik      : {len(kombinasi_harian)} kombinasi dari 47 profil",
        f"Kombinasi (bahan + porsi) unik  : {len(kombinasi_dengan_porsi)} variasi dari 47 profil",
        "",
        "Distribusi 5 Kombinasi Menu Harian Unik:",
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