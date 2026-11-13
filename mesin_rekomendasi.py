"""
mesin_rekomendasi.py  (BAGIAN 1 + BAGIAN 2)

Kelas MesinRekomendasi (Class Diagram, Gambar 3.4), inti metode Content-Based Filtering.

Bagian 1 memuat:
    hitung_kontribusi_peran()      rumus (10)
    normalisasi_data()             normalisasi vektor (Subbab 3.3.3 butir 7)
    hitung_cosine_similarity()     rumus (11)
    cari_k_tetangga_terdekat()     KNN (K = 5 per peran) dengan jarak cosine

Bagian 2 memuat:
    hitung_porsi_gram()            rumus (12), bounded least squares, kelipatan 5 g
    hitung_persentase_pemenuhan()  rumus (13)
    susun_menu_harian()            125 kombinasi per waktu makan, seleksi 90-110%

Alur target:
    G_(w,j) (rumus 9, dari KalkulatorGizi)
        -> G_(r,j) = c_(r,j) x G_(w,j)   (rumus 10, target per peran)
        -> vektor target peran dinormalisasi menjadi (1, 1, 1, 1)
        -> KNN mencari K bahan terdekat (cosine) pada peran tersebut
"""

from itertools import product
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear
from sklearn.neighbors import NearestNeighbors

from kalkulator_gizi import KKAL_PER_GRAM, RASIO_WAKTU_MAKAN, ZAT_GIZI
from repositori_makanan import KOLOM_MAKANAN, PERAN_VALID

# ---------------------------------------------------------------------------
# KONSTANTA (ketetapan perancangan kecuali dinyatakan lain)
# ---------------------------------------------------------------------------

# Berat hidangan acuan tiap peran (gram), satu porsi menurut Subbab 2.1.2.11;
# dipakai pada rumus (10).
BERAT_ACUAN: Dict[str, float] = {"pokok": 100.0, "lauk": 40.0, "sayur": 100.0}

# Batas porsi g_(min,i) dan g_(max,i) (gram) untuk rumus (12).
BATAS_GRAM: Dict[str, Tuple[float, float]] = {
    "pokok": (100.0, 400.0),
    "lauk": (40.0, 200.0),
    "sayur": (50.0, 250.0),
}

# Jumlah tetangga terdekat (K) per peran.
K_TETANGGA: int = 5

# Zat gizi yang dibebankan per peran pada rumus (10); energi peran diturunkan
# dengan faktor Atwater: E_r = 4 P_r + 9 L_r + 4 K_r.
ZAT_MAKRO: Tuple[str, ...] = ("protein", "lemak", "karbohidrat")

# Fitur vektor pada Cosine Similarity (urutan tetap: energi, protein, lemak, karbohidrat).
KOLOM_FITUR: Tuple[str, ...] = ZAT_GIZI

# Awalan nama kolom hasil normalisasi.
AWALAN_NORMALISASI: str = "norm_"
KOLOM_NORMALISASI: Tuple[str, ...] = tuple(AWALAN_NORMALISASI + z for z in KOLOM_FITUR)

# Nama kolom skor kemiripan pada hasil KNN.
KOLOM_SKOR: str = "skor_similarity"

# Metrik dan algoritma pencarian tetangga.
METRIK_KNN: str = "cosine"
ALGORITMA_KNN: str = "brute"

# Rumus (12): pembulatan berat ke kelipatan KELIPATAN_GRAM gram; semua batas
# pada BATAS_GRAM adalah kelipatan 5 sehingga hasil pembulatan tetap di dalam batas.
KELIPATAN_GRAM: float = 5.0

# Rumus (12): metode scipy.optimize.lsq_linear (Trust Region Reflective).
METODE_LSQ: str = "trf"

# Seleksi kombinasi menu: rentang persentase pemenuhan yang dinyatakan sesuai (%).
TOLERANSI_BAWAH: float = 90.0
TOLERANSI_ATAS: float = 110.0
PERSEN_SEMPURNA: float = 100.0   # pembanding untuk penyimpangan

# Galat numerik yang dimaafkan saat membandingkan persentase dengan batas toleransi.
EPSILON: float = 1e-9


class MesinRekomendasi:
    """Mesin Content-Based Filtering (KNN + Cosine Similarity).

    Atribut (sesuai Class Diagram):
        data_makanan (DataFrame): seluruh bahan (790 baris) dengan kolom KOLOM_MAKANAN.
        target_gizi (dict): target tiap waktu makan hasil rumus (9), berbentuk
            {"sarapan": {"energi","protein","lemak","karbohidrat"}, "siang": {...}, "malam": {...}}.
        k (int): jumlah tetangga terdekat per peran.
        batas_gram (dict): BATAS_GRAM (dipakai tahap 4).
        porsi_acuan (dict): BERAT_ACUAN.

    Metode bagian 1:
        hitung_kontribusi_peran()                      -> dict
        normalisasi_data(waktu_makan, peran, ...)       -> DataFrame
        hitung_cosine_similarity(vektor_user, vektor_makanan) -> float
        cari_k_tetangga_terdekat(waktu_makan, peran, ...)     -> DataFrame

    Metode bagian 2:
        hitung_porsi_gram(waktu_makan, kandidat)        -> dict
        hitung_persentase_pemenuhan(total, target)      -> dict
        susun_menu_harian(dikecualikan)                 -> dict
    """

    def __init__(
        self,
        data_makanan: pd.DataFrame,
        target_gizi: Dict[str, Dict[str, float]],
        k: int = K_TETANGGA,
    ) -> None:
        """Menyimpan data dan target setelah divalidasi.

        Raises:
            ValueError: kolom data kurang, ada peran yang tidak punya bahan,
                target_gizi tidak lengkap atau tidak positif, atau k < 1.
        """
        self.data_makanan: pd.DataFrame = data_makanan
        self.target_gizi: Dict[str, Dict[str, float]] = target_gizi
        self.k: int = k
        self.batas_gram: Dict[str, Tuple[float, float]] = BATAS_GRAM
        self.porsi_acuan: Dict[str, float] = BERAT_ACUAN
        self._validasi()
        # x_bar_(r,j): rata-rata zat gizi j per 100 g seluruh bahan berperan r.
        self._rata_rata: Dict[str, Dict[str, float]] = self._hitung_rata_rata()

    # ------------------------------------------------------------------
    # Validasi dan pembantu
    # ------------------------------------------------------------------
    def _validasi(self) -> None:
        if isinstance(self.k, bool) or not isinstance(self.k, int) or self.k < 1:
            raise ValueError("k harus bilangan bulat >= 1.")
        kurang = [c for c in KOLOM_MAKANAN if c not in self.data_makanan.columns]
        if kurang:
            raise ValueError(f"Kolom data_makanan kurang: {', '.join(kurang)}.")
        for peran in PERAN_VALID:
            if not (self.data_makanan["peran_menu"] == peran).any():
                raise ValueError(f"Tidak ada bahan berperan {peran!r} pada data_makanan.")
        for waktu in RASIO_WAKTU_MAKAN:
            if waktu not in self.target_gizi:
                raise ValueError(f"target_gizi tidak memuat waktu makan {waktu!r}.")
            for zat in ZAT_GIZI:
                nilai = self.target_gizi[waktu].get(zat)
                if nilai is None or not np.isfinite(nilai) or nilai <= 0:
                    raise ValueError(
                        f"target_gizi[{waktu!r}][{zat!r}] harus angka berhingga > 0."
                    )

    def _hitung_rata_rata(self) -> Dict[str, Dict[str, float]]:
        """Rata-rata zat gizi (protein, lemak, karbohidrat) per 100 g untuk tiap peran."""
        hasil: Dict[str, Dict[str, float]] = {}
        for peran in PERAN_VALID:
            bagian = self.data_makanan[self.data_makanan["peran_menu"] == peran]
            hasil[peran] = {zat: float(bagian[zat].mean()) for zat in ZAT_MAKRO}
        return hasil

    @staticmethod
    def _periksa_peran(peran: str) -> None:
        if peran not in PERAN_VALID:
            raise ValueError(
                f"peran tidak valid: {peran!r}. Pilihan: {', '.join(PERAN_VALID)}."
            )

    def _periksa_waktu(self, waktu_makan: str) -> None:
        if waktu_makan not in RASIO_WAKTU_MAKAN:
            raise ValueError(
                f"waktu_makan tidak valid: {waktu_makan!r}. "
                f"Pilihan: {', '.join(RASIO_WAKTU_MAKAN)}."
            )

    # ------------------------------------------------------------------
    # Rumus (10)
    # ------------------------------------------------------------------
    def hitung_kontribusi_peran(self) -> Dict[str, Dict[str, float]]:
        """Rumus (10): kontribusi peran r terhadap zat gizi j.

            c_(r,j) = (g_r^acuan x x_bar_(r,j)) / SUM_r' (g_r'^acuan x x_bar_(r',j))

        Returns:
            {"pokok": {"protein": c, "lemak": c, "karbohidrat": c}, "lauk": {...}, "sayur": {...}}
            dengan c berupa pecahan (0-1); untuk persen kalikan 100. Untuk tiap zat
            gizi, jumlah c ketiga peran = 1.
        """
        kontribusi: Dict[str, Dict[str, float]] = {peran: {} for peran in PERAN_VALID}
        for zat in ZAT_MAKRO:
            beban = {
                peran: BERAT_ACUAN[peran] * self._rata_rata[peran][zat]
                for peran in PERAN_VALID
            }
            penyebut = sum(beban.values())
            for peran in PERAN_VALID:
                kontribusi[peran][zat] = beban[peran] / penyebut
        return kontribusi

    def _hitung_target_peran(self, waktu_makan: str, peran: str) -> Dict[str, float]:
        """Target gizi peran r pada waktu makan w: G_(r,j) = c_(r,j) x G_(w,j).

        Energi peran dihitung dengan faktor Atwater dari target makro peran:
        E_r = 4 P_r + 9 L_r + 4 K_r.
        """
        self._periksa_waktu(waktu_makan)
        self._periksa_peran(peran)
        kontribusi = self.hitung_kontribusi_peran()[peran]
        target = {
            zat: kontribusi[zat] * self.target_gizi[waktu_makan][zat] for zat in ZAT_MAKRO
        }
        target["energi"] = sum(KKAL_PER_GRAM[zat] * target[zat] for zat in ZAT_MAKRO)
        return {zat: target[zat] for zat in KOLOM_FITUR}

    # ------------------------------------------------------------------
    # Normalisasi
    # ------------------------------------------------------------------
    def normalisasi_data(
        self,
        waktu_makan: str,
        peran: str,
        dikecualikan: Optional[Iterable[int]] = None,
    ) -> pd.DataFrame:
        """Normalisasi vektor gizi bahan satu peran terhadap target peran tersebut.

        Setiap nilai energi, protein, lemak, dan karbohidrat dibagi dengan nilai
        target peran yang bersangkutan, sehingga vektor target menjadi (1, 1, 1, 1).

        Args:
            waktu_makan: "sarapan", "siang", atau "malam".
            peran: "pokok", "lauk", atau "sayur".
            dikecualikan: id_makanan yang tidak boleh menjadi kandidat (item yang
                sudah dipakai pada hari yang sama atau pada rekomendasi sebelumnya).

        Returns:
            DataFrame bahan berperan `peran` (tanpa yang dikecualikan) dengan
            kolom asli ditambah norm_energi, norm_protein, norm_lemak, norm_karbohidrat.
        """
        target = self._hitung_target_peran(waktu_makan, peran)
        data = self.data_makanan[self.data_makanan["peran_menu"] == peran].copy()
        if dikecualikan is not None:
            data = data[~data["id_makanan"].isin(set(dikecualikan))]
        if data.empty:
            raise ValueError(f"Tidak ada kandidat tersisa untuk peran {peran!r}.")
        for zat in KOLOM_FITUR:
            data[AWALAN_NORMALISASI + zat] = data[zat] / target[zat]
        return data.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Rumus (11)
    # ------------------------------------------------------------------
    @staticmethod
    def hitung_cosine_similarity(
        vektor_user: Sequence[float], vektor_makanan: Sequence[float]
    ) -> float:
        """Rumus (11): cos(theta) = (A . B) / (||A|| ||B||).

        Args:
            vektor_user: vektor A, yaitu vektor target peran yang sudah dinormalisasi.
            vektor_makanan: vektor B, yaitu vektor makanan yang sudah dinormalisasi.

        Catatan: bila salah satu vektor bernilai nol semua (||.|| = 0), rumus tidak
        terdefinisi; fungsi mengembalikan 0.0 (tanpa kemiripan), sama dengan
        perilaku scikit-learn.

        Raises:
            ValueError: bila panjang kedua vektor berbeda.
        """
        a = np.asarray(vektor_user, dtype=float)
        b = np.asarray(vektor_makanan, dtype=float)
        if a.shape != b.shape or a.ndim != 1:
            raise ValueError("Kedua vektor harus satu dimensi dan berpanjang sama.")
        panjang_a = float(np.linalg.norm(a))
        panjang_b = float(np.linalg.norm(b))
        if panjang_a == 0.0 or panjang_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (panjang_a * panjang_b))

    # ------------------------------------------------------------------
    # KNN
    # ------------------------------------------------------------------
    def cari_k_tetangga_terdekat(
        self,
        waktu_makan: str,
        peran: str,
        dikecualikan: Optional[Iterable[int]] = None,
    ) -> pd.DataFrame:
        """Mencari K bahan terdekat dengan vektor target peran (K-Nearest Neighbors).

        Memakai NearestNeighbors(metric="cosine", algorithm="brute"). Jarak cosine =
        1 - cosine similarity, sehingga skor_similarity = 1 - jarak.

        Item `dikecualikan` dibuang sebelum pencarian, sehingga K kandidat tetap
        terisi dari bahan yang tersisa. Bila kandidat tersisa kurang dari K,
        semua kandidat dikembalikan.

        Returns:
            DataFrame berurut dari skor_similarity tertinggi: kolom asli, kolom
            norm_*, dan skor_similarity.
        """
        data = self.normalisasi_data(waktu_makan, peran, dikecualikan)
        fitur = data[list(KOLOM_NORMALISASI)].to_numpy(dtype=float)
        vektor_target = np.ones((1, len(KOLOM_FITUR)))  # target ternormalisasi = (1,1,1,1)

        jumlah = min(self.k, len(data))
        knn = NearestNeighbors(n_neighbors=jumlah, metric=METRIK_KNN, algorithm=ALGORITMA_KNN)
        knn.fit(fitur)
        jarak, indeks = knn.kneighbors(vektor_target)

        hasil = data.iloc[indeks[0]].copy()
        hasil[KOLOM_SKOR] = 1.0 - jarak[0]
        return hasil.reset_index(drop=True)

    # ==================================================================
    # BAGIAN 2: porsi gram, persentase pemenuhan, dan menu harian
    # ==================================================================

    def _target_waktu_makan_vektor(self, waktu_makan: str) -> np.ndarray:
        """Vektor G_(w,j) berurutan energi, protein, lemak, karbohidrat."""
        return np.array(
            [self.target_gizi[waktu_makan][zat] for zat in KOLOM_FITUR], dtype=float
        )

    @staticmethod
    def _matriks_gizi(kandidat: Mapping[str, Mapping[str, float]]) -> np.ndarray:
        """Matriks x_ij berukuran 4 x 3 (baris j = zat gizi, kolom i = pokok, lauk, sayur)."""
        return np.array(
            [[float(kandidat[peran][zat]) for peran in PERAN_VALID] for zat in KOLOM_FITUR],
            dtype=float,
        )

    def _selesaikan_porsi(
        self, waktu_makan: str, kandidat: Mapping[str, Mapping[str, float]]
    ) -> np.ndarray:
        """Menyelesaikan rumus (12) tanpa pembulatan; mengembalikan g* = (g_1, g_2, g_3).

        Rumus (12):  g* = arg min_g  SUM_j [ ( SUM_i g_i x_ij / 100 - G_(w,j) ) / G_(w,j) ]^2
                     dengan g_(min,i) <= g_i <= g_(max,i).

        Bentuk ini sama dengan  ||A g - 1||^2  untuk  A_(j,i) = x_ij / (100 G_(w,j)),
        sehingga dapat diselesaikan dengan scipy.optimize.lsq_linear (bounded least squares).
        """
        target = self._target_waktu_makan_vektor(waktu_makan)
        x = self._matriks_gizi(kandidat)
        a = (x / 100.0) / target[:, None]
        b = np.ones(len(KOLOM_FITUR))
        bawah = [self.batas_gram[peran][0] for peran in PERAN_VALID]
        atas = [self.batas_gram[peran][1] for peran in PERAN_VALID]
        hasil = lsq_linear(a, b, bounds=(bawah, atas), method=METODE_LSQ)
        return hasil.x

    def hitung_porsi_gram(
        self, waktu_makan: str, kandidat: Mapping[str, Mapping[str, float]]
    ) -> Dict[str, float]:
        """Rumus (12): berat (gram) pokok, lauk, dan sayur untuk satu waktu makan.

        Args:
            waktu_makan: "sarapan", "siang", atau "malam".
            kandidat: {"pokok": baris, "lauk": baris, "sayur": baris}; tiap baris
                memuat energi, protein, lemak, karbohidrat per 100 g.

        Returns:
            {"pokok": gram, "lauk": gram, "sayur": gram}, dibulatkan ke kelipatan
            5 gram (pembulatan ke terdekat, .5 ke atas) dan berada dalam BATAS_GRAM.
        """
        self._periksa_waktu(waktu_makan)
        mentah = self._selesaikan_porsi(waktu_makan, kandidat)
        gram: Dict[str, float] = {}
        for nilai, peran in zip(mentah, PERAN_VALID):
            bulat = np.floor(nilai / KELIPATAN_GRAM + 0.5) * KELIPATAN_GRAM
            bawah, atas = self.batas_gram[peran]
            gram[peran] = float(min(max(bulat, bawah), atas))
        return gram

    @staticmethod
    def _gizi_item(baris: Mapping[str, float], gram: float) -> Dict[str, float]:
        """Kandungan gizi suatu bahan pada berat tertentu: x_ij x gram / 100."""
        return {zat: float(baris[zat]) * gram / 100.0 for zat in KOLOM_FITUR}

    def _total_gizi(
        self, kandidat: Mapping[str, Mapping[str, float]], gram: Mapping[str, float]
    ) -> Dict[str, float]:
        """Total gizi satu waktu makan: SUM_i g_i x_ij / 100, dari berat yang sudah dibulatkan."""
        total = {zat: 0.0 for zat in KOLOM_FITUR}
        for peran in PERAN_VALID:
            for zat, nilai in self._gizi_item(kandidat[peran], gram[peran]).items():
                total[zat] += nilai
        return total

    @staticmethod
    def hitung_persentase_pemenuhan(
        total: Mapping[str, float], target: Mapping[str, float]
    ) -> Dict[str, float]:
        """Rumus (13): persentase pemenuhan = total gizi / target x 100%."""
        return {zat: total[zat] / target[zat] * 100.0 for zat in KOLOM_FITUR}

    @staticmethod
    def _memenuhi(pemenuhan: Mapping[str, float]) -> bool:
        """True bila keempat zat gizi berada pada rentang 90-110%."""
        return all(
            TOLERANSI_BAWAH - EPSILON <= pemenuhan[zat] <= TOLERANSI_ATAS + EPSILON
            for zat in KOLOM_FITUR
        )

    @staticmethod
    def _penyimpangan_terbesar(pemenuhan: Mapping[str, float]) -> float:
        """Penyimpangan terbesar terhadap target (poin persen): max_j |pemenuhan_j - 100|."""
        return max(abs(pemenuhan[zat] - PERSEN_SEMPURNA) for zat in KOLOM_FITUR)

    def _pilih_menu_waktu_makan(
        self, waktu_makan: str, dikecualikan: Set[int]
    ) -> Dict[str, Any]:
        """Memilih satu kombinasi menu untuk satu waktu makan.

        Langkah (Subbab 3.3.3 butir 8):
          1. 5 kandidat terdekat per peran (KNN) -> 5 x 5 x 5 = 125 kombinasi.
          2. Berat tiap kombinasi dari rumus (12), dibulatkan kelipatan 5 g.
          3. Persentase pemenuhan dihitung dari berat yang sudah dibulatkan.
          4. Dipilih kombinasi yang keempat persentasenya 90-110% dengan rata-rata
             skor kemiripan tertinggi. Jika tidak ada, dipilih kombinasi dengan
             penyimpangan terbesar yang paling kecil.

        Pemutus seri (ketetapan implementasi agar hasil deterministik):
        pada kombinasi yang memenuhi, penyimpangan terkecil lalu id_makanan terkecil;
        pada kombinasi yang tidak memenuhi, skor rata-rata tertinggi lalu id_makanan terkecil.
        """
        tetangga = {
            peran: self.cari_k_tetangga_terdekat(waktu_makan, peran, dikecualikan)
            for peran in PERAN_VALID
        }
        target = self.target_gizi[waktu_makan]

        terbaik: Optional[Tuple] = None
        for indeks in product(*(range(len(tetangga[peran])) for peran in PERAN_VALID)):
            kandidat = {
                peran: tetangga[peran].iloc[i] for peran, i in zip(PERAN_VALID, indeks)
            }
            gram = self.hitung_porsi_gram(waktu_makan, kandidat)
            total = self._total_gizi(kandidat, gram)
            pemenuhan = self.hitung_persentase_pemenuhan(total, target)
            memenuhi = self._memenuhi(pemenuhan)
            simpangan = self._penyimpangan_terbesar(pemenuhan)
            skor = float(np.mean([kandidat[p][KOLOM_SKOR] for p in PERAN_VALID]))
            ids = tuple(int(kandidat[p]["id_makanan"]) for p in PERAN_VALID)

            if memenuhi:
                kunci = (0, -skor, simpangan, ids)
            else:
                kunci = (1, simpangan, -skor, ids)
            if terbaik is None or kunci < terbaik[0]:
                terbaik = (kunci, kandidat, gram, total, pemenuhan, memenuhi, skor)

        _, kandidat, gram, total, pemenuhan, memenuhi, skor = terbaik
        item: Dict[str, Dict[str, Any]] = {}
        for peran in PERAN_VALID:
            baris = kandidat[peran]
            item[peran] = {
                "id_makanan": int(baris["id_makanan"]),
                "nama_bahan": str(baris["nama_bahan"]),
                "porsi_gram": gram[peran],
                "skor_similarity": float(baris[KOLOM_SKOR]),
                **self._gizi_item(baris, gram[peran]),
            }
        return {
            "waktu_makan": waktu_makan,
            "item": item,
            "total": total,
            "target": {zat: float(target[zat]) for zat in KOLOM_FITUR},
            "pemenuhan": pemenuhan,
            "memenuhi": memenuhi,
            "skor_rata_rata": skor,
        }

    def susun_menu_harian(
        self, dikecualikan: Optional[Iterable[int]] = None
    ) -> Dict[str, Any]:
        """Menyusun menu sarapan, makan siang, dan makan malam.

        Item yang sudah dipakai pada waktu makan sebelumnya di hari yang sama tidak
        dipilih lagi. Pada permintaan ulang ("Minta Ulang"), isi `dikecualikan`
        dengan id_makanan dari rekomendasi sebelumnya.

        Returns:
            {"menu": {"sarapan": {...}, "siang": {...}, "malam": {...}},
             "harian": {"total", "target", "pemenuhan", "memenuhi"}}
            Pemenuhan harian memakai rumus (13) terhadap target gizi harian
            (jumlah target ketiga waktu makan = hasil rumus (5)-(8)).
        """
        terpakai: Set[int] = set(dikecualikan) if dikecualikan is not None else set()
        menu: Dict[str, Dict[str, Any]] = {}
        for waktu in RASIO_WAKTU_MAKAN:
            menu[waktu] = self._pilih_menu_waktu_makan(waktu, terpakai)
            terpakai |= {butir["id_makanan"] for butir in menu[waktu]["item"].values()}

        total_harian = {zat: sum(menu[w]["total"][zat] for w in menu) for zat in KOLOM_FITUR}
        target_harian = {
            zat: sum(self.target_gizi[w][zat] for w in RASIO_WAKTU_MAKAN) for zat in KOLOM_FITUR
        }
        pemenuhan_harian = self.hitung_persentase_pemenuhan(total_harian, target_harian)
        return {
            "menu": menu,
            "harian": {
                "total": total_harian,
                "target": target_harian,
                "pemenuhan": pemenuhan_harian,
                "memenuhi": self._memenuhi(pemenuhan_harian),
            },
        }