import unittest
from app import app
import models
import database

class TestRolesAndDanaSHU(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app_ctx = app.app_context()
        self.app_ctx.push()

    def tearDown(self):
        self.app_ctx.pop()

    def test_01_user_roles_in_database(self):
        """Pastikan role superadmin, admin, dan anggota terpasang dengan tepat."""
        gilang = models.get_anggota_by_id(7)
        self.assertIsNotNone(gilang)
        self.assertEqual(gilang['role'], 'superadmin')

        erlina = models.get_anggota_by_id(19)
        self.assertIsNotNone(erlina)
        self.assertEqual(erlina['role'], 'admin')

        darojatun = models.get_anggota_by_id(2)
        self.assertIsNotNone(darojatun)
        self.assertEqual(darojatun['role'], 'admin')

        dama = models.get_anggota_by_id(1)
        self.assertIsNotNone(dama)
        self.assertEqual(dama['role'], 'anggota')

    def test_02_superadmin_access(self):
        """Superadmin dapat mengakses semua halaman konfigurasi dan operasional."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 7
            sess['role'] = 'superadmin'

        # Dashboard Admin OK
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)

        # Halaman Monitoring & Kelola Dana SHU OK
        res = self.client.get('/admin/dana-shu')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Level Superadmin", res.data)
        self.assertIn(b"Tambah Dana Baru", res.data)

        # Halaman Manajemen Role OK
        res = self.client.get('/superadmin/manajemen-role')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Manajemen Hak Akses", res.data)

    def test_03_admin_access_restrictions(self):
        """Admin operasional dapat melihat monitoring dana RAT tetapi TIDAK dapat mengubahnya."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 19
            sess['role'] = 'admin'

        # Dashboard Admin OK
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)

        # Halaman Monitoring Dana RAT OK (View / Read-Only)
        res = self.client.get('/admin/dana-shu')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Mode Monitoring", res.data)
        self.assertNotIn(b"Tambah Dana Baru", res.data)

        # Ditolak saat mencoba akses Manajemen Role
        res = self.client.get('/superadmin/manajemen-role', follow_redirects=True)
        self.assertIn(b"hanya untuk Superadmin", res.data)

        # Ditolak saat mencoba post tambah dana
        post_data = {
            'tahun': 2026,
            'nama_dana': 'Dana Ilegal',
            'persentase': 5.0,
            'kategori': 'DANA'
        }
        res = self.client.post('/superadmin/dana-shu/tambah', data=post_data, follow_redirects=True)
        self.assertIn(b"hanya untuk Superadmin", res.data)

    def test_04_anggota_access_restrictions(self):
        """Anggota biasa tidak dapat mengakses dashboard admin, dana-shu, atau manajemen role."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'anggota'

        # Dashboard Anggota OK
        res = self.client.get('/anggota/dashboard')
        self.assertEqual(res.status_code, 200)

        # Estimasi SHU Anggota OK
        res = self.client.get('/anggota/shu')
        self.assertEqual(res.status_code, 200)

        # Ditolak saat mencoba akses /admin/dashboard
        res = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertIn(b"Akses ditolak", res.data)

        # Ditolak saat mencoba akses /admin/dana-shu
        res = self.client.get('/admin/dana-shu', follow_redirects=True)
        self.assertIn(b"Akses ditolak", res.data)

    def test_05_dynamic_dana_shu_crud(self):
        """Uji alur CRUD dan kalkulasi dinamis alokasi dana SHU."""
        # 1. Cek alokasi default tahun 2026
        shu = models.hitung_shu_koperasi(38706812.69, tahun=2026)
        self.assertEqual(shu['total_persentase'], 100.0)
        self.assertTrue(shu['is_valid_100'])
        self.assertEqual(len(shu['dana_list']), 8)

        # 2. Tambah dana baru untuk tahun 2030 (testing isolated year)
        new_id = models.tambah_dana_shu({
            'tahun': 2030,
            'nama_dana': 'Dana Riset AI',
            'persentase': 10.0,
            'kategori': 'DANA',
            'is_bagian_anggota': 0,
            'keterangan': 'Dana penelitian',
            'warna_badge': 'cyan',
            'urutan': 1
        })
        self.assertIsNotNone(new_id)

        # Tambahkan bagian anggota 90%
        models.tambah_dana_shu({
            'tahun': 2030,
            'nama_dana': 'SHU Bagian Anggota',
            'persentase': 90.0,
            'kategori': 'ANGGOTA',
            'is_bagian_anggota': 1,
            'porsi_jasa_modal': 60.0,
            'porsi_jasa_pinjaman': 40.0,
            'keterangan': 'Porsi Anggota 2030',
            'warna_badge': 'indigo',
            'urutan': 2
        })

        # 3. Hitung SHU untuk tahun 2030
        shu_2030 = models.hitung_shu_koperasi(100000000.0, tahun=2030)
        self.assertEqual(shu_2030['total_persentase'], 100.0)
        self.assertTrue(shu_2030['is_valid_100'])
        self.assertEqual(shu_2030['alokasi']['shu_bagian_anggota'], 90000000.0)
        self.assertEqual(shu_2030['alokasi']['jasa_modal_total'], 54000000.0)
        self.assertEqual(shu_2030['alokasi']['jasa_pinjaman_total'], 36000000.0)

        # 4. Update dana
        models.update_dana_shu(new_id, {
            'tahun': 2030,
            'nama_dana': 'Dana Riset AI & Big Data',
            'persentase': 10.0,
            'kategori': 'DANA',
            'is_bagian_anggota': 0,
            'keterangan': 'Diperbarui',
            'warna_badge': 'emerald',
            'urutan': 1
        })
        updated = models.get_dana_shu_by_id(new_id)
        self.assertEqual(updated['nama_dana'], 'Dana Riset AI & Big Data')

        # 5. Hapus dana tahun 2030
        models.hapus_dana_shu(new_id)
        shu_after_del = models.hitung_shu_koperasi(100000000.0, tahun=2030)
        self.assertEqual(shu_after_del['total_persentase'], 90.0)
        self.assertFalse(shu_after_del['is_valid_100'])

        # Bersihkan data test 2030
        conn = database.get_db()
        conn.execute("DELETE FROM alokasi_dana_shu WHERE tahun = 2030")
        conn.commit()
        conn.close()

    def test_06_superadmin_role_management(self):
        """Superadmin dapat mengubah role anggota lain tetapi tidak akun sendiri."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 7
            sess['role'] = 'superadmin'

        # Ubah Dama (ID 1) jadi admin
        res = self.client.post('/superadmin/manajemen-role', data={
            'anggota_id': 1,
            'new_role': 'admin'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        dama = models.get_anggota_by_id(1)
        self.assertEqual(dama['role'], 'admin')

        # Kembalikan Dama jadi anggota
        models.update_user_role(1, 'anggota')
        dama_reset = models.get_anggota_by_id(1)
        self.assertEqual(dama_reset['role'], 'anggota')

        # Coba degradasi akun sendiri (ID 7) -> Ditolak!
        res_self = self.client.post('/superadmin/manajemen-role', data={
            'anggota_id': 7,
            'new_role': 'anggota'
        }, follow_redirects=True)
        self.assertIn(b"tidak dapat mengubah level role akun Anda sendiri", res_self.data)
        gilang = models.get_anggota_by_id(7)
        self.assertEqual(gilang['role'], 'superadmin')

if __name__ == '__main__':
    unittest.main()
