import unittest
import database
import models
from app import app

class TestKoreksiBatalSuperadmin(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_koreksi_margin_oleh_superadmin(self):
        # 1. Login sebagai superadmin (Gilang Abdul Aziz, id=7)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 7
            sess['role'] = 'superadmin'

        conn = database.get_db()
        cursor = conn.cursor()
        
        # Buat pengajuan dummy
        no_req = "REQ-TEST-KOR-01"
        cursor.execute("DELETE FROM pengajuan_online WHERE no_pengajuan = ?", (no_req,))
        cursor.execute('''
        INSERT INTO pengajuan_online (no_pengajuan, anggota_id, jenis, kategori, nominal, tenor_bulan, alasan, status)
        VALUES (?, 2, 'PINJAMAN', 'JAPEN', 5000000.0, 10, 'Modal usaha', 'Menunggu')
        ''', (no_req,))
        req_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Setujui pengajuan awal
        self.client.post(f'/admin/pengajuan/{req_id}/proses', data={
            'action': 'TERIMA',
            'plafon_pokok': '5000000',
            'tenor_bulan': '10',
            'margin_per_bulan': '1.0',
            'margin_persen': '10.0',
            'margin_nominal': '500000',
            'catatan_admin': 'Disetujui awal'
        }, follow_redirects=True)

        # Ambil pinjaman yang terbentuk
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT pinjaman_id FROM pengajuan_online WHERE id = ?", (req_id,))
        pj_id = cursor.fetchone()[0]
        self.assertIsNotNone(pj_id)
        conn.close()

        # 2. Superadmin melakukan koreksi: Plafon diubah jadi 4.000.000, tenor 8 bln, margin 1.25%/bln (total 10% = 400.000)
        res_kor = self.client.post(f'/admin/pinjaman/{pj_id}/koreksi', data={
            'plafon_pokok': '4000000',
            'tenor_bulan': '8',
            'margin_per_bulan': '1.25',
            'margin_persen': '10.0',
            'margin_nominal': '400000',
            'alasan_koreksi': 'Koreksi salah hitung plafon dan tenor oleh Ketua'
        }, follow_redirects=True)
        self.assertEqual(res_kor.status_code, 200)

        # Verifikasi hasil koreksi
        pj_updated = models.get_pinjaman_by_id(pj_id)
        self.assertEqual(pj_updated['plafon_pokok'], 4000000.0)
        self.assertEqual(pj_updated['tenor_bulan'], 8)
        self.assertEqual(pj_updated['margin_nominal'], 400000.0)
        # Angsuran pokok baru = 4.000.000 / 8 = 500.000
        self.assertEqual(pj_updated['angsuran_pokok_bulanan'], 500000.0)
        # Angsuran margin baru = 400.000 / 8 = 50.000
        self.assertEqual(pj_updated['angsuran_margin_bulanan'], 50000.0)
        # Total angsuran baru = 550.000
        self.assertEqual(pj_updated['total_angsuran_bulanan'], 550000.0)
        self.assertIn('Koreksi salah hitung', pj_updated['keterangan'])

        # 3. Superadmin membatalkan pinjaman dan mengembalikan status ke 'Menunggu'
        res_batal = self.client.post(f'/admin/pinjaman/{pj_id}/batalkan', data={
            'alasan_batal': 'Dibatalkan untuk penyesuaian ulang',
            'kembalikan_ke_menunggu': '1'
        }, follow_redirects=True)
        self.assertEqual(res_batal.status_code, 200)

        # Verifikasi pinjaman sudah terhapus
        pj_deleted = models.get_pinjaman_by_id(pj_id)
        self.assertIsNone(pj_deleted)

        # Verifikasi status pengajuan online kembali ke 'Menunggu'
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT status, catatan_admin FROM pengajuan_online WHERE id = ?", (req_id,))
        req_row = cursor.fetchone()
        self.assertEqual(req_row[0], 'Menunggu')
        self.assertIn('Approval Dibatalkan Superadmin', req_row[1])

        # Cleanup
        cursor.execute("DELETE FROM pengajuan_online WHERE id = ?", (req_id,))
        conn.commit()
        conn.close()

    def test_hak_akses_admin_biasa_ditolak_koreksi_dan_batal(self):
        # Login sebagai admin biasa (Darojatun, id=2)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['role'] = 'admin'

        # Coba akses koreksi
        res_kor = self.client.post('/admin/pinjaman/1/koreksi', data={'plafon_pokok': 5000000})
        self.assertEqual(res_kor.status_code, 302)

        # Coba akses batal
        res_batal = self.client.post('/admin/pinjaman/1/batalkan', data={'alasan_batal': 'coba'})
        self.assertEqual(res_batal.status_code, 302)

    def test_koreksi_margin_batas_cicilan_kedua(self):
        # Login sebagai superadmin (id=7)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 7
            sess['role'] = 'superadmin'

        # Buat pinjaman uji
        pj_id = models.tambah_pinjaman({
            'anggota_id': 2,
            'jenis_pinjaman': 'JAPEN',
            'plafon_pokok': 5000000,
            'tenor_bulan': 5,
            'margin_persen': 5.0, # 250.000
            'keperluan': 'Uji batas cicilan'
        })

        # Skenario 1: Cicilan ke-1 dibayar (angsuran_ke = 1) -> Edit margin HARUS BISA
        models.bayar_angsuran({
            'pinjaman_id': pj_id,
            'angsuran_pokok': 1000000,
            'angsuran_margin': 50000,
            'metode_bayar': 'Transfer'
        })
        pj_1 = models.get_pinjaman_by_id(pj_id)
        self.assertEqual(pj_1['angsuran_ke'], 1)

        # Edit margin saat cicilan ke-1
        success_1, msg_1 = models.koreksi_pinjaman_margin(pj_id, {
            'plafon_pokok': 5000000,
            'tenor_bulan': 5,
            'margin_persen': 7.5, # 375.000
            'alasan_koreksi': 'Koreksi margin disetujui saat cicilan ke-1'
        })
        self.assertTrue(success_1, "Edit margin saat cicilan ke-1 harus berhasil")
        pj_after_1 = models.get_pinjaman_by_id(pj_id)
        self.assertEqual(pj_after_1['margin_persen'], 7.5)
        self.assertEqual(pj_after_1['margin_nominal'], 375000.0)
        # Sisa margin = 375.000 - 50.000 (sudah bayar) = 325.000
        self.assertEqual(pj_after_1['saldo_margin'], 325000.0)

        # Skenario 2: Cicilan ke-2 dibayar (angsuran_ke = 2) -> Edit margin HARUS GAGAL
        models.bayar_angsuran({
            'pinjaman_id': pj_id,
            'angsuran_pokok': 1000000,
            'angsuran_margin': 75000,
            'metode_bayar': 'Transfer'
        })
        pj_2 = models.get_pinjaman_by_id(pj_id)
        self.assertEqual(pj_2['angsuran_ke'], 2)

        # Coba edit margin saat cicilan ke-2
        success_2, msg_2 = models.koreksi_pinjaman_margin(pj_id, {
            'plafon_pokok': 5000000,
            'tenor_bulan': 5,
            'margin_persen': 10.0,
            'alasan_koreksi': 'Coba edit saat cicilan ke-2'
        })
        self.assertFalse(success_2, "Edit margin saat cicilan ke-2 HARUS DITOLAK")
        self.assertIn("TIDAK BISA DILAKUKAN", msg_2)

        # Verifikasi margin tidak berubah
        pj_after_2 = models.get_pinjaman_by_id(pj_id)
        self.assertEqual(pj_after_2['margin_persen'], 7.5) # Tetap 7.5, tidak menjadi 10.0

        # Cleanup
        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM angsuran_pinjaman WHERE pinjaman_id = ?", (pj_id,))
        cur.execute("DELETE FROM pinjaman WHERE id = ?", (pj_id,))
        conn.commit()
        conn.close()

if __name__ == '__main__':
    unittest.main()
