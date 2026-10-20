# 🏛️ KOSITAS - Aplikasi Web Simpan Pinjam Syariah
### Koperasi Statistik Tasikmalaya (BPS Kabupaten Tasikmalaya)
*Jl. Raya Timur Singaparna KM. 4 Cintaraja, Kec. Singaparna, Tasikmalaya*

---

## 📖 Ringkasan & Latar Belakang

Aplikasi ini dikembangkan berdasarkan analisis mendalam terhadap **Buku Laporan Tahunan Rapat Anggota Tahunan (RAT) Tahun Buku 2025 KOSITAS BPS Kabupaten Tasikmalaya**. 

Sistem ini merealisasikan rekomendasi resmi Badan Pemeriksa KOSITAS (Laporan RAT hal. 16 butir 4):
> *"Aplikasi yang bisa diakses oleh seluruh anggota segera direalisasikan."*

Aplikasi mencakup manajemen lengkap simpanan, pembiayaan/pinjaman syariah, rekapitulasi pemotongan gaji kolektif bulanan untuk Admin, portal mandiri anggota, hingga pembagian SHU otomatis sesuai AD/ART KOSITAS.

---

## 🌟 Fitur Utama Sistem

### 1. 👥 Manajemen Keanggotaan (Master Data Anggota)
- Database terisi **38 Anggota Real KOSITAS** dari dokumen RAT 2025 (Ketua Gilang Abdul Aziz, Sekretaris Darojatun, Bendahara Erlina Hardiyanti, Badan Pemeriksa Dama Herdiaman & Deden Osep Dianar, dll).
- Entri anggota baru lengkap dengan penomoran otomatis `KST-xxx`, NIP, Jabatan BPS, Jenis Kelamin, No HP/WA, dan otomatisasi setoran **Simpanan Pokok awal Rp 25.000,-**.
- Filter status aktif/keluar dan pencarian cepat.

### 2. 💰 Pengelolaan Simpanan / Tabungan
Mendukung 5 jenis simpanan sesuai AD/ART KOSITAS:
1. **Simpanan Pokok**: Rp 25.000,- (dibayar 1x saat menjadi anggota).
2. **Simpanan Wajib**: Rp 100.000,- per bulan (rutin tiap bulan).
3. **Simpanan Hari Raya (Lebaran)**: Min. Rp 50.000,-/bln, dicairkan menjelang Idul Fitri.
4. **Simpanan Qurban**: Tabungan qurban tahunan, dicairkan menjelang Idul Adha.
5. **Simpanan Manasuka / Sukarela**: Fleksibel, dapat disetor & ditarik sewaktu-waktu.
- Form entri setor/tarik dengan indikator saldo real-time.
- Riwayat mutasi lengkap & tombol cetak kuitansi transaksi resmi.

### 3. 💳 Pengelolaan Pinjaman & Pembiayaan Syariah
Mendukung 4 produk pembiayaan KOSITAS:
1. **JAPAN (Jangka Panjang)**: Plafon s.d Rp 30.000.000, tenor s.d 30 bulan, Provisi 1%, DRK (Dana Risiko Kredit) 0.5%, margin syariah.
2. **JAPEN (Jangka Pendek)**: Plafon s.d Rp 7.000.000, tenor s.d 10 bulan, Provisi 1%.
3. **Bon Putih (Pinjaman Kas/Lainnya)**: Maks Rp 1.000.000, margin 2%/bulan.
4. **Pinjaman Barang**: Plafon s.d Rp 7.500.000, tenor s.d 10 bulan, margin koperasi rata-rata 20%.
- Kalkulator simulasi kredit live: otomatis menghitung angsuran pokok, margin, provisi, DRK, dan dana bersih yang diterima.
- Kartu pinjaman digital dengan progress bar pelunasan & pencatatan angsuran.

### 4. 📅 Rekap Transaksi Bulanan & Tahunan Kolektif (Admin Payroll Deduction)
- **Filter Fleksibel Bulanan & Tahunan**:
  * **Mode Bulanan**: Menampilkan rincian potongan gaji dan setoran per bulan (`YYYY-MM`). Admin dapat mengeksekusi potong gaji serentak 1-klik untuk seluruh anggota aktif.
  * **Mode Tahunan Penuh**: Menampilkan akumulasi setoran dan potongan 12 bulan per anggota untuk tahun buku tertentu (2025, 2026, 2027) lengkap dengan catatan pelunasan/top-up.
- **Pengecualian Otomatis Pinjaman Lunas**: Pinjaman yang telah dilunasi dipercepat secara otomatis tidak dipotong lagi dari gaji bulanan.
- **Penyesuaian Otomatis Pinjaman Top Up**: Pinjaman lama otomatis ditutup dan cicilan bulanan langsung beralih ke kontrak pinjaman baru.
- Ekspor rekap bulanan dan tahunan ke **Excel (.xlsx)** berformat resmi.
- Cetak format A4 siap arsip.

### 5. ⚡ Pelunasan Dipercepat & Top Up Pembiayaan
- **Pelunasan Dipercepat (Early Settlement)**:
  * Pelunasan lunas sisa pokok kredit sekaligus sebelum jatuh tempo.
  * Opsi diskon/keringanan margin (*Ibra'* syariah) untuk sisa margin ke depan.
  * Otomatis menghentikan pemotongan rutin payroll pada bulan-bulan berikutnya.
  * Mencetak **Surat Keterangan Pelunasan Pinjaman** resmi.
- **Top Up Pembiayaan (Refinancing)**:
  * Peminjaman ulang pada koperasi dengan melunasi sisa pokok pinjaman sebelumnya.
  * Kalkulator pencairan bersih live: `Plafon Baru - Sisa Pokok Lama - Provisi (1%) - DRK (0.5%)`.
  * Pinjaman lama otomatis ditutup (*Lunas Top Up*), pinjaman baru mulai berjalan.
  * Mencetak **Bukti Realisasi & Akad Top Up Pembiayaan**.

### 6. 👤 Portal Mandiri Anggota (Member Area) & Cetak Slip Ganda
- **Dashboard Pribadi**: Ringkasan saldo simpanan, sisa pokok hutang, dan estimasi pembagian SHU.
- **Buku Tabungan Digital**: Rincian mutasi simpanan per tanggal & per jenis tabungan.
- **Kartu Pinjaman Digital**: Histori cicilan, rincian sisa pinjaman, tombol pengajuan pelunasan/top up, dan jadwal angsuran.
- **Slip Ganda per Periode Bulan**:
  1. **Slip Potongan Gaji Koperasi Bulanan**: Rincian pemotongan simpanan wajib, sukarela, dan cicilan pinjaman dari payroll BPS (dilengkapi catatan jika pinjaman telah lunas/top up).
  2. **Slip Setoran Tabungan Bulanan**: Rincian setoran tabungan bulan berjalan beserta posisi saldo akumulatif per jenis simpanan terkini.
- **Layanan Pengajuan Mandiri Online**: Form pengajuan pinjaman & penarikan simpanan yang masuk ke antrean verifikasi pengurus.

### 7. 📊 Laporan RAT KOSITAS Resmi
Format laporan presisi persis Buku Laporan RAT 2025:
- **Rekapitulasi Simpanan Anggota** (RAT Hal. 14-15) - Total Rp 476.247.125,-
- **Data Piutang Anggota** (RAT Hal. 16-17) - Total Rp 355.015.987,-
- **Daftar Pembagian SHU Anggota** (RAT Hal. 13 & 24-25) - Jasa Modal 50% & Jasa Pinjaman 50%
- Semua laporan dilengkapi fitur **Unduh Excel (.xlsx)** dan **Cetak PDF**.

---

## ⚡ Cara Menjalankan & Mengakses

Server saat ini **sudah aktif berjalan di background**:
- **URL Akses**: [http://localhost:5000](http://localhost:5000) atau [http://127.0.0.1:5000](http://127.0.0.1:5000)

### Akun Login Demo:
1. **Administrator / Pengurus**:
   - Username: `admin`
   - Password: `admin` (atau `123456`)
2. **Akun Anggota**:
   - Dapat login menggunakan **No Anggota** (contoh: `KST-007` untuk Gilang Abdul Aziz, `KST-019` untuk Erlina Hardiyanti, `KST-016` untuk Irwan Setiawan, dll)
   - Password: `123456`
3. **Fitur Instant Switcher**:
   - Tersedia tombol **"Ganti Akun Demo"** di bilah atas (topbar) untuk beralih instan antara Admin dan anggota manapun dengan 1 klik tanpa harus mengetik password!
