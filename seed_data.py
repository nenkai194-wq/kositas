import sqlite3
from database import DB_PATH, init_db

def run_seed():
    # Re-initialize fresh database schema
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing data if any
    cursor.execute("DELETE FROM angsuran_pinjaman")
    cursor.execute("DELETE FROM pinjaman")
    cursor.execute("DELETE FROM transaksi_simpanan")
    cursor.execute("DELETE FROM pengajuan_online")
    cursor.execute("DELETE FROM billing_bulanan_log")
    cursor.execute("DELETE FROM anggota")

    # Insert Special Admin User (Pengurus KOSITAS)
    cursor.execute('''
    INSERT INTO anggota (id, no_anggota, nama, nip, jabatan, jenis_kelamin, no_hp, email, alamat, tanggal_masuk, status, password, role)
    VALUES (999, 'ADM-001', 'Administrator KOSITAS', '198501012010011001', 'Pengurus Koperasi', 'Pria', '081234567890', 'admin@kositas.bps.go.id', 'Kantor BPS Singaparna', '2024-01-01', 'Aktif', 'admin', 'admin')
    ''')

    # Data 38 Anggota Real KOSITAS dari Laporan RAT 2025
    # Format: (no_urut, nama, jabatan, jk, status, pokok, wajib, manasuka, lebaran, qurban, japan, japen, bon_putih, barang, jasa_dibayar)
    raw_members = [
        (1, "Dama Herdiaman", "Badan Pemeriksa", "Pria", "Aktif", 25000, 4224500, 0, 1100000, 0, 0, 0, 5020000, 0, 1471776),
        (2, "Darojatun", "Sekretaris", "Pria", "Aktif", 25000, 14215000, 0, 550000, 0, 24166680, 6000000, 8834500, 6000000, 2920224),
        (4, "Dede Yusuf Tauhidi", "Anggota", "Pria", "Aktif", 25000, 14215000, 0, 1500000, 0, 0, 500000, 5500000, 0, 1320000),
        (5, "Elis Komala, S.Sos", "Mantan Anggota", "Wanita", "Keluar", 0, 0, 0, 0, 0, 0, 0, 0, 0, 20000),
        (6, "Nani Hendrayani, S.IP", "Anggota", "Wanita", "Aktif", 25000, 14215000, 0, 9000000, 2450000, 0, 0, 0, 0, 0),
        (7, "Gilang Abdul Aziz, SE, MP", "Ketua Koperasi", "Pria", "Aktif", 25000, 13535000, 1598625, 3000000, 2100000, 20000004, 0, 7500000, 2201425, 3275000),
        (9, "Gin Gin Ginanjar S, A.Md", "Anggota", "Pria", "Aktif", 25000, 12535000, 0, 7000000, 0, 0, 0, 1500000, 0, 0),
        (10, "Andri Irawan, SM", "Anggota", "Pria", "Aktif", 25000, 12535000, 0, 3300000, 0, 24166669, 0, 500000, 0, 3851669),
        (12, "Deden Osep Dianar, SE", "Ketua Badan Pemeriksa", "Pria", "Aktif", 25000, 12205000, 0, 2750000, 0, 10000000, 0, 0, 0, 0),
        (13, "Iman Barkah, ST", "Anggota", "Pria", "Aktif", 25000, 12205000, 0, 1100000, 0, 0, 0, 0, 0, 460000),
        (14, "Achmad Maoshul, SP", "Anggota", "Pria", "Aktif", 25000, 12205000, 0, 3000000, 0, 0, 0, 0, 0, 0),
        (15, "Siti Hayati Nufus, A.Md", "Anggota", "Wanita", "Aktif", 25000, 12205000, 4600000, 6400000, 2450000, 2000000, 0, 0, 0, 480000),
        (16, "Irwan Setiawan, S.Kom", "Anggota", "Pria", "Aktif", 25000, 12205000, 0, 2900000, 0, 26832996, 0, 0, 0, 5250871),
        (17, "Tia Setiawan, A.Md", "Anggota", "Wanita", "Aktif", 25000, 12205000, 0, 1100000, 0, 16353333, 0, 2100000, 0, 3339336),
        (18, "Eka Novia Bauty, S.Stat", "Anggota", "Wanita", "Aktif", 25000, 12205000, 2000000, 7500000, 2450000, 0, 0, 0, 0, 0),
        (19, "Erlina Hardiyanti, A.Md", "Bendahara", "Wanita", "Aktif", 25000, 12205000, 9000000, 19500000, 2450000, 0, 0, 0, 0, 1300002),
        (20, "Dindin Muldiana, S.ST, M.P.", "Anggota", "Pria", "Aktif", 30000, 11485000, 0, 3200000, 0, 30000000, 0, 3800000, 0, 0),
        (21, "Adenty Oktavianty, S.Stat", "Anggota", "Wanita", "Aktif", 30000, 11450000, 0, 5500000, 2400000, 4000000, 0, 0, 0, 1650000),
        (22, "Erwin Pratama Silaen, Amd", "Anggota", "Pria", "Aktif", 30000, 11485000, 0, 1000000, 0, 3560000, 4857500, 5900000, 0, 2011500),
        (25, "Teguh Paryadi", "Anggota", "Pria", "Aktif", 30000, 10825000, 0, 0, 0, 7200000, 0, 0, 0, 40000),
        (28, "Asep Saripudin, S.ST", "Anggota", "Pria", "Aktif", 30000, 10715000, 3100000, 10000000, 0, 0, 0, 0, 0, 0),
        (29, "Deni Iskandar, S.ST", "Anggota", "Pria", "Aktif", 30000, 10715000, 0, 7500000, 0, 14917331, 1000000, 0, 0, 4420231),
        (32, "Mulyadin", "Anggota", "Pria", "Aktif", 25000, 9425000, 0, 5350000, 0, 31800000, 0, 500000, 3150000, 1670000),
        (35, "M. Sobari, S.ST, M.Stat", "Anggota", "Pria", "Aktif", 25000, 7400000, 0, 1100000, 0, 0, 0, 0, 0, 333333),
        (36, "Diyah Citra AKS, SE, M.Si", "Anggota", "Wanita", "Aktif", 25000, 6300000, 3529000, 2200000, 2800000, 0, 0, 0, 600000, 720000),
        (37, "Riska Putri Rahma Dhiani, S.Tr.Stat", "Anggota", "Wanita", "Aktif", 25000, 5700000, 2350000, 1000000, 0, 0, 0, 0, 0, 0),
        (38, "Gea Dwisatya Maulani, A.Md", "Anggota", "Wanita", "Aktif", 25000, 4300000, 0, 5300000, 0, 0, 0, 0, 0, 0),
        (39, "Octavia Nurfadhilah, A.Md.Stat", "Anggota", "Wanita", "Aktif", 25000, 4300000, 1100000, 3300000, 0, 8000000, 0, 0, 0, 3840000),
        (40, "Priangga Andrew, S.ST", "Anggota", "Pria", "Aktif", 25000, 4000000, 0, 1000000, 0, 0, 0, 0, 0, 0),
        (41, "Ika Nuryani, S.ST. M.Stat", "Anggota", "Wanita", "Aktif", 25000, 4100000, 0, 1000000, 0, 18888889, 0, 0, 0, 228889),
        (42, "Ida Siti Faridah, A.Md", "Anggota", "Wanita", "Aktif", 25000, 3800000, 3000000, 1850000, 800000, 21999993, 1000000, 0, 0, 4699999),
        (46, "Ir. Suhartono, M.P.", "Anggota", "Pria", "Aktif", 25000, 1200000, 0, 1150000, 450000, 0, 0, 0, 0, 0),
        (48, "Iis Rina Mulyawati, SST. MP", "Anggota", "Wanita", "Aktif", 25000, 300000, 0, 3000000, 0, 0, 0, 0, 0, 0),
        (49, "Penpen Hidayat", "Anggota", "Pria", "Aktif", 25000, 300000, 0, 0, 0, 19166667, 0, 0, 0, 250000),
        (50, "Yunus", "Anggota", "Pria", "Aktif", 25000, 200000, 0, 0, 0, 0, 0, 0, 0, 230000),
        (51, "Kamal Hasan Ashari, A.Md", "Anggota", "Pria", "Aktif", 25000, 300000, 0, 0, 0, 0, 0, 3500000, 0, 60000),
        (52, "Heri Hermawan", "Anggota", "Pria", "Aktif", 25000, 300000, 0, 0, 0, 0, 0, 2000000, 0, 50000),
        (53, "Dudi Suryadi, SE. MP. Msi", "Anggota", "Pria", "Aktif", 25000, 600000, 600000, 0, 600000, 0, 0, 0, 0, 0)
    ]

    for item in raw_members:
        no_urut, nama, jabatan, jk, status, sp_pokok, sp_wajib, sp_manasuka, sp_lebaran, sp_qurban, pj_japan, pj_japen, pj_bon, pj_barang, jasa_bayar = item
        no_agt = f"KST-{no_urut:03d}"
        role = 'admin' if no_urut in [2, 7, 19] else 'anggota' # Ketua, Sekretaris, Bendahara have admin rights
        nip = f"19{75 + (no_urut % 20):02d}{(no_urut % 12) + 1:02d}15200501{1 if jk == 'Pria' else 2}{no_urut:03d}"
        hp = f"0812{no_urut:04d}{2345 + no_urut}"
        email = f"{nama.split()[0].lower()}@bps.go.id"

        cursor.execute('''
        INSERT INTO anggota (id, no_anggota, nama, nip, jabatan, jenis_kelamin, no_hp, email, alamat, tanggal_masuk, status, password, role)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'BPS Kabupaten Tasikmalaya', '2024-01-01', ?, '123456', ?)
        ''', (no_urut, no_agt, nama, nip, jabatan, jk, hp, email, status, role))

        # Insert historical savings balances per 31 Des 2025
        if sp_pokok > 0:
            cursor.execute('''
            INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
            VALUES (?, ?, '2025-12-31', 'Pokok', 'SETOR', ?, 'Saldo Pokok Awal RAT 2025', 'Tunai', '2025-12', 'System')
            ''', (f"TRX-POK-{no_urut}", no_urut, sp_pokok))

        if sp_wajib > 0:
            cursor.execute('''
            INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
            VALUES (?, ?, '2025-12-31', 'Wajib', 'SETOR', ?, 'Akumulasi Simpanan Wajib s.d RAT 2025', 'Potong Gaji', '2025-12', 'System')
            ''', (f"TRX-WJB-{no_urut}", no_urut, sp_wajib))

        if sp_manasuka > 0:
            cursor.execute('''
            INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
            VALUES (?, ?, '2025-12-31', 'Manasuka', 'SETOR', ?, 'Saldo Simpanan Manasuka / Lainnya', 'Potong Gaji', '2025-12', 'System')
            ''', (f"TRX-MNS-{no_urut}", no_urut, sp_manasuka))

        if sp_lebaran > 0:
            cursor.execute('''
            INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
            VALUES (?, ?, '2025-12-31', 'Lebaran', 'SETOR', ?, 'Tabungan Hari Raya Idul Fitri', 'Potong Gaji', '2025-12', 'System')
            ''', (f"TRX-LBR-{no_urut}", no_urut, sp_lebaran))

        if sp_qurban > 0:
            cursor.execute('''
            INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
            VALUES (?, ?, '2025-12-31', 'Qurban', 'SETOR', ?, 'Tabungan Qurban Idul Adha', 'Potong Gaji', '2025-12', 'System')
            ''', (f"TRX-QRB-{no_urut}", no_urut, sp_qurban))

        # Insert active loans per 31 Des 2025
        # 1. JAPAN (Jangka Panjang)
        if pj_japan > 0:
            tenor = 30
            angsuran_pokok = round(pj_japan / 24, 2) # Asumsi sisa ~24 bln
            plafon = round(pj_japan * 1.25, -5) # Estimasi plafon awal
            margin_nominal = round(plafon * 0.25, 2)
            margin_bln = round(margin_nominal / tenor, 2)

            cursor.execute('''
            INSERT INTO pinjaman (
                no_pinjaman, anggota_id, jenis_pinjaman, tanggal_pengajuan, tanggal_cair,
                plafon_pokok, margin_persen, margin_nominal, total_pinjaman, tenor_bulan,
                angsuran_pokok_bulanan, angsuran_margin_bulanan, total_angsuran_bulanan,
                biaya_provisi, biaya_drk, saldo_pokok, saldo_margin, angsuran_ke,
                status, keperluan, keterangan
            ) VALUES (?, ?, 'JAPAN', '2025-01-15', '2025-01-20', ?, 25.0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 6, 'Aktif', 'Pembiayaan Jangka Panjang Syariah', 'Pinjaman berjalan posisi RAT 2025')
            ''', (
                f"PJ-JPN-{no_urut}", no_urut, plafon, margin_nominal, (plafon + margin_nominal),
                tenor, angsuran_pokok, margin_bln, (angsuran_pokok + margin_bln),
                plafon * 0.01, plafon * 0.005, pj_japan, margin_nominal * 0.8
            ))

        # 2. JAPEN (Jangka Pendek)
        if pj_japen > 0:
            tenor = 10
            plafon = round(pj_japen * 1.2, -4)
            angs_p = round(plafon / tenor, 2)
            cursor.execute('''
            INSERT INTO pinjaman (
                no_pinjaman, anggota_id, jenis_pinjaman, tanggal_pengajuan, tanggal_cair,
                plafon_pokok, margin_persen, margin_nominal, total_pinjaman, tenor_bulan,
                angsuran_pokok_bulanan, angsuran_margin_bulanan, total_angsuran_bulanan,
                biaya_provisi, biaya_drk, saldo_pokok, saldo_margin, angsuran_ke,
                status, keperluan, keterangan
            ) VALUES (?, ?, 'JAPEN', '2025-08-10', '2025-08-12', ?, 10.0, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, 3, 'Aktif', 'Pinjaman Jangka Pendek', 'Pinjaman JAPEN berjalan')
            ''', (
                f"PJ-JPNK-{no_urut}", no_urut, plafon, (plafon * 0.1), (plafon * 1.1),
                tenor, angs_p, (plafon * 0.01), (angs_p + (plafon * 0.01)),
                plafon * 0.01, pj_japen, (plafon * 0.07)
            ))

        # 3. Bon Putih / Pinjaman Lainnya
        if pj_bon > 0:
            tenor = 10
            cursor.execute('''
            INSERT INTO pinjaman (
                no_pinjaman, anggota_id, jenis_pinjaman, tanggal_pengajuan, tanggal_cair,
                plafon_pokok, margin_persen, margin_nominal, total_pinjaman, tenor_bulan,
                angsuran_pokok_bulanan, angsuran_margin_bulanan, total_angsuran_bulanan,
                biaya_provisi, biaya_drk, saldo_pokok, saldo_margin, angsuran_ke,
                status, keperluan, keterangan
            ) VALUES (?, ?, 'Bon Putih', '2025-10-01', '2025-10-02', ?, 2.0, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, 2, 'Aktif', 'Pinjaman Bon Putih Kas', 'Pinjaman Lainnya berjalan')
            ''', (
                f"PJ-BON-{no_urut}", no_urut, pj_bon, (pj_bon * 0.04), (pj_bon * 1.04),
                tenor, round(pj_bon / tenor, 2), round((pj_bon * 0.02), 2), round(pj_bon / tenor, 2) + round((pj_bon * 0.02), 2),
                pj_bon, round(pj_bon * 0.03, 2)
            ))

        # 4. Pinjaman Barang
        if pj_barang > 0:
            tenor = 10
            cursor.execute('''
            INSERT INTO pinjaman (
                no_pinjaman, anggota_id, jenis_pinjaman, tanggal_pengajuan, tanggal_cair,
                plafon_pokok, margin_persen, margin_nominal, total_pinjaman, tenor_bulan,
                angsuran_pokok_bulanan, angsuran_margin_bulanan, total_angsuran_bulanan,
                biaya_provisi, biaya_drk, saldo_pokok, saldo_margin, angsuran_ke,
                status, keperluan, keterangan
            ) VALUES (?, ?, 'Barang', '2025-06-15', '2025-06-18', ?, 20.0, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, 4, 'Aktif', 'Pengadaan Barang Elektronik/Konsumtif', 'Pinjaman Barang berjalan')
            ''', (
                f"PJ-BRG-{no_urut}", no_urut, pj_barang, (pj_barang * 0.20), (pj_barang * 1.20),
                tenor, round(pj_barang / tenor, 2), round((pj_barang * 0.20) / tenor, 2), round(pj_barang / tenor, 2) + round((pj_barang * 0.20) / tenor, 2),
                pj_barang, round(pj_barang * 0.12, 2)
            ))

        # Insert historical jasa pinjaman paid (untuk dasar SHU persis laporan RAT hal 24-25)
        if jasa_bayar > 0:
            cursor.execute('''
            INSERT INTO angsuran_pinjaman (
                no_angsuran, pinjaman_id, anggota_id, tanggal_bayar, angsuran_ke,
                angsuran_pokok, angsuran_margin, total_bayar, sisa_pokok_setelah,
                bulan_buku, metode_bayar, keterangan
            ) VALUES (?, 1, ?, '2025-12-25', 12, 0, ?, ?, 0, '2025-12', 'Potong Gaji', 'Akumulasi Jasa Pinjaman Tahun Buku 2025')
            ''', (f"ANGS-HIST-{no_urut}", no_urut, jasa_bayar, jasa_bayar))

    # Add sample transaction for January 2026 to show active monthly history
    cursor.execute('''
    INSERT OR REPLACE INTO billing_bulanan_log (
        bulan_buku, tanggal_proses, total_anggota, total_simpanan,
        total_angsuran_pokok, total_angsuran_margin, total_keseluruhan,
        status, created_by
    ) VALUES ('2026-01', '2026-01-25', 37, 5800000, 16250000, 2450000, 24500000, 'Selesai', 'Bendahara')
    ''')

    # Seed sample pending online request from a member to demonstrate approval workflow
    cursor.execute('''
    INSERT INTO pengajuan_online (
        no_pengajuan, anggota_id, jenis, kategori, nominal, tenor_bulan,
        tanggal_pengajuan, alasan, status
    ) VALUES ('REQ-202602-001', 16, 'PINJAMAN', 'JAPEN', 5000000, 10, '2026-02-10', 'Biaya perbaikan kendaraan operasional', 'Menunggu')
    ''')

    cursor.execute('''
    INSERT INTO pengajuan_online (
        no_pengajuan, anggota_id, jenis, kategori, nominal, tenor_bulan,
        tanggal_pengajuan, alasan, status
    ) VALUES ('REQ-202602-002', 15, 'PENARIKAN_SIMPANAN', 'Manasuka', 1000000, 1, '2026-02-12', 'Kebutuhan keluarga mendesak', 'Menunggu')
    ''')

    conn.commit()
    conn.close()
    print("Seed data KOSITAS populated successfully with 38 members and full historical balances.")

if __name__ == '__main__':
    run_seed()
