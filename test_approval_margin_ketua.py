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

if __name__ == '__main__':
    unittest.main()
