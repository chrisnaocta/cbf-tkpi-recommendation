"""Tes MesinRekomendasi bagian 1: rumus (10), normalisasi, rumus (11), KNN K=5."""

import numpy as np
import pandas as pd
import pytest

from kalkulator_gizi import KalkulatorGizi
from mesin_rekomendasi import (
    BERAT_ACUAN, KOLOM_NORMALISASI, KOLOM_SKOR, MesinRekomendasi,
)
from repositori_makanan import PERAN_VALID

'''
=== TABEL RATA-RATA DAN KONTRIBUSI ===
peran_menu                       pokok    lauk  sayur
Jumlah bahan                     44.00  154.00  58.00
Rata-rata Protein (g/100 g)       3.35   16.52   3.11
Rata-rata Lemak (g/100 g)         2.56   11.55   3.91
Rata-rata Karbohidrat (g/100 g)  29.59   11.10   7.53
Kontribusi Protein (%)           25.63   50.57  23.80
Kontribusi Lemak (%)             23.10   41.66  35.24
Kontribusi Karbohidrat (%)       71.21   10.69  18.11
'''

# Pool siap makan hasil kurasi (256 bahan: pokok 44, lauk 154, sayur 58), dalam persen.
# Dihitung terpisah dengan pandas dari data_makanan.csv + kurasi_makanan.py.
JUMLAH_POOL_KURASI = {"pokok": 44, "lauk": 154, "sayur": 58}
KONTRIBUSI_POOL_KURASI = {
    "pokok": {"protein": 25.63, "lemak": 23.10, "karbohidrat": 71.21},
    "lauk": {"protein": 50.57, "lemak": 41.66, "karbohidrat": 10.69},
    "sayur": {"protein": 23.80, "lemak": 35.24, "karbohidrat": 18.11},
}
RATA_RATA_POOL_KURASI = {
    "pokok": {"protein": 3.35, "lemak": 2.56, "karbohidrat": 29.59},
    "lauk": {"protein": 16.52, "lemak": 11.55, "karbohidrat": 11.10},
    "sayur": {"protein": 3.11, "lemak": 3.91, "karbohidrat": 7.53},
}
ZAT = ("energi", "protein", "lemak", "karbohidrat")


@pytest.fixture
def data_makanan(repositori):
    return repositori.get_all_makanan()


@pytest.fixture
def target_gizi():
    """Target tiap waktu makan untuk pria 30 th, 70 kg, 170 cm, menetap (profil A tahap 2)."""
    return KalkulatorGizi(30, "pria", 70.0, 170.0, "menetap").hitung_target_waktu_makan()


@pytest.fixture
def mesin(data_makanan, target_gizi):
    return MesinRekomendasi(data_makanan, target_gizi)


# ---------------------------------------------------------------------------
# Rumus (10)
# ---------------------------------------------------------------------------
def test_jumlah_pool_kurasi(data_makanan):
    assert data_makanan["peran_menu"].value_counts().to_dict() == JUMLAH_POOL_KURASI


def test_kontribusi_pool_kurasi(mesin):
    c = mesin.hitung_kontribusi_peran()
    for peran in PERAN_VALID:
        for zat, persen in KONTRIBUSI_POOL_KURASI[peran].items():
            assert round(c[peran][zat] * 100, 2) == persen, (peran, zat)


def test_rata_rata_pool_kurasi(mesin):
    for peran in PERAN_VALID:
        for zat, nilai in RATA_RATA_POOL_KURASI[peran].items():
            assert round(mesin._rata_rata[peran][zat], 2) == nilai, (peran, zat)


def test_kontribusi_ketiga_peran_berjumlah_100_persen(mesin):
    c = mesin.hitung_kontribusi_peran()
    for zat in ("protein", "lemak", "karbohidrat"):
        assert sum(c[p][zat] for p in PERAN_VALID) == pytest.approx(1.0)


def test_kontribusi_cocok_dengan_hitungan_manual_independen(data_makanan):
    """Hitung ulang rumus (10) langsung dari DataFrame tanpa memakai kelas."""
    rata = data_makanan.groupby("peran_menu")[["protein", "lemak", "karbohidrat"]].mean()
    for zat in ("protein", "lemak", "karbohidrat"):
        penyebut = sum(BERAT_ACUAN[p] * rata.loc[p, zat] for p in PERAN_VALID)
        for p in PERAN_VALID:
            harapan = BERAT_ACUAN[p] * rata.loc[p, zat] / penyebut
            mesin = MesinRekomendasi(
                data_makanan,
                KalkulatorGizi(30, "pria", 70.0, 170.0, "menetap").hitung_target_waktu_makan(),
            )
            assert mesin.hitung_kontribusi_peran()[p][zat] == pytest.approx(harapan)


# ---------------------------------------------------------------------------
# Target peran
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("waktu", ["sarapan", "siang", "malam"])
def test_target_peran_berjumlah_target_waktu_makan(mesin, target_gizi, waktu):
    for zat in ("protein", "lemak", "karbohidrat"):
        total = sum(mesin._hitung_target_peran(waktu, p)[zat] for p in PERAN_VALID)
        assert total == pytest.approx(target_gizi[waktu][zat])


def test_energi_peran_memakai_atwater(mesin):
    t = mesin._hitung_target_peran("siang", "lauk")
    assert t["energi"] == pytest.approx(4 * t["protein"] + 9 * t["lemak"] + 4 * t["karbohidrat"])


# ---------------------------------------------------------------------------
# Normalisasi
# ---------------------------------------------------------------------------
def test_normalisasi_membagi_dengan_target_peran(mesin):
    hasil = mesin.normalisasi_data("siang", "pokok")
    target = mesin._hitung_target_peran("siang", "pokok")
    assert len(hasil) == JUMLAH_POOL_KURASI["pokok"]
    assert set(hasil["peran_menu"]) == {"pokok"}
    for zat in ZAT:
        np.testing.assert_allclose(hasil["norm_" + zat], hasil[zat] / target[zat])


def test_normalisasi_vektor_target_menjadi_satu(mesin):
    """Bila nilai bahan = target peran, vektor ternormalisasi = (1,1,1,1)."""
    target = mesin._hitung_target_peran("sarapan", "sayur")
    contoh = pd.DataFrame([{zat: target[zat] for zat in ZAT}])
    np.testing.assert_allclose((contoh / pd.Series(target)).to_numpy(), np.ones((1, 4)))


def test_normalisasi_mengecualikan_id(mesin, data_makanan):
    dua_id = data_makanan.loc[data_makanan["peran_menu"] == "sayur", "id_makanan"].tolist()[:2]
    hasil = mesin.normalisasi_data("siang", "sayur", dikecualikan=dua_id)
    assert len(hasil) == JUMLAH_POOL_KURASI["sayur"] - 2
    assert not hasil["id_makanan"].isin(dua_id).any()


# ---------------------------------------------------------------------------
# Rumus (11)
# ---------------------------------------------------------------------------
def test_cosine_nilai_dikenal():
    f = MesinRekomendasi.hitung_cosine_similarity
    assert f([1, 0], [1, 1]) == pytest.approx(1 / np.sqrt(2))
    assert f([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert f([1, 0], [0, 1]) == pytest.approx(0.0)
    assert f([1, 1, 1, 1], [3, 3, 3, 3]) == pytest.approx(1.0)   # tidak peka skala
    assert f([1, 2], [3, 4]) == pytest.approx(11 / (np.sqrt(5) * 5))  # 0,98387


def test_cosine_vektor_nol_dan_panjang_beda():
    f = MesinRekomendasi.hitung_cosine_similarity
    assert f([1, 1], [0, 0]) == 0.0
    with pytest.raises(ValueError):
        f([1, 2], [1, 2, 3])


# ---------------------------------------------------------------------------
# KNN K = 5
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("waktu", ["sarapan", "siang", "malam"])
@pytest.mark.parametrize("peran", PERAN_VALID)
def test_knn_lima_tetangga_urut_dan_sesuai_peran(mesin, waktu, peran):
    hasil = mesin.cari_k_tetangga_terdekat(waktu, peran)
    assert len(hasil) == 5
    assert set(hasil["peran_menu"]) == {peran}
    skor = hasil[KOLOM_SKOR].to_numpy()
    assert (np.diff(skor) <= 1e-12).all()          # urut menurun
    assert ((skor >= -1e-12) & (skor <= 1 + 1e-12)).all()


@pytest.mark.parametrize("peran", PERAN_VALID)
def test_knn_sama_dengan_brute_force_rumus_11(mesin, peran):
    """5 skor tertinggi dari scikit-learn = 5 skor tertinggi dari rumus (11) buatan sendiri."""
    data = mesin.normalisasi_data("siang", peran)
    target = np.ones(4)
    semua = np.array([
        mesin.hitung_cosine_similarity(target, baris[list(KOLOM_NORMALISASI)].to_numpy(float))
        for _, baris in data.iterrows()
    ])
    harapan = np.sort(semua)[::-1][:5]
    hasil = mesin.cari_k_tetangga_terdekat("siang", peran)
    np.testing.assert_allclose(hasil[KOLOM_SKOR].to_numpy(), harapan, atol=1e-9)


def test_knn_dikecualikan_tidak_muncul_dan_tetap_lima(mesin):
    awal = mesin.cari_k_tetangga_terdekat("siang", "lauk")
    ditolak = awal["id_makanan"].tolist()[:2]
    baru = mesin.cari_k_tetangga_terdekat("siang", "lauk", dikecualikan=ditolak)
    assert len(baru) == 5
    assert not baru["id_makanan"].isin(ditolak).any()
    # skor kandidat terbaik baru tidak lebih tinggi dari yang lama
    assert baru[KOLOM_SKOR].iloc[0] <= awal[KOLOM_SKOR].iloc[0] + 1e-12


def test_knn_kandidat_kurang_dari_k_mengembalikan_semua(mesin):
    semua_sayur = mesin.data_makanan.loc[mesin.data_makanan["peran_menu"] == "sayur", "id_makanan"]
    sisakan = semua_sayur.tolist()[:3]
    ditolak = [i for i in semua_sayur if i not in sisakan]
    assert len(mesin.cari_k_tetangga_terdekat("malam", "sayur", dikecualikan=ditolak)) == 3


# ---------------------------------------------------------------------------
# Validasi
# ---------------------------------------------------------------------------
def test_peran_dan_waktu_tidak_valid_ditolak(mesin):
    with pytest.raises(ValueError):
        mesin.cari_k_tetangga_terdekat("siang", "buah")
    with pytest.raises(ValueError):
        mesin.cari_k_tetangga_terdekat("brunch", "pokok")


def test_semua_kandidat_dikecualikan_ditolak(mesin):
    semua = mesin.data_makanan.loc[mesin.data_makanan["peran_menu"] == "pokok", "id_makanan"].tolist()
    with pytest.raises(ValueError):
        mesin.normalisasi_data("siang", "pokok", dikecualikan=semua)


@pytest.mark.parametrize("k", [0, -1, 2.5, True])
def test_k_tidak_valid_ditolak(data_makanan, target_gizi, k):
    with pytest.raises(ValueError):
        MesinRekomendasi(data_makanan, target_gizi, k=k)


def test_target_tidak_lengkap_atau_nol_ditolak(data_makanan, target_gizi):
    rusak = {w: dict(v) for w, v in target_gizi.items()}
    rusak["siang"]["protein"] = 0
    with pytest.raises(ValueError):
        MesinRekomendasi(data_makanan, rusak)
    del rusak["malam"]
    with pytest.raises(ValueError):
        MesinRekomendasi(data_makanan, rusak)


def test_peran_tanpa_bahan_ditolak(data_makanan, target_gizi):
    tanpa_sayur = data_makanan[data_makanan["peran_menu"] != "sayur"]
    with pytest.raises(ValueError):
        MesinRekomendasi(tanpa_sayur, target_gizi)