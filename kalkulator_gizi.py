"""
kalkulator_gizi.py

Kelas KalkulatorGizi (Class Diagram, Gambar 3.4).

Tugas kelas: menghitung IMT, BMR, TEE, target energi harian, target makronutrien
harian, dan target gizi tiap waktu makan dari data diri pengguna, sesuai
Subbab 3.3.3 (Rumus (1)-(9)). Kelas ini tidak mengakses basis data dan tidak
memuat rumus (10)-(13); rumus tersebut berada pada MesinRekomendasi.

Rumus yang diimplementasikan:
    (1)     IMT = BB(kg) / TB(m)^2
    (2)(3)  BMR Mifflin-St Jeor (pria / wanita)
    (4)     TEE = BMR x FA
    (5)     Target Energi = TEE - 500 jika IMT > 25,0; selain itu TEE
    (6)(7)(8) Target Protein, Lemak, Karbohidrat = (persen x Target Energi) / faktor Atwater
    (9)     G_(w,j) = rho_w x G_(h,j)
"""

import math
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# KONSTANTA
# Nilai bertanda "Tabel" atau "rumus" berasal dari Bab 3; nilai bertanda
# "ketetapan perancangan" ditetapkan penulis pada Subbab 3.3.3.
# ---------------------------------------------------------------------------

# Pilihan masukan (ketetapan perancangan, sesuai nilai pada form dan basis data)
JENIS_KELAMIN_VALID: Tuple[str, ...] = ("pria", "wanita")
TINGKAT_AKTIVITAS_VALID: Tuple[str, ...] = ("menetap", "aktif", "sangat_aktif")

# Batas usia pengguna (batasan masalah: karyawan usia 19-49 tahun)
USIA_MIN: int = 19
USIA_MAX: int = 49

# Faktor aktivitas fisik, Tabel 3.1 (titik tengah rentang PAL, dua desimal)
FAKTOR_AKTIVITAS: Dict[str, float] = {
    "menetap": 1.55,
    "aktif": 1.85,
    "sangat_aktif": 2.20,
}

# Koefisien persamaan Mifflin-St Jeor, rumus (2) dan (3)
BMR_KOEF_BERAT: float = 10.0
BMR_KOEF_TINGGI: float = 6.25
BMR_KOEF_USIA: float = 5.0
BMR_KONSTANTA_PRIA: float = 5.0
BMR_KONSTANTA_WANITA: float = -161.0

# Penyesuaian target energi, rumus (5)
BATAS_IMT_LEBIH: float = 25.0      # IMT di atas nilai ini = lebih / berisiko obesitas
DEFISIT_ENERGI: float = 500.0      # pengurangan kkal/hari (Bab 2, diterapkan pada rumus (5))

# Distribusi makronutrien (ketetapan perancangan, dalam rentang AMDR dan berjumlah 100%)
PERSEN_MAKRO: Dict[str, float] = {
    "protein": 0.15,
    "lemak": 0.25,
    "karbohidrat": 0.60,
}

# Faktor Atwater (kkal/gram), rumus (6), (7), (8)
KKAL_PER_GRAM: Dict[str, float] = {
    "protein": 4.0,
    "lemak": 9.0,
    "karbohidrat": 4.0,
}

# Proporsi waktu makan rho_w, rumus (9) (ketetapan perancangan)
RASIO_WAKTU_MAKAN: Dict[str, float] = {
    "sarapan": 0.30,
    "siang": 0.40,
    "malam": 0.30,
}

# Batas kategori IMT, Tabel 2.1
IMT_BATAS_KURUS_BERAT: float = 17.0     # < 17,0
IMT_BATAS_KURUS_RINGAN: float = 18.5    # 17,0 - 18,4
IMT_BATAS_NORMAL: float = 25.0          # 18,5 - 25,0
IMT_BATAS_GEMUK_RINGAN: float = 27.0    # 25,1 - 27,0; di atasnya = gemuk berat

KATEGORI_IMT: Dict[str, str] = {
    "kurus_berat": "Kekurangan berat badan tingkat berat",
    "kurus_ringan": "Kekurangan berat badan tingkat ringan",
    "normal": "Berat badan normal",
    "gemuk_ringan": "Kelebihan berat badan tingkat ringan",
    "gemuk_berat": "Kelebihan berat badan tingkat berat",
}

# Urutan zat gizi pada dict hasil
ZAT_GIZI: Tuple[str, ...] = ("energi", "protein", "lemak", "karbohidrat")


class KalkulatorGizi:
    """Perhitungan kebutuhan gizi personal.

    Atribut (sesuai Class Diagram):
        usia (int), jenis_kelamin (str), berat_badan (float, kg),
        tinggi_badan (float, cm), tingkat_aktivitas (str).

    Metode (sesuai Class Diagram):
        hitung_imt()               -> float   rumus (1)
        hitung_bmr()               -> float   rumus (2) atau (3)
        hitung_tee()               -> float   rumus (4)
        hitung_target_gizi()       -> dict    rumus (4)-(8), target harian
        klasifikasi_imt()          -> str     Tabel 2.1
        hitung_target_waktu_makan()-> dict    rumus (9)
    """

    def __init__(
        self,
        usia: int,
        jenis_kelamin: str,
        berat_badan: float,
        tinggi_badan: float,
        tingkat_aktivitas: str,
    ) -> None:
        """Menyimpan data diri setelah divalidasi.

        Raises:
            ValueError: bila usia di luar 19-49, jenis kelamin atau tingkat
                aktivitas bukan pilihan yang valid, atau berat/tinggi badan
                bukan angka berhingga yang lebih besar dari nol.
        """
        self.usia: int = usia
        self.jenis_kelamin: str = jenis_kelamin
        self.berat_badan: float = berat_badan
        self.tinggi_badan: float = tinggi_badan
        self.tingkat_aktivitas: str = tingkat_aktivitas
        self._validasi()

    def _validasi(self) -> None:
        """Memeriksa kelas masukan valid (equivalence partitioning, Tabel 3.2 baris 2-3)."""
        if isinstance(self.usia, bool) or not isinstance(self.usia, int):
            raise ValueError("Usia harus berupa bilangan bulat.")
        if not (USIA_MIN <= self.usia <= USIA_MAX):
            raise ValueError(f"Usia harus antara {USIA_MIN} dan {USIA_MAX} tahun.")
        if self.jenis_kelamin not in JENIS_KELAMIN_VALID:
            raise ValueError(
                f"Jenis kelamin tidak valid: {self.jenis_kelamin!r}. "
                f"Pilihan: {', '.join(JENIS_KELAMIN_VALID)}."
            )
        if self.tingkat_aktivitas not in TINGKAT_AKTIVITAS_VALID:
            raise ValueError(
                f"Tingkat aktivitas tidak valid: {self.tingkat_aktivitas!r}. "
                f"Pilihan: {', '.join(TINGKAT_AKTIVITAS_VALID)}."
            )
        for nama, nilai in (("Berat badan", self.berat_badan), ("Tinggi badan", self.tinggi_badan)):
            if isinstance(nilai, bool) or not isinstance(nilai, (int, float)):
                raise ValueError(f"{nama} harus berupa angka.")
            if not math.isfinite(nilai) or nilai <= 0:
                raise ValueError(f"{nama} harus berupa angka lebih besar dari nol.")

    # ------------------------------------------------------------------
    # Rumus (1) dan klasifikasi Tabel 2.1
    # ------------------------------------------------------------------
    def hitung_imt(self) -> float:
        """Rumus (1): IMT = berat badan (kg) / tinggi badan (m) kuadrat."""
        tinggi_m = self.tinggi_badan / 100.0
        return self.berat_badan / (tinggi_m ** 2)

    def klasifikasi_imt(self) -> str:
        """Mengelompokkan IMT menurut Tabel 2.1 dan mengembalikan nama klasifikasinya."""
        imt = self.hitung_imt()
        if imt < IMT_BATAS_KURUS_BERAT:
            kunci = "kurus_berat"
        elif imt < IMT_BATAS_KURUS_RINGAN:
            kunci = "kurus_ringan"
        elif imt <= IMT_BATAS_NORMAL:
            kunci = "normal"
        elif imt <= IMT_BATAS_GEMUK_RINGAN:
            kunci = "gemuk_ringan"
        else:
            kunci = "gemuk_berat"
        return KATEGORI_IMT[kunci]

    # ------------------------------------------------------------------
    # Rumus (2), (3)
    # ------------------------------------------------------------------
    def hitung_bmr(self) -> float:
        """Rumus (2) untuk pria atau rumus (3) untuk wanita (kkal/hari)."""
        dasar = (
            BMR_KOEF_BERAT * self.berat_badan
            + BMR_KOEF_TINGGI * self.tinggi_badan
            - BMR_KOEF_USIA * self.usia
        )
        if self.jenis_kelamin == "pria":
            return dasar + BMR_KONSTANTA_PRIA
        return dasar + BMR_KONSTANTA_WANITA

    # ------------------------------------------------------------------
    # Rumus (4)
    # ------------------------------------------------------------------
    def hitung_tee(self) -> float:
        """Rumus (4): TEE = BMR x FA (kkal/hari)."""
        return self.hitung_bmr() * FAKTOR_AKTIVITAS[self.tingkat_aktivitas]

    def _hitung_tee(self) -> float:
        """Nama lama untuk hitung_tee(); dipertahankan agar tes tahap 2 tetap berlaku."""
        return self.hitung_tee()

    # ------------------------------------------------------------------
    # Rumus (5)-(8)
    # ------------------------------------------------------------------
    def hitung_target_gizi(self) -> Dict[str, float]:
        """Target gizi harian: energi (kkal), protein, lemak, karbohidrat (gram).

        Rumus (5): Target Energi = TEE - 500 jika IMT > 25,0; selain itu TEE.
        Rumus (6), (7), (8): target makro = (persen x Target Energi) / faktor Atwater.
        Pengurangan 500 kkal hanya berlaku pada Target Energi; target makro
        dihitung dari Target Energi tersebut (bukan dari TEE).
        """
        tee = self.hitung_tee()
        if self.hitung_imt() > BATAS_IMT_LEBIH:
            target_energi = tee - DEFISIT_ENERGI
        else:
            target_energi = tee

        target: Dict[str, float] = {"energi": target_energi}
        for zat in ("protein", "lemak", "karbohidrat"):
            target[zat] = (PERSEN_MAKRO[zat] * target_energi) / KKAL_PER_GRAM[zat]
        return target

    # ------------------------------------------------------------------
    # Rumus (9)
    # ------------------------------------------------------------------
    def hitung_target_waktu_makan(self) -> Dict[str, Dict[str, float]]:
        """Rumus (9): G_(w,j) = rho_w x G_(h,j) untuk sarapan, siang, dan malam.

        Returns:
            {"sarapan": {"energi":..,"protein":..,"lemak":..,"karbohidrat":..},
             "siang": {...}, "malam": {...}}
        """
        harian = self.hitung_target_gizi()
        return {
            waktu: {zat: rho * harian[zat] for zat in ZAT_GIZI}
            for waktu, rho in RASIO_WAKTU_MAKAN.items()
        }