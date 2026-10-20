from app import app
import models

def test_endpoints():
    client = app.test_client()

    print("Testing GET / ...")
    r = client.get('/', follow_redirects=True)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    print("GET / OK!")

    print("Testing GET /login ...")
    r = client.get('/login')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    print("GET /login OK!")

    # Login as admin
    print("Testing Login Admin...")
    r = client.post('/login', data={'username': 'admin', 'password': '123'}, follow_redirects=True)
    # password default is 'admin' or '123456'
    r = client.post('/login', data={'username': 'admin', 'password': '123456'}, follow_redirects=True)
    assert r.status_code == 200
    print("Admin login OK!")

    # Check Admin Dashboard
    print("Testing GET /admin/dashboard ...")
    r = client.get('/admin/dashboard')
    assert r.status_code == 200
    assert b'KOSITAS' in r.data
    print("Admin dashboard OK!")

    # Check Admin Anggota List
    print("Testing GET /admin/anggota ...")
    r = client.get('/admin/anggota')
    assert r.status_code == 200
    assert b'Dama Herdiaman' in r.data
    print("Admin anggota list OK!")

    # Check Admin Simpanan
    print("Testing GET /admin/simpanan ...")
    r = client.get('/admin/simpanan')
    assert r.status_code == 200
    print("Admin simpanan OK!")

    # Check Admin Pinjaman
    print("Testing GET /admin/pinjaman ...")
    r = client.get('/admin/pinjaman')
    assert r.status_code == 200
    print("Admin pinjaman OK!")

    # Check Admin Rekap Bulanan
    print("Testing GET /admin/rekap-bulanan ...")
    r = client.get('/admin/rekap-bulanan?bulan=2026-02')
    assert r.status_code == 200
    assert b'Rekap Transaksi Bulanan' in r.data
    print("Admin rekap bulanan OK!")

    # Check Laporan RAT Simpanan
    print("Testing GET /admin/laporan/simpanan ...")
    r = client.get('/admin/laporan/simpanan')
    assert r.status_code == 200
    assert b'REKAPITULASI SIMPANAN ANGGOTA' in r.data
    print("Laporan Simpanan OK!")

    # Check Laporan RAT Piutang
    print("Testing GET /admin/laporan/piutang ...")
    r = client.get('/admin/laporan/piutang')
    assert r.status_code == 200
    assert b'DATA PIUTANG ANGGOTA' in r.data
    print("Laporan Piutang OK!")

    # Check Laporan RAT SHU
    print("Testing GET /admin/laporan/shu ...")
    r = client.get('/admin/laporan/shu')
    assert r.status_code == 200
    assert b'DAFTAR PEMBAGIAN SHU ANGGOTA' in r.data
    print("Laporan SHU OK!")

    # Test Switch to Member (e.g. Gilang Abdul Aziz - id 7)
    print("Testing Switch User to Member 7 (Gilang Abdul Aziz)...")
    r = client.get('/switch-user/7', follow_redirects=True)
    assert r.status_code == 200
    print("Switch user OK!")

    # Check Member Dashboard
    print("Testing GET /anggota/dashboard ...")
    r = client.get('/anggota/dashboard')
    assert r.status_code == 200
    assert b'Gilang Abdul Aziz' in r.data
    print("Anggota dashboard OK!")

    # Check Member Simpanan (Buku Tabungan)
    print("Testing GET /anggota/simpanan ...")
    r = client.get('/anggota/simpanan')
    assert r.status_code == 200
    assert b'Buku Tabungan Simpanan Digital' in r.data
    print("Anggota simpanan OK!")

    # Check Member Pinjaman
    print("Testing GET /anggota/pinjaman ...")
    r = client.get('/anggota/pinjaman')
    assert r.status_code == 200
    assert b'Kartu Pinjaman' in r.data
    print("Anggota pinjaman OK!")

    # Check Member Rekap Bulanan
    print("Testing GET /anggota/rekap-bulanan ...")
    r = client.get('/anggota/rekap-bulanan')
    assert r.status_code == 200
    assert b'Rekap Pemotongan Gaji Bulanan' in r.data
    print("Anggota rekap bulanan OK!")

    # Check Member Pengajuan
    print("Testing GET /anggota/pengajuan ...")
    r = client.get('/anggota/pengajuan')
    assert r.status_code == 200
    assert b'Pengajuan Mandiri' in r.data
    print("Anggota pengajuan OK!")

    # Check Slip Bulanan Print
    print("Testing GET /cetak/slip-bulanan/7/2026-01 ...")
    r = client.get('/cetak/slip-bulanan/7/2026-01')
    assert r.status_code == 200
    assert b'SLIP RINCIAN PEMOTONGAN KOPERASI' in r.data
    print("Cetak Slip Bulanan OK!")

    # Test Excel Export
    print("Testing GET /admin/laporan/simpanan/export-excel ...")
    # Switch back to admin
    client.get('/switch-user/999')
    r = client.get('/admin/laporan/simpanan/export-excel')
    assert r.status_code == 200
    assert r.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    print("Excel export OK!")

    print("\nALL 17 ENDPOINT TESTS PASSED WITH 100% SUCCESS!")

if __name__ == '__main__':
    test_endpoints()
