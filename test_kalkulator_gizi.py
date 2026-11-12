"""
Tes KalkulatorGizi (rumus (1)-(9)) terhadap perhitungan manual.

Tiga profil, nilai harapan dihitung tangan (tidak memakai kode):
  A. Pria 30 th, 70 kg, 170 cm, menetap     -> IMT <= 25 (tanpa pengurangan)
  B. Wanita 35 th, 80 kg, 160 cm, aktif     -> IMT > 25  (dikurangi 500 kkal)
  C. Pria 40 th, 100 kg, 200 cm, sangat aktif -> IMT = 25,0 tepat (batas, tidak dikurangi)
"""

import pytest

from kalkulator_gizi import KalkulatorGizi, RASIO_WAKTU_MAKAN

TOL = 1e-6

# Nilai harapan hasil hitung tangan
#   A: IMT = 70/1,7^2 = 24,2214; BMR = 10(70)+6,25(170)-5(30)+5 = 1617,5
#      TEE = 1617,5 x 1,55 = 2507,125; protein = 0,15 x 2507,125 / 4 = 94,0172
#   B: IMT = 80/1,6^2 = 31,25; BMR = 800+1000-175-161 = 1464; TEE = 1464 x 1,85 = 2708,4
#      energi = 2708,4 - 500 = 2208,4; protein = 0,15 x 2208,4 / 4 = 82,815
#   C: IMT = 100/2^2 = 25,0; BMR = 1000+1250-200+5 = 2055; TEE = 2055 x 2,2 = 4521
PROFIL = {
    "A": dict(
        data=(30, "pria", 70.0, 170.0, "menetap"),
        imt=70 / 1.7**2, bmr=1617.5, klasifikasi="Berat badan normal",
        energi=2507.125, protein=94.017188, lemak=69.642361, karbohidrat=376.06875,
    ),
    "B": dict(
        data=(35, "wanita", 80.0, 160.0, "aktif"),
        imt=31.25, bmr=1464.0, klasifikasi="Kelebihan berat badan tingkat berat",
        energi=2208.4, protein=82.815, lemak=61.344444, karbohidrat=331.26,
    ),
    "C": dict(
        data=(40, "pria", 100.0, 200.0, "sangat_aktif"),
        imt=25.0, bmr=2055.0, klasifikasi="Berat badan normal",
        energi=4521.0, protein=169.5375, lemak=125.583333, karbohidrat=678.15,
    ),
}


@pytest.fixture(params=list(PROFIL))
def profil(request):
    p = PROFIL[request.param]
    return KalkulatorGizi(*p["data"]), p


def test_imt_bmr_klasifikasi(profil):
    k, p = profil
    assert k.hitung_imt() == pytest.approx(p["imt"], abs=TOL)
    assert k.hitung_bmr() == pytest.approx(p["bmr"], abs=TOL)
    assert k.klasifikasi_imt() == p["klasifikasi"]


def test_target_gizi_harian(profil):
    k, p = profil
    t = k.hitung_target_gizi()
    for zat in ("energi", "protein", "lemak", "karbohidrat"):
        assert t[zat] == pytest.approx(p[zat], abs=1e-4)


def test_target_waktu_makan_rumus_9(profil):
    k, p = profil
    harian = k.hitung_target_gizi()
    per = k.hitung_target_waktu_makan()
    assert set(per) == {"sarapan", "siang", "malam"}
    for waktu, rho in RASIO_WAKTU_MAKAN.items():
        for zat in harian:
            assert per[waktu][zat] == pytest.approx(rho * harian[zat], abs=TOL)
    # ketiga waktu makan harus berjumlah target harian
    for zat in harian:
        assert sum(per[w][zat] for w in per) == pytest.approx(harian[zat], abs=TOL)


def test_pengurangan_500_hanya_untuk_imt_di_atas_25():
    a = KalkulatorGizi(*PROFIL["A"]["data"])
    b = KalkulatorGizi(*PROFIL["B"]["data"])
    c = KalkulatorGizi(*PROFIL["C"]["data"])
    assert a.hitung_target_gizi()["energi"] == pytest.approx(a._hitung_tee())
    assert b.hitung_target_gizi()["energi"] == pytest.approx(b._hitung_tee() - 500)
    assert c.hitung_target_gizi()["energi"] == pytest.approx(c._hitung_tee())  # IMT = 25,0


def test_makro_dari_target_energi_dan_energi_kembali():
    """Protein/lemak/karbohidrat x Atwater = 15/25/60% dari Target Energi."""
    t = KalkulatorGizi(*PROFIL["B"]["data"]).hitung_target_gizi()
    e = t["energi"]
    assert 4 * t["protein"] == pytest.approx(0.15 * e)
    assert 9 * t["lemak"] == pytest.approx(0.25 * e)
    assert 4 * t["karbohidrat"] == pytest.approx(0.60 * e)
    assert 4 * t["protein"] + 9 * t["lemak"] + 4 * t["karbohidrat"] == pytest.approx(e)


def test_faktor_aktivitas_mengubah_tee_pada_pengguna_sama():
    tee = {
        a: KalkulatorGizi(30, "pria", 70.0, 170.0, a)._hitung_tee()
        for a in ("menetap", "aktif", "sangat_aktif")
    }
    bmr = 1617.5
    assert tee["menetap"] == pytest.approx(bmr * 1.55)
    assert tee["aktif"] == pytest.approx(bmr * 1.85)
    assert tee["sangat_aktif"] == pytest.approx(bmr * 2.20)


def test_rumus_bmr_pria_dan_wanita_berbeda_161_plus_5():
    pria = KalkulatorGizi(30, "pria", 70.0, 170.0, "menetap").hitung_bmr()
    wanita = KalkulatorGizi(30, "wanita", 70.0, 170.0, "menetap").hitung_bmr()
    assert pria - wanita == pytest.approx(166.0)


@pytest.mark.parametrize("imt_bb,kategori", [
    (45.0, "Kekurangan berat badan tingkat berat"),     # IMT 15,57
    (52.0, "Kekurangan berat badan tingkat ringan"),    # IMT 17,99
    (60.0, "Berat badan normal"),                       # IMT 20,76
    (72.0, "Berat badan normal"),                       # IMT 24,91
    (75.0, "Kelebihan berat badan tingkat ringan"),     # IMT 25,95
    (85.0, "Kelebihan berat badan tingkat berat"),      # IMT 29,41
])
def test_klasifikasi_imt_tabel_2_1(imt_bb, kategori):
    assert KalkulatorGizi(30, "pria", imt_bb, 170.0, "menetap").klasifikasi_imt() == kategori


@pytest.mark.parametrize("kwargs", [
    dict(usia=18), dict(usia=50), dict(usia=30.5), dict(usia="30"),
    dict(jenis_kelamin="Laki-laki"), dict(jenis_kelamin=""),
    dict(tingkat_aktivitas="berat"), dict(tingkat_aktivitas=None),
    dict(berat_badan=0), dict(berat_badan=-5), dict(berat_badan="abc"), dict(berat_badan=float("nan")),
    dict(tinggi_badan=0), dict(tinggi_badan=-170), dict(tinggi_badan="abc"), dict(tinggi_badan=float("inf")),
])
def test_masukan_tidak_valid_ditolak(kwargs):
    dasar = dict(usia=30, jenis_kelamin="pria", berat_badan=70.0, tinggi_badan=170.0, tingkat_aktivitas="menetap")
    dasar.update(kwargs)
    with pytest.raises(ValueError):
        KalkulatorGizi(**dasar)


@pytest.mark.parametrize("usia", [19, 49])
def test_batas_usia_diterima(usia):
    assert KalkulatorGizi(usia, "wanita", 60.0, 160.0, "aktif").hitung_bmr() > 0