import sqlite3
import pandas as pd

# Nama file database SQLite yang akan dibuat secara otomatis (lokal)
DB_NAME = 'rekomendasi_makanan.db'

def create_tables():
    # Membuka koneksi ke SQLite (file akan dibuat jika belum ada)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Membuat Tabel MAKANAN
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS makanan (
        id_makanan INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_tkpi TEXT,
        nama_bahan TEXT,
        kategori TEXT,
        energi REAL,
        protein REAL,
        lemak REAL,
        karbohidrat REAL
    )
    ''')

    # 2. Membuat Tabel SESI_PENGGUNA
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
        waktu_input DATETIME DEFAULT CURRENT_TIMESTAMP
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
        waktu_rekomendasi DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(id_sesi) REFERENCES sesi_pengguna(id_sesi),
        FOREIGN KEY(id_makanan) REFERENCES makanan(id_makanan)
    )
    ''')

    conn.commit()
    conn.close()
    print("Database SQLite dan ketiga tabel (makanan, sesi_pengguna, riwayat_rekomendasi) berhasil dibuat!")

def import_csv_to_db(csv_filename):
    """
    Fungsi ini akan kita jalankan nanti setelah file CSV TKPI sudah siap.
    Fungsinya untuk memasukkan data dari CSV ke dalam tabel 'makanan'.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        # Membaca CSV menggunakan pandas
        df = pd.read_csv(csv_filename)
        # Memasukkan data ke SQLite (tanpa menyertakan index pandas)
        df.to_sql('makanan', conn, if_exists='append', index=False)
        conn.close()
        print(f"Data dari {csv_filename} berhasil diimpor ke tabel makanan!")
    except Exception as e:
        print("Terjadi kesalahan saat impor CSV:", e)

if __name__ == "__main__":
    # Jalankan pembuatan tabel
    create_tables()