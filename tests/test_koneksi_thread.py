"""Koneksi harus dapat dipakai dari thread lain (Streamlit memakai thread baru per interaksi)."""

import threading


def test_koneksi_dapat_dipakai_dari_thread_lain(koneksi):
    koneksi.connect()                     # dibuat di thread tes
    hasil = {}

    def kerja():
        try:
            hasil["n"] = koneksi.execute_query("SELECT COUNT(*) AS n FROM makanan")["n"][0]
        except Exception as galat:        # noqa: BLE001
            hasil["galat"] = galat

    t = threading.Thread(target=kerja)
    t.start()
    t.join()
    assert "galat" not in hasil, hasil.get("galat")
    assert hasil["n"] == 257   # bahan siap makan hasil kurasi