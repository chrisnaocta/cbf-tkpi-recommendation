"""
audit_kurasi_makanan.py
Audit terpisah untuk memeriksa angka Tabel 4.5.
Tidak mengubah atau menjalankan kurasi_makanan.py.
Input: data_makanan.csv dan kurasi_makanan.csv di folder yang sama.
Output: laporan_audit_kurasi.txt
"""
from pathlib import Path
import pandas as pd

FOLDER = Path(__file__).parent
FILE_SOURCE = FOLDER / "data_makanan.csv"
FILE_CURATED = FOLDER / "kurasi_makanan.csv"
FILE_REPORT = FOLDER / "laporan_audit_kurasi.txt"

TARGET = {
    "awal": 1146, "K0_keluar": 356, "K6_keluar": 10,
    "K1_keluar": 401, "K2_keluar": 48, "K3_masuk": 179,
    "K4_keluar": 23, "K5_keluar": 52, "K5_masuk": 77,
    "akhir_keluar": 890, "akhir_masuk": 256,
}
KODE_K6 = {
    "FP063", "FP087", "FP054", "FP064", "FP066",
    "FP059", "FP035", "FP053", "FP005", "FP020",
}

def fmt(n):
    return f"{n:,}".replace(",", ".")

def require_columns(df, columns, filename):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom hilang di {filename}: {missing}")

def main():
    if not FILE_SOURCE.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {FILE_SOURCE}")
    if not FILE_CURATED.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {FILE_CURATED}")

    source = pd.read_csv(FILE_SOURCE)
    curated = pd.read_csv(FILE_CURATED)
    require_columns(source, ["kode_tkpi", "nama_bahan", "peran_menu"], FILE_SOURCE.name)
    require_columns(curated, ["kode_tkpi", "nama_bahan", "peran_menu", "keputusan", "dasar"], FILE_CURATED.name)

    if source["kode_tkpi"].duplicated().any():
        raise ValueError("Kode TKPI duplikat pada data_makanan.csv.")
    if curated["kode_tkpi"].duplicated().any():
        raise ValueError("Kode TKPI duplikat pada kurasi_makanan.csv.")

    source_codes = set(source["kode_tkpi"].astype(str))
    curated_codes = set(curated["kode_tkpi"].astype(str))
    missing_codes = source_codes - curated_codes
    extra_codes = curated_codes - source_codes

    merged = source.merge(
        curated[["kode_tkpi", "keputusan", "dasar"]],
        on="kode_tkpi", how="left", validate="one_to_one"
    )
    if merged["keputusan"].isna().any() or merged["dasar"].isna().any():
        raise ValueError("Ada baris sumber yang tidak memiliki keputusan/dasar kurasi.")

    basis = merged["dasar"].astype(str).str.upper()
    decision = merged["keputusan"].astype(str).str.lower().str.strip()
    count_k0 = int((basis == "K0").sum())
    count_k6 = int((basis == "K6").sum())
    count_k1 = int((basis == "K1").sum())
    count_k2 = int((basis == "K2").sum())
    count_k3_in = int(((basis == "K3") & (decision == "masuk")).sum())
    count_k4 = int((basis == "K4").sum())
    count_k5_out = int(((basis == "K5") & (decision == "keluar")).sum())
    count_k5_in = int(((basis == "K5") & (decision == "masuk")).sum())
    total_out = int((decision == "keluar").sum())
    total_in = int((decision == "masuk").sum())
    total_source = len(source)

    actual = {
        "awal": total_source, "K0_keluar": count_k0, "K6_keluar": count_k6,
        "K1_keluar": count_k1, "K2_keluar": count_k2, "K3_masuk": count_k3_in,
        "K4_keluar": count_k4, "K5_keluar": count_k5_out, "K5_masuk": count_k5_in,
        "akhir_keluar": total_out, "akhir_masuk": total_in,
    }
    label = {
        "awal": "Jumlah awal", "K0_keluar": "K0 keluar", "K6_keluar": "K6 keluar",
        "K1_keluar": "K1 keluar", "K2_keluar": "K2 keluar", "K3_masuk": "K3 masuk",
        "K4_keluar": "K4 keluar", "K5_keluar": "K5 keluar", "K5_masuk": "K5 masuk",
        "akhir_keluar": "Hasil akhir keluar", "akhir_masuk": "Hasil akhir masuk",
    }

    lines = [
        "LAPORAN AUDIT KURASI BAHAN MAKANAN - TABEL 4.5",
        "=" * 55, "", f"Sumber: {FILE_SOURCE.name}",
        f"Hasil kurasi: {FILE_CURATED.name}", "",
        "A. PEMERIKSAAN TARGET TABEL", "-" * 55,
        f"{'Pemeriksaan':<22} {'Target':>10} {'Aktual':>10} {'Status':>10}",
        "-" * 55,
    ]
    checks = []
    for key, target_value in TARGET.items():
        actual_value = actual[key]
        status = "PASS" if actual_value == target_value else "FAIL"
        checks.append(status)
        lines.append(f"{label[key]:<22} {fmt(target_value):>10} {fmt(actual_value):>10} {status:>10}")

    residual_1 = total_source - count_k0 - count_k6 - count_k1 - count_k2
    residual_2 = residual_1 - count_k3_in
    residual_3 = residual_2 - count_k4
    residual_4 = residual_3 - count_k5_out - count_k5_in
    arithmetic = [
    ("Sisa setelah K0, K6, K1, K2", 331, residual_1),
    ("Sisa setelah K3", 152, residual_2),
    ("Sisa setelah K4", 129, residual_3),
    ("Sisa setelah K5", 0, residual_4),
    ("Keluar + masuk sama dengan jumlah awal", total_source, total_out + total_in),
    ("Jumlah baris output sama dengan sumber", total_source, len(curated)),
    ]
    lines += ["", "B. PEMERIKSAAN ARITMETIKA", "-" * 55,
              f"{'Pemeriksaan':<38} {'Target':>10} {'Aktual':>10} {'Status':>10}",
              "-" * 55]
    arithmetic_status = []
    for name, target_value, actual_value in arithmetic:
        status = "PASS" if target_value == actual_value else "FAIL"
        arithmetic_status.append(status)
        lines.append(f"{name:<38} {fmt(target_value):>10} {fmt(actual_value):>10} {status:>10}")

    k6_actual = set(merged.loc[basis == "K6", "kode_tkpi"].astype(str))
    k6_ok = k6_actual == KODE_K6
    lines += ["", "C. PEMERIKSAAN KODE K6", "-" * 55,
              f"Jumlah kode K6 aktual: {fmt(len(k6_actual))}",
              f"Daftar kode K6 cocok dengan 10 kode pengecualian: {'PASS' if k6_ok else 'FAIL'}"]
    if not k6_ok:
        lines += [f"Kode K6 aktual: {sorted(k6_actual)}", f"Kode K6 target: {sorted(KODE_K6)}"]

    code_match = not missing_codes and not extra_codes
    lines += ["", "D. PEMERIKSAAN KODE DATA", "-" * 55,
              f"Kode sumber tidak ada di output: {len(missing_codes)}",
              f"Kode output tidak ada di sumber: {len(extra_codes)}",
              f"Kode sumber dan output sama: {'PASS' if code_match else 'FAIL'}"]
    if missing_codes:
        lines.append(f"Kode hilang: {sorted(missing_codes)}")
    if extra_codes:
        lines.append(f"Kode tambahan: {sorted(extra_codes)}")

    lines += ["", "E. RINGKASAN DASAR DAN KEPUTUSAN", "-" * 55]
    summary = merged.assign(basis=basis, decision=decision).groupby(["basis", "decision"]).size().sort_index()
    for (b, d), count in summary.items():
        lines.append(f"{b} - {d}: {fmt(int(count))}")

    passed = all(s == "PASS" for s in checks) and all(s == "PASS" for s in arithmetic_status) and k6_ok and code_match
    lines += ["", "=" * 55, f"STATUS AUDIT KESELURUHAN: {'PASS' if passed else 'FAIL'}",
              "Audit ini memeriksa angka tabel, konsistensi aritmetika, kode, dan dasar/keputusan yang tercatat.",
              "Audit tidak menggantikan tinjauan manual atas keputusan K5."]
    report = "\n".join(lines)
    FILE_REPORT.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nLaporan TXT disimpan: {FILE_REPORT}")

if __name__ == "__main__":
    main()