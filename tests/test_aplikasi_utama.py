"""
Tes AplikasiUtama: alur input -> gizi -> rekomendasi -> simpan, validasi, dan Minta Ulang.
Tanpa UI Streamlit.
"""

import pandas as pd
import pytest

from aplikasi_utama import (
    CATATAN_IMT_KURUS, KOLOM_TABEL_REKOMENDASI, AplikasiUtama,
)
from kalkulator_gizi import KalkulatorGizi
from sesi_pengguna import SesiPengguna, kumpulkan_id_makanan

PROFIL_A = (30, "pria", 70.0, 170.0, "menetap")
PROFIL_B = (35, "wanita", 80.0, 160.0, "aktif")
ZAT = ("energi", "protein", "lemak", "karbohidrat")


@pytest.fixture
def aplikasi(repositori):
    return AplikasiUtama(repositori)


def jumlah(koneksi, tabel):
    return int(koneksi.execute_query(f"SELECT COUNT(*) AS n FROM {tabel}")["n"][0])


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------
def test_form_input_memuat_batas_dan_tiga_aktivitas(aplikasi):
    f = aplikasi.tampilkan_form_input()
    assert (f["usia"]["min"], f["usia"]["max"]) == (19, 49)
    assert [k for k, _ in f["jenis_kelamin"]] == ["pria", "wanita"]
    assert [a["kunci"] for a in f["tingkat_aktivitas"]] == ["menetap", "aktif", "sangat_aktif"]
    assert [a["faktor"] for a in f["tingkat_aktivitas"]] == [1.55, 1.85, 2.20]
    assert [a["rentang_pal"] for a in f["tingkat_aktivitas"]] == [
        "1,40 - 1,69", "1,70 - 1,99", "2,00 - 2,40"]
    assert all(a["contoh"] for a in f["tingkat_aktivitas"])


# ---------------------------------------------------------------------------
# Input valid
# ---------------------------------------------------------------------------
def test_input_valid_hasil_gizi_cocok_hitungan_manual(aplikasi):
    hasil = aplikasi.proses_input_pengguna(*PROFIL_A)
    assert hasil["imt"] == pytest.approx(24.2215, abs=1e-3)
    assert hasil["klasifikasi"] == "Berat badan normal"
    assert hasil["bmr"] == pytest.approx(1617.5)
    assert hasil["faktor_aktivitas"] == 1.55
    assert hasil["tee"] == pytest.approx(2507.125)
    assert hasil["target_harian"]["energi"] == pytest.approx(2507.125)   # IMT <= 25
    assert hasil["catatan"] is None


def test_input_imt_di_atas_25_target_dikurangi_500(aplikasi):
    hasil = aplikasi.proses_input_pengguna(*PROFIL_B)
    assert hasil["imt"] == pytest.approx(31.25)
    assert hasil["tee"] == pytest.approx(2708.4)
    assert hasil["target_harian"]["energi"] == pytest.approx(2208.4)


def test_data_tersimpan_ke_sesi_dan_riwayat(aplikasi, koneksi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    sesi = koneksi.execute_query("SELECT * FROM sesi_pengguna")
    assert len(sesi) == 1
    baris = sesi.iloc[0]
    assert baris["id_sesi"] == aplikasi.sesi.id_sesi
    assert (baris["usia"], baris["jenis_kelamin"], baris["tingkat_aktivitas"]) == (30, "pria", "menetap")
    assert baris["bmr"] == pytest.approx(1617.5)
    assert baris["target_energi"] == pytest.approx(2507.125)

    riwayat = koneksi.execute_query("SELECT * FROM riwayat_rekomendasi")
    assert len(riwayat) == 9
    assert (riwayat["id_sesi"] == baris["id_sesi"]).all()
    assert riwayat["jenis_waktu_makan"].value_counts().to_dict() == {"sarapan": 3, "siang": 3, "malam": 3}
    assert (riwayat["porsi_gram"] % 5 == 0).all()
    assert riwayat["skor_similarity"].between(0, 1).all()


def test_rekomendasi_pertama_menjadi_rekomendasi_saat_ini(aplikasi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    assert aplikasi.sesi.aktif
    assert len(kumpulkan_id_makanan(aplikasi.sesi.rekomendasi_saat_ini)) == 9
    assert aplikasi.sesi.item_sebelumnya == []
    assert aplikasi.kalkulator is not None and aplikasi.mesin is not None


def test_masukan_teks_angka_dan_koma_diterima(aplikasi):
    hasil = aplikasi.proses_input_pengguna("30", "pria", "70,0", " 170 ", "menetap")
    assert hasil["bmr"] == pytest.approx(1617.5)
    aplikasi.proses_input_pengguna(30.0, "pria", 70, 170, "menetap")   # usia float bulat


def test_catatan_imt_di_bawah_18_5(aplikasi):
    hasil = aplikasi.proses_input_pengguna(30, "pria", 50.0, 170.0, "menetap")   # IMT 17,3
    assert hasil["catatan"] == CATATAN_IMT_KURUS
    # target energi tidak ditambah: sama dengan TEE
    assert hasil["target_harian"]["energi"] == pytest.approx(hasil["tee"])


# ---------------------------------------------------------------------------
# Input tidak valid: tidak ada yang tersimpan
# ---------------------------------------------------------------------------
INPUT_RUSAK = [
    (None, "pria", 70.0, 170.0, "menetap"),          # kolom kosong
    (30, "", 70.0, 170.0, "menetap"),
    (30, "pria", "  ", 170.0, "menetap"),
    (30, "pria", 70.0, 170.0, None),
    (None, None, None, None, None),
    (30, "pria", 0, 170.0, "menetap"),               # nol
    (30, "pria", 70.0, 0, "menetap"),
    (30, "pria", -70.0, 170.0, "menetap"),           # negatif
    (30, "pria", 70.0, -170.0, "menetap"),
    (30, "pria", "abc", 170.0, "menetap"),           # teks
    (30, "pria", 70.0, "tinggi", "menetap"),
    ("tiga puluh", "pria", 70.0, 170.0, "menetap"),
    (30.5, "pria", 70.0, 170.0, "menetap"),          # usia bukan bulat
    (18, "pria", 70.0, 170.0, "menetap"),            # usia di luar 19-49
    (50, "pria", 70.0, 170.0, "menetap"),
    (30, "laki", 70.0, 170.0, "menetap"),            # pilihan tidak dikenal
    (30, "pria", 70.0, 170.0, "berat"),
    (30, "pria", float("nan"), 170.0, "menetap"),
    (30, "pria", True, 170.0, "menetap"),
]


@pytest.mark.parametrize("masukan", INPUT_RUSAK)
def test_input_tidak_valid_ditolak_tanpa_menyimpan(aplikasi, koneksi, masukan):
    with pytest.raises(ValueError):
        aplikasi.proses_input_pengguna(*masukan)
    assert jumlah(koneksi, "sesi_pengguna") == 0
    assert jumlah(koneksi, "riwayat_rekomendasi") == 0
    assert not aplikasi.sesi.aktif


def test_pesan_kolom_kosong_menyebut_semua_kolom(aplikasi):
    with pytest.raises(ValueError, match="usia, berat badan"):
        aplikasi.proses_input_pengguna(None, "pria", None, 170.0, "menetap")


def test_input_gagal_tidak_merusak_sesi_sebelumnya(aplikasi, koneksi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    id_awal = aplikasi.sesi.id_sesi
    with pytest.raises(ValueError):
        aplikasi.proses_input_pengguna(18, "pria", 70.0, 170.0, "menetap")
    assert aplikasi.sesi.id_sesi == id_awal and jumlah(koneksi, "sesi_pengguna") == 1


# ---------------------------------------------------------------------------
# Minta Ulang
# ---------------------------------------------------------------------------
def test_minta_ulang_item_berbeda_target_sama_dan_tersimpan(aplikasi, koneksi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    awal = aplikasi.sesi.rekomendasi_saat_ini
    ids_awal = kumpulkan_id_makanan(awal)

    baru = aplikasi.refresh_rekomendasi()
    ids_baru = kumpulkan_id_makanan(baru)
    assert len(ids_baru) == 9 and set(ids_baru).isdisjoint(ids_awal)
    assert aplikasi.sesi.item_sebelumnya == ids_awal
    assert kumpulkan_id_makanan(aplikasi.sesi.rekomendasi_saat_ini) == ids_baru

    # target gizi tetap sama
    for waktu in awal["menu"]:
        assert baru["menu"][waktu]["target"] == awal["menu"][waktu]["target"]
    assert baru["harian"]["target"] == awal["harian"]["target"]

    # sesi tetap satu; riwayat bertambah 9 baris
    assert jumlah(koneksi, "sesi_pengguna") == 1
    riwayat = koneksi.execute_query("SELECT id_sesi, id_makanan FROM riwayat_rekomendasi")
    assert len(riwayat) == 18 and (riwayat["id_sesi"] == aplikasi.sesi.id_sesi).all()
    assert riwayat["id_makanan"].tolist() == ids_awal + ids_baru


def test_minta_ulang_berturut_turut_hanya_menghindari_rekomendasi_sebelumnya(aplikasi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    ids = [kumpulkan_id_makanan(aplikasi.sesi.rekomendasi_saat_ini)]
    for _ in range(3):
        ids.append(kumpulkan_id_makanan(aplikasi.refresh_rekomendasi()))
    for sebelum, sesudah in zip(ids, ids[1:]):
        assert set(sebelum).isdisjoint(sesudah)
        assert len(set(sesudah)) == 9


def test_minta_ulang_menjaga_kesesuaian_gizi(aplikasi):
    aplikasi.proses_input_pengguna(*PROFIL_B)
    baru = aplikasi.refresh_rekomendasi()
    for menu in baru["menu"].values():
        for zat in ZAT:
            expected = sum(b[zat] for b in menu["item"].values())
            assert menu["total"][zat] == pytest.approx(expected)


def test_input_baru_memulai_sesi_baru(aplikasi, koneksi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    aplikasi.refresh_rekomendasi()
    id_lama = aplikasi.sesi.id_sesi
    aplikasi.proses_input_pengguna(*PROFIL_B)
    assert aplikasi.sesi.id_sesi == id_lama + 1
    assert aplikasi.sesi.item_sebelumnya == []
    assert jumlah(koneksi, "sesi_pengguna") == 2


# ---------------------------------------------------------------------------
# Data siap tampil
# ---------------------------------------------------------------------------
def test_tampilkan_sebelum_input_ditolak(aplikasi):
    with pytest.raises(RuntimeError):
        aplikasi.refresh_rekomendasi()
    with pytest.raises(RuntimeError):
        aplikasi.tampilkan_hasil_gizi()
    with pytest.raises(RuntimeError):
        aplikasi.tampilkan_rekomendasi()
    with pytest.raises(RuntimeError):
        aplikasi.tampilkan_detail_nutrisi(1)


def test_tampilkan_hasil_gizi(aplikasi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    h = aplikasi.tampilkan_hasil_gizi()
    assert h["profil"]["usia"] == 30
    assert set(h["target_waktu_makan"]) == {"sarapan", "siang", "malam"}
    h["profil"]["usia"] = 99                       # salinan; sesi tidak berubah
    assert aplikasi.sesi.profil["usia"] == 30


def test_tampilkan_rekomendasi_tabel_dan_pemenuhan(aplikasi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    r = aplikasi.tampilkan_rekomendasi()
    assert list(r["menu"]) == ["sarapan", "siang", "malam"]
    for waktu, menu in r["menu"].items():
        tabel = menu["tabel"]
        assert isinstance(tabel, pd.DataFrame)
        assert tuple(tabel.columns) == KOLOM_TABEL_REKOMENDASI
        assert tabel["peran"].tolist() == ["Makanan pokok", "Lauk", "Sayur"]
        assert menu["memenuhi"] == all(90 - 1e-9 <= v <= 110 + 1e-9 for v in menu["pemenuhan"].values())
        for zat in ZAT:
            assert menu["total"][zat] == pytest.approx(tabel[zat].sum())
    assert set(r["harian"]) == {"total", "target", "pemenuhan", "memenuhi"}
    assert r["catatan"] is None   # profil A: semua waktu makan memenuhi


def test_detail_nutrisi_item(aplikasi, repositori):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    tabel = aplikasi.tampilkan_rekomendasi()["menu"]["siang"]["tabel"]
    baris = tabel.iloc[0]
    d = aplikasi.tampilkan_detail_nutrisi(int(baris["id_makanan"]))
    asli = repositori.get_all_makanan().set_index("id_makanan").loc[int(baris["id_makanan"])]
    assert d["nama_bahan"] == asli["nama_bahan"] and d["kode_tkpi"] == asli["kode_tkpi"]
    assert d["waktu_makan"] == "Makan Siang" and d["peran"] == "Makanan pokok"
    assert d["porsi_gram"] == baris["porsi_gram"]
    for zat in ZAT:
        assert d["per_100_gram"][zat] == asli[zat]
        assert d["per_porsi"][zat] == pytest.approx(asli[zat] * d["porsi_gram"] / 100)


def test_detail_nutrisi_id_tidak_ada_pada_rekomendasi_ditolak(aplikasi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    ada = set(kumpulkan_id_makanan(aplikasi.sesi.rekomendasi_saat_ini))
    tidak_ada = next(i for i in range(1, 791) if i not in ada)
    with pytest.raises(ValueError):
        aplikasi.tampilkan_detail_nutrisi(tidak_ada)


def test_detail_nutrisi_mengikuti_rekomendasi_terbaru(aplikasi):
    aplikasi.proses_input_pengguna(*PROFIL_A)
    lama = kumpulkan_id_makanan(aplikasi.sesi.rekomendasi_saat_ini)[0]
    aplikasi.refresh_rekomendasi()
    with pytest.raises(ValueError):
        aplikasi.tampilkan_detail_nutrisi(lama)