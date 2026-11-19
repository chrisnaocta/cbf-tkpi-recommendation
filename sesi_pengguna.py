"""
sesi_pengguna.py

Kelas SesiPengguna (Class Diagram, Gambar 3.4).

Tugas kelas: menyimpan status satu sesi penggunaan di memori, yaitu profil,
hasil perhitungan gizi, rekomendasi yang sedang tampil, item dari rekomendasi
sebelumnya, dan seluruh item yang pernah ditampilkan pada sesi (untuk
"Minta Ulang"). Kelas ini tidak mengakses basis data; penyimpanan ke SQLite
dilakukan AplikasiUtama melalui RepositoriMakanan.
"""

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional


def kumpulkan_id_makanan(rekomendasi: Mapping[str, Any]) -> List[int]:
    """Mengumpulkan id_makanan seluruh item pada hasil susun_menu_harian().

    Urutan: sarapan, siang, malam; pada tiap waktu makan pokok, lauk, sayur.
    Mengembalikan daftar kosong bila rekomendasi kosong.
    """
    if not rekomendasi:
        return []
    return [
        int(butir["id_makanan"])
        for menu in rekomendasi["menu"].values()
        for butir in menu["item"].values()
    ]


class SesiPengguna:
    """Status satu sesi penggunaan sistem.

    Atribut (sesuai Class Diagram):
        id_sesi (int | None): id baris sesi_pengguna; None sebelum data disimpan.
        profil (dict): usia, jenis_kelamin, berat_badan, tinggi_badan, tingkat_aktivitas.
        hasil_gizi (dict): IMT, BMR, TEE, target gizi harian dan per waktu makan.
        rekomendasi_saat_ini (dict): hasil susun_menu_harian() yang sedang tampil.
        item_sebelumnya (list[int]): id_makanan dari rekomendasi sebelum yang sekarang.
        item_terpakai (list[int]): seluruh id_makanan yang pernah ditampilkan pada
            sesi ini. Dipakai "Minta Ulang" agar menu yang sama tidak kembali muncul.

    Metode (sesuai Class Diagram):
        simpan_profil()       -> None
        update_rekomendasi()  -> None
    """

    def __init__(self) -> None:
        self.id_sesi: Optional[int] = None
        self.profil: Dict[str, Any] = {}
        self.hasil_gizi: Dict[str, Any] = {}
        self.rekomendasi_saat_ini: Dict[str, Any] = {}
        self.item_sebelumnya: List[int] = []
        self.item_terpakai: List[int] = []

    @property
    def aktif(self) -> bool:
        """True bila profil sudah disimpan pada sesi ini."""
        return self.id_sesi is not None

    def simpan_profil(
        self, profil: Mapping[str, Any], hasil_gizi: Mapping[str, Any], id_sesi: int
    ) -> None:
        """Menyimpan profil dan hasil gizi pada sesi, dan mengosongkan rekomendasi lama.

        Dipanggil setiap kali pengguna mengirim data diri baru, sehingga sesi
        dimulai dari awal (rekomendasi, item sebelumnya, dan item terpakai dikosongkan).
        """
        if isinstance(id_sesi, bool) or not isinstance(id_sesi, int):
            raise ValueError("id_sesi harus bilangan bulat.")
        self.id_sesi = id_sesi
        self.profil = deepcopy(dict(profil))
        self.hasil_gizi = deepcopy(dict(hasil_gizi))
        self.rekomendasi_saat_ini = {}
        self.item_sebelumnya = []
        self.item_terpakai = []

    def update_rekomendasi(self, rekomendasi: Mapping[str, Any]) -> None:
        """Mengganti rekomendasi yang tampil.

        Item pada rekomendasi yang digantikan disimpan di `item_sebelumnya`.
        Item rekomendasi baru ditambahkan ke `item_terpakai` (tanpa duplikat,
        urutan kemunculan dipertahankan), sehingga daftar itu memuat seluruh
        item yang pernah tampil pada sesi ini.
        """
        self.item_sebelumnya = kumpulkan_id_makanan(self.rekomendasi_saat_ini)
        self.rekomendasi_saat_ini = deepcopy(dict(rekomendasi))
        for id_makanan in kumpulkan_id_makanan(self.rekomendasi_saat_ini):
            if id_makanan not in self.item_terpakai:
                self.item_terpakai.append(id_makanan)