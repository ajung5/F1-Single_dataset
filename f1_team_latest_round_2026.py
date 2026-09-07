import os
from datetime import datetime

import pandas as pd
import fastf1
import requests
from bs4 import BeautifulSoup


# =====================================================================
# CONFIG
# =====================================================================

YEAR = 2026

# Folder cache FastF1
cache_dir = "f1_cache"
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

fastf1.Cache.enable_cache(cache_dir)


# =====================================================================
# MASTER LIST ENGINE MANUFACTURERS
# =====================================================================

KNOWN_ENGINES = [
    "Alfa Romeo",
    "Alta",
    "Aston Martin",
    "Audi",
    "BMW",
    "BRM",
    "Bugatti",
    "Climax",
    "Cosworth",
    "Cummins",
    "Ferrari",
    "Ford Cosworth",
    "Ford",
    "Gordini",
    "Hart",
    "Honda",
    "Hyundai",
    "Isotta Fraschini",
    "Judd",
    "Lamborghini",
    "Lancia",
    "Life",
    "Maserati",
    "Matra",
    "Mercedes",
    "Mugen Honda",
    "Offenhauser",
    "Porsche",
    "Pratt & Whitney",
    "Renault",
    "Repco",
    "Rover",
    "Simca-Gordini",
    "Subaru",
    "Supertec",
    "Talbot",
    "Tecno",
    "Toyota",
    "Vanwall",
    "Weslake",
    "Yamaha",
    "Red Bull Powertrains",
]

# Supaya nama yang lebih spesifik terdeteksi lebih dulu.
# Contoh: "Ford Cosworth" sebelum "Ford".
KNOWN_ENGINES = sorted(KNOWN_ENGINES, key=len, reverse=True)


# =====================================================================
# WEB SCRAPING & ENGINE MATCHING
# =====================================================================

def scrape_f1_engines(year):
    """Scraping tabel Wikipedia sebagai fallback data engine."""
    urls = [
        f"https://en.wikipedia.org/wiki/{year}_Formula_One_season",
        f"https://en.wikipedia.org/wiki/{year}_Formula_One_World_Championship",
    ]

    response = None

    for url in urls:
        try:
            response = requests.get(
                url,
                timeout=20,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                    )
                },
            )

            if response.status_code == 200:
                break
        except requests.RequestException:
            response = None

    if response is None or response.status_code != 200:
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    engine_map = {}

    tables = soup.find_all("table", {"class": "wikitable"})

    for table in tables:
        rows = table.find_all("tr")

        if not rows:
            continue

        # Header hanya dibaca dari baris pertama.
        header_cells = rows[0].find_all(["th", "td"])
        headers = [cell.get_text(" ", strip=True).lower() for cell in header_cells]

        if not (
            any("constructor" in h or "entrant" in h for h in headers)
            and any("engine" in h for h in headers)
        ):
            continue

        try:
            const_idx = next(
                i
                for i, h in enumerate(headers)
                if "constructor" in h or "entrant" in h
            )
            eng_idx = next(
                i for i, h in enumerate(headers)
                if "engine" in h
            )
        except StopIteration:
            continue

        for row in rows[1:]:
            cols = row.find_all(["td", "th"])

            if len(cols) <= max(const_idx, eng_idx):
                continue

            constructor = (
                cols[const_idx]
                .get_text(" ", strip=True)
                .split("[")[0]
                .strip()
                .lower()
            )

            engine = (
                cols[eng_idx]
                .get_text(" ", strip=True)
                .split("[")[0]
                .strip()
            )

            if constructor and engine:
                engine_map[constructor] = engine

        if engine_map:
            break

    return engine_map


def extract_engine(team_name, scraped_engine_map):
    """
    Urutan pencarian engine:
    1. Cari nama engine langsung dari nama team.
    2. Jika tidak ditemukan, gunakan mapping hasil scraping Wikipedia.
    """
    if not isinstance(team_name, str):
        return "Unknown"

    team_lower = team_name.lower()

    # Prioritas 1: berdasarkan nama team
    for engine in KNOWN_ENGINES:
        if engine.lower() in team_lower:
            return engine

    # Prioritas 2: fallback Wikipedia
    raw_scraped_engine = None

    if team_lower in scraped_engine_map:
        raw_scraped_engine = scraped_engine_map[team_lower]
    else:
        for constructor, engine in scraped_engine_map.items():
            if constructor in team_lower or team_lower in constructor:
                raw_scraped_engine = engine
                break

    if raw_scraped_engine:
        raw_engine_lower = raw_scraped_engine.lower()

        for engine in KNOWN_ENGINES:
            if engine.lower() in raw_engine_lower:
                return engine

        return raw_scraped_engine

    return "Unknown"


# =====================================================================
# HELPER
# =====================================================================

def get_event_session_names(event):
    """Mengambil nama-nama session dari satu row schedule FastF1."""
    names = []

    for col in (
        "Session1",
        "Session2",
        "Session3",
        "Session4",
        "Session5",
    ):
        if col in event.index and pd.notna(event[col]):
            names.append(str(event[col]).strip())

    return names


def event_has_sprint(event):
    """True jika GP tersebut mempunyai session Sprint."""
    return any(
        "sprint" in session_name.lower()
        for session_name in get_event_session_names(event)
    )


def get_latest_completed_round(year, schedule):
    """
    Mencari round TERBARU yang benar-benar sudah mempunyai
    hasil Main Race.

    Metode ini lebih aman dibanding hanya memakai tanggal schedule,
    karena race yang belum selesai / ditunda tidak akan dianggap selesai.
    """
    valid_events = schedule.copy()

    # Buang testing dan round 0.
    valid_events = valid_events[
        ~valid_events["EventName"].astype(str).str.contains(
            "Testing",
            case=False,
            na=False,
        )
    ]

    valid_events = valid_events[
        pd.to_numeric(
            valid_events["RoundNumber"],
            errors="coerce",
        ).fillna(0) > 0
    ]

    valid_events = valid_events.sort_values(
        "RoundNumber",
        ascending=False,
    )

    print("\nMencari round terbaru yang sudah selesai...")

    for _, event in valid_events.iterrows():
        round_number = int(event["RoundNumber"])
        event_name = str(event["EventName"])

        try:
            print(
                f"  Mengecek Round {round_number}: "
                f"{event_name}..."
            )

            session = fastf1.get_session(
                year,
                round_number,
                "R",
            )

            session.load(
                telemetry=False,
                weather=False,
                messages=False,
            )

            results = session.results

            if results is not None and not results.empty:
                print(
                    f"\nRound terbaru ditemukan: "
                    f"Round {round_number} - {event_name}"
                )

                return round_number, event

        except Exception:
            # Jika data race belum tersedia, lanjut cek round sebelumnya.
            continue

    return None, None


def process_session_teams(
    year,
    round_number,
    session_type,
    race_type_label,
    event,
    scraped_engine_map,
):
    """Mengambil data tim dari satu session."""
    rows = []

    try:
        session = fastf1.get_session(
            year,
            round_number,
            session_type,
        )

        session.load(
            telemetry=False,
            weather=False,
            messages=False,
        )

        results = session.results

        if results is None or results.empty:
            return rows

        res_df = results.copy()

        if (
            "TeamName" not in res_df.columns
            or "Points" not in res_df.columns
        ):
            return rows

        if "TeamAbbreviation" not in res_df.columns:
            res_df["TeamAbbreviation"] = (
                res_df["TeamName"]
                .astype(str)
                .str[:3]
                .str.upper()
            )

        team_grouped = (
            res_df.groupby(
                ["TeamName", "TeamAbbreviation"],
                as_index=False,
            )["Points"]
            .sum()
        )

        gp_name = (
            str(event["EventName"])
            .replace(" Grand Prix", "")
            .strip()
        )

        gp_initial = (
            "AUT GP"
            if ("Austria" in gp_name or gp_name == "Austrian")
            else gp_name[:3].upper() + " GP"
        )

        circuit_name = event.get("Location", "")
        city = event.get("Location", "")
        nation = event.get("Country", "")

        for _, team_row in team_grouped.iterrows():
            team_name = team_row["TeamName"]

            rows.append(
                {
                    "Round": round_number,
                    "Season": year,
                    "Grand Prix": gp_name,
                    "Circuit Name": circuit_name,
                    "City": city,
                    "Nation": nation,
                    "GP Initial": gp_initial,
                    "Race Type": race_type_label,
                    "Team Name": team_name,
                    "Team Initial": team_row["TeamAbbreviation"],
                    "Engine Manufacture": extract_engine(
                        team_name,
                        scraped_engine_map,
                    ),
                    "Race Points": team_row["Points"],
                }
            )

    except Exception as exc:
        print(
            f"  Gagal mengambil {race_type_label}: {exc}"
        )

    return rows


# =====================================================================
# MAIN PROGRAM
# =====================================================================

def main():
    print("=" * 70)
    print(
        f"F1 TEAM SEARCH - HANYA ROUND TERBARU MUSIM {YEAR}"
    )
    print("=" * 70)

    print(
        f"\nMengambil mapping engine untuk musim {YEAR}..."
    )
    yearly_engine_map = scrape_f1_engines(YEAR)

    print(
        f"Mengambil jadwal Formula 1 musim {YEAR}..."
    )

    try:
        schedule = fastf1.get_event_schedule(YEAR)
    except Exception as exc:
        print(
            f"Gagal mengambil schedule musim {YEAR}: {exc}"
        )
        return

    latest_round, latest_event = get_latest_completed_round(
        YEAR,
        schedule,
    )

    if latest_round is None:
        print(
            "\nTidak ditemukan round yang sudah memiliki hasil race."
        )
        return

    all_teams_data = []

    # Sprint hanya diproses jika event terbaru memang mempunyai Sprint.
    if event_has_sprint(latest_event):
        print(
            f"\nMemproses Sprint Round {latest_round}..."
        )

        all_teams_data.extend(
            process_session_teams(
                YEAR,
                latest_round,
                "S",
                "Sprint",
                latest_event,
                yearly_engine_map,
            )
        )

    print(
        f"Memproses Main Race Round {latest_round}..."
    )

    all_teams_data.extend(
        process_session_teams(
            YEAR,
            latest_round,
            "R",
            "Main Race",
            latest_event,
            yearly_engine_map,
        )
    )

    df_latest = pd.DataFrame(all_teams_data)

    if df_latest.empty:
        print(
            "\nTidak ada data tim yang berhasil dikumpulkan."
        )
        return

    desired_columns = [
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

    df_latest = df_latest[desired_columns]

    output_filename = (
        f"F1_Team_Latest_Round_{YEAR}_"
        f"R{latest_round}.xlsx"
    )

    df_latest.to_excel(
        output_filename,
        index=False,
    )

    print("\n" + "=" * 70)
    print(
        f"SELESAI - hanya Round {latest_round} yang diproses."
    )
    print(
        f"Total data: {len(df_latest)} baris"
    )
    print(
        f"Output    : {output_filename}"
    )
    print("=" * 70)

    print("\nPreview:")
    print(
        df_latest[
            [
                "Round",
                "Race Type",
                "Team Name",
                "Engine Manufacture",
                "Race Points",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
