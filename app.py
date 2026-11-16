"""
app.py

Antarmuka Streamlit sistem rekomendasi menu makanan harian.

Jalankan dari folder website/:
    streamlit run app.py

Berkas ini hanya menggambar tampilan. Seluruh perhitungan (rumus 1-13) dan alur
sesi berada di AplikasiUtama dan kelas-kelas yang dipanggilnya (Gambar 3.4).
"""

import html
import os
from typing import Any, Dict, List, Mapping, Optional, Tuple

import streamlit as st

from aplikasi_utama import (
    AplikasiUtama, LABEL_PERAN, LABEL_WAKTU_MAKAN, SATUAN_ZAT,
)
from kalkulator_gizi import DEFISIT_ENERGI, BATAS_IMT_LEBIH, ZAT_GIZI
from koneksi_database import DB_PATH_BAWAAN, KoneksiDatabase
from mesin_rekomendasi import TOLERANSI_ATAS, TOLERANSI_BAWAH
from repositori_makanan import PERAN_VALID, RepositoriMakanan

# ---------------------------------------------------------------------------
# KONSTANTA TAMPILAN (bukan rumus; ketetapan pelaksanaan)
# ---------------------------------------------------------------------------
# Basis data dapat diganti lewat variabel lingkungan (dipakai oleh tes agar
# basis data skripsi tidak tertulis oleh pengujian).
VARIABEL_DB = "SKRIPSI_DB_PATH"

JUDUL_HALAMAN = "Menu Harian Seimbang"
KUNCI_APLIKASI = "aplikasi"
KUNCI_KESALAHAN = "kesalahan"

# Skala pengukur persentase pemenuhan (%). Pita 90-110 diambil dari TOLERANSI_*.
PENGUKUR_BAWAH = 80.0
PENGUKUR_ATAS = 120.0
PENGUKUR_TANDA = (80, 90, 100, 110, 120)

LABEL_ZAT = {"energi": "Energi", "protein": "Protein", "lemak": "Lemak", "karbohidrat": "Karbohidrat"}

# Palet: bahan dan alat dapur Indonesia.
WARNA = {
    "piring": "#F1F4F2",    # latar halaman
    "nampan": "#FFFFFF",    # permukaan nampan
    "tinta": "#17252E",     # teks dan tombol
    "pudar": "#4F5F68",     # teks sekunder
    "garis": "#CBD5CF",     # garis tipis
    "kunyit": "#E0A412",    # makanan pokok, penanda utama
    "teal": "#2E6C78",      # lauk
    "daun": "#6FA05A",      # sayur
    "hijau_ok": "#2F7D4F",  # sesuai rentang
    "cabai": "#B23A2E",     # di luar rentang
}
WARNA_PERAN = {"pokok": WARNA["kunyit"], "lauk": WARNA["teal"], "sayur": WARNA["daun"]}

PILIHAN_KOSONG_AKTIVITAS = "Pilih tingkat aktivitas"


# ---------------------------------------------------------------------------
# Pembantu format
# ---------------------------------------------------------------------------
def fmt(nilai: float, desimal: int = 0) -> str:
    """Format angka gaya Indonesia: titik pemisah ribuan, koma desimal."""
    teks = f"{nilai:,.{desimal}f}"
    return teks.replace(",", "\0").replace(".", ",").replace("\0", ".")


def esc(teks: Any) -> str:
    return html.escape(str(teks), quote=True)


def rentang_toleransi() -> str:
    return f"{fmt(TOLERANSI_BAWAH)}-{fmt(TOLERANSI_ATAS)}%"


# ---------------------------------------------------------------------------
# Gaya
# ---------------------------------------------------------------------------
def gaya() -> str:
    variabel = ":root{" + "".join(f"--{k}:{v};" for k, v in WARNA.items()) + "}"
    pita_kiri = (TOLERANSI_BAWAH - PENGUKUR_BAWAH) / (PENGUKUR_ATAS - PENGUKUR_BAWAH) * 100
    pita_lebar = (TOLERANSI_ATAS - TOLERANSI_BAWAH) / (PENGUKUR_ATAS - PENGUKUR_BAWAH) * 100
    pita = f".pita{{left:{pita_kiri:.2f}%;width:{pita_lebar:.2f}%;}}"
    return (
        "<style>"
        "@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700"
        "&family=IBM+Plex+Sans:wght@400;500;600&display=swap');"
        + variabel + pita + _GAYA_TETAP + "</style>"
    )


_GAYA_TETAP = """
/* Font teks; ikon Material Streamlit dikecualikan agar tidak tampil sebagai tulisan. */
.stApp *:not([data-testid="stIconMaterial"]):not(code):not(pre) { font-family: 'IBM Plex Sans', system-ui, sans-serif; }
.block-container { max-width: 62rem; padding-top: 2.2rem; }
.stApp h1, .stApp h2, .stApp h3, .stApp .judul, .stApp .judul * { font-family: 'Bricolage Grotesque', 'IBM Plex Sans', system-ui, sans-serif; letter-spacing: -0.01em; color: var(--tinta); }
h1 { font-size: 2.3rem; line-height: 1.1; margin-bottom: .3rem; }
.pengantar { max-width: 38rem; color: var(--pudar); font-size: 1.05rem; line-height: 1.55; margin: 0 0 1.6rem; }
footer, #MainMenu { visibility: hidden; }

/* fakta hasil perhitungan */
.fakta { display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); gap: 0; border-top: 2px solid var(--tinta); border-bottom: 1px solid var(--garis); margin: .4rem 0 1.2rem; }
.fakta > div { padding: .8rem 1rem .9rem 0; }
.fakta .nama { color: var(--pudar); font-size: .9rem; }
.stApp .fakta .nilai { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700; font-size: 1.75rem; line-height: 1.15; font-variant-numeric: tabular-nums; }
.stApp .fakta .nilai small { font-family: 'IBM Plex Sans', sans-serif; font-weight: 400; font-size: .85rem; color: var(--pudar); margin-left: .25rem; }
.fakta .ket { font-size: .88rem; color: var(--pudar); margin-top: .1rem; }

/* tabel target */
table.target { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; font-size: .95rem; }
table.target th { text-align: right; font-weight: 600; padding: .45rem .6rem; border-bottom: 1px solid var(--tinta); }
table.target td { text-align: right; padding: .45rem .6rem; border-bottom: 1px solid var(--garis); }
table.target th:first-child, table.target td:first-child { text-align: left; padding-left: 0; }
table.target tr.harian td { font-weight: 600; }

/* nampan: satu waktu makan */
.nampan { background: var(--nampan); border: 1px solid var(--garis); border-radius: 10px; margin: 0 0 1.4rem; overflow: hidden; }
.nampan > header { display: flex; flex-wrap: wrap; gap: .4rem 1rem; align-items: baseline; justify-content: space-between; padding: .9rem 1.2rem .6rem; }
.nampan h3 { margin: 0; font-size: 1.45rem; }
.status { font-size: .9rem; font-weight: 500; }
.status.ok { color: var(--hijau_ok); }
.status.belum { color: var(--cabai); }
.petak { display: flex; gap: 3px; height: 2.2rem; margin: 0 1.2rem; }
.petak span { display: flex; align-items: center; justify-content: center; border-radius: 3px; min-width: 3.2rem; color: #fff; font-weight: 600; font-size: .88rem; font-variant-numeric: tabular-nums; }
.petak span.pokok { color: var(--tinta); }
.hidangan { margin: .7rem 1.2rem .3rem; }
.baris { display: grid; grid-template-columns: 9.5rem minmax(0,1fr) 5rem 15rem; gap: .2rem 1rem; align-items: baseline; padding: .55rem 0; border-top: 1px solid var(--garis); }
.baris:first-child { border-top: 0; }
.peran { display: flex; align-items: center; gap: .5rem; font-weight: 500; }
.peran i { width: .8rem; height: .8rem; border-radius: 2px; display: inline-block; flex: none; }
.bahan { overflow-wrap: anywhere; }
.stApp .gram { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700; font-size: 1.25rem; text-align: right; font-variant-numeric: tabular-nums; }
.gizi { color: var(--pudar); font-size: .88rem; font-variant-numeric: tabular-nums; }

/* pengukur pemenuhan: elemen utama halaman ini */
.pengukur { padding: .5rem 1.2rem 1.1rem; }
.pengukur .judul-kecil { font-size: .9rem; color: var(--pudar); margin-bottom: .2rem; }
.baris-ukur { display: grid; grid-template-columns: 6.5rem minmax(0,1fr) 9.5rem; gap: .8rem; align-items: center; padding: .25rem 0; }
.baris-ukur .zat { font-weight: 500; }
.lintasan { position: relative; height: .9rem; background: #EEF1EF; border-radius: 2px; }
.pita { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--hijau_ok) 22%, white); border-left: 2px solid var(--hijau_ok); border-right: 2px solid var(--hijau_ok); }
.tengah { position: absolute; top: -2px; bottom: -2px; width: 1px; background: var(--pudar); opacity: .55; }
.penanda { position: absolute; top: -4px; width: 6px; height: calc(100% + 8px); margin-left: -3px; border-radius: 1px; background: var(--hijau_ok); }
.penanda.luar { background: var(--cabai); }
.nilai-ukur { text-align: right; font-variant-numeric: tabular-nums; font-size: .85rem; color: var(--pudar); line-height: 1.25; }
.nilai-ukur b { display: block; color: var(--tinta); }
.nilai-ukur b { font-size: 1.02rem; }
.nilai-ukur.luar b { color: var(--cabai); }
.sumbu { display: grid; grid-template-columns: 6.5rem minmax(0,1fr) 9.5rem; gap: .8rem; margin-bottom: .1rem; }
.sumbu .skala { position: relative; height: 1rem; font-size: .75rem; color: var(--pudar); font-variant-numeric: tabular-nums; }
.sumbu .skala span { position: absolute; transform: translateX(-50%); }

/* detail nutrisi */
table.detail { border-collapse: collapse; font-variant-numeric: tabular-nums; min-width: 22rem; max-width: 100%; }
table.detail th { text-align: right; font-weight: 600; padding: .4rem .8rem; border-bottom: 1px solid var(--tinta); }
table.detail td { text-align: right; padding: .4rem .8rem; border-bottom: 1px solid var(--garis); }
table.detail th:first-child, table.detail td:first-child { text-align: left; padding-left: 0; }
.stApp .rincian-judul { font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.25rem; font-weight: 700; margin: .6rem 0 .1rem; }
.rincian-ket { color: var(--pudar); font-size: .92rem; margin-bottom: .5rem; }

.kosong { border-top: 2px solid var(--tinta); padding-top: 1rem; max-width: 40rem; }
.kosong p { font-size: 1.05rem; line-height: 1.6; margin: 0 0 .6rem; }
.catatan-akhir { color: var(--pudar); font-size: .88rem; max-width: 42rem; margin-top: 1.6rem; }

@media (max-width: 720px) {
  h1 { font-size: 1.8rem; }
  .baris { grid-template-columns: 1fr auto; }
  .baris .bahan { grid-column: 1 / -1; order: 3; }
  .baris .gizi { grid-column: 1 / -1; order: 4; }
  .baris-ukur, .sumbu { grid-template-columns: 5rem minmax(0,1fr); }
  .baris-ukur .nilai-ukur { grid-column: 1 / -1; text-align: left; }
  .sumbu > :last-child { display: none; }
}
"""


# ---------------------------------------------------------------------------
# Potongan HTML
# ---------------------------------------------------------------------------
def html_fakta(h: Mapping[str, Any]) -> str:
    imt, harian = h["imt"], h["target_harian"]
    if imt > BATAS_IMT_LEBIH:
        ket_target = f"TEE dikurangi {fmt(DEFISIT_ENERGI)} kkal karena IMT di atas {fmt(BATAS_IMT_LEBIH, 1)}"
    else:
        ket_target = "Sama dengan TEE (tanpa pengurangan)"
    blok = [
        ("Indeks Massa Tubuh", fmt(imt, 1), "", h["klasifikasi"]),
        ("BMR", fmt(h["bmr"]), "kkal/hari", "Energi saat istirahat"),
        ("TEE", fmt(h["tee"]), "kkal/hari", f"BMR dikali faktor aktivitas {fmt(h['faktor_aktivitas'], 2)}"),
        ("Target energi", fmt(harian["energi"]), "kkal/hari", ket_target),
    ]
    isi = "".join(
        f'<div><div class="nama">{esc(n)}</div>'
        f'<div class="nilai">{esc(v)}<small>{esc(s)}</small></div>'
        f'<div class="ket">{esc(k)}</div></div>'
        for n, v, s, k in blok
    )
    return f'<div class="fakta">{isi}</div>'


def html_tabel_target(h: Mapping[str, Any]) -> str:
    kepala = "".join(
        f"<th>{LABEL_ZAT[z]} ({SATUAN_ZAT[z]})</th>" for z in ZAT_GIZI
    )
    def baris(nama: str, nilai: Mapping[str, float], kelas: str = "") -> str:
        sel = "".join(
            f"<td>{fmt(nilai[z], 0 if z == 'energi' else 1)}</td>" for z in ZAT_GIZI
        )
        return f'<tr class="{kelas}"><td>{esc(nama)}</td>{sel}</tr>'
    isi = baris("Satu hari", h["target_harian"], "harian")
    for waktu, nilai in h["target_waktu_makan"].items():
        isi += baris(LABEL_WAKTU_MAKAN[waktu], nilai)
    return (
        '<table class="target"><thead><tr><th>Target gizi</th>'
        f"{kepala}</tr></thead><tbody>{isi}</tbody></table>"
    )


def html_pengukur(pemenuhan: Mapping[str, float], total: Mapping[str, float],
                  target: Mapping[str, float], judul: str) -> str:
    """Pengukur: pita hijau = rentang sesuai (90-110%); penanda = posisi pemenuhan."""
    rentang = PENGUKUR_ATAS - PENGUKUR_BAWAH
    tanda = "".join(
        f'<span style="left:{(t - PENGUKUR_BAWAH) / rentang * 100:.2f}%">{t}%</span>'
        for t in PENGUKUR_TANDA
    )
    isi = (
        f'<div class="judul-kecil">{esc(judul)}</div>'
        f'<div class="sumbu"><span></span><div class="skala">{tanda}</div><span></span></div>'
    )
    for zat in ZAT_GIZI:
        persen = pemenuhan[zat]
        dalam = TOLERANSI_BAWAH - 1e-9 <= persen <= TOLERANSI_ATAS + 1e-9
        posisi = min(max((persen - PENGUKUR_BAWAH) / rentang * 100, 0.0), 100.0)
        satuan = SATUAN_ZAT[zat]
        desimal = 0 if zat == "energi" else 1
        teks = (f"{LABEL_ZAT[zat]} {fmt(persen, 1)} persen dari target; rentang sesuai "
                f"{fmt(TOLERANSI_BAWAH)} sampai {fmt(TOLERANSI_ATAS)} persen")
        isi += (
            '<div class="baris-ukur">'
            f'<span class="zat">{LABEL_ZAT[zat]}</span>'
            f'<div class="lintasan" role="img" aria-label="{esc(teks)}">'
            '<div class="pita"></div><div class="tengah" style="left:50%"></div>'
            f'<div class="penanda{"" if dalam else " luar"}" style="left:{posisi:.2f}%"></div></div>'
            f'<span class="nilai-ukur{"" if dalam else " luar"}"><b>{fmt(persen, 1)}%</b>'
            f'{fmt(total[zat], desimal)} dari {fmt(target[zat], desimal)} {satuan}</span>'
            "</div>"
        )
    return f'<div class="pengukur">{isi}</div>'


def html_nampan(waktu: str, menu: Mapping[str, Any]) -> str:
    tabel = menu["tabel"]
    petak = "".join(
        f'<span class="{p}" style="flex:{g} 1 0;background:{WARNA_PERAN[p]}" '
        f'title="{esc(LABEL_PERAN[p])} {fmt(g)} g">{fmt(g)} g</span>'
        for p, g in zip(PERAN_VALID, tabel["porsi_gram"])
    )
    baris = ""
    for peran, (_, b) in zip(PERAN_VALID, tabel.iterrows()):
        gizi = ", ".join(
            f"{LABEL_ZAT[z].lower()} {fmt(b[z], 0 if z == 'energi' else 1)} {SATUAN_ZAT[z]}"
            for z in ZAT_GIZI
        )
        baris += (
            '<div class="baris">'
            f'<span class="peran"><i style="background:{WARNA_PERAN[peran]}"></i>{esc(b["peran"])}</span>'
            f'<span class="bahan">{esc(b["bahan"])}</span>'
            f'<span class="gram">{fmt(b["porsi_gram"])} g</span>'
            f'<span class="gizi">{esc(gizi)}</span></div>'
        )
    if menu["memenuhi"]:
        status = f'<span class="status ok">Sesuai: keempat zat gizi dalam rentang {rentang_toleransi()}</span>'
    else:
        status = f'<span class="status belum">Belum sesuai: ada zat gizi di luar rentang {rentang_toleransi()}</span>'
    return (
        '<section class="nampan">'
        f'<header><h3>{esc(menu["label"])}</h3>{status}</header>'
        f'<div class="petak" aria-label="Perbandingan berat tiap hidangan">{petak}</div>'
        f'<div class="hidangan">{baris}</div>'
        + html_pengukur(menu["pemenuhan"], menu["total"], menu["target"],
                        "Pemenuhan terhadap target waktu makan")
        + "</section>"
    )


def html_detail(d: Mapping[str, Any]) -> str:
    baris = "".join(
        f"<tr><td>{LABEL_ZAT[z]} ({SATUAN_ZAT[z]})</td>"
        f"<td>{fmt(d['per_100_gram'][z], 1)}</td><td>{fmt(d['per_porsi'][z], 1)}</td></tr>"
        for z in ZAT_GIZI
    )
    return (
        f'<div class="rincian-judul">{esc(d["nama_bahan"])}</div>'
        f'<div class="rincian-ket">{esc(d["peran"])} untuk {esc(d["waktu_makan"].lower())}. '
        f'Kode TKPI {esc(d["kode_tkpi"])}, kelompok {esc(d["kategori"])}.</div>'
        '<table class="detail"><thead><tr><th>Kandungan gizi</th><th>Per 100 g</th>'
        f'<th>Porsi {fmt(d["porsi_gram"])} g</th></tr></thead><tbody>{baris}</tbody></table>'
    )


# ---------------------------------------------------------------------------
# Bagian halaman
# ---------------------------------------------------------------------------
def siapkan_aplikasi() -> Optional[AplikasiUtama]:
    """Membuat AplikasiUtama sekali per sesi browser. Mengembalikan None bila DB tidak ada."""
    jalur = os.environ.get(VARIABEL_DB, DB_PATH_BAWAAN)
    if not os.path.isfile(jalur):
        st.error(
            f"Basis data tidak ditemukan di {jalur}. "
            "Jalankan setup_db.py di folder database terlebih dahulu."
        )
        return None
    if KUNCI_APLIKASI not in st.session_state:
        st.session_state[KUNCI_APLIKASI] = AplikasiUtama(RepositoriMakanan(KoneksiDatabase(jalur)))
    return st.session_state[KUNCI_APLIKASI]


def formulir(aplikasi: AplikasiUtama) -> None:
    """Panel data diri di sisi kiri: lima input dan tombol hitung."""
    spesifikasi = aplikasi.tampilkan_form_input()
    pilihan_aktivitas = {a["kunci"]: a for a in spesifikasi["tingkat_aktivitas"]}
    label_jk = dict(spesifikasi["jenis_kelamin"])

    with st.sidebar:
        st.markdown('<div class="judul" style="font-size:1.4rem;font-weight:700">Data diri</div>',
                    unsafe_allow_html=True)
        usia = st.text_input(
            f"Usia ({spesifikasi['usia']['satuan']})", key="in_usia", placeholder="mis. 30",
            help=f"Sistem melayani usia {spesifikasi['usia']['min']} sampai {spesifikasi['usia']['max']} tahun.",
        )
        jenis_kelamin = st.radio(
            "Jenis kelamin", options=list(label_jk), index=None, key="in_jk",
            format_func=lambda k: label_jk[k], horizontal=True,
        )
        berat = st.text_input(f"Berat badan ({spesifikasi['berat_badan']['satuan']})",
                              key="in_berat", placeholder="mis. 70")
        tinggi = st.text_input(f"Tinggi badan ({spesifikasi['tinggi_badan']['satuan']})",
                               key="in_tinggi", placeholder="mis. 170")
        aktivitas = st.selectbox(
            "Tingkat aktivitas fisik", options=list(pilihan_aktivitas), index=None, key="in_aktivitas",
            format_func=lambda k: pilihan_aktivitas[k]["label"], placeholder=PILIHAN_KOSONG_AKTIVITAS,
        )
        if aktivitas:
            a = pilihan_aktivitas[aktivitas]
            st.caption(f"PAL {a['rentang_pal']}, dihitung dengan faktor {fmt(a['faktor'], 2)}. {a['contoh']}")
        else:
            st.caption("Pilih yang paling dekat dengan kebiasaan harian Anda.")

        kirim = st.button("Hitung dan susun menu", type="primary", use_container_width=True)

    if kirim:
        try:
            aplikasi.proses_input_pengguna(usia, jenis_kelamin, berat, tinggi, aktivitas)
            st.session_state[KUNCI_KESALAHAN] = None
        except ValueError as galat:
            st.session_state[KUNCI_KESALAHAN] = str(galat)


def bagian_kosong() -> None:
    st.markdown(
        '<div class="kosong"><p>Isi data diri di panel kiri, lalu pilih <b>Hitung dan susun menu</b>.</p>'
        "<p>Anda akan mendapat target gizi harian, serta menu sarapan, makan siang, dan makan malam "
        "lengkap dengan berat tiap hidangan dalam gram.</p></div>",
        unsafe_allow_html=True,
    )


def bagian_hasil_gizi(aplikasi: AplikasiUtama) -> None:
    h = aplikasi.tampilkan_hasil_gizi()
    st.markdown("## Kebutuhan gizi Anda")
    st.markdown(html_fakta(h) + html_tabel_target(h), unsafe_allow_html=True)
    if h["catatan"]:
        st.warning(h["catatan"])


def bagian_menu(aplikasi: AplikasiUtama) -> None:
    st.markdown("## Menu hari ini")
    kolom_tombol, kolom_ket = st.columns([1, 3], vertical_alignment="center")
    with kolom_tombol:
        minta_ulang = st.button("Minta Ulang", use_container_width=True)
    with kolom_ket:
        st.caption("Menghasilkan menu lain dari bahan yang berbeda, dengan target gizi yang sama.")
    if minta_ulang:
        try:
            aplikasi.refresh_rekomendasi()
        except ValueError as galat:
            st.error(f"Menu lain belum bisa disusun: {galat}")

    r = aplikasi.tampilkan_rekomendasi()
    if r["catatan"]:
        st.warning(r["catatan"])
    for waktu, menu in r["menu"].items():
        st.markdown(html_nampan(waktu, menu), unsafe_allow_html=True)

    harian = r["harian"]
    st.markdown(
        '<section class="nampan"><header><h3>Total satu hari</h3>'
        + (f'<span class="status ok">Sesuai: keempat zat gizi dalam rentang {rentang_toleransi()}</span>'
           if harian["memenuhi"] else
           f'<span class="status belum">Belum sesuai: ada zat gizi di luar rentang {rentang_toleransi()}</span>')
        + "</header>"
        + html_pengukur(harian["pemenuhan"], harian["total"], harian["target"],
                        "Pemenuhan terhadap target gizi harian")
        + "</section>",
        unsafe_allow_html=True,
    )


def bagian_detail(aplikasi: AplikasiUtama) -> None:
    st.markdown("## Detail nutrisi")
    r = aplikasi.tampilkan_rekomendasi()
    opsi: List[Tuple[int, str]] = [
        (int(b["id_makanan"]), f'{menu["label"]}: {b["bahan"]}')
        for menu in r["menu"].values() for _, b in menu["tabel"].iterrows()
    ]
    nama = dict(opsi)
    pilihan = st.selectbox(
        "Pilih satu bahan untuk melihat kandungan gizinya", options=[i for i, _ in opsi],
        format_func=lambda i: nama[i], index=None, placeholder="Pilih bahan", key="in_detail",
    )
    if pilihan is not None:
        st.markdown(html_detail(aplikasi.tampilkan_detail_nutrisi(pilihan)), unsafe_allow_html=True)


def halaman() -> None:
    st.set_page_config(page_title=JUDUL_HALAMAN, page_icon=None, layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(gaya(), unsafe_allow_html=True)
    st.markdown(f"# {JUDUL_HALAMAN}")
    st.markdown(
        '<p class="pengantar">Tiga kali makan sehari yang disusun dari Tabel Komposisi Pangan '
        "Indonesia 2020 dan dihitung dari data diri Anda.</p>",
        unsafe_allow_html=True,
    )

    aplikasi = siapkan_aplikasi()
    if aplikasi is None:
        st.stop()
    formulir(aplikasi)

    kesalahan = st.session_state.get(KUNCI_KESALAHAN)
    if kesalahan:
        st.error(kesalahan)

    if aplikasi.sesi.aktif and aplikasi.sesi.rekomendasi_saat_ini and not kesalahan:
        bagian_hasil_gizi(aplikasi)
        bagian_menu(aplikasi)
        bagian_detail(aplikasi)
        st.markdown(
            '<p class="catatan-akhir">Rekomendasi ini hasil perhitungan dari data TKPI 2020 dan '
            "bukan pengganti saran tenaga kesehatan.</p>",
            unsafe_allow_html=True,
        )
    elif not kesalahan:
        bagian_kosong()


halaman()