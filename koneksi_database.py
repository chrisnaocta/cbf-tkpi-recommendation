"""
koneksi_database.py

Kelas KoneksiDatabase (Class Diagram, Gambar 3.4).

Tugas kelas: mengelola satu koneksi SQLite ke berkas rekomendasi_makanan.db
dan menyediakan pembacaan data dalam bentuk DataFrame. Kelas ini tidak berisi
rumus perhitungan apa pun; seluruh rumus (1)-(13) berada pada KalkulatorGizi
dan MesinRekomendasi.
"""

import os
import sqlite3
from typing import Optional, Sequence

import pandas as pd

# ---------------------------------------------------------------------------
# KONSTANTA
# ---------------------------------------------------------------------------
# Struktur folder proyek (ketetapan pelaksanaan):
#   website/            <- modul Python (berkas ini)
#   website/database/   <- rekomendasi_makanan.db, setup_db.py, berkas CSV
FOLDER_MODUL = os.path.dirname(os.path.abspath(__file__))
NAMA_FOLDER_DATABASE = "database"
NAMA_BERKAS_DB = "rekomendasi_makanan.db"

# Lokasi basis data bawaan, dihitung dari lokasi modul ini sehingga aplikasi
# dapat dijalankan dari folder mana pun.
DB_PATH_BAWAAN = os.path.join(FOLDER_MODUL, NAMA_FOLDER_DATABASE, NAMA_BERKAS_DB)

# Basis data sementara di memori milik SQLite (bukan berkas).
DB_DI_MEMORI = ":memory:"

# Kunci asing SQLite tidak aktif secara bawaan dan harus dinyalakan pada setiap
# koneksi agar relasi pada ERD (Gambar 3.3) benar-benar ditegakkan.
PERINTAH_AKTIFKAN_FK = "PRAGMA foreign_keys = ON"


class KoneksiDatabase:
    """Pengelola koneksi SQLite.

    Atribut (sesuai Class Diagram):
        db_path (str): lokasi berkas basis data SQLite.

    Metode (sesuai Class Diagram):
        connect()       -> sqlite3.Connection
        execute_query() -> pandas.DataFrame
        close()         -> None
    """

    def __init__(self, db_path: str = DB_PATH_BAWAAN) -> None:
        """Menyimpan lokasi basis data. Koneksi baru dibuka saat connect()."""
        self.db_path: str = db_path
        # Penampung koneksi aktif agar satu objek memakai satu koneksi saja.
        self._koneksi: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Membuka koneksi ke basis data dan mengembalikannya.

        Jika koneksi sudah terbuka, koneksi yang sama dikembalikan.
        Kunci asing diaktifkan pada koneksi baru.

        Raises:
            FileNotFoundError: bila berkas basis data tidak ada. Pemeriksaan
                ini mencegah sqlite3 membuat berkas kosong secara diam-diam
                sehingga kesalahan jalur baru muncul sebagai "no such table".
        """
        if self._koneksi is not None:
            return self._koneksi

        if self.db_path != DB_DI_MEMORI and not os.path.isfile(self.db_path):
            raise FileNotFoundError(
                f"Berkas basis data tidak ditemukan: {self.db_path}. "
                "Jalankan setup_db.py terlebih dahulu."
            )

        koneksi = sqlite3.connect(self.db_path)
        koneksi.execute(PERINTAH_AKTIFKAN_FK)
        self._koneksi = koneksi
        return self._koneksi

    def execute_query(
        self, query: str, params: Optional[Sequence] = None
    ) -> pd.DataFrame:
        """Menjalankan kueri SELECT dan mengembalikan hasilnya sebagai DataFrame.

        Args:
            query: pernyataan SQL; nilai variabel ditulis sebagai tanda tanya (?).
            params: nilai untuk tanda tanya pada query (kueri berparameter,
                sehingga tidak ada penyusunan SQL dari teks masukan pengguna).

        Catatan: metode ini hanya untuk pembacaan. Penulisan data (INSERT)
        dilakukan melalui connect() oleh RepositoriMakanan.
        """
        koneksi = self.connect()
        return pd.read_sql_query(query, koneksi, params=params)

    def close(self) -> None:
        """Menutup koneksi bila terbuka. Aman dipanggil berulang kali."""
        if self._koneksi is not None:
            self._koneksi.close()
            self._koneksi = None