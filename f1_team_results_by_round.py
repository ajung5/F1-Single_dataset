"""Ambil poin tim Formula 1 pada satu musim dan satu round tertentu.

Sumber hasil: FastF1 (Sprint dan Main Race).
Sumber nama sirkuit (opsional): Jolpica F1 API.

Instalasi:
    pip install -U fastf1 pandas openpyxl requests
"""

from pathlib import Path
import re

import fastf1
import pandas as pd
import requests

# =========================================================
# 1. KONFIGURASI
# =========================================================
TARGET_SEASON = 2026
TARGET_ROUND = 17
CACHE_DIR = Path("f1_cache")

OUTPUT_COLUMNS = [
    "Round",
    "Season",
    "Grand Prix",
    "Circuit Name",
    "City",
    "Nation",
    "GP Initial",
    "Race Type",
    "Team Name",
    "Team Initial",
    "Engine Manufacture",
    "Race Points",
]

# Nama di sini adalah nama singkat untuk matching TeamName FastF1.
# Urutan diperhatikan agar nama yang mirip tidak salah dikenali.
TEAM_ALIASES = [
    ("Racing Bulls", ("racing bulls", "visa cash app rb", "rb f1 team")),
    ("Red Bull Racing", ("red bull racing", "red bull")),
    ("Aston Martin", ("aston martin",)),
    ("McLaren", ("mclaren",)),
    ("Mercedes", ("mercedes",)),
    ("Ferrari", ("ferrari",)),
    ("Williams", ("williams",)),
    ("Haas", ("haas",)),
    ("Alpine", ("alpine",)),
    ("Audi", ("audi",)),
    ("Cadillac", ("cadillac",)),
    ("Sauber", ("sauber",)),
]

TEAM_INITIALS = {
    "Racing Bulls": "RBU",
    "Red Bull Racing": "RBR",
    "Aston Martin": "AST",
    "McLaren": "MCL",
    "Mercedes": "MER",
    "Ferrari": "FER",
    "Williams": "WIL",
    "Haas": "HAA",
    "Alpine": "ALP",
    "Audi": "AUD",
    "Cadillac": "CAD",
    "Sauber": "SAU",
}

# Mapping pemasok mesin HARUS memperhitungkan musim.
# Untuk musim selain yang tercantum, kolom diisi "Unknown"
# agar tidak salah menganggap pemasok mesin sama antar-musim.
ENGINE_BY_SEASON = {
    2025: {
        "Racing Bulls": "Honda RBPT",
        "Red Bull Racing": "Honda RBPT",
        "Aston Martin": "Mercedes",
        "McLaren": "Mercedes",
        "Mercedes": "Mercedes",
        "Ferrari": "Ferrari",
        "Williams": "Mercedes",
        "Haas": "Ferrari",
        "Alpine": "Renault",
        "Sauber": "Ferrari",
    },
    2026: {
        "Racing Bulls": "Red Bull Ford",
        "Red Bull Racing": "Red Bull Ford",
        "Aston Martin": "Honda",
        "McLaren": "Mercedes",
        "Mercedes": "Mercedes",
        "Ferrari": "Ferrari",
        "Williams": "Mercedes",
        "Haas": "Ferrari",
        "Alpine": "Mercedes",
        "Audi": "Audi",
        "Cadillac": "Ferrari",
    },
}


def normalize_name(value):
    """Normalisasi nama tim agar toleran terhadap variasi penulisan."""
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def get_team_metadata(team_name, season):
    """Kembalikan (initial, engine) untuk nama tim dan musim tertentu."""
    normalized = normalize_name(team_name)
    for canonical, aliases in TEAM_ALIASES:
        if any(alias == normalized or alias in normalized for alias in aliases):
            return (
                TEAM_INITIALS[canonical],
                ENGINE_BY_SEASON.get(season, {}).get(canonical, "Unknown"),
            )

    # Nama tim tak dikenali: kode sementara, tanpa menebak jenis mesin.
    initial = re.sub(r"[^A-Z]", "", str(team_name).upper())[:3] or "UNK"
    return initial, "Unknown"


def get_circuit_name(season, round_number):
    """Ambil nama sirkuit sebenarnya; kegagalan API tidak menggagalkan hasil balapan."""
    url = f"https://api.jolpi.ca/ergast/f1/{season}/{round_number}/circuits/"
    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        circuits = response.json().get("MRData", {}).get("CircuitTable", {}).get("Circuits", [])
        return str(circuits[0].get("circuitName", "")) if circuits else ""
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        print(f"  Peringatan: nama sirkuit tidak dapat diambil: {exc}")
        return ""


def get_event_info(event, season, round_number):
    gp_name = re.sub(r" Grand Prix$", "", str(event.get("EventName", ""))).strip()
    gp_initial = "AUT GP" if gp_name in ("Austria", "Austrian") else gp_name[:3].upper() + " GP"
    return {
        "Round": round_number,
        "Season": season,
        "Grand Prix": gp_name,
        "Circuit Name": "",  # Diisi setelah hasil balapan dinyatakan valid.
        "City": str(event.get("Location", "")),
        "Nation": str(event.get("Country", "")),
        "GP Initial": gp_initial,
    }


def has_sprint(event):
    """Cek sesi bernama Sprint, bukan Sprint Qualifying saja."""
    return any(str(event.get(f"Session{i}", "")).strip().lower() == "sprint" for i in range(1, 6))


def get_team_results(season, round_number, session_code, race_type, event_info):
    """Agregasikan poin seluruh pembalap per tim untuk satu sesi."""
    print(f"\nMemproses {race_type}...", flush=True)

    try:
        session = fastf1.get_session(season, round_number, session_code)
        # Hanya membutuhkan klasifikasi hasil, tidak perlu lap/telemetry.
        session.load(laps=False, telemetry=False, weather=False, messages=False)
        results = session.results

        if results is None or results.empty:
            print(f"  Hasil {race_type} belum tersedia.")
            return []

        required = {"TeamName", "Points", "Position"}
        missing = required.difference(results.columns)
        if missing:
            print(f"  Data tidak lengkap; kolom hilang: {sorted(missing)}")
            return []

        # Hindari menulis data tim sebelum hasil resmi/klasifikasi tersedia.
        positions = pd.to_numeric(results["Position"], errors="coerce")
        if not positions.gt(0).any():
            print(f"  Klasifikasi {race_type} belum tersedia.")
            return []

        clean = results[["TeamName", "Points"]].copy()
        clean["TeamName"] = clean["TeamName"].fillna("").astype(str).str.strip()
        clean = clean[(clean["TeamName"] != "") & (clean["TeamName"].str.lower() != "nan")]
        clean["Points"] = pd.to_numeric(clean["Points"], errors="coerce").fillna(0)

        # Contoh: Ferrari (P1 = 25, P7 = 6) -> 31 poin tim.
        team_points = (
            clean.groupby("TeamName", as_index=False, sort=False)["Points"]
            .sum()
            .sort_values("Points", ascending=False, kind="stable")
        )

        rows = []
        for _, team in team_points.iterrows():
            team_name = team["TeamName"]
            team_initial, engine = get_team_metadata(team_name, season)
            rows.append(
                {
                    **event_info,
                    "Race Type": race_type,
                    "Team Name": team_name,
                    "Team Initial": team_initial,
                    "Engine Manufacture": engine,
                    "Race Points": float(team["Points"]),
                }
            )
            if engine == "Unknown":
                print(f"  Peringatan: pemasok mesin '{team_name}' musim {season} belum dipetakan.")

        print(f"  Berhasil: {len(rows)} tim.")
        return rows

    except Exception as exc:
        print(f"  Gagal mengambil {race_type}: {exc}")
        return []


def main():
    print("=" * 60)
    print("F1 TEAM RESULTS - MUSIM DAN ROUND TERTENTU")
    print(f"Season : {TARGET_SEASON}")
    print(f"Round  : {TARGET_ROUND}")
    print("=" * 60)

    if TARGET_SEASON < 1950 or TARGET_ROUND < 1:
        print("Konfigurasi musim/round tidak valid. File Excel tidak dibuat.")
        return

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    try:
        schedule = fastf1.get_event_schedule(TARGET_SEASON)
        matches = schedule.loc[pd.to_numeric(schedule["RoundNumber"], errors="coerce") == TARGET_ROUND]
    except Exception as exc:
        print(f"Gagal mengambil jadwal: {exc}")
        print("File Excel tidak dibuat.")
        return

    if matches.empty:
        print(f"Round {TARGET_ROUND} tidak ditemukan pada musim {TARGET_SEASON}.")
        print("File Excel tidak dibuat.")
        return

    event = matches.iloc[0]
    print(f"Grand Prix: {event.get('EventName', '')}")
    print(f"Lokasi    : {event.get('Location', '')}, {event.get('Country', '')}")

    event_info = get_event_info(event, TARGET_SEASON, TARGET_ROUND)
    sessions = []
    if has_sprint(event):
        sessions.append(("S", "Sprint"))
    sessions.append(("R", "Main Race"))

    all_team_data = []
    for session_code, race_type in sessions:
        all_team_data.extend(get_team_results(TARGET_SEASON, TARGET_ROUND, session_code, race_type, event_info))

    df = pd.DataFrame(all_team_data, columns=OUTPUT_COLUMNS)

    print("\n" + "=" * 60)
    if df.empty:
        print("Tidak ada data balapan yang berhasil diambil.")
        print("File Excel tidak dibuat.")
        print("=" * 60)
        return

    # Pengayaan circuit hanya dilakukan ketika hasil balapan tersedia.
    df["Circuit Name"] = get_circuit_name(TARGET_SEASON, TARGET_ROUND)

    # Sprint diletakkan sebelum Main Race, lalu urutkan poin tertinggi.
    df["_session_order"] = df["Race Type"].map({"Sprint": 0, "Main Race": 1})
    df = (
        df.sort_values(["_session_order", "Race Points"], ascending=[True, False])
        .drop(columns=["_session_order"])
        .reset_index(drop=True)
    )
    filename = f"F1_Team_{TARGET_SEASON}_Round_{TARGET_ROUND}.xlsx"
    try:
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Team Results", index=False)
            sheet = writer.sheets["Team Results"]
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cells in sheet.columns:
                column_letter = cells[0].column_letter
                max_length = max(len(str(cell.value or "")) for cell in cells)
                sheet.column_dimensions[column_letter].width = min(max_length + 3, 32)
    except Exception as exc:
        print(f"Gagal menyimpan Excel: {exc}")
        return

    print(f"Total data : {len(df)} baris")
    print("Jumlah tim per sesi:")
    print(df.groupby("Race Type", sort=False)["Team Name"].nunique().to_string())
    print(f"File output: {filename}")
    print("=" * 60)
    print("\nPreview:")
    print(df[["Race Type", "Team Name", "Team Initial", "Engine Manufacture", "Race Points"]].to_string(index=False))


if __name__ == "__main__":
    main()
