
"""
audit_tabel_4_6.py

Audit independen untuk memeriksa kebenaran Tabel 4.6
Komposisi Bahan pada Tabel Makanan Menurut Peran
dan Kelompok Pangan.

Input:
    rekomendasi_makanan.db

Output:
    laporan_audit_tabel_4_6.txt

Skrip ini hanya membaca database, tidak mengubah data.
"""

from pathlib import Path
import sqlite3

FOLDER = Path(__file__).parent
FILE_DB = FOLDER / "rekomendasi_makanan.db"
FILE_REPORT = FOLDER / "laporan_audit_tabel_4_6.txt"

# Target berdasarkan Tabel 4.6
TARGET = {
    ("pokok", "Serealia"): 29,
    ("pokok", "Umbi Berpati"): 15,
    ("lauk", "Daging"): 71,
    ("lauk", "Ikan Kerang Udang"): 56,
    ("lauk", "Kacang dan Biji"): 22,
    ("lauk", "Telur"): 5,
    ("sayur", "Sayuran"): 58,
}

TARGET_SUBTOTAL = {
    "pokok": 44,
    "lauk": 154,
    "sayur": 58,
}

TARGET_TOTAL = 256


def fmt(n):
    return f"{n:,}".replace(",", ".")


def main():
    if not FILE_DB.exists():
        raise FileNotFoundError(
            f"Database tidak ditemukan: {FILE_DB}"
        )

    conn = sqlite3.connect(FILE_DB)

    try:
        cursor = conn.cursor()

        # Memastikan tabel makanan tersedia
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'makanan'
        """)

        if cursor.fetchone() is None:
            raise ValueError(
                "Tabel 'makanan' tidak ditemukan di database."
            )

        # Memastikan kolom yang diperlukan tersedia
        cursor.execute("PRAGMA table_info(makanan)")
        columns = {
            row[1] for row in cursor.fetchall()
        }

        required_columns = {
            "id_makanan", "kode_tkpi",
            "nama_bahan", "kategori", "peran_menu"
        }

        missing_columns = required_columns - columns

        if missing_columns:
            raise ValueError(
                f"Kolom database tidak lengkap: "
                f"{sorted(missing_columns)}"
            )

        # Membaca komposisi data berdasarkan peran dan kategori
        cursor.execute("""
            SELECT
                LOWER(TRIM(peran_menu)),
                TRIM(kategori),
                COUNT(*)
            FROM makanan
            GROUP BY
                LOWER(TRIM(peran_menu)),
                TRIM(kategori)
            ORDER BY
                LOWER(TRIM(peran_menu)),
                TRIM(kategori)
        """)

        rows = cursor.fetchall()

        actual = {
            (role, category): count
            for role, category, count in rows
        }

        # Menghitung subtotal berdasarkan peran menu
        subtotal = {
            "pokok": 0,
            "lauk": 0,
            "sayur": 0,
        }

        for (role, category), count in actual.items():
            if role in subtotal:
                subtotal[role] += count

        total_data = sum(actual.values())

        # Membuat laporan
        lines = [
            "LAPORAN AUDIT TABEL 4.6",
            "KOMPOSISI BAHAN MENURUT PERAN "
            "DAN KELOMPOK PANGAN",
            "=" * 65,
            "",
            f"Database: {FILE_DB.name}",
            "Tabel database: makanan",
            "",
            "A. PEMERIKSAAN KELOMPOK PANGAN",
            "-" * 65,
            f"{'Peran menu':<12} "
            f"{'Kelompok pangan':<30} "
            f"{'Target':>8} "
            f"{'Aktual':>8} "
            f"{'Status':>8}",
            "-" * 65,
        ]

        category_status = []

        for key, target_value in TARGET.items():
            actual_value = actual.get(key, 0)

            status = (
                "PASS"
                if actual_value == target_value
                else "FAIL"
            )

            category_status.append(status)

            role, category = key

            lines.append(
                f"{role:<12} "
                f"{category:<30} "
                f"{fmt(target_value):>8} "
                f"{fmt(actual_value):>8} "
                f"{status:>8}"
            )

        # Memeriksa kategori yang tidak terdapat dalam target
        unexpected = {
            key: value
            for key, value in actual.items()
            if key not in TARGET
        }

        lines += [
            "",
            "B. PEMERIKSAAN SUBTOTAL PERAN MENU",
            "-" * 65,
            f"{'Peran menu':<20} "
            f"{'Target':>10} "
            f"{'Aktual':>10} "
            f"{'Status':>10}",
            "-" * 65,
        ]

        subtotal_status = []

        for role, target_value in TARGET_SUBTOTAL.items():
            actual_value = subtotal[role]

            status = (
                "PASS"
                if actual_value == target_value
                else "FAIL"
            )

            subtotal_status.append(status)

            lines.append(
                f"{role:<20} "
                f"{fmt(target_value):>10} "
                f"{fmt(actual_value):>10} "
                f"{status:>10}"
            )

        # Memeriksa total keseluruhan
        total_status = (
            "PASS"
            if total_data == TARGET_TOTAL
            else "FAIL"
        )

        lines += [
            "",
            "C. PEMERIKSAAN TOTAL BAHAN",
            "-" * 65,
            f"Target total bahan : {fmt(TARGET_TOTAL)}",
            f"Total aktual       : {fmt(total_data)}",
            f"Status             : {total_status}",
        ]

        # Memeriksa apakah subtotal konsisten
        subtotal_sum = sum(subtotal.values())

        subtotal_consistency = (
            "PASS"
            if subtotal_sum == total_data
            else "FAIL"
        )

        lines += [
            "",
            "D. PEMERIKSAAN KONSISTENSI SUBTOTAL",
            "-" * 65,
            f"Jumlah subtotal : {fmt(subtotal_sum)}",
            f"Total database : {fmt(total_data)}",
            f"Status         : {subtotal_consistency}",
        ]

        # Melaporkan kategori yang tidak sesuai target
        lines += [
            "",
            "E. PEMERIKSAAN KATEGORI TAMBAHAN",
            "-" * 65,
        ]

        if unexpected:
            unexpected_status = "FAIL"

            lines.append(
                "Kategori/peran yang tidak terdaftar dalam target:"
            )

            for (role, category), count in sorted(
                unexpected.items()
            ):
                lines.append(
                    f"- {role} | {category}: {fmt(count)}"
                )
        else:
            unexpected_status = "PASS"
            lines.append(
                "Tidak ditemukan kategori/peran tambahan."
            )

        # Ringkasan status
        passed = (
            all(s == "PASS" for s in category_status)
            and all(s == "PASS" for s in subtotal_status)
            and total_status == "PASS"
            and subtotal_consistency == "PASS"
            and unexpected_status == "PASS"
        )

        lines += [
            "",
            "=" * 65,
            f"STATUS AUDIT KESELURUHAN: "
            f"{'PASS' if passed else 'FAIL'}",
            "",
            "Audit memeriksa jumlah bahan berdasarkan peran menu,",
            "kelompok pangan, subtotal, total, dan kategori tambahan.",
            "Audit tidak mengubah isi database.",
        ]

        report = "\n".join(lines)

        # Menyimpan laporan TXT
        FILE_REPORT.write_text(
            report,
            encoding="utf-8"
        )

        print(report)

        print(
            f"\nLaporan TXT disimpan: {FILE_REPORT}"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()