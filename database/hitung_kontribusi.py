import pandas as pd

import kurasi_makanan  # kurasi bahan siap makan (K0-K6), satu folder dengan berkas ini

# Berat hidangan acuan satu porsi (gram) menurut pedoman
BERAT_ACUAN = {'pokok': 100, 'lauk': 40, 'sayur': 100}
PERAN = ['pokok', 'lauk', 'sayur']
ZAT = ['protein', 'lemak', 'karbohidrat']

# 1. Baca data TKPI dan terapkan kurasi: hanya bahan pokok/lauk/sayur yang siap makan
#    (sama persis dengan isi tabel makanan pada rekomendasi_makanan.db)
data = kurasi_makanan.ambil_siap_makan('data_makanan.csv')

# 2. Rata-rata kandungan gizi per 100 g pada setiap peran (x bar)
rata = data.groupby('peran_menu')[ZAT].mean().loc[PERAN]
jumlah = data.groupby('peran_menu').size().loc[PERAN]

# 3. Kandungan gizi hidangan acuan = rata-rata per 100 g x berat acuan / 100
isi_acuan = rata.copy()
for r in PERAN:
    isi_acuan.loc[r] = rata.loc[r] * BERAT_ACUAN[r] / 100

# 4. Kontribusi peran = bagian peran dari total ketiga peran (rumus 10), dalam persen
kontribusi = (isi_acuan / isi_acuan.sum() * 100)

# 5. Format hasil
tabel = pd.DataFrame({
    'Jumlah bahan': jumlah,
    'Rata-rata Protein (g/100 g)': rata['protein'],
    'Rata-rata Lemak (g/100 g)': rata['lemak'],
    'Rata-rata Karbohidrat (g/100 g)': rata['karbohidrat'],
    'Kontribusi Protein (%)': kontribusi['protein'],
    'Kontribusi Lemak (%)': kontribusi['lemak'],
    'Kontribusi Karbohidrat (%)': kontribusi['karbohidrat'],
}).round(2)

tabel_transpose = tabel.T
tabel_transpose.to_csv('hasil_kontribusi.csv')

with open('hasil_kontribusi.txt', 'w') as f:
    f.write("=== TABEL RATA-RATA DAN KONTRIBUSI ===\n\n")
    f.write(tabel_transpose.to_string())
    f.write("\n\n\n=== PENGECEKAN JUMLAH KONTRIBUSI (HARUS 100) ===\n\n")
    f.write(kontribusi.sum().round(1).to_string())

print("Proses selesai! Silakan buka file 'hasil_kontribusi.csv' atau 'hasil_kontribusi.txt' di folder yang sama.")