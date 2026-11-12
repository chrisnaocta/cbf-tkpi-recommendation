"""Tes untuk KoneksiDatabase."""

import sqlite3

import pandas as pd
import pytest

from koneksi_database import KoneksiDatabase


def test_connect_mengaktifkan_kunci_asing(koneksi):
    konn = koneksi.connect()
    assert konn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_connect_dua_kali_memakai_koneksi_yang_sama(koneksi):
    assert koneksi.connect() is koneksi.connect()


def test_berkas_tidak_ada_memicu_error_dan_tidak_membuat_berkas(tmp_path):
    jalur = tmp_path / "tidak_ada.db"
    with pytest.raises(FileNotFoundError):
        KoneksiDatabase(str(jalur)).connect()
    assert not jalur.exists()


def test_execute_query_mengembalikan_dataframe_dengan_parameter(koneksi):
    df = koneksi.execute_query(
        "SELECT nama_bahan FROM makanan WHERE kode_tkpi = ?", ("AR001",)
    )
    assert isinstance(df, pd.DataFrame)
    assert df["nama_bahan"].tolist() == ["Beras giling, mentah"]


def test_close_aman_dipanggil_berulang_dan_koneksi_bisa_dibuka_lagi(koneksi):
    lama = koneksi.connect()
    koneksi.close()
    koneksi.close()  # tidak boleh error
    with pytest.raises(sqlite3.ProgrammingError):
        lama.execute("SELECT 1")  # koneksi lama benar-benar tertutup
    baru = koneksi.connect()
    assert baru is not lama
    assert baru.execute("SELECT 1").fetchone()[0] == 1


def test_jalur_bawaan_menunjuk_ke_folder_database_di_samping_modul():
    import os
    from koneksi_database import DB_PATH_BAWAAN, FOLDER_MODUL

    assert KoneksiDatabase().db_path == DB_PATH_BAWAAN
    assert DB_PATH_BAWAAN == os.path.join(
        FOLDER_MODUL, "database", "rekomendasi_makanan.db"
    )