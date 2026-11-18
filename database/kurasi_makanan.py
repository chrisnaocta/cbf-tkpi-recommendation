"""
kurasi_makanan.py

Kurasi pool bahan makanan: memilih bahan TKPI yang siap dimakan langsung.

Kriteria "siap makan" diturunkan dari sistem pengkodean dan penamaan TKPI 2020,
bukan dari penilaian penulis:
  K0  Peran menu bukan pokok, lauk, atau sayur -> tidak dipakai (sama dengan
      penyaringan peran pada setup_db.py).
  K1  Alfabet kedua kode TKPI = "R" (bahan mentah/segar) -> keluar.
  K2  Nama bahan memuat "mentah" -> keluar.
  K3  Alfabet kedua = "P" (olahan) dan nama memuat keterangan pemasakan
      (rebus, kukus, bakar, goreng, panggang, masakan, matang, presto, pepes,
      tumis, seduh, asap) -> masuk.
  K4  Alfabet kedua = "P" dan nama memuat "kering", "tepung", atau "bubuk"
      (tanpa keterangan pemasakan) -> keluar, karena berupa bahan baku.
  K5  Alfabet kedua = "P" tanpa keterangan apa pun pada nama -> ditinjau satu
      per satu; keputusan dan alasannya dicatat pada KEPUTUSAN_TINJAUAN di bawah.

  K6  Pengecualian oleh peneliti: bahan berasal dari anjing, tikus, penyu,
      kelelawar, atau babi (termasuk produk olahannya) -> keluar. Ini keputusan
      peneliti dan BUKAN berasal dari TKPI; daftar kodenya ada pada
      KODE_DIKECUALIKAN_PENELITI di bawah.

Prinsip pada K5: bila dari nama dan kode TKPI tidak dapat dipastikan bahwa bahan
itu sudah siap dimakan, bahan dikeluarkan (tidak merekomendasikan bahan yang
belum matang). Daftar K5 dapat diubah oleh peneliti; setiap perubahan tercatat
pada berkas kurasi_makanan.csv yang dihasilkan modul ini.

Kriteria "umum dimakan karyawan di Jakarta" tidak diterapkan. Pengguna dapat
meminta menu lain lewat tombol "Minta Ulang".

Jalankan dari folder database:  python kurasi_makanan.py
"""

import re

import pandas as pd

# ---------------------------------------------------------------------------
# Konstanta kriteria
# ---------------------------------------------------------------------------
PERAN_DIPAKAI = ["pokok", "lauk", "sayur"]
HURUF_MENTAH = "R"  # alfabet kedua kode TKPI: mentah/segar
HURUF_OLAHAN = "P"  # alfabet kedua kode TKPI: olahan/proses

POLA_MENTAH = r"mentah"
POLA_MASAK = (
    r"rebus|kukus|bakar|goreng|panggang|masakan|matang|presto|pepes|tumis|seduh|asap"
)
POLA_BAHAN_BAKU = r"kering|tepung|bubuk"

KEPUTUSAN_MASUK = "masuk"
KEPUTUSAN_KELUAR = "keluar"

# Nama berkas
BERKAS_SUMBER = "data_makanan.csv"
BERKAS_KURASI = "kurasi_makanan.csv"

# ---------------------------------------------------------------------------
# K6: pengecualian oleh peneliti (kode TKPI -> jenis hewan asal bahan).
# Keputusan peneliti, bukan dari TKPI. Hanya bahan yang lolos K0-K5 yang terdampak.
# ---------------------------------------------------------------------------
KODE_DIKECUALIKAN_PENELITI = {
    "FP063": "anjing",     # RW, anjing, masakan
    "FP087": "tikus",      # Tikus rica, masakan
    "FP054": "penyu",      # Lawar penyu, masakan
    "FP064": "penyu",      # Sate, penyu, masakan
    "FP066": "penyu",      # Penyu, serapah, masakan
    "FP059": "kelelawar",  # Paniki masak santan, masakan
    "FP035": "babi",       # Babi hutan masak rica, masakan
    "FP053": "babi",       # Lawar babi, masakan
    "FP005": "babi",       # Ham (produk olahan daging babi)
}

# ---------------------------------------------------------------------------
# K5: keputusan tinjauan untuk bahan olahan (P) tanpa keterangan pada nama.
# Bentuk: kelompok -> (keputusan, alasan, [kode_tkpi, ...])
# ---------------------------------------------------------------------------
KEPUTUSAN_TINJAUAN = {
    "masuk_hidangan": (
        "masuk",
        "Hidangan atau makanan jadi yang lazim langsung dimakan",
        [
            "AP001",  # Nasi
            "AP002",  # Nasi tim
            "AP005",  # Nasi beras merah
            "AP014",  # Ketupat ketan
            "AP021",  # Mi basah
            "AP024",  # Roti putih
            "AP031",  # Bakwan
            "AP040",  # Bubur tinotuan (Manado)
            "AP041",  # Cake tape
            "AP048",  # Gemblong
            "AP051",  # Jagung gerontol
            "AP061",  # Ketupat kandangan
            "AP085",  # Mie ayam
            "AP086",  # Mie bakso
            "AP087",  # Mie celon
            "AP088",  # Mie pangsit basah
            "AP089",  # Nasi gemuk
            "AP090",  # Nasi gurih
            "AP091",  # Nasi minyak
            "AP092",  # Nasi rames
            "AP098",  # Pundut nasi
            "AP106",  # Spaghetti
            "BP023",  # Bubur sagu
            "BP032",  # Kapurung
            "BP075",  # Ubi cilembu
            "CP058",  # Sayur lebui
            "CP063",  # Tahu telur
            "FP005",  # Ham
            "FP011",  # Sapi, abon
            "FP012",  # Sapi, abon, asli
            "FP015",  # Sapi, daging, kornet
            "FP016",  # Sapi, daging, sosis (Worst)
            "FP017",  # Sapi, hati, sosis (liverworst)
            "FP036",  # Beef burger
            "FP039",  # Brongkos
            "FP047",  # Gulai kambing
            "GP049",  # Sardines dalam kaleng
            "GP053",  # Abon haruwan
            "GP054",  # Abon ikan
            "GP061",  # Fillet o-fish
            "GP073",  # Lawara penjah
            "GP090",  # Sate bandeng
            "DP023",  # Anyang, sayur
            "DP024",  # Ares, sayur
            "DP025",  # Arwan sirsir
            "DP026",  # Beberuk
            "DP027",  # Botok lamtoro
            "DP028",  # Buntil daun talas
            "DP029",  # Cammetutu
            "DP030",  # Cap cai, sayur
            "DP031",  # Gado-gado
            "DP032",  # Gudeg, sayur
            "DP033",  # Gulai pakis
            "DP034",  # Gulai pliek
            "DP035",  # Kadada katembe
            "DP036",  # Kaparende, sayur
            "DP037",  # Karedok, sayur
            "DP039",  # Kotiu hinela tawang nggole
            "DP040",  # Lema/rebung asam
            "DP041",  # Lilin bungkus gedi
            "DP042",  # Olah-olah
            "DP043",  # Paku hinela wulelenggapaya
            "DP044",  # Pelecing kangkung
            "DP045",  # Purundawa
            "DP047",  # Sayur asem
            "DP048",  # Sayur bunga pepaya
            "DP049",  # Sayur garu
            "DP050",  # Sayur kohu-kohu
            "DP051",  # Sayur lilin-terubuk
            "DP052",  # Sayur ndusuk
            "DP053",  # Sayur sop
            "DP054",  # Sayur umbut kelapa
            "DP055",  # Sayur umbut rotan
            "DP056",  # Shabu-shabu
            "DP057",  # Semur jengkol
            "DP058",  # Tinira ninahu nggaluku
            "DP060",  # Waluh balamak
            "DP061",  # Woku ubi
        ],
    ),
    "keluar_bahan_baku": (
        "keluar",
        "Bahan baku atau olahan setengah jadi (nilai energi setara bentuk kering), masih perlu diolah",
        [
            "AP009",  # Nasi jagung
            "AP023",  # Misoa
            "AP052",  # Jagung titi
            "BP019",  # Beras Cerdas
            "BP020",  # Beras ganyong
            "BP021",  # Beras Siger
            "BP049",  # Mi golosor
            "BP050",  # Mie bendo
            "BP051",  # Mie sagu
            "BP053",  # Oyek
            "BP055",  # Rasbi (beras ubi)
            "BP056",  # Rasi (beras singkong)
            "BP057",  # Sagu fomo
            "BP059",  # Sagu manis
            "BP060",  # Sagu rendang
            "BP061",  # Sagu sinole
        ],
    ),
    "keluar_tidak_jelas": (
        "keluar",
        "Bentuk atau jenis bahan tidak dapat dipastikan dari namanya, sehingga tidak dianggap siap makan",
        [
            "BP022",  # Biji nangka/Biji salak
            "CP033",  # Kacang negara
            "CP050",  # Moon tahu
            "GP085",  # Pinda
            "CP019",  # Pepea oncom ampas tahu
        ],
    ),
    "keluar_hasil_samping": (
        "keluar",
        "Ampas atau bungkil hasil samping pengolahan, bukan makanan jadi",
        [
            "CP015",  # Ampas kacang hijau
            "CP020",  # Bungkil biji karet
            "CP021",  # Bungkil kacang tanah
            "CP022",  # Bungkil kelapa
        ],
    ),
    "keluar_bumbu_selai_camilan": (
        "keluar",
        "Bumbu, selai, atau camilan; bukan lauk yang dimakan sebagai hidangan utama",
        [
            "CP035",  # Kacang tanah sari
            "CP036",  # Keju kacang tanah (peanut butter)
            "CP045",  # Kerupuk tempe abadi prima
            "FP007",  # Kerupuk urat
            "CP065",  # Tauco
            "CP066",  # Tauco cap beruang, cake
            "CP067",  # Tauco cap DAS, cake
            "CP068",  # Tauco cap meong
            "CP069",  # Tauji cap singa
        ],
    ),
    "keluar_minuman": (
        "keluar",
        "Minuman, bukan lauk",
        [
            "CP060",  # Susu kedelai
        ],
    ),
    "keluar_bentuk_mentah": (
        "keluar",
        "Bentuk belum dimasak; versi matangnya tercatat pada baris TKPI lain (goreng/rebus/pepes)",
        [
            "CP037",  # Kembang tahu
            "CP051",  # Oncom
            "CP052",  # Oncom ampas kacang hijau
            "CP053",  # Oncom kacang hijau + singkong
            "CP064",  # Takwa
            "CP070",  # Tempe bongkrek
            "CP071",  # Tempe gembus P3G
            "CP072",  # Tempe gembus yogya
            "CP073",  # Tempe kacang babi
            "CP074",  # Tempe kacang belimbing
            "CP075",  # Tempe kedelai + jagung
            "CP078",  # Tempe koro benguk
            "CP079",  # Tempe lamtoro
            "CP080",  # Tempe lamtoro var. gung dengan kulit
            "CP081",  # Tempe lamtoro var. gung tanpa kulit
            "CP082",  # Tempe pasar
            "GP015",  # Ikan katombo, asin
        ],
    ),
}


def _peta_tinjauan():
    """Membalik KEPUTUSAN_TINJAUAN menjadi {kode_tkpi: (keputusan, alasan)}."""
    peta = {}
    for keputusan, alasan, daftar_kode in KEPUTUSAN_TINJAUAN.values():
        for kode in daftar_kode:
            if kode in peta:
                raise ValueError(f"Kode {kode} muncul lebih dari sekali pada KEPUTUSAN_TINJAUAN.")
            peta[kode] = (keputusan, alasan)
    return peta


def _putuskan_baris(baris, peta_tinjauan):
    """Mengembalikan (keputusan, dasar, alasan) untuk satu baris CSV."""
    if baris["peran_menu"] not in PERAN_DIPAKAI:
        return KEPUTUSAN_KELUAR, "K0", "Peran menu bukan pokok, lauk, atau sayur"

    if baris["kode_tkpi"] in KODE_DIKECUALIKAN_PENELITI:
        jenis = KODE_DIKECUALIKAN_PENELITI[baris["kode_tkpi"]]
        return (
            KEPUTUSAN_KELUAR, "K6",
            f"Dikecualikan atas keputusan peneliti (bahan berasal dari {jenis})",
        )

    nama = str(baris["nama_bahan"]).lower()
    huruf = str(baris["kode_tkpi"])[1]

    if huruf == HURUF_MENTAH:
        return KEPUTUSAN_KELUAR, "K1", "Kode TKPI berhuruf R (bahan mentah/segar)"
    if re.search(POLA_MENTAH, nama):
        return KEPUTUSAN_KELUAR, "K2", 'Nama bahan memuat "mentah"'
    if huruf != HURUF_OLAHAN:
        raise ValueError(f"Alfabet kedua kode {baris['kode_tkpi']} bukan R atau P.")
    if re.search(POLA_MASAK, nama):
        return KEPUTUSAN_MASUK, "K3", "Olahan dengan keterangan pemasakan pada nama"
    if re.search(POLA_BAHAN_BAKU, nama):
        return KEPUTUSAN_KELUAR, "K4", 'Olahan berupa bahan baku (nama memuat kering/tepung/bubuk)'

    kode = baris["kode_tkpi"]
    if kode not in peta_tinjauan:
        raise ValueError(
            f"{kode} ({baris['nama_bahan']}) belum diputuskan: tambahkan ke "
            "KEPUTUSAN_TINJAUAN."
        )
    keputusan, alasan = peta_tinjauan[kode]
    return keputusan, "K5", alasan


def kurasi(df):
    """Menambahkan kolom keputusan, dasar, dan alasan pada data CSV TKPI.

    Args:
        df: DataFrame dengan kolom kode_tkpi, nama_bahan, peran_menu.

    Returns:
        Salinan df dengan tiga kolom tambahan: keputusan ("masuk"/"keluar"),
        dasar (K0..K6), dan alasan.

    Raises:
        ValueError: bila ada baris olahan tanpa keterangan yang belum diputuskan,
            atau KEPUTUSAN_TINJAUAN memuat kode yang tidak ada pada data, atau
            memuat bahan yang sebenarnya sudah diputuskan oleh kriteria K0-K4.
    """
    peta = _peta_tinjauan()
    hasil = df.copy()
    hasil[["keputusan", "dasar", "alasan"]] = [
        _putuskan_baris(baris, peta) for _, baris in hasil.iterrows()
    ]

    kode_k6 = set(hasil.loc[hasil["dasar"] == "K6", "kode_tkpi"])
    # Kode K6 boleh tetap tercatat pada KEPUTUSAN_TINJAUAN (keputusan K5 sebelumnya).
    kode_tinjauan_dipakai = set(hasil.loc[hasil["dasar"] == "K5", "kode_tkpi"]) | kode_k6
    tidak_dipakai = set(peta) - kode_tinjauan_dipakai
    if tidak_dipakai:
        raise ValueError(
            "KEPUTUSAN_TINJAUAN memuat kode yang tidak termasuk kriteria K5 pada "
            f"data ini: {sorted(tidak_dipakai)}"
        )
    k6_hilang = set(KODE_DIKECUALIKAN_PENELITI) - kode_k6
    if k6_hilang:
        raise ValueError(
            "KODE_DIKECUALIKAN_PENELITI memuat kode yang tidak ada pada data "
            f"(atau berperan di luar pokok/lauk/sayur): {sorted(k6_hilang)}"
        )
    return hasil


def baca_dan_kurasi(csv_sumber):
    """Membaca CSV TKPI lalu menerapkan kurasi. Mengembalikan DataFrame lengkap."""
    df = pd.read_csv(csv_sumber)
    if df["kode_tkpi"].duplicated().any():
        raise ValueError("Ada kode_tkpi ganda pada " + str(csv_sumber))
    return kurasi(df)


def ambil_siap_makan(csv_sumber):
    """Baris berkeputusan "masuk", hanya kolom data makanan (tanpa kolom kurasi)."""
    hasil = baca_dan_kurasi(csv_sumber)
    kolom_asli = [k for k in hasil.columns if k not in ("keputusan", "dasar", "alasan")]
    masuk = hasil[hasil["keputusan"] == KEPUTUSAN_MASUK]
    return masuk[kolom_asli].reset_index(drop=True)


def ringkas(hasil):
    """Tabel ringkasan jumlah baris per peran dan dasar keputusan."""
    return pd.crosstab(
        [hasil["keputusan"], hasil["dasar"]], hasil["peran_menu"], margins=True
    )


if __name__ == "__main__":
    kurasi_df = baca_dan_kurasi(BERKAS_SUMBER)
    kurasi_df.to_csv(BERKAS_KURASI, index=False, encoding="utf-8")
    print(f"Berkas {BERKAS_KURASI} dibuat ({len(kurasi_df)} baris).")
    print(ringkas(kurasi_df).to_string())
    masuk = kurasi_df[kurasi_df["keputusan"] == KEPUTUSAN_MASUK]
    print("\nBahan siap makan per peran:")
    print(masuk["peran_menu"].value_counts().to_string())