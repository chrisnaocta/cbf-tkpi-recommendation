"""
Tes MesinRekomendasi bagian 2: rumus (12) porsi gram, rumus (13) pemenuhan,
seleksi 125 kombinasi (90-110%), dan susun_menu_harian.

Tiga profil sama dengan tes KalkulatorGizi:
  A. Pria 30 th, 70 kg, 170 cm, menetap
  B. Wanita 35 th, 80 kg, 160 cm, aktif (IMT > 25, target dikurangi 500 kkal)
  C. Pria 40 th, 100 kg, 200 cm, sangat aktif (target energi besar)
"""

from itertools import product

import numpy as np
import pytest

from kalkulator_gizi import KalkulatorGizi, RASIO_WAKTU_MAKAN
from mesin_rekomendasi import (
    BATAS_GRAM, KELIPATAN_GRAM, KOLOM_FITUR, KOLOM_SKOR, MesinRekomendasi,
)
from repositori_makanan import PERAN_VALID

PROFIL = {
    "A": (30, "pria", 70.0, 170.0, "menetap"),
    "B": (35, "wanita", 80.0, 160.0, "aktif"),
    "C": (40, "pria", 100.0, 200.0, "sangat_aktif"),
}
ZAT = tuple(KOLOM_FITUR)


@pytest.fixture
def data_makanan(repositori):
    return repositori.get_all_makanan()


def buat_mesin(data_makanan, profil):
    return MesinRekomendasi(
        data_makanan, KalkulatorGizi(*PROFIL[profil]).hitung_target_waktu_makan()
    )


def objektif(x, target, g):
    """Fungsi tujuan rumus (12) ditulis ulang dari definisi: SUM_j [(SUM_i g_i x_ij/100 - G_j)/G_j]^2."""
    total = x @ np.asarray(g) / 100.0
    return float(np.sum(((total - target) / target) ** 2))


def semua_kombinasi(mesin, waktu):
    """Menghitung ulang 125 kombinasi secara mandiri (tanpa memakai _pilih_menu_waktu_makan)."""
    tetangga = {p: mesin.cari_k_tetangga_terdekat(waktu, p) for p in PERAN_VALID}
    target = np.array([mesin.target_gizi[waktu][z] for z in ZAT])
    hasil = []
    for idx in product(*(range(len(tetangga[p])) for p in PERAN_VALID)):
        baris = {p: tetangga[p].iloc[i] for p, i in zip(PERAN_VALID, idx)}
        gram = mesin.hitung_porsi_gram(waktu, baris)
        total = np.array([
            sum(baris[p][z] * gram[p] / 100.0 for p in PERAN_VALID) for z in ZAT
        ])
        persen = total / target * 100.0
        hasil.append(dict(
            ids=tuple(int(baris[p]["id_makanan"]) for p in PERAN_VALID),
            skor=float(np.mean([baris[p][KOLOM_SKOR] for p in PERAN_VALID])),
            persen=persen,
            memenuhi=bool(np.all((persen >= 90 - 1e-9) & (persen <= 110 + 1e-9))),
            simpangan=float(np.max(np.abs(persen - 100.0))),
        ))
    return hasil


# ---------------------------------------------------------------------------
# Rumus (12)
# ---------------------------------------------------------------------------
def kandidat_contoh(data_makanan):
    return {
        "pokok": data_makanan[data_makanan.peran_menu == "pokok"].iloc[0],
        "lauk": data_makanan[data_makanan.peran_menu == "lauk"].iloc[10],
        "sayur": data_makanan[data_makanan.peran_menu == "sayur"].iloc[5],
    }


def mesin_dengan_target(data_makanan, kandidat, gram_benar, kali=1.0):
    """Mesin dengan target yang dibuat dari gram_benar (sehingga solusi tepat diketahui)."""
    total = {z: kali * sum(kandidat[p][z] * g / 100.0 for p, g in zip(PERAN_VALID, gram_benar))
             for z in ZAT}
    return MesinRekomendasi(data_makanan, {w: dict(total) for w in RASIO_WAKTU_MAKAN})


def test_porsi_menemukan_solusi_yang_diketahui(data_makanan):
    kandidat = kandidat_contoh(data_makanan)
    mesin = mesin_dengan_target(data_makanan, kandidat, (150.0, 60.0, 100.0))
    mentah = mesin._selesaikan_porsi("siang", kandidat)
    np.testing.assert_allclose(mentah, [150.0, 60.0, 100.0], atol=1e-3)
    assert mesin.hitung_porsi_gram("siang", kandidat) == {"pokok": 150.0, "lauk": 60.0, "sayur": 100.0}


def test_porsi_menyentuh_batas_atas_dan_bawah(data_makanan):
    kandidat = kandidat_contoh(data_makanan)
    besar = mesin_dengan_target(data_makanan, kandidat, (150.0, 60.0, 100.0), kali=20)
    kecil = mesin_dengan_target(data_makanan, kandidat, (150.0, 60.0, 100.0), kali=0.01)
    assert besar.hitung_porsi_gram("siang", kandidat) == {p: BATAS_GRAM[p][1] for p in PERAN_VALID}
    assert kecil.hitung_porsi_gram("siang", kandidat) == {p: BATAS_GRAM[p][0] for p in PERAN_VALID}


@pytest.mark.parametrize("profil", PROFIL)
def test_porsi_optimal_dibanding_titik_acak_dalam_batas(data_makanan, profil):
    """Solusi lsq_linear harus memberi nilai tujuan terkecil dibanding 5000 titik acak dalam batas."""
    mesin = buat_mesin(data_makanan, profil)
    kandidat = {p: mesin.cari_k_tetangga_terdekat("siang", p).iloc[0] for p in PERAN_VALID}
    x = mesin._matriks_gizi(kandidat)
    target = mesin._target_waktu_makan_vektor("siang")
    terbaik = objektif(x, target, mesin._selesaikan_porsi("siang", kandidat))

    rng = np.random.default_rng(0)
    bawah = np.array([BATAS_GRAM[p][0] for p in PERAN_VALID])
    atas = np.array([BATAS_GRAM[p][1] for p in PERAN_VALID])
    acak = rng.uniform(bawah, atas, size=(5000, 3))
    assert all(terbaik <= objektif(x, target, g) + 1e-9 for g in acak)


@pytest.mark.parametrize("profil", PROFIL)
def test_pembulatan_kelipatan_5_dan_dalam_batas(data_makanan, profil):
    mesin = buat_mesin(data_makanan, profil)
    for waktu in RASIO_WAKTU_MAKAN:
        kandidat = {p: mesin.cari_k_tetangga_terdekat(waktu, p).iloc[0] for p in PERAN_VALID}
        mentah = mesin._selesaikan_porsi(waktu, kandidat)
        gram = mesin.hitung_porsi_gram(waktu, kandidat)
        for nilai, p in zip(mentah, PERAN_VALID):
            assert gram[p] % KELIPATAN_GRAM == 0
            assert BATAS_GRAM[p][0] <= gram[p] <= BATAS_GRAM[p][1]
            assert abs(gram[p] - nilai) <= KELIPATAN_GRAM / 2 + 1e-9


def test_pembulatan_setengah_ke_atas():
    class Palsu(MesinRekomendasi):
        def __init__(self):
            self.batas_gram = BATAS_GRAM
        def _periksa_waktu(self, w): pass
        def _selesaikan_porsi(self, w, k): return np.array([112.5, 117.4, 52.4])
    gram = Palsu().hitung_porsi_gram("siang", {})
    assert gram == {"pokok": 115.0, "lauk": 115.0, "sayur": 50.0}


def test_waktu_makan_tidak_valid_ditolak(data_makanan):
    mesin = buat_mesin(data_makanan, "A")
    with pytest.raises(ValueError):
        mesin.hitung_porsi_gram("brunch", kandidat_contoh(data_makanan))


# ---------------------------------------------------------------------------
# Rumus (13)
# ---------------------------------------------------------------------------
def test_persentase_pemenuhan_rumus_13():
    total = {"energi": 1800.0, "protein": 45.0, "lemak": 66.0, "karbohidrat": 300.0}
    target = {"energi": 2000.0, "protein": 50.0, "lemak": 60.0, "karbohidrat": 300.0}
    hasil = MesinRekomendasi.hitung_persentase_pemenuhan(total, target)
    assert hasil == pytest.approx(
        {"energi": 90.0, "protein": 90.0, "lemak": 110.0, "karbohidrat": 100.0}
    )


# ---------------------------------------------------------------------------
# Seleksi 125 kombinasi
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("profil", PROFIL)
@pytest.mark.parametrize("waktu", ["sarapan", "siang", "malam"])
def test_seleksi_sama_dengan_perhitungan_mandiri(data_makanan, profil, waktu):
    mesin = buat_mesin(data_makanan, profil)
    semua = semua_kombinasi(mesin, waktu)
    assert len(semua) == 125
    terpilih = mesin._pilih_menu_waktu_makan(waktu, set())
    ids = tuple(terpilih["item"][p]["id_makanan"] for p in PERAN_VALID)

    layak = [k for k in semua if k["memenuhi"]]
    if layak:
        assert terpilih["memenuhi"] is True
        terbaik = max(k["skor"] for k in layak)
        assert terpilih["skor_rata_rata"] == pytest.approx(terbaik)
    else:
        assert terpilih["memenuhi"] is False
        assert max(abs(v - 100) for v in terpilih["pemenuhan"].values()) == pytest.approx(
            min(k["simpangan"] for k in semua)
        )
    dipilih = next(k for k in semua if k["ids"] == ids)
    np.testing.assert_allclose([terpilih["pemenuhan"][z] for z in ZAT], dipilih["persen"])


def test_tanpa_kombinasi_layak_dipilih_penyimpangan_terkecil(data_makanan):
    """Target 10x lebih besar tidak bisa dipenuhi dalam batas gram -> jalur cadangan."""
    kandidat = kandidat_contoh(data_makanan)
    mesin = mesin_dengan_target(data_makanan, kandidat, (150.0, 60.0, 100.0), kali=10)
    semua = semua_kombinasi(mesin, "siang")
    assert not any(k["memenuhi"] for k in semua)
    terpilih = mesin._pilih_menu_waktu_makan("siang", set())
    assert terpilih["memenuhi"] is False
    simpangan = max(abs(v - 100) for v in terpilih["pemenuhan"].values())
    assert simpangan == pytest.approx(min(k["simpangan"] for k in semua))


# ---------------------------------------------------------------------------
# Menu harian
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("profil", PROFIL)
def test_menu_harian_struktur_dan_angka(data_makanan, profil):
    kalk = KalkulatorGizi(*PROFIL[profil])
    mesin = MesinRekomendasi(data_makanan, kalk.hitung_target_waktu_makan())
    hasil = mesin.susun_menu_harian()
    peran_bahan = data_makanan.set_index("id_makanan")["peran_menu"]
    baris_bahan = data_makanan.set_index("id_makanan")

    assert list(hasil["menu"]) == ["sarapan", "siang", "malam"]
    semua_id = []
    for waktu, menu in hasil["menu"].items():
        assert list(menu["item"]) == list(PERAN_VALID)
        total = dict.fromkeys(ZAT, 0.0)
        for peran, butir in menu["item"].items():
            assert peran_bahan[butir["id_makanan"]] == peran
            assert butir["porsi_gram"] % 5 == 0
            assert BATAS_GRAM[peran][0] <= butir["porsi_gram"] <= BATAS_GRAM[peran][1]
            for z in ZAT:
                harapan = baris_bahan.loc[butir["id_makanan"], z] * butir["porsi_gram"] / 100
                assert butir[z] == pytest.approx(harapan)
                total[z] += harapan
            semua_id.append(butir["id_makanan"])
        for z in ZAT:
            assert menu["total"][z] == pytest.approx(total[z])
            assert menu["pemenuhan"][z] == pytest.approx(
                total[z] / mesin.target_gizi[waktu][z] * 100
            )
    # item tidak berulang pada hari yang sama
    assert len(semua_id) == 9 and len(set(semua_id)) == 9

    # target harian = hasil rumus (5)-(8) dan pemenuhan harian = rumus (13)
    harian = kalk.hitung_target_gizi()
    for z in ZAT:
        assert hasil["harian"]["target"][z] == pytest.approx(harian[z])
        jumlah = sum(hasil["menu"][w]["total"][z] for w in hasil["menu"])
        assert hasil["harian"]["total"][z] == pytest.approx(jumlah)
        assert hasil["harian"]["pemenuhan"][z] == pytest.approx(jumlah / harian[z] * 100)
    assert hasil["harian"]["memenuhi"] == all(
        90 - 1e-9 <= hasil["harian"]["pemenuhan"][z] <= 110 + 1e-9 for z in ZAT
    )


def test_minta_ulang_tidak_mengulang_item(data_makanan):
    mesin = buat_mesin(data_makanan, "A")
    pertama = mesin.susun_menu_harian()
    ids1 = {b["id_makanan"] for m in pertama["menu"].values() for b in m["item"].values()}
    kedua = mesin.susun_menu_harian(dikecualikan=ids1)
    ids2 = {b["id_makanan"] for m in kedua["menu"].values() for b in m["item"].values()}
    assert len(ids2) == 9 and ids1.isdisjoint(ids2)


def test_hasil_deterministik(data_makanan):
    mesin = buat_mesin(data_makanan, "B")
    a = mesin.susun_menu_harian()
    b = mesin.susun_menu_harian()
    assert a == b