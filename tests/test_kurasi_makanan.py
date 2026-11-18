"""Tes kurasi_makanan.py (kriteria siap makan) dan impor setup_db.py."""

import os
import sqlite3
import sys
import time

import pandas as pd
import pytest

FOLDER_DATABASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database")
CSV_MAKANAN = os.path.join(FOLDER_DATABASE, "data_makanan.csv")
sys.path.insert(0, FOLDER_DATABASE)

import kurasi_makanan as K  # noqa: E402
import setup_db  # noqa: E402


@pytest.fixture(scope="module")
def hasil():
    return K.baca_dan_kurasi(CSV_MAKANAN)


def _baris(nama, kode, peran="lauk"):
    return {
        "kode_tkpi": kode, "nama_bahan": nama, "kategori": "X",
        "energi": 100, "protein": 1.0, "lemak": 1.0, "karbohidrat": 1.0, "peran_menu": peran,
    }


def test_ringkasan_jumlah_baris(hasil):
    assert len(hasil) == 1146
    masuk = hasil[hasil["keputusan"] == "masuk"]
    assert masuk["peran_menu"].value_counts().to_dict() == {"lauk": 155, "sayur": 58, "pokok": 44}
    assert len(masuk) == 257


def test_jumlah_per_dasar(hasil):
    h = hasil.groupby(["keputusan", "dasar"]).size().to_dict()
    assert h == {
        ("keluar", "K0"): 356, ("keluar", "K1"): 401, ("keluar", "K2"): 48,
        ("keluar", "K4"): 23, ("keluar", "K5"): 52, ("keluar", "K6"): 9,
        ("masuk", "K3"): 180, ("masuk", "K5"): 77,
    }


def test_tidak_ada_kode_r_atau_kata_mentah_yang_masuk(hasil):
    masuk = hasil[hasil["keputusan"] == "masuk"]
    assert (masuk["kode_tkpi"].str[1] == "P").all()
    assert not masuk["nama_bahan"].str.lower().str.contains("mentah").any()
    assert set(masuk["peran_menu"]) == {"pokok", "lauk", "sayur"}


@pytest.mark.parametrize("nama,harapan", [
    ("Nasi", "masuk"), ("Nasi tim", "masuk"), ("Bayam, rebus", "masuk"),
    ("Ayam goreng kalasan, paha", "masuk"), ("Gado-gado", "masuk"),
    ("Beras giling, mentah", "keluar"), ("Bayam, segar", "keluar"),
    ("Tepung terigu", "keluar"), ("Ikan teri, kering, mentah", "keluar"),
    ("Tempe pasar", "keluar"), ("Tempe pasar goreng", "masuk"),
])
def test_contoh_keputusan(hasil, nama, harapan):
    baris = hasil[hasil["nama_bahan"] == nama]
    assert len(baris) == 1, nama
    assert baris["keputusan"].iloc[0] == harapan


def test_kolom_dan_nilai_gizi_tidak_berubah(hasil):
    asli = pd.read_csv(CSV_MAKANAN)
    pd.testing.assert_frame_equal(hasil[asli.columns], asli)


def test_bahan_olahan_tanpa_keputusan_ditolak():
    df = pd.DataFrame([_baris("Hidangan baru", "FP999")])
    with pytest.raises(ValueError, match="belum diputuskan"):
        K.kurasi(df)


def test_kode_tinjauan_tidak_dipakai_ditolak():
    df = pd.DataFrame([_baris("Bayam, segar", "DR001", "sayur")])
    with pytest.raises(ValueError, match="KEPUTUSAN_TINJAUAN"):
        K.kurasi(df)


def test_kode_tinjauan_tidak_ada_ganda():
    kode = [k for _, _, daftar in K.KEPUTUSAN_TINJAUAN.values() for k in daftar]
    assert len(kode) == len(set(kode)) == 130


@pytest.mark.parametrize("nama", [
    "RW, anjing, masakan", "Tikus rica, masakan", "Lawar penyu, masakan", "Sate, penyu, masakan",
    "Penyu, serapah, masakan", "Paniki masak santan, masakan", "Babi hutan masak rica, masakan",
    "Lawar babi, masakan", "Ham",
])
def test_bahan_pengecualian_peneliti_keluar_dengan_dasar_k6(hasil, nama):
    baris = hasil[hasil["nama_bahan"] == nama]
    assert len(baris) == 1, nama
    assert baris["keputusan"].iloc[0] == "keluar"
    assert baris["dasar"].iloc[0] == "K6"


def test_pool_tidak_memuat_hewan_yang_dikecualikan(hasil):
    masuk = hasil[hasil["keputusan"] == "masuk"]["nama_bahan"].str.lower()
    for kata in ("anjing", "tikus", "penyu", "paniki", "babi"):
        assert not masuk.str.contains(kata).any(), kata
    assert len(K.KODE_DIKECUALIKAN_PENELITI) == 9


def test_kode_pengecualian_tidak_ada_pada_data_ditolak(monkeypatch):
    monkeypatch.setitem(K.KODE_DIKECUALIKAN_PENELITI, "XX999", "babi")
    with pytest.raises(ValueError, match="KODE_DIKECUALIKAN_PENELITI"):
        K.baca_dan_kurasi(CSV_MAKANAN)


def test_kode_dengan_alfabet_kedua_tidak_dikenal_ditolak():
    df = pd.DataFrame([_baris("Bahan aneh", "FX001")])
    with pytest.raises(ValueError, match="bukan R atau P"):
        K.kurasi(df)


def test_impor_hanya_memasukkan_bahan_siap_makan(db_uji):
    c = sqlite3.connect(db_uji)
    n = c.execute("SELECT COUNT(*) FROM makanan").fetchone()[0]
    ids = [r[0] for r in c.execute("SELECT id_makanan FROM makanan ORDER BY id_makanan")]
    c.close()
    assert n == 257
    assert ids == list(range(1, 258))


def test_impor_dua_kali_tidak_menggandakan_data(db_uji, capsys):
    setup_db.import_csv_to_db(CSV_MAKANAN)
    c = sqlite3.connect(db_uji)
    n = c.execute("SELECT COUNT(*) FROM makanan").fetchone()[0]
    c.close()
    assert n == 257
    assert "impor dibatalkan" in capsys.readouterr().out


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="time.tzset tidak tersedia di Windows")
def test_waktu_default_memakai_waktu_lokal(db_uji, monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Jakarta")
    time.tzset()
    try:
        c = sqlite3.connect(db_uji)
        c.execute("INSERT INTO sesi_pengguna (usia) VALUES (30)")
        selisih = c.execute(
            "SELECT CAST(strftime('%s', waktu_input) AS INTEGER) - "
            "CAST(strftime('%s', 'now') AS INTEGER) FROM sesi_pengguna"
        ).fetchone()[0]
        c.close()
        assert abs(selisih - 7 * 3600) <= 5   # WIB = UTC + 7 jam
    finally:
        monkeypatch.undo()
        time.tzset()