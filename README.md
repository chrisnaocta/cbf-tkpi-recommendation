# Sistem Rekomendasi Menu Makanan Harian Berbasis Content-Based Filtering dan TKPI 2020

## Tentang Penulis

Repositori ini disusun oleh Chrisna Octavianus (NIM 32230110), mahasiswa Program Studi Informatika, Fakultas Teknik dan Desain, Universitas Bunda Mulia, Jakarta.

## Tentang Penelitian

Repositori ini memuat kode program dan data dari skripsi berjudul **"Penerapan Content-Based Filtering pada Sistem Rekomendasi Makanan Harian untuk Risiko Obesitas Karyawan Berbasis TKPI"**. Penelitian ini merupakan penelitian perekayasaan yang dikembangkan dengan model Waterfall, dan disusun sebagai salah satu syarat untuk memperoleh gelar Sarjana.

## Tujuan Sistem

Sistem ini merupakan aplikasi web yang dijalankan secara lokal untuk membantu karyawan berusia 19 sampai 49 tahun menyusun menu makanan harian sebagai upaya mengurangi risiko obesitas. Pengguna cukup mengisi lima data diri, yaitu usia, jenis kelamin, berat badan, tinggi badan, dan tingkat aktivitas fisik, tanpa membuat akun. Sistem kemudian:

1. menghitung Indeks Massa Tubuh (IMT), Basal Metabolic Rate (BMR), kebutuhan energi total, serta target energi, protein, lemak, dan karbohidrat harian;
2. membagi target tersebut ke tiga waktu makan (sarapan, makan siang, dan makan malam);
3. menyusun menu untuk setiap waktu makan yang terdiri atas satu makanan pokok, satu lauk, dan satu sayur, lengkap dengan berat tiap hidangan dalam gram.

Hasil perhitungan bersifat sebagai acuan awal dan tidak menggantikan saran tenaga kesehatan.

## Fitur

- Formulir lima data diri beserta validasi masukan.
- Tampilan hasil perhitungan IMT, kategori berat badan, BMR, dan target gizi.
- Menu harian per waktu makan beserta persentase pemenuhan terhadap target.
- Detail kandungan gizi setiap bahan yang direkomendasikan.
- Tombol "Minta Ulang" untuk memperoleh menu alternatif dengan target gizi yang sama.
- Penyimpanan sesi dan riwayat rekomendasi ke basis data SQLite.

## Metode

Rekomendasi disusun dengan metode Content-Based Filtering. Setiap bahan dibandingkan dengan target gizi pada peran menunya (pokok, lauk, atau sayur) menggunakan K-Nearest Neighbor (K = 5, `NearestNeighbors` dengan metrik cosine dan algoritma brute). Dari 5 kandidat tiap peran terbentuk 125 kombinasi per waktu makan. Berat tiap hidangan ditentukan dengan kuadrat terkecil berbatas (`scipy.optimize.lsq_linear`) lalu dibulatkan ke kelipatan 5 gram. Kombinasi yang dipilih adalah kombinasi dengan keempat zat gizi (energi, protein, lemak, karbohidrat) berada pada rentang 90 sampai 110 persen dari target dan memiliki rata-rata kemiripan tertinggi.

Rumus (1) sampai (13) yang dipakai diuraikan pada Subbab 3.3.3 skripsi. Rumus (1) sampai (9) berada pada kelas `KalkulatorGizi`, dan rumus (10) sampai (13) berada pada kelas `MesinRekomendasi`.

## Data

Data gizi bersumber dari Tabel Komposisi Pangan Indonesia (TKPI) 2020 yang diterbitkan oleh Kementerian Kesehatan Republik Indonesia. Sebanyak 1.146 bahan didigitalisasi ke `database/data_makanan.csv`. Bahan kemudian disaring dengan kriteria K0 sampai K6 (Subbab 3.3.3 skripsi, diimplementasikan pada `database/kurasi_makanan.py`) sehingga tersisa 256 bahan siap makan, yaitu 44 makanan pokok, 154 lauk, dan 58 sayur. Hasil keputusan penyaringan setiap bahan tercatat pada `database/kurasi_makanan.csv`.

## Teknologi

| Komponen | Versi |
|---|---|
| Python | 3.15 |
| Streamlit | 1.66 |
| pandas | 3.1 |
| NumPy | 2.5 |
| scikit-learn | 1.9 |
| SciPy | 1.18 |
| SQLite (modul `sqlite3`) | bawaan Python |
| pytest | 9.2 |

## Struktur Folder

```
website/
├── app.py                    Antarmuka Streamlit
├── aplikasi_utama.py         Kelas AplikasiUtama
├── kalkulator_gizi.py        Kelas KalkulatorGizi (rumus 1 sampai 9)
├── mesin_rekomendasi.py      Kelas MesinRekomendasi (rumus 10 sampai 13)
├── repositori_makanan.py     Kelas RepositoriMakanan
├── koneksi_database.py       Kelas KoneksiDatabase
├── sesi_pengguna.py          Kelas SesiPengguna
├── requirements.txt          Daftar pustaka
├── pytest.ini                Konfigurasi pengujian
├── .streamlit/               Konfigurasi tampilan
├── database/                 Data, penyaringan, dan skrip basis data
│   ├── data_makanan.csv
│   ├── kurasi_makanan.py
│   ├── kurasi_makanan.csv
│   ├── hitung_kontribusi.py
│   ├── hasil_kontribusi.txt
│   ├── setup_db.py
│   └── rekomendasi_makanan.db
└── tests/                    Pengujian unit (pytest)
```

## Cara Menjalankan

Perintah berikut ditulis untuk Windows PowerShell.

1. Buat dan aktifkan lingkungan virtual, lalu pasang pustaka.

   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Siapkan basis data. Langkah ini hanya diperlukan bila berkas `database/rekomendasi_makanan.db` belum ada. Perintah dijalankan dari folder `database`.

   ```
   cd database
   python setup_db.py
   cd ..
   ```

   Skrip membatalkan impor bila tabel `makanan` sudah terisi. Untuk membuat ulang basis data, hapus berkas `rekomendasi_makanan.db` terlebih dahulu.

3. Jalankan aplikasi dari folder utama, lalu buka alamat lokal yang tampil pada terminal melalui peramban.

   ```
   streamlit run app.py
   ```

Perhitungan tidak membutuhkan sambungan internet. Sambungan hanya dipakai untuk memuat jenis huruf dari Google Fonts, dan bila tidak tersedia, peramban memakai huruf bawaan.

## Pengujian

Pengujian unit dijalankan dari folder utama dengan perintah berikut.

```
pytest
```

Pengujian fungsional sistem dilakukan dengan metode black box (teknik equivalence partitioning) sesuai Tabel 3.2 skripsi, dan hasilnya diuraikan pada BAB 4.

## Keterbatasan

- Sistem hanya melayani pengguna berusia 19 sampai 49 tahun dan hanya menyusun menu untuk satu hari. Perencanaan mingguan atau bulanan berada di luar cakupan.
- Parameter gizi dibatasi pada energi, protein, lemak, dan karbohidrat.
- Pengguna dengan IMT di bawah 18,5 hanya mendapat catatan, dan target energinya tidak ditambah.
- Tidak semua bahan pada 256 bahan hasil penyaringan lazim disajikan sebagai menu harian, sehingga sebagian menu dapat terasa tidak biasa.
- Nilai gizi TKPI dipakai apa adanya. Pada sebagian bahan, nilai energi pada TKPI tidak sama dengan energi hasil perhitungan faktor Atwater.
- Sistem dirancang berjalan secara lokal dan tidak mencakup penyebaran daring.