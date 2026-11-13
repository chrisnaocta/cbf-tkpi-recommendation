"""
aplikasi_utama.py

Kelas AplikasiUtama (Class Diagram, Gambar 3.4): pengendali alur aplikasi.

Tugas kelas: menerima data diri, memvalidasinya, memanggil KalkulatorGizi dan
MesinRekomendasi, menyimpan sesi dan riwayat melalui RepositoriMakanan, serta
mengelola "Minta Ulang". Kelas ini TIDAK memuat kode Streamlit. Metode
tampilkan_*() menyiapkan data siap tampil (dict atau DataFrame); pemanggilan
st.* dilakukan di app.py (tahap 6).

Alur (Activity Diagram, Gambar 3.2):
    input data diri -> validasi -> IMT/BMR -> target gizi (harian dan per waktu makan)
    -> pencocokan KNN + Cosine -> porsi gram dan susun menu -> simpan riwayat
    -> tampil -> (Minta Ulang | Lihat Detail)
"""

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pandas as pd

from kalkulator_gizi import (
    FAKTOR_AKTIVITAS, IMT_BATAS_KURUS_RINGAN, JENIS_KELAMIN_VALID,
    KalkulatorGizi, RASIO_WAKTU_MAKAN, TINGKAT_AKTIVITAS_VALID, USIA_MAX, USIA_MIN, ZAT_GIZI,
)
from mesin_rekomendasi import MesinRekomendasi, TOLERANSI_ATAS, TOLERANSI_BAWAH
from repositori_makanan import PERAN_VALID, RepositoriMakanan
from sesi_pengguna import SesiPengguna, kumpulkan_id_makanan

# ---------------------------------------------------------------------------
# KONSTANTA TAMPILAN (teks antarmuka; bukan rumus)
# ---------------------------------------------------------------------------
LABEL_JENIS_KELAMIN: Dict[str, str] = {"pria": "Laki-laki", "wanita": "Perempuan"}

# Tingkat aktivitas: rentang PAL mengacu pada Tabel 2.2; faktor FA pada Tabel 3.1
# (diambil dari FAKTOR_AKTIVITAS); contoh merangkum uraian Subbab 2.1.2.7 (BAB 2).
RENTANG_PAL: Dict[str, str] = {
    "menetap": "1,40 - 1,69",
    "aktif": "1,70 - 1,99",
    "sangat_aktif": "2,00 - 2,40",
}
LABEL_AKTIVITAS: Dict[str, str] = {
    "menetap": "Gaya hidup menetap atau aktivitas ringan",
    "aktif": "Gaya hidup aktif atau cukup aktif",
    "sangat_aktif": "Gaya hidup sangat aktif",
}
CONTOH_AKTIVITAS: Dict[str, str] = {
    "menetap": (
        "Pekerja kantoran di perkotaan atau ibu rumah tangga dengan pekerjaan domestik "
        "ringan; banyak duduk atau berdiri dan jarang berolahraga."
    ),
    "aktif": (
        "Pekerja konstruksi atau masyarakat perdesaan yang harus berjalan jauh; pekerja "
        "kantoran juga termasuk bila berolahraga sedang hingga berat (lari, bersepeda, "
        "senam aerobik) sekitar satu jam per hari."
    ),
    "sangat_aktif": (
        "Buruh tani tradisional yang bekerja dengan alat manual di medan berat, atau "
        "berolahraga intens seperti berenang lebih dari dua jam setiap hari."
    ),
}

LABEL_WAKTU_MAKAN: Dict[str, str] = {
    "sarapan": "Sarapan", "siang": "Makan Siang", "malam": "Makan Malam",
}
LABEL_PERAN: Dict[str, str] = {"pokok": "Makanan pokok", "lauk": "Lauk", "sayur": "Sayur"}
SATUAN_ZAT: Dict[str, str] = {
    "energi": "kkal", "protein": "g", "lemak": "g", "karbohidrat": "g",
}
NAMA_KOLOM_INPUT: Dict[str, str] = {
    "usia": "usia", "jenis_kelamin": "jenis kelamin", "berat_badan": "berat badan",
    "tinggi_badan": "tinggi badan", "tingkat_aktivitas": "tingkat aktivitas",
}

# Catatan untuk IMT di bawah 18,5 (Tabel 2.1: kategori kurus). Sistem ditujukan
# untuk pencegahan obesitas, sehingga target energi tidak ditambah (Subbab 3.3.3 butir 4).
CATATAN_IMT_KURUS: str = (
    "IMT Anda di bawah 18,5 (kategori kurus). Sistem ini dirancang untuk pencegahan "
    "obesitas dan menjaga berat badan, sehingga target energi tidak ditambah. "
    "Konsultasikan kebutuhan gizi Anda dengan tenaga kesehatan."
)
CATATAN_BELUM_MEMENUHI: str = (
    f"Sebagian waktu makan belum seluruhnya berada pada rentang {TOLERANSI_BAWAH:.0f}-"
    f"{TOLERANSI_ATAS:.0f}% dari target; kombinasi terdekat yang ditampilkan."
)

KOLOM_TABEL_REKOMENDASI: Tuple[str, ...] = (
    "id_makanan", "peran", "bahan", "porsi_gram", "energi", "protein", "lemak",
    "karbohidrat", "skor_similarity",
)


class AplikasiUtama:
    """Pengendali aplikasi rekomendasi menu harian.

    Atribut (sesuai Class Diagram):
        sesi (SesiPengguna), kalkulator (KalkulatorGizi | None),
        mesin (MesinRekomendasi | None), repositori (RepositoriMakanan).
        kalkulator dan mesin dibuat setelah data diri diterima.

    Metode (sesuai Class Diagram; tampilkan_* mengembalikan data, bukan menggambar UI):
        tampilkan_form_input()    -> dict
        proses_input_pengguna()   -> dict
        tampilkan_hasil_gizi()    -> dict
        tampilkan_rekomendasi()   -> dict
        tampilkan_detail_nutrisi()-> dict
        refresh_rekomendasi()     -> dict
    """

    def __init__(self, repositori: RepositoriMakanan, sesi: Optional[SesiPengguna] = None) -> None:
        self.repositori: RepositoriMakanan = repositori
        self.sesi: SesiPengguna = sesi if sesi is not None else SesiPengguna()
        self.kalkulator: Optional[KalkulatorGizi] = None
        self.mesin: Optional[MesinRekomendasi] = None
        self._data_makanan: Optional[pd.DataFrame] = None   # dibaca sekali dari basis data

    # ------------------------------------------------------------------
    # Pembantu internal
    # ------------------------------------------------------------------
    def _data(self) -> pd.DataFrame:
        if self._data_makanan is None:
            self._data_makanan = self.repositori.get_all_makanan()
        return self._data_makanan

    def _periksa_sesi_aktif(self) -> None:
        if not self.sesi.aktif or not self.sesi.rekomendasi_saat_ini or self.mesin is None:
            raise RuntimeError("Belum ada data diri. Isi dan kirim data diri terlebih dahulu.")

    @staticmethod
    def _kosong(nilai: Any) -> bool:
        return nilai is None or (isinstance(nilai, str) and nilai.strip() == "")

    @staticmethod
    def _ke_angka(nilai: Any, nama: str) -> float:
        """Mengubah masukan (angka atau teks, koma desimal diterima) menjadi float."""
        if isinstance(nilai, bool):
            raise ValueError(f"{nama.capitalize()} harus berupa angka.")
        if isinstance(nilai, (int, float)):
            return float(nilai)
        if isinstance(nilai, str):
            try:
                return float(nilai.strip().replace(",", "."))
            except ValueError:
                pass
        raise ValueError(f"{nama.capitalize()} harus berupa angka.")

    def _periksa_masukan(
        self, usia: Any, jenis_kelamin: Any, berat_badan: Any, tinggi_badan: Any,
        tingkat_aktivitas: Any,
    ) -> Tuple[int, str, float, float, str]:
        """Memeriksa kolom kosong dan tipe angka (Tabel 3.2 baris 2 dan 3).

        Batas usia, pilihan jenis kelamin/aktivitas, dan berat/tinggi > 0 diperiksa
        lebih lanjut oleh KalkulatorGizi.
        """
        masukan = {
            "usia": usia, "jenis_kelamin": jenis_kelamin, "berat_badan": berat_badan,
            "tinggi_badan": tinggi_badan, "tingkat_aktivitas": tingkat_aktivitas,
        }
        kosong = [NAMA_KOLOM_INPUT[k] for k, v in masukan.items() if self._kosong(v)]
        if kosong:
            raise ValueError(f"Kolom wajib diisi: {', '.join(kosong)}.")

        usia_angka = self._ke_angka(usia, "usia")
        if not usia_angka.is_integer():
            raise ValueError("Usia harus berupa bilangan bulat.")
        return (
            int(usia_angka),
            str(jenis_kelamin).strip(),
            self._ke_angka(berat_badan, "berat badan"),
            self._ke_angka(tinggi_badan, "tinggi badan"),
            str(tingkat_aktivitas).strip(),
        )

    @staticmethod
    def _hitung_hasil_gizi(kalkulator: KalkulatorGizi) -> Dict[str, Any]:
        """Menjalankan rumus (1)-(9) dan merangkum hasilnya."""
        imt = kalkulator.hitung_imt()
        return {
            "imt": imt,
            "klasifikasi": kalkulator.klasifikasi_imt(),
            "bmr": kalkulator.hitung_bmr(),
            "faktor_aktivitas": FAKTOR_AKTIVITAS[kalkulator.tingkat_aktivitas],
            "tee": kalkulator.hitung_tee(),
            "target_harian": kalkulator.hitung_target_gizi(),
            "target_waktu_makan": kalkulator.hitung_target_waktu_makan(),
            "catatan": CATATAN_IMT_KURUS if imt < IMT_BATAS_KURUS_RINGAN else None,
        }

    @staticmethod
    def _baris_riwayat(id_sesi: int, rekomendasi: Mapping[str, Any]) -> List[Dict[str, Any]]:
        """Membentuk baris riwayat_rekomendasi (9 baris: 3 waktu makan x 3 item)."""
        return [
            {
                "id_sesi": id_sesi,
                "id_makanan": butir["id_makanan"],
                "jenis_waktu_makan": waktu,
                "skor_similarity": butir["skor_similarity"],
                "porsi_gram": butir["porsi_gram"],
            }
            for waktu, menu in rekomendasi["menu"].items()
            for butir in menu["item"].values()
        ]

    # ------------------------------------------------------------------
    # Alur utama
    # ------------------------------------------------------------------
    def tampilkan_form_input(self) -> Dict[str, Any]:
        """Data untuk membangun form input (lima data diri)."""
        return {
            "usia": {"min": USIA_MIN, "max": USIA_MAX, "satuan": "tahun"},
            "jenis_kelamin": [(k, LABEL_JENIS_KELAMIN[k]) for k in JENIS_KELAMIN_VALID],
            "berat_badan": {"satuan": "kg"},
            "tinggi_badan": {"satuan": "cm"},
            "tingkat_aktivitas": [
                {
                    "kunci": k,
                    "label": LABEL_AKTIVITAS[k],
                    "rentang_pal": RENTANG_PAL[k],
                    "faktor": FAKTOR_AKTIVITAS[k],
                    "contoh": CONTOH_AKTIVITAS[k],
                }
                for k in TINGKAT_AKTIVITAS_VALID
            ],
        }

    def proses_input_pengguna(
        self, usia: Any, jenis_kelamin: Any, berat_badan: Any, tinggi_badan: Any,
        tingkat_aktivitas: Any,
    ) -> Dict[str, Any]:
        """Memproses data diri sampai rekomendasi pertama tersimpan.

        Urutan: validasi -> rumus (1)-(9) -> menu harian -> simpan sesi dan riwayat.
        Tidak ada yang ditulis ke basis data bila validasi atau perhitungan gagal.

        Returns:
            hasil_gizi (dict), sama dengan sesi.hasil_gizi.

        Raises:
            ValueError: kolom kosong, bukan angka, atau di luar batas.
        """
        masukan = self._periksa_masukan(
            usia, jenis_kelamin, berat_badan, tinggi_badan, tingkat_aktivitas
        )
        kalkulator = KalkulatorGizi(*masukan)          # validasi batas (ValueError)
        hasil_gizi = self._hitung_hasil_gizi(kalkulator)
        mesin = MesinRekomendasi(self._data(), hasil_gizi["target_waktu_makan"])
        rekomendasi = mesin.susun_menu_harian()

        profil = {
            "usia": kalkulator.usia, "jenis_kelamin": kalkulator.jenis_kelamin,
            "berat_badan": kalkulator.berat_badan, "tinggi_badan": kalkulator.tinggi_badan,
            "tingkat_aktivitas": kalkulator.tingkat_aktivitas,
        }
        harian = hasil_gizi["target_harian"]
        id_sesi = self.repositori.simpan_sesi_pengguna({
            **profil,
            "imt": hasil_gizi["imt"], "bmr": hasil_gizi["bmr"],
            "target_energi": harian["energi"], "target_protein": harian["protein"],
            "target_lemak": harian["lemak"], "target_karbohidrat": harian["karbohidrat"],
        })
        self.repositori.simpan_riwayat_rekomendasi(self._baris_riwayat(id_sesi, rekomendasi))

        self.kalkulator = kalkulator
        self.mesin = mesin
        self.sesi.simpan_profil(profil, hasil_gizi, id_sesi)
        self.sesi.update_rekomendasi(rekomendasi)
        return deepcopy(hasil_gizi)

    def refresh_rekomendasi(self) -> Dict[str, Any]:
        """"Minta Ulang": menu alternatif dengan target gizi yang sama.

        Item dari rekomendasi yang sedang tampil dikecualikan (Subbab 3.3.3 butir 8).
        Hasil baru disimpan sebagai baris riwayat tambahan pada sesi yang sama.

        Raises:
            RuntimeError: bila belum ada data diri.
            ValueError: bila kandidat habis setelah pengecualian.
        """
        self._periksa_sesi_aktif()
        dikecualikan = kumpulkan_id_makanan(self.sesi.rekomendasi_saat_ini)
        rekomendasi = self.mesin.susun_menu_harian(dikecualikan=dikecualikan)
        self.repositori.simpan_riwayat_rekomendasi(
            self._baris_riwayat(self.sesi.id_sesi, rekomendasi)
        )
        self.sesi.update_rekomendasi(rekomendasi)
        return deepcopy(rekomendasi)

    # ------------------------------------------------------------------
    # Data siap tampil
    # ------------------------------------------------------------------
    def tampilkan_hasil_gizi(self) -> Dict[str, Any]:
        """Hasil perhitungan gizi (Tabel 3.2 baris 4-7): IMT, kategori, BMR, TEE, target."""
        self._periksa_sesi_aktif()
        return {"profil": deepcopy(self.sesi.profil), **deepcopy(self.sesi.hasil_gizi)}

    def tampilkan_rekomendasi(self) -> Dict[str, Any]:
        """Menu harian siap tampil.

        Returns:
            {"menu": {waktu: {"label", "tabel" (DataFrame), "total", "target",
                              "pemenuhan", "memenuhi"}},
             "harian": {"total", "target", "pemenuhan", "memenuhi"},
             "catatan": str | None}
        """
        self._periksa_sesi_aktif()
        rekomendasi = self.sesi.rekomendasi_saat_ini
        menu: Dict[str, Any] = {}
        for waktu, isi in rekomendasi["menu"].items():
            baris = [
                {
                    "id_makanan": butir["id_makanan"], "peran": LABEL_PERAN[peran],
                    "bahan": butir["nama_bahan"], "porsi_gram": butir["porsi_gram"],
                    **{zat: butir[zat] for zat in ZAT_GIZI},
                    "skor_similarity": butir["skor_similarity"],
                }
                for peran, butir in isi["item"].items()
            ]
            menu[waktu] = {
                "label": LABEL_WAKTU_MAKAN[waktu],
                "tabel": pd.DataFrame(baris, columns=list(KOLOM_TABEL_REKOMENDASI)),
                "total": deepcopy(isi["total"]), "target": deepcopy(isi["target"]),
                "pemenuhan": deepcopy(isi["pemenuhan"]), "memenuhi": isi["memenuhi"],
            }
        semua_memenuhi = all(m["memenuhi"] for m in menu.values())
        return {
            "menu": menu,
            "harian": deepcopy(rekomendasi["harian"]),
            "catatan": None if semua_memenuhi else CATATAN_BELUM_MEMENUHI,
        }

    def tampilkan_detail_nutrisi(self, id_makanan: int) -> Dict[str, Any]:
        """Rincian gizi satu item pada rekomendasi yang sedang tampil (Tabel 3.2 baris 10).

        Returns:
            dict berisi nama, kode TKPI, kategori, peran, waktu makan, porsi_gram,
            gizi per 100 gram (data TKPI), dan gizi pada porsi tersebut.

        Raises:
            ValueError: bila id_makanan tidak ada pada rekomendasi yang tampil.
        """
        self._periksa_sesi_aktif()
        for waktu, isi in self.sesi.rekomendasi_saat_ini["menu"].items():
            for peran, butir in isi["item"].items():
                if butir["id_makanan"] == id_makanan:
                    data = self._data()
                    baris = data[data["id_makanan"] == id_makanan].iloc[0]
                    return {
                        "id_makanan": int(id_makanan),
                        "nama_bahan": str(baris["nama_bahan"]),
                        "kode_tkpi": str(baris["kode_tkpi"]),
                        "kategori": str(baris["kategori"]),
                        "peran": LABEL_PERAN[peran],
                        "waktu_makan": LABEL_WAKTU_MAKAN[waktu],
                        "porsi_gram": butir["porsi_gram"],
                        "per_100_gram": {zat: float(baris[zat]) for zat in ZAT_GIZI},
                        "per_porsi": {zat: butir[zat] for zat in ZAT_GIZI},
                    }
        raise ValueError(f"id_makanan {id_makanan} tidak ada pada rekomendasi yang sedang tampil.")