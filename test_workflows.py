from app import app
import models
import database

def test_full_workflows():
    client = app.test_client()

    print("--- 1. Testing Login & Session ---")
    r = client.post('/login', data={'username': 'admin', 'password': '123456'}, follow_redirects=True)
    assert r.status_code == 200
    print("Admin login successfully verified!")

    print("--- 2. Testing Tambah Anggota Baru ---")
    r = client.post('/admin/anggota/tambah', data={
        'no_anggota': 'KST-099',
        'nama': 'Ahmad Fauzi, S.Tr.Stat',
        'nip': '199505052018011002',
        'jabatan': 'Anggota',
        'jenis_kelamin': 'Pria',
        'no_hp': '081299887766',
        'email': 'ahmad.fauzi@bps.go.id',
        'alamat': 'Singaparna, Tasikmalaya',
        'tanggal_masuk': '2026-02-01',
        'status': 'Aktif',
        'role': 'anggota',
        'simpanan_pokok_awal': '25000'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b'Ahmad Fauzi' in r.data
    print("Tambah anggota baru OK!")

    # Verify Ahmad Fauzi in DB
    new_member = models.get_all_anggota(search='Ahmad Fauzi')
    assert len(new_member) == 1
    new_id = new_member[0]['id']
    assert new_member[0]['simpanan_pokok'] == 25000
    print(f"Anggota baru ID {new_id} memiliki simpanan pokok Rp 25.000 OK!")

    print("--- 3. Testing Entri Transaksi Simpanan ---")
    r = client.post('/admin/simpanan', data={
        'anggota_id': new_id,
        'jenis_simpanan': 'Wajib',
        'tipe': 'SETOR',
        'nominal': '100000',
        'tanggal': '2026-02-15',
        'metode_bayar': 'Tunai',
        'bulan_buku': '2026-02',
        'keterangan': 'Setoran simpanan wajib perdana'
    }, follow_redirects=True)
    assert r.status_code == 200
    bal = models.get_anggota_balance(new_id)
    assert bal['simpanan_wajib'] == 100000
    print("Entri Simpanan Wajib Rp 100.000 berhasil dan saldo terupdate!")

    print("--- 4. Testing Tambah Pinjaman Baru ---")
    r = client.post('/admin/pinjaman/tambah', data={
        'anggota_id': new_id,
        'jenis_pinjaman': 'JAPEN',
        'plafon_pokok': '5000000',
        'tenor_bulan': '10',
        'margin_persen': '10.0',
        'tanggal_cair': '2026-02-15',
        'keperluan': 'Pembelian laptop operasional kantor',
        'keterangan': 'Akad Murabahah JAPEN'
    }, follow_redirects=True)
    assert r.status_code == 200
    bal = models.get_anggota_balance(new_id)
    assert bal['piutang_japen'] == 5000000
    print("Tambah Pinjaman JAPEN Rp 5.000.000 berhasil dan saldo piutang terupdate!")

    # Get the loan ID
    loans = models.get_pinjaman_by_anggota(new_id)
    assert len(loans) == 1
    loan_id = loans[0]['id']

    print("--- 5. Testing Bayar Angsuran Pinjaman ---")
    r = client.post(f'/admin/pinjaman/{loan_id}/bayar', data={
        'pinjaman_id': loan_id,
        'tanggal_bayar': '2026-02-20',
        'bulan_buku': '2026-02',
        'angsuran_pokok': '500000',
        'angsuran_margin': '50000',
        'metode_bayar': 'Potong Gaji',
        'keterangan': 'Angsuran ke-1 JAPEN'
    }, follow_redirects=True)
    assert r.status_code == 200
    bal_after = models.get_anggota_balance(new_id)
    assert bal_after['piutang_japen'] == 4500000
    print("Pembayaran angsuran berhasil! Sisa pokok berkurang menjadi Rp 4.500.000!")

    print("--- 6. Testing Rekap Bulanan Kolektif Potong Gaji ---")
    # Execute batch deduction for 2026-03
    r = client.post('/admin/rekap-bulanan/proses', data={'bulan_buku': '2026-03'}, follow_redirects=True)
    assert r.status_code == 200
    assert b'berhasil diselesaikan' in r.data or b'Sudah Diproses' in r.data
    print("Eksekusi potong gaji kolektif bulanan 2026-03 berhasil!")

    print("--- 7. Testing Pengajuan Mandiri Anggota ---")
    # Switch to Ahmad Fauzi
    client.get(f'/switch-user/{new_id}')
    r = client.post('/anggota/pengajuan', data={
        'jenis': 'PINJAMAN',
        'kategori': 'Bon Putih',
        'nominal': '800000',
        'tenor_bulan': '2',
        'alasan': 'Kebutuhan mendesak keluarga'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b'berhasil dikirim' in r.data
    print("Pengajuan mandiri anggota berhasil diajukan!")

    print("--- 8. Testing Persetujuan Pengurus atas Pengajuan Online ---")
    # Switch to admin
    client.get('/switch-user/999')
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM pengajuan_online WHERE anggota_id = ? AND status = 'Menunggu' ORDER BY id DESC LIMIT 1", (new_id,))
    req_id = c.fetchone()[0]
    conn.close()

    r = client.post(f'/admin/pengajuan/{req_id}/proses', data={
        'action': 'TERIMA',
        'catatan_admin': 'Disetujui oleh Pengurus KOSITAS'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b'disetujui' in r.data
    print("Pengurus menyetujui pengajuan mandiri anggota secara sukses!")

    print("--- 9. Testing Unduh Semua Laporan Excel ---")
    for url, name in [
        ('/admin/rekap-bulanan/export-excel?bulan=2026-03', 'Rekap Bulanan'),
        ('/admin/laporan/simpanan/export-excel', 'Rekap Simpanan'),
        ('/admin/laporan/piutang/export-excel', 'Data Piutang'),
        ('/admin/laporan/shu/export-excel', 'Daftar SHU')
    ]:
        r = client.get(url)
        assert r.status_code == 200
        assert len(r.data) > 1000
        print(f"Export Excel {name}: OK ({len(r.data)} bytes)!")

    print("\n=======================================================")
    print("ALL ADVANCED BUSINESS WORKFLOW TESTS COMPLETED 100%!")
    print("=======================================================")

if __name__ == '__main__':
    test_full_workflows()
