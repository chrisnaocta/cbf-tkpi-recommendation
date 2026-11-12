"""
Tes untuk RepositoriMakanan: get_all_makanan, get_makanan_by_peran,
simpan_riwayat_rekomendasi.

Angka acuan (790 bahan; pokok 133, lauk 433, sayur 224) berasal dari data
TKPI 2020 yang tersimpan di data_makanan.csv dan rentang id pada dump
rekomendasi_makanan.db.
"""

import sqlite3

import numpy as np
import pandas as pd
import pytest

from repositori_makanan import KOLOM_MAKANAN, PERAN_VALID

# ---------------------------------------------------------------------------
# KONSTANTA ACUAN TES (hasil pencacahan data_makanan.csv)
# ---------------------------------------------------------------------------
JUMLAH_TOTAL = 790
JUMLAH_PER_PERAN = {"pokok": 133, "lauk": 433, "sayur": 224}
RENTANG_ID_PER_PERAN = {"pokok": (1, 133), "sayur": (248, 471)}  # lauk terpisah dua blok

SQL_HITUNG_RIWAYAT = "SELECT COUNT(*) FROM riwayat_rekomendasi"


def _baris_riwayat(id_sesi, **ubah):
    """Satu baris riwayat contoh yang sah; nilai dapat diubah per tes."""
    baris = {
        "id_sesi": id_sesi,
        "id_makanan": 22,  # Nasi
        "jenis_waktu_makan": "sarapan",
        "skor_similarity": 0.9731,
        "porsi_gram": 150.0,
    }
    baris.update(ubah)
    return baris


def _jumlah_riwayat(koneksi):
    return koneksi.connect().execute(SQL_HITUNG_RIWAYAT).fetchone()[0]


# ---------------------------------------------------------------------------
# get_all_makanan
# ---------------------------------------------------------------------------
class TestGetAllMakanan:
    def test_mengembalikan_dataframe_790_baris_dengan_kolom_sesuai_erd(self, repositori):
        df = repositori.get_all_makanan()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == JUMLAH_TOTAL
        assert tuple(df.columns) == KOLOM_MAKANAN

    def test_jumlah_per_peran_sesuai_data(self, repositori):
        df = repositori.get_all_makanan()
        assert df["peran_menu"].value_counts().to_dict() == JUMLAH_PER_PERAN

    def test_id_unik_berurutan_dan_tanpa_nilai_kosong(self, repositori):
        df = repositori.get_all_makanan()
        assert df["id_makanan"].tolist() == list(range(1, JUMLAH_TOTAL + 1))
        assert not df.isna().any().any()

    def test_baris_pertama_dan_terakhir_sesuai_dump(self, repositori):
        df = repositori.get_all_makanan()
        pertama, terakhir = df.iloc[0], df.iloc[-1]
        assert (pertama["kode_tkpi"], pertama["nama_bahan"]) == ("AR001", "Beras giling, mentah")
        assert pertama["energi"] == 357 and pertama["karbohidrat"] == 77.1
        assert (terakhir["kode_tkpi"], terakhir["nama_bahan"]) == ("HP007", "Kalio telur, masakan")
        assert terakhir["peran_menu"] == "lauk"


# ---------------------------------------------------------------------------
# get_makanan_by_peran
# ---------------------------------------------------------------------------
class TestGetMakananByPeran:
    @pytest.mark.parametrize("peran", PERAN_VALID)
    def test_jumlah_dan_isi_peran_benar(self, repositori, peran):
        df = repositori.get_makanan_by_peran(peran)
        assert len(df) == JUMLAH_PER_PERAN[peran]
        assert set(df["peran_menu"]) == {peran}
        assert tuple(df.columns) == KOLOM_MAKANAN

    @pytest.mark.parametrize("peran", ["pokok", "sayur"])
    def test_rentang_id_sesuai_dump(self, repositori, peran):
        awal, akhir = RENTANG_ID_PER_PERAN[peran]
        df = repositori.get_makanan_by_peran(peran)
        assert df["id_makanan"].min() == awal
        assert df["id_makanan"].max() == akhir

    def test_gabungan_tiga_peran_sama_dengan_get_all(self, repositori):
        gabungan = pd.concat(
            [repositori.get_makanan_by_peran(p) for p in PERAN_VALID]
        ).sort_values("id_makanan").reset_index(drop=True)
        pd.testing.assert_frame_equal(gabungan, repositori.get_all_makanan())

    @pytest.mark.parametrize(
        "peran", ["camilan", "buah", "", "POKOK", "pokok'; DROP TABLE makanan;--"]
    )
    def test_peran_tidak_valid_ditolak(self, repositori, peran):
        with pytest.raises(ValueError):
            repositori.get_makanan_by_peran(peran)

    def test_tabel_makanan_tetap_utuh_setelah_masukan_berbahaya(self, repositori):
        with pytest.raises(ValueError):
            repositori.get_makanan_by_peran("pokok'; DROP TABLE makanan;--")
        assert len(repositori.get_all_makanan()) == JUMLAH_TOTAL


# ---------------------------------------------------------------------------
# simpan_riwayat_rekomendasi
# ---------------------------------------------------------------------------
class TestSimpanRiwayatRekomendasi:
    def test_simpan_dataframe_tiga_item_dan_baca_kembali(self, repositori, koneksi, id_sesi):
        # satu waktu makan = 1 pokok + 1 lauk + 1 sayur
        data = pd.DataFrame([
            _baris_riwayat(id_sesi, id_makanan=22, skor_similarity=0.95, porsi_gram=150),
            _baris_riwayat(id_sesi, id_makanan=134, skor_similarity=0.88, porsi_gram=60),
            _baris_riwayat(id_sesi, id_makanan=248, skor_similarity=0.91, porsi_gram=100),
        ])
        assert repositori.simpan_riwayat_rekomendasi(data) is None

        df = koneksi.execute_query(
            "SELECT * FROM riwayat_rekomendasi ORDER BY id_rekomendasi"
        )
        assert len(df) == 3
        assert df["id_sesi"].tolist() == [id_sesi] * 3
        assert df["id_makanan"].tolist() == [22, 134, 248]
        assert df["jenis_waktu_makan"].tolist() == ["sarapan"] * 3
        assert df["skor_similarity"].tolist() == [0.95, 0.88, 0.91]
        assert df["porsi_gram"].tolist() == [150.0, 60.0, 100.0]

    def test_waktu_rekomendasi_terisi_otomatis(self, repositori, koneksi, id_sesi):
        repositori.simpan_riwayat_rekomendasi([_baris_riwayat(id_sesi)])
        df = koneksi.execute_query("SELECT waktu_rekomendasi FROM riwayat_rekomendasi")
        assert df["waktu_rekomendasi"].notna().all()

    def test_menerima_daftar_dict_dan_tipe_numpy(self, repositori, koneksi, id_sesi):
        baris = _baris_riwayat(
            id_sesi,
            id_makanan=np.int64(22),
            skor_similarity=np.float64(0.5),
            porsi_gram=np.float64(125.0),
        )
        repositori.simpan_riwayat_rekomendasi([baris])
        assert _jumlah_riwayat(koneksi) == 1

    def test_simpan_berulang_menambah_baris_dan_tidak_menimpa(self, repositori, koneksi, id_sesi):
        """Perilaku 'Minta Ulang': semua hasil disimpan sebagai bahan uji Bab 4."""
        repositori.simpan_riwayat_rekomendasi([_baris_riwayat(id_sesi, id_makanan=22)])
        repositori.simpan_riwayat_rekomendasi([_baris_riwayat(id_sesi, id_makanan=23)])
        df = koneksi.execute_query(
            "SELECT id_rekomendasi, id_makanan FROM riwayat_rekomendasi ORDER BY id_rekomendasi"
        )
        assert df["id_makanan"].tolist() == [22, 23]
        assert df["id_rekomendasi"].is_unique

    @pytest.mark.parametrize("waktu", ["sarapan", "siang", "malam"])
    def test_ketiga_waktu_makan_diterima(self, repositori, koneksi, id_sesi, waktu):
        repositori.simpan_riwayat_rekomendasi(
            [_baris_riwayat(id_sesi, jenis_waktu_makan=waktu)]
        )
        df = koneksi.execute_query("SELECT jenis_waktu_makan FROM riwayat_rekomendasi")
        assert df["jenis_waktu_makan"].tolist() == [waktu]

    def test_id_sesi_tidak_ada_ditolak_kunci_asing(self, repositori, koneksi, id_sesi):
        with pytest.raises(sqlite3.IntegrityError):
            repositori.simpan_riwayat_rekomendasi([_baris_riwayat(id_sesi + 999)])
        assert _jumlah_riwayat(koneksi) == 0

    def test_id_makanan_tidak_ada_ditolak_kunci_asing(self, repositori, koneksi, id_sesi):
        with pytest.raises(sqlite3.IntegrityError):
            repositori.simpan_riwayat_rekomendasi(
                [_baris_riwayat(id_sesi, id_makanan=JUMLAH_TOTAL + 1)]
            )
        assert _jumlah_riwayat(koneksi) == 0

    def test_satu_baris_gagal_membatalkan_seluruh_penyimpanan(self, repositori, koneksi, id_sesi):
        """Transaksi atomik: 2 baris sah + 1 baris dengan id_makanan tidak ada -> 0 tersimpan."""
        data = [
            _baris_riwayat(id_sesi, id_makanan=22),
            _baris_riwayat(id_sesi, id_makanan=134),
            _baris_riwayat(id_sesi, id_makanan=JUMLAH_TOTAL + 1),
        ]
        with pytest.raises(sqlite3.IntegrityError):
            repositori.simpan_riwayat_rekomendasi(data)
        assert _jumlah_riwayat(koneksi) == 0

    def test_data_kosong_ditolak(self, repositori):
        with pytest.raises(ValueError):
            repositori.simpan_riwayat_rekomendasi([])
        with pytest.raises(ValueError):
            repositori.simpan_riwayat_rekomendasi(pd.DataFrame())

    def test_kolom_wajib_kurang_ditolak(self, repositori, koneksi, id_sesi):
        baris = _baris_riwayat(id_sesi)
        del baris["porsi_gram"]
        with pytest.raises(ValueError, match="porsi_gram"):
            repositori.simpan_riwayat_rekomendasi([baris])
        assert _jumlah_riwayat(koneksi) == 0

    @pytest.mark.parametrize("waktu", ["makan siang", "Sarapan", "", None])
    def test_jenis_waktu_makan_tidak_valid_ditolak(self, repositori, koneksi, id_sesi, waktu):
        with pytest.raises(ValueError, match="jenis_waktu_makan"):
            repositori.simpan_riwayat_rekomendasi(
                [_baris_riwayat(id_sesi, jenis_waktu_makan=waktu)]
            )
        assert _jumlah_riwayat(koneksi) == 0

    @pytest.mark.parametrize("kolom", ["skor_similarity", "porsi_gram"])
    @pytest.mark.parametrize("nilai", [float("nan"), float("inf")])
    def test_nilai_numerik_tidak_berhingga_ditolak(self, repositori, koneksi, id_sesi, kolom, nilai):
        with pytest.raises(ValueError):
            repositori.simpan_riwayat_rekomendasi([_baris_riwayat(id_sesi, **{kolom: nilai})])
        assert _jumlah_riwayat(koneksi) == 0