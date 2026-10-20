@echo off
title KOSITAS - Koperasi Simpan Pinjam Syariah BPS Kabupaten Tasikmalaya
color 0a
echo =========================================================================
echo         KOSITAS - PORTAL SIMPAN PINJAM SYARIAH BPS TASIKMALAYA
echo =========================================================================
echo.
echo Memeriksa database...
if not exist kositas.db (
    echo Menginisialisasi database dan memasukkan data awal...
    python seed_data.py
)
echo.
echo =========================================================================
echo  INFORMASI TAUTAN AKSES APLIKASI:
echo.
echo  [1] Dari Komputer Ini (Lokal)       : http://localhost:5000 atau http://127.0.0.1:5000
echo  [2] Dari Komputer / HP Lain (Jaringan) : http://192.168.200.9:5000
echo.
echo  *Pastikan komputer / HP lain berada di jaringan Wi-Fi / LAN yang sama.
echo  *Jika komputer/HP lain tidak bisa membuka, jalankan file:
echo   IZINKAN_FIREWALL_PORT_5000.bat (Klik kanan -^> Run as Administrator)
echo =========================================================================
echo.
echo Menjalankan server aplikasi... Tekan CTRL + C untuk menghentikan server.
echo.
python app.py
pause
