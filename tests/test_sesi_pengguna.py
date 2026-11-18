"""Tes SesiPengguna dan RepositoriMakanan.simpan_sesi_pengguna."""

import math

import pytest

from sesi_pengguna import SesiPengguna, kumpulkan_id_makanan

SESI_CONTOH = {
    "usia": 30, "jenis_kelamin": "pria", "berat_badan": 70.0, "tinggi_badan": 170.0,
    "tingkat_aktivitas": "menetap", "imt": 24.22, "bmr": 1617.5,
    "target_energi": 2507.1, "target_protein": 94.0, "target_lemak": 69.6, "target_karbohidrat": 376.1,
}


def rekomendasi_palsu(ids):
    """Rekomendasi minimal: 9 id dibagi ke 3 waktu makan x 3 peran."""
    a = iter(ids)
    return {"menu": {
        w: {"item": {p: {"id_makanan": next(a)} for p in ("pokok", "lauk", "sayur")}}
        for w in ("sarapan", "siang", "malam")
    }}


# ---------------------------------------------------------------------------
# SesiPengguna
# ---------------------------------------------------------------------------
def test_kumpulkan_id_urut_dan_kosong():
    assert kumpulkan_id_makanan(rekomendasi_palsu(range(1, 10))) == list(range(1, 10))
    assert kumpulkan_id_makanan({}) == []


def test_sesi_baru_belum_aktif():
    s = SesiPengguna()
    assert not s.aktif and s.id_sesi is None
    assert s.profil == {} and s.rekomendasi_saat_ini == {} and s.item_sebelumnya == []


def test_simpan_profil_mengaktifkan_dan_menyalin():
    s = SesiPengguna()
    profil = {"usia": 30}
    s.simpan_profil(profil, {"imt": 24.0}, 7)
    profil["usia"] = 99                      # perubahan di luar tidak boleh menembus sesi
    assert s.aktif and s.id_sesi == 7 and s.profil == {"usia": 30}


@pytest.mark.parametrize("id_sesi", [None, "1", 1.5, True])
def test_id_sesi_tidak_valid_ditolak(id_sesi):
    with pytest.raises(ValueError):
        SesiPengguna().simpan_profil({}, {}, id_sesi)


def test_update_rekomendasi_memindahkan_item_ke_sebelumnya():
    s = SesiPengguna()
    s.simpan_profil({}, {}, 1)
    pertama, kedua, ketiga = (rekomendasi_palsu(range(i, i + 9)) for i in (1, 10, 19))
    s.update_rekomendasi(pertama)
    assert s.item_sebelumnya == []                       # rekomendasi pertama
    s.update_rekomendasi(kedua)
    assert s.item_sebelumnya == list(range(1, 10))       # item rekomendasi pertama
    s.update_rekomendasi(ketiga)
    assert s.item_sebelumnya == list(range(10, 19))      # hanya satu rekomendasi sebelumnya
    assert kumpulkan_id_makanan(s.rekomendasi_saat_ini) == list(range(19, 28))


def test_simpan_profil_baru_mengosongkan_rekomendasi():
    s = SesiPengguna()
    s.simpan_profil({}, {}, 1)
    s.update_rekomendasi(rekomendasi_palsu(range(1, 10)))
    s.update_rekomendasi(rekomendasi_palsu(range(10, 19)))
    s.simpan_profil({}, {}, 2)
    assert s.rekomendasi_saat_ini == {} and s.item_sebelumnya == [] and s.id_sesi == 2


# ---------------------------------------------------------------------------
# RepositoriMakanan.simpan_sesi_pengguna
# ---------------------------------------------------------------------------
def test_simpan_sesi_mengembalikan_id_dan_menyimpan_semua_kolom(repositori, koneksi):
    id_baru = repositori.simpan_sesi_pengguna(SESI_CONTOH)
    assert isinstance(id_baru, int)
    df = koneksi.execute_query("SELECT * FROM sesi_pengguna WHERE id_sesi = ?", (id_baru,))
    baris = df.iloc[0]
    for kolom, nilai in SESI_CONTOH.items():
        assert baris[kolom] == nilai
    assert df["waktu_input"].notna().all()


def test_id_sesi_bertambah_dan_bisa_dipakai_riwayat(repositori, koneksi):
    a = repositori.simpan_sesi_pengguna(SESI_CONTOH)
    b = repositori.simpan_sesi_pengguna(SESI_CONTOH)
    assert b == a + 1
    repositori.simpan_riwayat_rekomendasi([{
        "id_sesi": b, "id_makanan": 22, "jenis_waktu_makan": "siang",
        "skor_similarity": 0.9, "porsi_gram": 100.0,
    }])
    assert koneksi.execute_query("SELECT COUNT(*) AS n FROM riwayat_rekomendasi")["n"][0] == 1


def test_kolom_sesi_kurang_ditolak(repositori, koneksi):
    data = dict(SESI_CONTOH)
    del data["bmr"]
    with pytest.raises(ValueError, match="bmr"):
        repositori.simpan_sesi_pengguna(data)
    assert koneksi.execute_query("SELECT COUNT(*) AS n FROM sesi_pengguna")["n"][0] == 0


@pytest.mark.parametrize("kolom", ["imt", "bmr", "target_energi", "berat_badan"])
@pytest.mark.parametrize("nilai", [math.nan, math.inf])
def test_nilai_tidak_berhingga_ditolak(repositori, koneksi, kolom, nilai):
    with pytest.raises(ValueError):
        repositori.simpan_sesi_pengguna({**SESI_CONTOH, kolom: nilai})
    assert koneksi.execute_query("SELECT COUNT(*) AS n FROM sesi_pengguna")["n"][0] == 0