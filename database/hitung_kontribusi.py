import pandas as pd

# Berat hidangan acuan satu porsi (gram) menurut pedoman
BERAT_ACUAN = {'pokok': 100, 'lauk': 40, 'sayur': 100}
PERAN = ['pokok', 'lauk', 'sayur']
ZAT = ['protein', 'lemak', 'karbohidrat']

# 1. Baca data TKPI 
data_makanan = pd.read_csv('data_makanan.csv')

# Filter data hanya untuk bahan yang memiliki peran pokok, lauk, dan sayur
data = data_makanan[data_makanan['peran_menu'].isin(PERAN)]

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

# Mengubah baris menjadi kolom (transpose)
tabel_transpose = tabel.T

# 6. Simpan output ke dalam file
# Opsi A: Simpan sebagai file CSV agar mudah dirapikan/dikopi di Excel atau Google Sheets
tabel_transpose.to_csv('hasil_kontribusi.csv')

# Opsi B: Simpan sebagai file TXT agar format spasinya persis seperti di terminal
with open('hasil_kontribusi.txt', 'w') as f:
    f.write("=== TABEL RATA-RATA DAN KONTRIBUSI ===\n\n")
    f.write(tabel_transpose.to_string())
    f.write("\n\n\n=== PENGECEKAN JUMLAH KONTRIBUSI (HARUS 100) ===\n\n")
    f.write(kontribusi.sum().round(1).to_string())

print("Proses selesai! Silakan buka file 'hasil_kontribusi.csv' atau 'hasil_kontribusi.txt' di folder yang sama.")