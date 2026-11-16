"""
Tes antarmuka app.py dengan streamlit.testing.v1.AppTest (tanpa browser).

Basis data yang dipakai adalah salinan sementara dari fixture `db_uji`
(variabel lingkungan SKRIPSI_DB_PATH), sehingga rekomendasi_makanan.db milik
pengguna tidak tertulis oleh tes.
"""

import os
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

JALUR_APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
TIMEOUT = 90


@pytest.fixture
def app(db_uji, monkeypatch):
    monkeypatch.setenv("SKRIPSI_DB_PATH", db_uji)
    at = AppTest.from_file(JALUR_APP, default_timeout=TIMEOUT)
    at.db_path = db_uji
    return at.run()


def isi(at, usia="35", jk="wanita", berat="80", tinggi="160", aktivitas="aktif"):
    at.text_input(key="in_usia").input(usia)
    if jk:
        at.radio(key="in_jk").set_value(jk)
    at.text_input(key="in_berat").input(berat)
    at.text_input(key="in_tinggi").input(tinggi)
    if aktivitas:
        at.selectbox(key="in_aktivitas").set_value(aktivitas)
    return at


def tombol(at, label):
    return next(b for b in at.button if b.label == label)


def kirim(at, **kw):
    isi(at, **kw)
    return tombol(at, "Hitung dan susun menu").click().run()


def teks_markdown(at):
    return "\n".join(m.value for m in at.markdown)


def jumlah_baris(jalur, tabel):
    with sqlite3.connect(jalur) as k:
        return k.execute(f"SELECT COUNT(*) FROM {tabel}").fetchone()[0]


def test_tampilan_awal_tanpa_galat(app):
    assert not app.exception
    assert not app.error
    assert "Isi data diri di panel kiri" in teks_markdown(app)
    assert [b.label for b in app.button] == ["Hitung dan susun menu"]


def test_lima_input_tersedia(app):
    assert len(app.text_input) == 3          # usia, berat, tinggi
    assert len(app.radio) == 1               # jenis kelamin
    assert len(app.selectbox) == 1           # tingkat aktivitas
    assert [o for o in app.radio(key="in_jk").options] == ["Laki-laki", "Perempuan"]
    assert len(app.selectbox(key="in_aktivitas").options) == 3


def test_kolom_kosong_menampilkan_pesan_dan_tidak_menyimpan(app):
    app = tombol(app, "Hitung dan susun menu").click().run()
    assert any("Kolom wajib diisi" in e.value for e in app.error)
    assert "Menu hari ini" not in teks_markdown(app)
    assert jumlah_baris(app.db_path, "sesi_pengguna") == 0


def test_satu_kolom_kosong_disebut(app):
    app = kirim(app, berat="")
    pesan = " ".join(e.value for e in app.error)
    assert "berat badan" in pesan and "usia" not in pesan


@pytest.mark.parametrize("masukan", [
    dict(usia="18"), dict(usia="50"), dict(usia="30,5"), dict(usia="tiga puluh"),
    dict(berat="abc"), dict(berat="0"), dict(berat="-5"),
    dict(tinggi="0"), dict(tinggi="-160"), dict(tinggi="tinggi"),
])
def test_input_tidak_valid_menampilkan_galat(app, masukan):
    app = kirim(app, **masukan)
    assert not app.exception
    assert len(app.error) == 1 and app.error[0].value
    assert "Menu hari ini" not in teks_markdown(app)
    assert jumlah_baris(app.db_path, "sesi_pengguna") == 0
    assert jumlah_baris(app.db_path, "riwayat_rekomendasi") == 0


def test_input_valid_menampilkan_hasil_dan_menu(app):
    app = kirim(app)      # wanita 35 th, 80 kg, 160 cm, aktif -> IMT 31,25
    assert not app.exception and not app.error
    html = teks_markdown(app)
    for kata in ("Kebutuhan gizi Anda", "Menu hari ini", "Detail nutrisi",
                 "Sarapan", "Makan Siang", "Makan Malam", "Total satu hari"):
        assert kata in html
    assert "31,2" in html                       # IMT 31,25
    assert "2.708" in html and "2.208" in html  # TEE dan target energi (TEE - 500)
    assert "dikurangi 500 kkal" in html
    assert html.count('class="nampan"') == 4    # 3 waktu makan + total harian
    assert jumlah_baris(app.db_path, "sesi_pengguna") == 1
    assert jumlah_baris(app.db_path, "riwayat_rekomendasi") == 9


def test_imt_normal_tanpa_pengurangan(app):
    app = kirim(app, usia="30", jk="pria", berat="70", tinggi="170", aktivitas="menetap")
    html = teks_markdown(app)
    assert "Sama dengan TEE" in html and "dikurangi" not in html


def test_catatan_imt_di_bawah_18_5(app):
    app = kirim(app, usia="30", jk="pria", berat="50", tinggi="170", aktivitas="menetap")
    assert any("di bawah 18,5" in w.value for w in app.warning)


def test_minta_ulang_mengganti_menu_dan_menyimpan_riwayat(app):
    app = kirim(app)
    aplikasi = app.session_state["aplikasi"]
    sebelum = {b["id_makanan"] for m in aplikasi.sesi.rekomendasi_saat_ini["menu"].values()
               for b in m["item"].values()}
    app = tombol(app, "Minta Ulang").click().run()
    assert not app.exception and not app.error
    sesudah = {b["id_makanan"] for m in app.session_state["aplikasi"].sesi.rekomendasi_saat_ini["menu"].values()
               for b in m["item"].values()}
    assert len(sesudah) == 9 and sebelum.isdisjoint(sesudah)
    assert jumlah_baris(app.db_path, "sesi_pengguna") == 1
    assert jumlah_baris(app.db_path, "riwayat_rekomendasi") == 18
    assert "Menu hari ini" in teks_markdown(app)


def test_detail_nutrisi_item_terpilih(app):
    app = kirim(app)
    pilihan = app.selectbox(key="in_detail")
    assert len(pilihan.options) == 9
    id_pertama = int(app.session_state["aplikasi"].tampilkan_rekomendasi()
                     ["menu"]["sarapan"]["tabel"].iloc[0]["id_makanan"])
    app = pilihan.set_value(id_pertama).run()
    html = teks_markdown(app)
    assert "Kandungan gizi" in html and "Per 100 g" in html and "Kode TKPI" in html


def test_data_baru_menggantikan_hasil(app):
    app = kirim(app)
    app = kirim(app, usia="30", jk="pria", berat="70", tinggi="170", aktivitas="menetap")
    assert jumlah_baris(app.db_path, "sesi_pengguna") == 2
    assert "Sama dengan TEE" in teks_markdown(app)


def test_basis_data_tidak_ada_menampilkan_petunjuk(tmp_path, monkeypatch):
    monkeypatch.setenv("SKRIPSI_DB_PATH", str(tmp_path / "tidak_ada.db"))
    at = AppTest.from_file(JALUR_APP, default_timeout=TIMEOUT).run()
    assert not at.exception
    assert any("Basis data tidak ditemukan" in e.value and "setup_db.py" in e.value for e in at.error)
    assert not at.button                      # halaman berhenti sebelum formulir