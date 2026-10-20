@echo off
:: Batch script untuk membuka port 5000 di Windows Firewall
:: Agar komputer / HP lain dalam 1 jaringan LAN/Wi-Fi dapat mengakses KOSITAS

title Konfigurasi Firewall Port 5000 - KOSITAS
echo =========================================================================
echo    MEMBUKA PORT 5000 DI WINDOWS FIREWALL (AKSES JARINGAN KANTOR/WIFI)
echo =========================================================================
echo.

:: Memeriksa hak Administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Berjalan sebagai Administrator.
) else (
    echo [PERHATIAN] Script ini membutuhkan hak Administrator.
    echo Klik kanan file ini lalu pilih "Run as administrator" (Jalankan sebagai administrator).
    echo.
    pause
    exit /b 1
)

echo Membuka port TCP 5000 untuk profil Private dan Domain...
netsh advfirewall firewall add rule name="KOSITAS Port 5000" dir=in action=allow protocol=TCP localport=5000 profile=any

if %errorLevel% == 0 (
    echo.
    echo =========================================================================
    echo  BERHASIL! Port 5000 telah dibuka di Windows Firewall.
    echo  Sekarang komputer / HP lain dalam jaringan (LAN/Wi-Fi)
    echo  sudah dapat membuka aplikasi KOSITAS di:
    echo  http://192.168.200.9:5000
    echo =========================================================================
) else (
    echo.
    echo [ERROR] Gagal menambahkan aturan firewall. Pastikan Anda menjalankan sebagai Administrator.
)

echo.
pause
