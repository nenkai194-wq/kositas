import unittest
import database
import models
from app import app

class TestApprovalMarginKetua(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        # Login sebagai superadmin / Ketua Koperasi (Gilang Abdul Aziz, id=7)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 7
            sess['role'] = 'superadmin'

    def test_approval_pinjaman_dengan_margin_ketua(self):
        conn = database.get_db()
        cursor = conn.cursor()
        
        # Buat pengajuan pinjaman dummy untuk diuji
        no_req = "REQ-TEST-MARGIN-01"
        cursor.execute("DELETE FROM pengajuan_online WHERE no_pengajuan = ?", (no_req,))
        cursor.execute('''
        INSERT INTO pengajuan_online (no_pengajuan, anggota_id, jenis, kategori, nominal, tenor_bulan, alasan, status)
        VALUES (?, 2, 'PINJAMAN', 'JAPEN', 6000000.0, 6, 'Kebutuhan mendesak perbaikan rumah', 'Menunggu')
        ''', (no_req,))
        req_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Simulasi submit approval dari modal Ketua Koperasi
        # Ketua menentukan rate 1.2% / bulan -> untuk 6 bulan total margin = 7.2% = Rp 432.000
        response = self.client.post(f'/admin/pengajuan/{req_id}/proses', data={
            'action': 'TERIMA',
            'plafon_pokok': '6000000',
            'tenor_bulan': '6',
            'margin_per_bulan': '1.2',
            'margin_persen': '7.2',
            'margin_nominal': '432000',
            'catatan_admin': 'Disetujui Ketua Koperasi: Plafon Rp 6.000.000 tenor 6 bulan margin 1.2%/bln'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        # Verifikasi status pengajuan_online
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pengajuan_online WHERE id = ?", (req_id,))
        req = dict(cursor.fetchone())
        self.assertEqual(req['status'], 'Disetujui')
        self.assertIn('Disetujui Ketua Koperasi', req['catatan_admin'])
        self.assertEqual(req['tenor_bulan'], 6)
        self.assertEqual(req['nominal'], 6000000.0)

        # Verifikasi pinjaman yang diterbitkan
        cursor.execute('''
        SELECT * FROM pinjaman 
        WHERE anggota_id = 2 AND keterangan LIKE ?
        ORDER BY id DESC LIMIT 1
        ''', (f"%{no_req}%",))
        pj_row = cursor.fetchone()
        self.assertIsNotNone(pj_row, "Pinjaman harus terbentuk!")
        pj = dict(pj_row)

        self.assertEqual(pj['plafon_pokok'], 6000000.0)
        self.assertEqual(pj['tenor_bulan'], 6)
        self.assertAlmostEqual(pj['margin_persen'], 7.2, places=2)
        self.assertEqual(pj['margin_nominal'], 432000.0)
        self.assertEqual(pj['total_pinjaman'], 6432000.0)
        # Angsuran pokok = 6.000.000 / 6 = 1.000.000
        self.assertEqual(pj['angsuran_pokok_bulanan'], 1000000.0)
        # Angsuran margin = 432.000 / 6 = 72.000
        self.assertEqual(pj['angsuran_margin_bulanan'], 72000.0)
        # Total angsuran = 1.072.000
        self.assertEqual(pj['total_angsuran_bulanan'], 1072000.0)
        # Biaya Provisi (1% dari 6jt) = 60.000
        self.assertEqual(pj['biaya_provisi'], 60000.0)

        # Cleanup
        cursor.execute("DELETE FROM pinjaman WHERE id = ?", (pj['id'],))
        cursor.execute("DELETE FROM pengajuan_online WHERE id = ?", (req_id,))
        conn.commit()
        conn.close()

    def test_tolak_pengajuan_dengan_alasan(self):
        conn = database.get_db()
        cursor = conn.cursor()
        
        no_req = "REQ-TEST-TOLAK-01"
        cursor.execute("DELETE FROM pengajuan_online WHERE no_pengajuan = ?", (no_req,))
        cursor.execute('''
        INSERT INTO pengajuan_online (no_pengajuan, anggota_id, jenis, kategori, nominal, tenor_bulan, alasan, status)
        VALUES (?, 2, 'PINJAMAN', 'Bon Putih', 2000000.0, 3, 'Kebutuhan mendesak', 'Menunggu')
        ''', (no_req,))
        req_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Simulasi tolak
        response = self.client.post(f'/admin/pengajuan/{req_id}/proses', data={
            'action': 'TOLAK',
            'catatan_admin': 'Kapasitas angsuran bulanan telah melampaui batas maksimal potong gaji.'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pengajuan_online WHERE id = ?", (req_id,))
        req = dict(cursor.fetchone())
        self.assertEqual(req['status'], 'Ditolak')
        self.assertIn('Kapasitas angsuran', req['catatan_admin'])

        # Cleanup
        cursor.execute("DELETE FROM pengajuan_online WHERE id = ?", (req_id,))
        conn.commit()
        conn.close()

    def test_approval_penyesuaian_plafon_dan_tenor(self):
        conn = database.get_db()
        cursor = conn.cursor()
        
        # Anggota mengajukan 10 jt tenor 12 bln
        no_req = "REQ-TEST-ADJUST-01"
        cursor.execute("DELETE FROM pengajuan_online WHERE no_pengajuan = ?", (no_req,))
        cursor.execute('''
        INSERT INTO pengajuan_online (no_pengajuan, anggota_id, jenis, kategori, nominal, tenor_bulan, alasan, status)
        VALUES (?, 2, 'PINJAMAN', 'JAPAN', 10000000.0, 12, 'Renovasi ruko', 'Menunggu')
        ''', (no_req,))
        req_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Ketua Koperasi menyetujui plafon disesuaikan menjadi 8 jt, tenor 10 bln, margin 1.0%/bln -> total 10% = 800.000
        response = self.client.post(f'/admin/pengajuan/{req_id}/proses', data={
            'action': 'TERIMA',
            'plafon_pokok': '8000000',
            'tenor_bulan': '10',
            'margin_per_bulan': '1.0',
            'margin_persen': '10.0',
            'margin_nominal': '800000',
            'catatan_admin': 'Disetujui Ketua Koperasi: Plafon disesuaikan Rp 8.000.000 tenor 10 bln.'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pengajuan_online WHERE id = ?", (req_id,))
        req = dict(cursor.fetchone())
        self.assertEqual(req['status'], 'Disetujui')
        self.assertEqual(req['nominal'], 8000000.0)
        self.assertEqual(req['tenor_bulan'], 10)

        cursor.execute('''
        SELECT * FROM pinjaman 
        WHERE anggota_id = 2 AND keterangan LIKE ?
        ORDER BY id DESC LIMIT 1
        ''', (f"%{no_req}%",))
        pj = dict(cursor.fetchone())
        self.assertEqual(pj['plafon_pokok'], 8000000.0)
        self.assertEqual(pj['tenor_bulan'], 10)
        self.assertEqual(pj['margin_persen'], 10.0)
        self.assertEqual(pj['margin_nominal'], 800000.0)
        self.assertEqual(pj['total_pinjaman'], 8800000.0)
        self.assertEqual(pj['angsuran_pokok_bulanan'], 800000.0)
        self.assertEqual(pj['angsuran_margin_bulanan'], 80000.0)
        self.assertEqual(pj['total_angsuran_bulanan'], 880000.0)
        # Biaya provisi 1% = 80.000, DRK 0.5% (JAPAN) = 40.000
        self.assertEqual(pj['biaya_provisi'], 80000.0)
        self.assertEqual(pj['biaya_drk'], 40000.0)

        cursor.execute("DELETE FROM pinjaman WHERE id = ?", (pj['id'],))
        cursor.execute("DELETE FROM pengajuan_online WHERE id = ?", (req_id,))
        conn.commit()
        conn.close()

    def test_approval_penarikan_simpanan_manasuka(self):
        conn = database.get_db()
        cursor = conn.cursor()
        
        no_req = "REQ-TEST-TARIK-01"
        cursor.execute("DELETE FROM pengajuan_online WHERE no_pengajuan = ?", (no_req,))
        cursor.execute('''
        INSERT INTO pengajuan_online (no_pengajuan, anggota_id, jenis, kategori, nominal, tenor_bulan, alasan, status)
        VALUES (?, 2, 'PENARIKAN_SIMPANAN', 'Manasuka', 100000.0, 1, 'Kebutuhan keluarga', 'Menunggu')
        ''', (no_req,))
        req_id = cursor.lastrowid

        # Pastikan saldo manasuka anggota 2 cukup dengan menambah transaksi setor
        cursor.execute('''
        INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan)
        VALUES ('TRX-TEST-SETOR', 2, '2026-10-21', 'Manasuka', 'SETOR', 500000.0, 'Setor modal uji')
        ''')
        conn.commit()
        conn.close()

        response = self.client.post(f'/admin/pengajuan/{req_id}/proses', data={
            'action': 'TERIMA',
            'catatan_admin': 'Transfer via BRI No Ref 12345678'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pengajuan_online WHERE id = ?", (req_id,))
        req = dict(cursor.fetchone())
        self.assertEqual(req['status'], 'Disetujui')
        self.assertIn('Transfer via BRI', req['catatan_admin'])

        cursor.execute("DELETE FROM transaksi_simpanan WHERE no_transaksi = 'TRX-TEST-SETOR'")
        cursor.execute("DELETE FROM transaksi_simpanan WHERE keterangan LIKE ?", (f"%{no_req}%",))
        cursor.execute("DELETE FROM pengajuan_online WHERE id = ?", (req_id,))
        conn.commit()
        conn.close()

    def test_topup_dengan_rate_margin_per_bulan(self):
        conn = database.get_db()
        cursor = conn.cursor()

        # Buat pinjaman awal
        no_pj = "PJ-TEST-TOPUP-01"
        cursor.execute("DELETE FROM pinjaman WHERE no_pinjaman = ?", (no_pj,))
        cursor.execute('''
        INSERT INTO pinjaman (
            no_pinjaman, anggota_id, jenis_pinjaman, plafon_pokok, tenor_bulan,
            margin_persen, margin_nominal, total_pinjaman, angsuran_pokok_bulanan,
            angsuran_margin_bulanan, total_angsuran_bulanan, saldo_pokok, saldo_margin,
            biaya_provisi, biaya_drk, tanggal_pengajuan, tanggal_cair,
            status, angsuran_ke, pelunasan_tipe, keperluan
        ) VALUES (
            ?, 2, 'JAPEN', 3000000.0, 10,
            10.0, 300000.0, 3300000.0, 300000.0,
            30000.0, 330000.0, 2000000.0, 200000.0,
            30000.0, 0.0, '2026-01-01', '2026-01-01',
            'Aktif', 3, 'Normal', 'Pinjaman lama'
        )
        ''', (no_pj,))
        pj_lama_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Eksekusi top up dengan data form: Rate Margin 1.25%/bulan x 12 bulan = Total Margin 15%
        res = self.client.post(f'/admin/pinjaman/{pj_lama_id}/topup', data={
            'jenis_pinjaman': 'JAPEN',
            'plafon_pokok': '5000000',
            'tenor_bulan': '12',
            'margin_per_bulan': '1.25',
            'margin_persen': '15.0',
            'margin_nominal': '750000',
            'tanggal_cair': '2026-10-21',
            'keperluan': 'Top up refinancing margin uji'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)

        # Verifikasi pinjaman baru terbentuk dan margin sesuai
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM pinjaman WHERE anggota_id = 2 AND keperluan LIKE '%refinancing margin uji%'
        ORDER BY id DESC LIMIT 1
        ''')
        pj_baru = dict(cursor.fetchone())
        self.assertIsNotNone(pj_baru)
        self.assertEqual(pj_baru['plafon_pokok'], 5000000.0)
        self.assertEqual(pj_baru['tenor_bulan'], 12)
        self.assertEqual(pj_baru['margin_persen'], 15.0)
        self.assertEqual(pj_baru['margin_nominal'], 750000.0)
        self.assertEqual(pj_baru['angsuran_margin_bulanan'], 62500.0)

        # Verifikasi pinjaman lama ditutup
        cursor.execute("SELECT status, pelunasan_tipe FROM pinjaman WHERE id = ?", (pj_lama_id,))
        pj_lama_cek = dict(cursor.fetchone())
        self.assertEqual(pj_lama_cek['status'], 'Lunas')
        self.assertEqual(pj_lama_cek['pelunasan_tipe'], 'Top Up')

        # Cleanup
        cursor.execute("DELETE FROM angsuran_pinjaman WHERE pinjaman_id IN (?, ?)", (pj_lama_id, pj_baru['id']))
        cursor.execute("DELETE FROM pinjaman WHERE id IN (?, ?)", (pj_lama_id, pj_baru['id']))
        conn.commit()
        conn.close()

if __name__ == '__main__':
    unittest.main()
