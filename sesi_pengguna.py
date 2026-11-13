"""
sesi_pengguna.py

Kelas SesiPengguna (Class Diagram, Gambar 3.4).

Tugas kelas: menyimpan status satu sesi penggunaan di memori, yaitu profil,
hasil perhitungan gizi, rekomendasi yang sedang tampil, dan item dari
rekomendasi sebelumnya (untuk "Minta Ulang"). Kelas ini tidak mengakses basis
data; penyimpanan ke SQLite dilakukan AplikasiUtama melalui RepositoriMakanan.
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

    @property
    def aktif(self) -> bool:
        """True bila profil sudah disimpan pada sesi ini."""
        return self.id_sesi is not None

    def simpan_profil(
        self, profil: Mapping[str, Any], hasil_gizi: Mapping[str, Any], id_sesi: int
    ) -> None:
        """Menyimpan profil dan hasil gizi pada sesi, dan mengosongkan rekomendasi lama.

        Dipanggil setiap kali pengguna mengirim data diri baru, sehingga sesi
        dimulai dari awal (rekomendasi dan item sebelumnya dikosongkan).
        """
        if isinstance(id_sesi, bool) or not isinstance(id_sesi, int):
            raise ValueError("id_sesi harus bilangan bulat.")
        self.id_sesi = id_sesi
        self.profil = deepcopy(dict(profil))
        self.hasil_gizi = deepcopy(dict(hasil_gizi))
        self.rekomendasi_saat_ini = {}
        self.item_sebelumnya = []

    def update_rekomendasi(self, rekomendasi: Mapping[str, Any]) -> None:
        """Mengganti rekomendasi yang tampil.

        Item pada rekomendasi yang digantikan disimpan di `item_sebelumnya`
        (Subbab 3.3.3 butir 8: pada permintaan ulang, item dari rekomendasi
        sebelumnya dikecualikan). Pada rekomendasi pertama daftar ini kosong.
        """
        self.item_sebelumnya = kumpulkan_id_makanan(self.rekomendasi_saat_ini)
        self.rekomendasi_saat_ini = deepcopy(dict(rekomendasi))