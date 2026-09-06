import os
import pandas as pd
import fastf1
import requests
from bs4 import BeautifulSoup

# 1. Aktifkan cache untuk menghindari pengunduhan ulang data
cache_dir = 'f1_cache'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
fastf1.Cache.enable_cache(cache_dir)

# =====================================================================
# MASTER LIST ENGINE MANUFACTURERS (Sesuai masukan Anda)
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
    "Red Bull Powertrains"
]

# Trik Data Analis: Urutkan list berdasarkan panjang string menurun.
# Tujuannya agar "Ford Cosworth" terdeteksi lebih dulu sebelum "Ford",
# dan "Mugen Honda" terdeteksi sebelum "Honda".
KNOWN_ENGINES = sorted(KNOWN_ENGINES, key=len, reverse=True)


# =====================================================================
# FUNGSI WEB SCRAPING & PENCOCOKAN ENGINE
# =====================================================================
def scrape_f1_engines(year):
    """ Scraping tabel Wikipedia sebagai Fallback (cadangan) """
    url = f"https://en.wikipedia.org/wiki/{year}_Formula_One_season"
    response = requests.get(url)
    
    if response.status_code != 200:
        url = f"https://en.wikipedia.org/wiki/{year}_Formula_One_World_Championship"
        response = requests.get(url)
        
    soup = BeautifulSoup(response.text, 'html.parser')
    engine_map = {}
    
    tables = soup.find_all('table', {'class': 'wikitable'})
    for table in tables:
        headers = [th.text.strip().lower() for th in table.find_all(['th', 'td'])]
        if any('constructor' in h or 'entrant' in h for h in headers) and any('engine' in h for h in headers):
            try:
                const_idx = next(i for i, h in enumerate(headers) if 'constructor' in h or 'entrant' in h)
                eng_idx = next(i for i, h in enumerate(headers) if 'engine' in h)
                
                rows = table.find_all('tr')[1:]
                for row in rows:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) > max(const_idx, eng_idx):
                        constructor = cols[const_idx].text.strip().split('\n')[0].split('[')[0].strip().lower()
                        engine = cols[eng_idx].text.strip().split('\n')[0].split('[')[0].strip()
                        engine_map[constructor] = engine
                break 
            except Exception:
                pass 
    return engine_map

def extract_engine(team_name, scraped_engine_map):
    """
    Logika Ekstraksi Mesin:
    1. Cek langsung nama tim pakai Master List KNOWN_ENGINES.
    2. Jika tidak ketemu, fallback ke hasil Wikipedia, lalu bersihkan namanya.
    """
    if not isinstance(team_name, str):
        return "Unknown"
        
    team_lower = team_name.lower()
    
    # Prioritas 1: Cari dari kata di dalam nama Tim (berdasarkan list Anda)
    for engine in KNOWN_ENGINES:
        if engine.lower() in team_lower:
            return engine # Mengembalikan nama dengan huruf kapital yang rapi
            
    # Prioritas 2: Fallback ke data scraping Wikipedia
    raw_scraped_engine = None
    if team_lower in scraped_engine_map:
        raw_scraped_engine = scraped_engine_map[team_lower]
    else:
        # Coba pencocokan parsial di dictionary wikipedia
        for const, eng in scraped_engine_map.items():
            if const in team_lower or team_lower in const:
                raw_scraped_engine = eng
                break

    # Standardisasi hasil scraping menggunakan master list (jika memungkinkan)
    if raw_scraped_engine:
        raw_scraped_lower = raw_scraped_engine.lower()
        for engine in KNOWN_ENGINES:
            if engine.lower() in raw_scraped_lower:
                return engine
        return raw_scraped_engine # Jika tidak ada di list master, kembalikan data raw wikipedia
        
    return "Unknown"
# =====================================================================

# Rentang Waktu (Bisa disesuaikan)
start_year = 2026
end_year = 2026

all_teams_data = []

print(f"Memulai pengambilan data Klasemen Tim F1 dari tahun {start_year} hingga {end_year}...\n")

for year in range(start_year, end_year + 1):
    print("=" * 60)
    
    if year < 1958:
        print(f"Musim {year}: Kejuaraan Konstruktor belum diselenggarakan sebelum 1958. Melewati...")
        continue

    has_sprint = year >= 2021
    
    # 1. Scrape Wikipedia sekali di setiap awal musim
    print(f"Musim {year}: Melakukan scraping data fallback dari Wikipedia...")
    yearly_engine_map = scrape_f1_engines(year)
    
    print(f"Musim {year}: Mengambil jadwal balapan...")
    try:
        schedule = fastf1.get_event_schedule(year)
    except Exception as e:
        print(f"Gagal mengambil jadwal untuk tahun {year}: {e}")
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
        
        def process_session_teams(session_type, race_type_label):
            try:
                session = fastf1.get_session(year, round_number, session_type)
                if session:
                    session.load(telemetry=False, weather=False, messages=False)
                    results = session.results
                    
                    if results is not None and not results.empty:
                        res_df = results.copy()
                        
                        if 'TeamName' in res_df.columns and 'Points' in res_df.columns:
                            if 'TeamAbbreviation' not in res_df.columns:
                                res_df['TeamAbbreviation'] = res_df['TeamName'].apply(lambda x: str(x)[:3].upper())
                            
                            team_grouped = res_df.groupby(['TeamName', 'TeamAbbreviation'], as_index=False)['Points'].sum()
                            
                            for _, t_row in team_grouped.iterrows():
                                team_name_str = t_row['TeamName']
                                
                                # EKSEKUSI PENCARIAN ENGINE BERDASARKAN MASTER LIST
                                engine_manufacturer = extract_engine(team_name_str, yearly_engine_map)
                                
                                all_teams_data.append({
                                    'Round': round_number,
                                    'Season': year,
                                    'Grand Prix': gp_name,
                                    'Circuit Name': circuit_name,
                                    'City': city,
                                    'Nation': nation,
                                    'GP Initial': gp_initial,
                                    'Race Type': race_type_label,
                                    'Team Name': team_name_str,
                                    'Team Initial': t_row['TeamAbbreviation'],
                                    'Engine Manufacture': engine_manufacturer,
                                    'Race Points': t_row['Points']
                                })
            except Exception:
                pass 

        if has_sprint:
            print(f"  [{year}] Memproses Sprint Race Round {round_number}...")
            process_session_teams('S', 'Sprint')

        print(f"  [{year}] Memproses Main Race Round {round_number}...")
        process_session_teams('R', 'Main Race')

# Gabungkan & Simpan
df_all_teams = pd.DataFrame(all_teams_data)

if not df_all_teams.empty:
    desired_columns = [
        'Round', 'Season', 'Grand Prix', 'Circuit Name', 
        'City', 'Nation', 'GP Initial', 'Race Type', 
        'Team Name', 'Team Initial', 'Engine Manufacture', 'Race Points'
    ]
    df_all_teams = df_all_teams[desired_columns]

    output_filename = f'F1_Team_Standings_{start_year}_to_{end_year}.xlsx'
    df_all_teams.to_excel(output_filename, index=False)

    print("\n" + "=" * 60)
    print(f"Selesai! Total {len(df_all_teams)} baris data berhasil disimpan ke: {output_filename}")
    print("=" * 60)
else:
    print("\nTidak ada data yang berhasil dikumpulkan.")