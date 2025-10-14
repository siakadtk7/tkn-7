# main/context_processors.py
from datetime import date

def tahun_ajaran(request):
    today = date.today()

    # Hitung tahun ajaran
    if today.month >= 7:  # Juli - Desember
        start_year = today.year
        end_year = today.year + 1
    else:  # Januari - Juni
        start_year = today.year - 1
        end_year = today.year

    tahun_ajaran_str = f"{start_year}/{end_year}"

    # Peta hari & bulan ke bahasa Indonesia
    hari_map = {
        "Monday": "Senin",
        "Tuesday": "Selasa",
        "Wednesday": "Rabu",
        "Thursday": "Kamis",
        "Friday": "Jumat",
        "Saturday": "Sabtu",
        "Sunday": "Minggu",
    }
    bulan_map = {
        1: "Januari",
        2: "Februari",
        3: "Maret",
        4: "April",
        5: "Mei",
        6: "Juni",
        7: "Juli",
        8: "Agustus",
        9: "September",
        10: "Oktober",
        11: "November",
        12: "Desember",
    }

    hari = hari_map[today.strftime("%A")]
    bulan = bulan_map[today.month]
    hari_tanggal = f"{hari}, {today.day} {bulan} {today.year}"

    return {
        'tahun_ajaran': tahun_ajaran_str,
        'hari_tanggal': hari_tanggal,
    }
