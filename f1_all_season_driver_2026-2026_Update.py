import os
import pandas as pd
import fastf1

# 1. Aktifkan cache untuk efisiensi pengunduhan data
cache_dir = 'f1_cache'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
fastf1.Cache.enable_cache(cache_dir)

# Rentang tahun
start_year = 2026
end_year = 2026

all_races_data = []

print(f"Memulai pengambilan data F1 dari tahun {start_year} hingga {end_year}...\n")

for year in range(start_year, end_year + 1):
    print("=" * 50)
    has_sprint = year >= 2021
    
    try:
        schedule = fastf1.get_event_schedule(year)
    except Exception as e:
        print(f"Gagal mengambil jadwal tahun {year}: {e}")
        continue

    for index, event in schedule.iterrows():
        if 'Testing' in str(event['EventName']):
            continue
            
        round_number = event['RoundNumber']
        gp_name = str(event['EventName']).replace(' Grand Prix', '').strip()
        
        if round_number < 1:
            continue
            
        gp_initial = 'AUT GP' if ('Austria' in gp_name or gp_name == 'Austrian') else gp_name[:3].upper() + ' GP'
        circuit_name = event.get('Location', '') 
        city = event.get('Location', '') 
        nation = event.get('Country', '')
        
        # Tentukan sesi yang diproses
        sessions_to_process = []
        if has_sprint:
            sessions_to_process.append(('Sprint', 'S'))
        sessions_to_process.append(('Main Race', 'R'))
        
        for race_type, session_code in sessions_to_process:
            try:
                session = fastf1.get_session(year, round_number, session_code)
                if not session:
                    continue
                
                print(f"  [{year}] Memproses [{race_type}] Round {round_number}: {gp_name}...")
                
                # Muat data lap untuk mencari pemegang lap tercepat
                session.load(laps=True, telemetry=False, weather=False, messages=False)
                results = session.results
                
                # --- Cari siapa pencetak Fastest Lap di seluruh sesi ini ---
                fastest_driver_code = None
                try:
                    # Mengambil 1 lap paling cepat dari seluruh pembalap di sesi ini
                    overall_fastest_lap = session.laps.pick_fastest()
                    if overall_fastest_lap is not None:
                        fastest_driver_code = overall_fastest_lap['Driver']
                except Exception:
                    pass

                # Looping tiap pembalap dalam hasil balapan
                for idx, row in results.iterrows():
                    driver_code = row.get('Abbreviation', '')
                    
                    # Cek apakah pembalap ini yang mencetak lap tercepat (1 jika YA, 0 jika TIDAK)
                    is_fastest_lap = 1 if (fastest_driver_code and driver_code == fastest_driver_code) else 0

                    # Ambil Grid Position
                    grid_pos = row.get('GridPosition', None)
                    if pd.isna(grid_pos) or grid_pos == 0:
                        grid_pos = None
                    else:
                        grid_pos = int(grid_pos)

                    all_races_data.append({
                        'Round': round_number,
                        'Season': year,
                        'IsLatestSeason': 0,
                        'Grand Prix': gp_name,
                        'Circuit Name': circuit_name,
                        'City': city,
                        'Nation': nation,
                        'GP Initial': gp_initial,
                        'Race Type': race_type,
                        'Driver Name': row.get('FullName', ''),
                        'Last Name': row.get('LastName', ''),
                        'Driver Initial': driver_code,
                        'Grid Position': grid_pos,
                        'Finish Position': row.get('Position', None),
                        'Race Points': row.get('Points', 0),
                        'Fastest Lap': is_fastest_lap  # Berisi 1 atau 0
                    })
            except Exception as e:
                print(f"  [{year}] Gagal mengambil {race_type} untuk {gp_name}: {e}")

# 4. Simpan Data ke Excel
df_all_races = pd.DataFrame(all_races_data)
output_filename = f'F1_All_Races_{start_year}_to_{end_year}.xlsx'
df_all_races.to_excel(output_filename, index=False)

print("\n" + "=" * 50)
print(f"Selesai! Data berhasil disimpan ke: {output_filename}")
print("=" * 50)