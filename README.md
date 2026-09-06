# F1 Historical Data Explorer 🏎️

Repositori ini menyediakan kerangka kerja (*framework*) lengkap dan REST API untuk mengekstrak, memproses, menyimpan, dan menganalisis data historis Formula 1. Proyek ini mencakup statistik komprehensif mengenai pembalap, tim (konstruktor), dan hasil balapan dari masa ke masa.

## ✨ Fitur Utama

* **Analisis Pembalap (Driver):** Melacak riwayat karir pembalap, total kemenangan, *pole position*, jumlah poin, dan riwayat perpindahan tim.
* **Analisis Konstruktor (Team):** Menyediakan data gelar juara dunia, daftar pembalap per musim, pergantian nama tim, dan statistik pemasok mesin (*engine supplier*).
* **Data Balapan & Musim:** Rekapitulasi hasil balapan tiap seri, posisi *grid* vs *finish*, *fastest lap*, waktu balapan, dan status *Did Not Finish* (DNF).
* **REST API Bawaan:** Endpoint siap pakai (dibangun menggunakan FastAPI) untuk menyajikan data historis ke aplikasi *front-end* atau analitik.
* **Sistem Caching & Database:** Penyimpanan data lokal untuk mengurangi panggilan API berulang (*rate-limiting*) ke penyedia data pihak ketiga.

## 🛠️ Teknologi yang Digunakan

* **Bahasa:** Python 3.9+
* **Framework API:** FastAPI & Uvicorn
* **Pengolahan Data:** Pydantic (Validasi Skema), Pandas
* **Database/Cache:** SQLite / PostgreSQL, Redis (Opsional)
* **Sumber Data Eksternal:** [Ergast F1 API / Jolpica](https://ergast.com/mrd/) & [OpenF1](https://openf1.org/)

## 📁 Struktur Proyek

```text
f1-historical-data/
├── config/             # Konfigurasi sistem (API, DB, caching)
├── src/                # Kode sumber utama
│   ├── clients/        # Pengambil data dari provider eksternal
│   ├── models/         # Skema data (Driver, Constructor, Race)
│   ├── database/       # Operasi database lokal
│   ├── services/       # Logika bisnis dan agregasi data
│   └── api/            # Endpoint REST API (FastAPI)
├── scripts/            # Skrip otomatisasi ETL & seeding data awal
├── tests/              # Unit test dan Integration test
├── requirements.txt    # Daftar dependensi Python
└── README.md           # Dokumentasi proyek

```

####### 🚀 Prasyarat & Instalasi #######
Kloning Repositori:
```Bash
git clone [https://github.com/username-anda/f1-historical-data.git](https://github.com/username-anda/f1-historical-data.git)
cd f1-historical-data
```

* Buat Virtual Environment (Opsional tapi disarankan):
```Bash
python -m venv venv
source venv/bin/activate  # Untuk Linux/Mac
venv\Scripts\activate     # Untuk Windows
```

* Instal Dependensi:
```Bash
pip install -r requirements.txt
```
* Atur Environment Variables:
Salin file .env.example menjadi .env dan sesuaikan konfigurasinya (koneksi database, dll).
```Bash
cp .env.example .env
```

💻 Cara Penggunaan
1. Melakukan Seeding Data Awal (ETL)
Untuk mengunduh dan menyinkronkan data historis awal ke database lokal Anda, jalankan skrip seeder:
```Bash
python scripts/seed_data.py
```
2. Menjalankan REST API Server
Jalankan server pengembangan FastAPI menggunakan Uvicorn:

Bash
uvicorn src.api.app:app --reload
API sekarang dapat diakses di http://127.0.0.1:8000. Anda dapat melihat dokumentasi API interaktif (Swagger UI) di http://127.0.0.1:8000/docs.

📡 Contoh Endpoint API
GET /api/v1/drivers/{driver_id} - Mendapatkan profil dan statistik karir pembalap (misal: max_verstappen).

GET /api/v1/teams/{team_id}/history - Mendapatkan riwayat tim dan pemasok mesin.

GET /api/v1/races?year=2023&round=1 - Mendapatkan hasil balapan spesifik.

GET /api/v1/compare/drivers?d1=hamilton&d2=alonso - Membandingkan statistik head-to-head dua pembalap.

🤝 Kontribusi
Kontribusi selalu dipersilakan! Silakan buat Pull Request atau buka Issue untuk mendiskusikan perubahan, penambahan fitur, atau perbaikan bug.
