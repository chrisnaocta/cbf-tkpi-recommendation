import sqlite3
import pandas as pd

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
    Fungsi untuk memasukkan data dari CSV ke dalam tabel 'makanan'.
    Hanya memasukkan baris dengan peran_menu: 'pokok', 'lauk', atau 'sayur'.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        
        # Membaca CSV menggunakan pandas
        df = pd.read_csv(csv_filename)
        
        # Menyaring (filter) dataframe berdasarkan peran_menu yang diinginkan
        peran_valid = ['pokok', 'lauk', 'sayur']
        df_filtered = df[df['peran_menu'].isin(peran_valid)]
        
        # Memasukkan data ke SQLite (tanpa menyertakan index pandas)
        # Menggunakan if_exists='append' agar data ditambahkan ke tabel yang sudah ada
        df_filtered.to_sql('makanan', conn, if_exists='append', index=False)
        conn.close()
        
        print(f"Data dari {csv_filename} berhasil diimpor ke tabel makanan!")
        print(f"Total baris pada CSV awal: {len(df)}")
        print(f"Total baris yang dimasukkan ke database (hanya pokok/lauk/sayur): {len(df_filtered)}")
        
    except Exception as e:
        print("Terjadi kesalahan saat impor CSV:", e)

if __name__ == "__main__":
    # 1. Jalankan pembuatan tabel
    create_tables()
    
    # 2. Jalankan impor data
    # Pastikan data yang kamu cantumkan sudah disimpan dalam file 'data_makanan.csv'
    import_csv_to_db('data_makanan.csv')