import sqlite3
import pandas as pd

import kurasi_makanan

# Nama file database SQLite yang akan dibuat secara otomatis (lokal)
DB_NAME = 'rekomendasi_makanan.db'

def create_tables():
    # Membuka koneksi ke SQLite (file akan dibuat jika belum ada)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Membuat Tabel MAKANAN (Telah disesuaikan dengan kolom peran_menu)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS makanan (
        id_makanan INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_tkpi TEXT,
        nama_bahan TEXT,
        kategori TEXT,
        energi REAL,
        protein REAL,
        lemak REAL,
        karbohidrat REAL,
        peran_menu TEXT
    )
    ''')

    # 2. Membuat Tabel SESI_PENGGUNA
    # Waktu memakai waktu lokal komputer (datetime('now', 'localtime')), bukan UTC.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sesi_pengguna (
        id_sesi INTEGER PRIMARY KEY AUTOINCREMENT,
        usia INTEGER,
        jenis_kelamin TEXT,
        berat_badan REAL,
        tinggi_badan REAL,
        tingkat_aktivitas TEXT,
        imt REAL,
        bmr REAL,
        target_energi REAL,
        target_protein REAL,
        target_lemak REAL,
        target_karbohidrat REAL,
        waktu_input DATETIME DEFAULT (datetime('now', 'localtime'))
    )
    ''')

    # 3. Membuat Tabel RIWAYAT_REKOMENDASI
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS riwayat_rekomendasi (
        id_rekomendasi INTEGER PRIMARY KEY AUTOINCREMENT,
        id_sesi INTEGER,
        id_makanan INTEGER,
        jenis_waktu_makan TEXT,
        skor_similarity REAL,
        waktu_rekomendasi DATETIME DEFAULT (datetime('now', 'localtime')),
        porsi_gram REAL,
        FOREIGN KEY(id_sesi) REFERENCES sesi_pengguna(id_sesi),
        FOREIGN KEY(id_makanan) REFERENCES makanan(id_makanan)
    )
    ''')

    conn.commit()
    conn.close()
    print("Database SQLite dan ketiga tabel (makanan, sesi_pengguna, riwayat_rekomendasi) berhasil dibuat!")

def import_csv_to_db(csv_filename):
    """
    Memasukkan bahan siap makan dari CSV TKPI ke tabel 'makanan'.

    Penyaringan dilakukan oleh kurasi_makanan.py: hanya bahan berperan pokok, lauk,
    atau sayur yang siap dimakan langsung (kriteria K0-K6 pada kurasi_makanan.py)
    yang dimasukkan. Fungsi ini hanya mengisi tabel makanan bila tabelnya masih
    kosong, sehingga menjalankan setup_db.py dua kali tidak menggandakan data.
    """
    conn = None
    try:
        # Membaca CSV lalu menerapkan kurasi (pemeriksaan data ada di kurasi_makanan.py)
        hasil = kurasi_makanan.baca_dan_kurasi(csv_filename)
        df = kurasi_makanan.ambil_siap_makan(csv_filename)
        if df.empty:
            raise ValueError("Tidak ada bahan yang lolos kurasi.")

        conn = sqlite3.connect(DB_NAME)
        sudah_ada = conn.execute("SELECT COUNT(*) FROM makanan").fetchone()[0]
        if sudah_ada > 0:
            print(f"Tabel makanan sudah berisi {sudah_ada} baris; impor dibatalkan agar data tidak dobel.")
            print("Untuk mengulang dari awal, hapus berkas basis data lalu jalankan setup_db.py lagi.")
            return

        # Memasukkan data ke SQLite (tanpa menyertakan index pandas)
        df.to_sql('makanan', conn, if_exists='append', index=False)

        print(f"Data dari {csv_filename} berhasil diimpor ke tabel makanan!")
        print(f"Total baris pada CSV awal: {len(hasil)}")
        print(f"Total baris yang dimasukkan ke database (siap makan, pokok/lauk/sayur): {len(df)}")
        print(df['peran_menu'].value_counts().to_string())

    except Exception as e:
        print("Terjadi kesalahan saat impor CSV:", e)
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    # 1. Jalankan pembuatan tabel
    create_tables()

    # 2. Jalankan impor data
    # Pastikan data yang kamu cantumkan sudah disimpan dalam file 'data_makanan.csv'
    import_csv_to_db('data_makanan.csv')