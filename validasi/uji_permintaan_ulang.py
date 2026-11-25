"""
Simulasi pengujian siklus permintaan ulang ('Minta Ulang') pada satu sesi.
Membuktikan panjang siklus unik sebelum kandidat makanan pokok habis (14 permintaan),
pengulangan menu mulai permintaan ke-15, serta tren skor Cosine Similarity
dan pemenuhan makronutrisi harian.

Keluaran:
- data_uji/uji_permintaan_ulang.csv
- data_uji/ringkasan_uji_permintaan_ulang.txt
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
from koneksi_database import KoneksiDatabase  # noqa: E402
from repositori_makanan import RepositoriMakanan  # noqa: E402


PROFIL_UJI = {
    "usia": 25,
    "jenis_kelamin": "pria",
    "berat_badan": 70.0,
    "tinggi_badan": 170.0,
    "tingkat_aktivitas": "menetap",
}
JUMLAH_PERMINTAAN = 23


def buat_aplikasi_sementara(db_sementara: Path) -> AplikasiUtama:
    """Inisialisasi AplikasiUtama dengan mengarahkan koneksi ke basis data sementara."""
    sig = inspect.signature(AplikasiUtama.__init__)
    params = [p for p in sig.parameters if p != "self"]

    if not params:
        app = AplikasiUtama()
        if hasattr(app, "repositori") and hasattr(app.repositori, "koneksi"):
            app.repositori.koneksi.close()
            app.repositori.koneksi.db_path = str(db_sementara)
        return app

    nama_param = params[0]
    if "repo" in nama_param:
        koneksi = KoneksiDatabase(str(db_sementara))
        repo = RepositoriMakanan(koneksi)
        return AplikasiUtama(repo)
    if "koneksi" in nama_param:
        return AplikasiUtama(KoneksiDatabase(str(db_sementara)))
    return AplikasiUtama(str(db_sementara))


def jalankan_input_awal(app: AplikasiUtama, profil: dict) -> None:
    """Memanggil proses_input_pengguna sesuai parameter yang didefinisikan kelas."""
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
    folder_uji.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_sementara = Path(tmp_dir) / "rekomendasi_makanan_uji.db"
        shutil.copy2(db_asli, db_sementara)

        app = buat_aplikasi_sementara(db_sementara)

        # Permintaan ke-1 (input awal) + permintaan ke-2 s.d. ke-23 (Minta Ulang)
        jalankan_input_awal(app, PROFIL_UJI)
        for _ in range(JUMLAH_PERMINTAAN - 1):
            app.refresh_rekomendasi()

        if hasattr(app, "repositori") and hasattr(app.repositori, "koneksi"):
            app.repositori.koneksi.close()

        conn = sqlite3.connect(db_sementara)
        df_sesi = pd.read_sql_query("SELECT * FROM sesi_pengguna", conn)
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
                m.peran_menu,
                m.energi,
                m.protein,
                m.lemak,
                m.karbohidrat
            FROM riwayat_rekomendasi r
            JOIN makanan m ON r.id_makanan = m.id_makanan
            ORDER BY r.id_rekomendasi ASC
            """,
            conn,
        )
        jumlah_pokok_db = conn.execute(
            "SELECT COUNT(*) FROM makanan WHERE peran_menu = 'pokok'"
        ).fetchone()[0]
        conn.close()

    target = df_sesi.iloc[0]
    total_baris = len(df_riwayat)
    assert total_baris == JUMLAH_PERMINTAAN * 9, (
        f"Jumlah baris riwayat ({total_baris}) tidak sesuai harapan ({JUMLAH_PERMINTAAN * 9})."
    )

    jejak_menu = {}
    pokok_unik_kumulatif = set()
    baris_laporan = []

    for idx in range(JUMLAH_PERMINTAAN):
        permintaan_ke = idx + 1
        blok = df_riwayat.iloc[idx * 9 : (idx + 1) * 9].copy()

        sig_menu = tuple(
            (row["jenis_waktu_makan"], row["peran_menu"], int(row["id_makanan"]), float(row["porsi_gram"]))
            for _, row in blok.iterrows()
        )
        identik_dengan = jejak_menu.get(sig_menu, 0)
        if identik_dengan == 0:
            jejak_menu[sig_menu] = permintaan_ke

        id_pokok = [int(x) for x in blok[blok["peran_menu"] == "pokok"]["id_makanan"]]
        id_lauk = [int(x) for x in blok[blok["peran_menu"] == "lauk"]["id_makanan"]]
        id_sayur = [int(x) for x in blok[blok["peran_menu"] == "sayur"]["id_makanan"]]
        pokok_unik_kumulatif.update(id_pokok)

        faktor = blok["porsi_gram"] / 100.0
        tot_energi = float((blok["energi"] * faktor).sum())
        tot_protein = float((blok["protein"] * faktor).sum())
        tot_lemak = float((blok["lemak"] * faktor).sum())
        tot_karbo = float((blok["karbohidrat"] * faktor).sum())

        pct_energi = tot_energi / float(target["target_energi"]) * 100.0
        pct_protein = tot_protein / float(target["target_protein"]) * 100.0
        pct_lemak = tot_lemak / float(target["target_lemak"]) * 100.0
        pct_karbo = tot_karbo / float(target["target_karbohidrat"]) * 100.0

        dalam_toleransi = all(
            90.0 <= nilai <= 110.0
            for nilai in (pct_energi, pct_protein, pct_lemak, pct_karbo)
        )

        baris_laporan.append(
            {
                "permintaan_ke": permintaan_ke,
                "identik_dengan_permintaan": identik_dengan if identik_dengan > 0 else "-",
                "pokok_unik_kumulatif": len(pokok_unik_kumulatif),
                "rata_skor_similarity": round(float(blok["skor_similarity"].mean()), 4),
                "min_skor_similarity": round(float(blok["skor_similarity"].min()), 4),
                "max_skor_similarity": round(float(blok["skor_similarity"].max()), 4),
                "pemenuhan_energi_pct": round(pct_energi, 2),
                "pemenuhan_protein_pct": round(pct_protein, 2),
                "pemenuhan_lemak_pct": round(pct_lemak, 2),
                "pemenuhan_karbohidrat_pct": round(pct_karbo, 2),
                "status_toleransi_90_110": "Memenuhi" if dalam_toleransi else "Di luar toleransi",
                "id_pokok": ",".join(map(str, id_pokok)),
                "id_lauk": ",".join(map(str, id_lauk)),
                "id_sayur": ",".join(map(str, id_sayur)),
            }
        )

    df_hasil = pd.DataFrame(baris_laporan)
    path_csv = folder_uji / "uji_permintaan_ulang.csv"
    df_hasil.to_csv(path_csv, index=False)

    pengulangan_pertama = df_hasil[df_hasil["identik_dengan_permintaan"] != "-"].iloc[0]
    p1 = df_hasil.iloc[0]
    p14 = df_hasil.iloc[13]

    ringkasan = [
        "RINGKASAN PENGUJIAN SIKLUS PERMINTAAN ULANG ('MINTA ULANG')",
        "=" * 62,
        f"Profil uji                : {PROFIL_UJI['jenis_kelamin']}, {PROFIL_UJI['usia']} thn, "
        f"{PROFIL_UJI['berat_badan']} kg, {PROFIL_UJI['tinggi_badan']} cm, aktivitas {PROFIL_UJI['tingkat_aktivitas']}",
        f"Total permintaan diuji    : {JUMLAH_PERMINTAAN} permintaan ({total_baris} baris riwayat)",
        f"Total kandidat pokok DB   : {jumlah_pokok_db} bahan",
        f"Panjang siklus unik       : {int(pengulangan_pertama['permintaan_ke']) - 1} permintaan pertama berbeda seluruhnya",
        f"Pengulangan pertama       : Permintaan ke-{int(pengulangan_pertama['permintaan_ke'])} identik dengan "
        f"permintaan ke-{int(pengulangan_pertama['identik_dengan_permintaan'])} "
        f"(pokok ID: {pengulangan_pertama['id_pokok']})",
        f"Pokok terpakai s.d. ke-14 : {int(p14['pokok_unik_kumulatif'])} dari {jumlah_pokok_db} bahan "
        f"(sisa {jumlah_pokok_db - int(p14['pokok_unik_kumulatif'])} bahan < 3 bahan per hari)",
        f"Rata-rata similarity P1   : {p1['rata_skor_similarity']:.4f} (min: {p1['min_skor_similarity']:.4f})",
        f"Rata-rata similarity P14  : {p14['rata_skor_similarity']:.4f} (min: {p14['min_skor_similarity']:.4f})",
        f"Menu memenuhi 90-110%     : {(df_hasil['status_toleransi_90_110'] == 'Memenuhi').sum()} dari {JUMLAH_PERMINTAAN} permintaan",
    ]
    teks_ringkasan = "\n".join(ringkasan)
    path_txt = folder_uji / "ringkasan_uji_permintaan_ulang.txt"
    path_txt.write_text(teks_ringkasan + "\n", encoding="utf-8")

    print(teks_ringkasan)
    print(f"\nBerkas disimpan ke:\n- {path_csv}\n- {path_txt}")


if __name__ == "__main__":
    main()