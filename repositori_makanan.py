"""
repositori_makanan.py

Kelas RepositoriMakanan (Class Diagram, Gambar 3.4).

Tugas kelas: satu-satunya jalur akses data tabel `makanan` dan
`riwayat_rekomendasi` bagi MesinRekomendasi dan AplikasiUtama. Skema tabel
mengikuti ERD Gambar 3.3 dan setup_db.py. Tidak ada rumus perhitungan di sini.
"""

import math
from typing import Iterable, List, Mapping, Tuple, Union

import pandas as pd

from koneksi_database import KoneksiDatabase

# ---------------------------------------------------------------------------
# KONSTANTA
# ---------------------------------------------------------------------------
# Peran menu yang masuk basis data (ketetapan perancangan: pokok, lauk, sayur;
# 790 bahan, sesuai CHECK pada spesifikasi dan filter pada setup_db.py).
PERAN_VALID: Tuple[str, ...] = ("pokok", "lauk", "sayur")

# Jenis waktu makan (ketetapan perancangan; kunci yang sama dengan
# RASIO_WAKTU_MAKAN: sarapan 0,30, siang 0,40, malam 0,30).
WAKTU_MAKAN_VALID: Tuple[str, ...] = ("sarapan", "siang", "malam")

# Kolom tabel `makanan` (ERD Gambar 3.3), dipakai agar urutan kolom DataFrame tetap.
KOLOM_MAKANAN: Tuple[str, ...] = (
    "id_makanan", "kode_tkpi", "nama_bahan", "kategori",
    "energi", "protein", "lemak", "karbohidrat", "peran_menu",
)

# Kolom wajib pada data riwayat. Kolom waktu_rekomendasi tidak diminta karena
# diisi otomatis oleh basis data (DEFAULT CURRENT_TIMESTAMP pada setup_db.py).
KOLOM_RIWAYAT_WAJIB: Tuple[str, ...] = (
    "id_sesi", "id_makanan", "jenis_waktu_makan", "skor_similarity", "porsi_gram",
)

# Kueri SQL. Semua nilai variabel dikirim sebagai parameter (?).
SQL_SEMUA_MAKANAN = (
    f"SELECT {', '.join(KOLOM_MAKANAN)} FROM makanan ORDER BY id_makanan"
)
SQL_MAKANAN_PER_PERAN = (
    f"SELECT {', '.join(KOLOM_MAKANAN)} FROM makanan "
    "WHERE peran_menu = ? ORDER BY id_makanan"
)
SQL_SIMPAN_RIWAYAT = (
    "INSERT INTO riwayat_rekomendasi "
    "(id_sesi, id_makanan, jenis_waktu_makan, skor_similarity, porsi_gram) "
    "VALUES (?, ?, ?, ?, ?)"
)

DataRiwayat = Union[pd.DataFrame, Iterable[Mapping]]


class RepositoriMakanan:
    """Akses data makanan dan riwayat rekomendasi.

    Atribut (sesuai Class Diagram):
        koneksi (KoneksiDatabase): objek koneksi yang digunakan.

    Metode (sesuai Class Diagram):
        get_all_makanan()                      -> DataFrame
        get_makanan_by_peran(peran_menu)       -> DataFrame
        simpan_riwayat_rekomendasi(data)       -> None
    """

    def __init__(self, koneksi: KoneksiDatabase) -> None:
        self.koneksi: KoneksiDatabase = koneksi

    def get_all_makanan(self) -> pd.DataFrame:
        """Mengambil seluruh bahan pada tabel `makanan` (790 baris), urut id_makanan."""
        return self.koneksi.execute_query(SQL_SEMUA_MAKANAN)

    def get_makanan_by_peran(self, peran_menu: str) -> pd.DataFrame:
        """Mengambil bahan untuk satu peran menu.

        Args:
            peran_menu: salah satu dari "pokok", "lauk", "sayur".

        Raises:
            ValueError: bila peran_menu bukan salah satu dari PERAN_VALID.
        """
        if peran_menu not in PERAN_VALID:
            raise ValueError(
                f"peran_menu tidak valid: {peran_menu!r}. "
                f"Pilihan: {', '.join(PERAN_VALID)}."
            )
        return self.koneksi.execute_query(SQL_MAKANAN_PER_PERAN, (peran_menu,))

    def simpan_riwayat_rekomendasi(self, data: DataRiwayat) -> None:
        """Menyimpan baris rekomendasi ke tabel `riwayat_rekomendasi`.

        Penyimpanan bersifat menambah (append). Setiap pemanggilan, termasuk
        pada "Minta Ulang", menambah baris baru dan tidak menimpa riwayat lama.
        Seluruh baris disimpan dalam satu transaksi: bila satu baris gagal
        (misalnya id_sesi tidak ada di sesi_pengguna), tidak ada baris yang
        tersimpan.

        Args:
            data: DataFrame atau daftar dict dengan kolom id_sesi, id_makanan,
                jenis_waktu_makan, skor_similarity, porsi_gram.

        Raises:
            ValueError: data kosong, kolom wajib kurang, jenis_waktu_makan di
                luar WAKTU_MAKAN_VALID, atau nilai numerik bukan angka berhingga.
            sqlite3.IntegrityError: pelanggaran kunci asing (id_sesi atau
                id_makanan tidak ada).
        """
        baris = self._susun_baris(data)

        koneksi = self.koneksi.connect()
        # Blok `with` melakukan commit bila berhasil dan rollback bila gagal.
        with koneksi:
            koneksi.executemany(SQL_SIMPAN_RIWAYAT, baris)

    @staticmethod
    def _susun_baris(data: DataRiwayat) -> List[tuple]:
        """Memvalidasi data masukan dan mengubahnya menjadi tuple bertipe Python.

        Konversi ke int/float diperlukan karena sqlite3 tidak menerima tipe
        numpy (misalnya numpy.int64) secara langsung.
        """
        if isinstance(data, pd.DataFrame):
            daftar = data.to_dict(orient="records")
        else:
            daftar = [dict(baris) for baris in data]

        if not daftar:
            raise ValueError("Data riwayat kosong; tidak ada yang disimpan.")

        hasil: List[tuple] = []
        for nomor, baris in enumerate(daftar, start=1):
            kurang = [k for k in KOLOM_RIWAYAT_WAJIB if k not in baris]
            if kurang:
                raise ValueError(
                    f"Baris {nomor}: kolom wajib tidak ada: {', '.join(kurang)}."
                )

            waktu = baris["jenis_waktu_makan"]
            if waktu not in WAKTU_MAKAN_VALID:
                raise ValueError(
                    f"Baris {nomor}: jenis_waktu_makan tidak valid: {waktu!r}. "
                    f"Pilihan: {', '.join(WAKTU_MAKAN_VALID)}."
                )

            skor = float(baris["skor_similarity"])
            porsi = float(baris["porsi_gram"])
            if not (math.isfinite(skor) and math.isfinite(porsi)):
                raise ValueError(
                    f"Baris {nomor}: skor_similarity dan porsi_gram harus angka berhingga."
                )

            hasil.append(
                (int(baris["id_sesi"]), int(baris["id_makanan"]), waktu, skor, porsi)
            )
        return hasil