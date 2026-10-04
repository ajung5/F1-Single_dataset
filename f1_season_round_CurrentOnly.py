import os
import pandas as pd
import fastf1

# =========================================================
# KONFIGURASI
# =========================================================

TARGET_SEASON = 2017
TARGET_ROUND = 21

CACHE_DIR = "f1_cache"


# =========================================================
# FORMAT KOLOM OUTPUT
# =========================================================

OUTPUT_COLUMNS = [
    "Round",
    "Season",
    "IsLatestSeason",
    "Grand Prix",
    "Circuit Name",
    "City",
    "Nation",
    "GP Initial",
    "Race Type",
    "Driver Name",
    "Last Name",
    "Driver Initial",
    "Grid Position",
    "Finish Position",
    "Race Points",
    "Fastest Lap",
]


# =========================================================
# 1. AKTIFKAN CACHE FASTF1
# =========================================================

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

fastf1.Cache.enable_cache(CACHE_DIR)


# =========================================================
# 2. AMBIL JADWAL MUSIM
# =========================================================

all_races_data = []

print("=" * 60)
print("PENGAMBILAN DATA FORMULA 1")
print("=" * 60)

print(f"Season : {TARGET_SEASON}")
print(f"Round  : {TARGET_ROUND}")
print()


try:
    schedule = fastf1.get_event_schedule(TARGET_SEASON)

except Exception as e:
    print(f"Gagal mengambil jadwal musim {TARGET_SEASON}: {e}")
    schedule = None


# =========================================================
# 3. CARI EVENT BERDASARKAN ROUND
# =========================================================

if schedule is not None:

    target_event = schedule[schedule["RoundNumber"] == TARGET_ROUND]

    if target_event.empty:

        print(f"Round {TARGET_ROUND} tidak ditemukan " f"pada musim {TARGET_SEASON}.")

    else:

        # Karena satu round hanya memiliki satu event
        event = target_event.iloc[0]

        round_number = int(event["RoundNumber"])

        gp_name = str(event["EventName"]).replace(" Grand Prix", "").strip()

        circuit_name = event.get("Location", "")
        city = event.get("Location", "")
        nation = event.get("Country", "")

        # =================================================
        # GP INITIAL
        # =================================================

        if "Austria" in gp_name or gp_name == "Austrian":
            gp_initial = "AUT GP"
        else:
            gp_initial = gp_name[:3].upper() + " GP"

        print(f"Grand Prix : {gp_name}")
        print(f"Location   : {city}")
        print(f"Country    : {nation}")
        print()

        # =================================================
        # 4. DETEKSI SESSION YANG TERSEDIA
        # =================================================

        available_sessions = []

        for i in range(1, 6):

            session_name = event.get(f"Session{i}", None)

            if session_name is not None and not pd.isna(session_name):
                available_sessions.append(str(session_name))

        print("Session tersedia:", ", ".join(available_sessions))

        # =================================================
        # SESSION YANG AKAN DIPROSES
        # =================================================

        sessions_to_process = []

        # Sprint hanya diproses jika benar-benar tersedia
        if "Sprint" in available_sessions:
            sessions_to_process.append(("Sprint", "S"))

        # Main Race selalu dicoba
        sessions_to_process.append(("Main Race", "R"))

        # =================================================
        # 5. PROSES SETIAP SESSION
        # =================================================

        for race_type, session_code in sessions_to_process:

            try:

                print()
                print(f"[{TARGET_SEASON}] " f"Memproses [{race_type}] " f"Round {TARGET_ROUND}: {gp_name}...")

                # =========================================
                # AMBIL SESSION
                # =========================================

                session = fastf1.get_session(TARGET_SEASON, TARGET_ROUND, session_code)

                # =========================================
                # LOAD DATA
                # =========================================

                session.load(laps=True, telemetry=False, weather=False, messages=False)

                results = session.results

                # =========================================
                # CARI FASTEST LAP
                # =========================================

                fastest_driver_code = None

                try:

                    overall_fastest_lap = session.laps.pick_fastest()

                    if overall_fastest_lap is not None:

                        fastest_driver_code = overall_fastest_lap["Driver"]

                except Exception as e:

                    print(f"  Fastest lap tidak dapat " f"ditentukan: {e}")

                # =========================================
                # LOOP SETIAP DRIVER
                # =========================================

                for _, row in results.iterrows():

                    driver_code = row.get("Abbreviation", "")

                    # =====================================
                    # FASTEST LAP FLAG
                    # =====================================

                    is_fastest_lap = 1 if (fastest_driver_code and driver_code == fastest_driver_code) else 0

                    # =====================================
                    # GRID POSITION
                    # =====================================

                    grid_pos = row.get("GridPosition", None)

                    if pd.isna(grid_pos) or grid_pos == 0:

                        grid_pos = None

                    else:

                        grid_pos = int(grid_pos)

                    # =====================================
                    # SIMPAN DATA
                    # =====================================

                    all_races_data.append(
                        {
                            "Round": round_number,
                            "Season": TARGET_SEASON,
                            "IsLatestSeason": 1,
                            "Grand Prix": gp_name,
                            "Circuit Name": circuit_name,
                            "City": city,
                            "Nation": nation,
                            "GP Initial": gp_initial,
                            "Race Type": race_type,
                            "Driver Name": row.get("FullName", ""),
                            "Last Name": row.get("LastName", ""),
                            "Driver Initial": driver_code,
                            "Grid Position": grid_pos,
                            "Finish Position": row.get("Position", None),
                            "Race Points": row.get("Points", 0),
                            "Fastest Lap": is_fastest_lap,
                        }
                    )

                print(f"  Berhasil: " f"{len(results)} driver.")

            except Exception as e:

                print(f"  Gagal mengambil {race_type} " f"untuk {gp_name}: {e}")


# =========================================================
# 6. BUAT DATAFRAME
# =========================================================

df_all_races = pd.DataFrame(all_races_data, columns=OUTPUT_COLUMNS)


# =========================================================
# 7. CEK DATA & SIMPAN KE EXCEL
# =========================================================

print()
print("=" * 60)

if df_all_races.empty:

    print("Tidak ada data balapan yang berhasil diambil.")
    print("File Excel tidak dibuat.")

else:

    output_filename = f"F1_{TARGET_SEASON}_Round_{TARGET_ROUND}.xlsx"

    df_all_races.to_excel(output_filename, index=False)

    print(f"Total data : " f"{len(df_all_races)} baris")

    print()
    print("Race Type:")

    print(df_all_races["Race Type"].value_counts())

    print()
    print(f"File output: {output_filename}")

print("=" * 60)
