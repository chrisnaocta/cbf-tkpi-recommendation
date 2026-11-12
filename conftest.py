"""
conftest.py

Fixture bersama untuk seluruh tes. Basis data uji dibuat di folder sementara
dengan menjalankan setup_db.py (tidak diubah) pada data_makanan.csv asli,
sehingga tes memakai skema dan 790 bahan yang sama dengan basis data skripsi.
Berkas rekomendasi_makanan.db milik pengguna tidak disentuh.
"""

import os
import sys

import pytest

# Lokasi data sumber: folder `database` di samping modul ini.
FOLDER_PROYEK = os.path.dirname(os.path.abspath(__file__))
FOLDER_DATABASE = os.path.join(FOLDER_PROYEK, "database")
CSV_MAKANAN = os.path.join(FOLDER_DATABASE, "data_makanan.csv")

# setup_db.py berada di folder `database`, sehingga folder itu didaftarkan
# agar dapat di-import.
sys.path.insert(0, FOLDER_DATABASE)

import setup_db  # noqa: E402
from koneksi_database import KoneksiDatabase  # noqa: E402
from repositori_makanan import RepositoriMakanan  # noqa: E402

# Profil sesi contoh untuk mengisi sesi_pengguna (hanya untuk kebutuhan uji FK).
SQL_SESI_UJI = (
    "INSERT INTO sesi_pengguna "
    "(usia, jenis_kelamin, berat_badan, tinggi_badan, tingkat_aktivitas) "
    "VALUES (?, ?, ?, ?, ?)"
)
SESI_UJI = (30, "pria", 70.0, 170.0, "menetap")


@pytest.fixture
def db_uji(tmp_path, monkeypatch):
    """Membuat basis data sementara lengkap dengan 790 bahan. Mengembalikan jalurnya."""
    jalur = str(tmp_path / "uji.db")
    monkeypatch.setattr(setup_db, "DB_NAME", jalur)
    setup_db.create_tables()
    setup_db.import_csv_to_db(CSV_MAKANAN)
    return jalur


@pytest.fixture
def koneksi(db_uji):
    """Objek KoneksiDatabase untuk basis data uji; ditutup setelah tes selesai."""
    k = KoneksiDatabase(db_uji)
    yield k
    k.close()


@pytest.fixture
def repositori(koneksi):
    return RepositoriMakanan(koneksi)


@pytest.fixture
def id_sesi(koneksi):
    """Menambahkan satu baris sesi_pengguna dan mengembalikan id_sesi-nya."""
    konn = koneksi.connect()
    with konn:
        kursor = konn.execute(SQL_SESI_UJI, SESI_UJI)
    return kursor.lastrowid