from app import app
import models
import database

def test_features():
    client = app.test_client()

    print("--- 1. Login Admin ---")
    client.post('/login', data={'username': 'admin', 'password': '123456'}, follow_redirects=True)

    # Pick an active loan to test Early Settlement (e.g. loan for member 10 - Andri Irawan)
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT id, no_pinjaman, anggota_id, saldo_pokok, saldo_margin FROM pinjaman WHERE status = 'Aktif' AND saldo_pokok > 0 LIMIT 1")
    row = c.fetchone()
    conn.close()

    loan_id = row['id']
    no_pinj = row['no_pinjaman']
    agt_id = row['anggota_id']
    s_pokok = row['saldo_pokok']
    print(f"Testing Early Settlement on Loan ID {loan_id} ({no_pinj}) Saldo Pokok: Rp {s_pokok:,.0f} ...")

    # 1. Test Pelunasan Dipercepat
    r = client.post(f'/admin/pinjaman/{loan_id}/pelunasan-dipercepat', data={
        'tanggal_lunas': '2026-02-18',
        'diskon_margin': '50000',
        'metode_bayar': 'Tunai',
        'keterangan': 'Pelunasan lunas dipercepat tunai di kantor KOSITAS'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b'berhasil dilunasi dipercepat' in r.data

    # Verify loan status is now 'Lunas' and saldo_pokok = 0
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT status, saldo_pokok, pelunasan_tipe FROM pinjaman WHERE id = ?", (loan_id,))
    res_lunas = c.fetchone()
    conn.close()
    assert res_lunas['status'] == 'Lunas'
    assert res_lunas['saldo_pokok'] == 0.0
    assert res_lunas['pelunasan_tipe'] == 'Pelunasan Dipercepat'
    print(f"Loan {no_pinj} successfully closed as Lunas (Pelunasan Dipercepat)!")

    # Test Slip Pelunasan print
    r = client.get(f'/cetak/slip-pelunasan/{loan_id}')
    assert r.status_code == 200
    assert b'SURAT KETERANGAN PELUNASAN PINJAMAN' in r.data
    print("Cetak Surat Keterangan Pelunasan Pinjaman: OK!")

    # 2. Pick another active loan to test Top Up (e.g. member 7 or member 12)
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT id, no_pinjaman, anggota_id, saldo_pokok, plafon_pokok FROM pinjaman WHERE status = 'Aktif' AND jenis_pinjaman = 'JAPAN' LIMIT 1")
    row_top = c.fetchone()
    conn.close()

    top_loan_id = row_top['id']
    top_no = row_top['no_pinjaman']
    top_agt = row_top['anggota_id']
    top_sisa = row_top['saldo_pokok']
    print(f"\nTesting Top Up Refinancing on Loan ID {top_loan_id} ({top_no}) Sisa Pokok: Rp {top_sisa:,.0f} ...")

    new_plafon = top_sisa + 10000000 # Top up dengan tambahan 10 juta
    r = client.post(f'/admin/pinjaman/{top_loan_id}/topup', data={
        'jenis_pinjaman': 'JAPAN',
        'plafon_pokok': str(new_plafon),
        'tenor_bulan': '24',
        'margin_persen': '25.0',
        'tanggal_cair': '2026-02-20',
        'keperluan': 'Top Up peremajaan alat produksi & modal'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b'Proses Top Up berhasil' in r.data

    # Verify old loan is 'Lunas' and new loan is 'Aktif'
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT status, pelunasan_tipe FROM pinjaman WHERE id = ?", (top_loan_id,))
    res_old = c.fetchone()
    assert res_old['status'] == 'Lunas'
    assert res_old['pelunasan_tipe'] == 'Top Up'

    c.execute("SELECT id, no_pinjaman, status, plafon_pokok, is_topup FROM pinjaman WHERE ref_pinjaman_lama_id = ?", (top_loan_id,))
    res_new = c.fetchone()
    conn.close()
    assert res_new is not None
    assert res_new['status'] == 'Aktif'
    assert res_new['is_topup'] == 1
    new_pj_id = res_new['id']
    print(f"Old loan {top_no} marked as Lunas (Top Up). New loan {res_new['no_pinjaman']} created with Plafon Rp {res_new['plafon_pokok']:,.0f}!")

    # Test Slip Top Up print
    r = client.get(f'/cetak/slip-topup/{new_pj_id}')
    assert r.status_code == 200
    assert b'BUKTI REALISASI TOP UP PEMBIAYAAN SYARIAH' in r.data
    print("Cetak Bukti Realisasi Top Up: OK!")

    # 3. Test Annual Recap Report (Filter Tahunan)
    print("\nTesting Annual Reporting (Filter Tahunan 2025 & 2026) ...")
    r = client.get('/admin/rekap-bulanan?periode_type=tahunan&tahun=2025')
    assert r.status_code == 200
    assert b'Tahun Buku 2025' in r.data
    print("Rekap Tahunan 2025: OK!")

    r = client.get('/admin/rekap-bulanan?periode_type=tahunan&tahun=2026')
    assert r.status_code == 200
    assert b'Tahun Buku 2026' in r.data
    print("Rekap Tahunan 2026: OK!")

    # Test Export Excel Tahunan
    r = client.get('/admin/rekap-tahunan/export-excel?tahun=2025')
    assert r.status_code == 200
    assert len(r.data) > 1000
    print(f"Export Excel Rekap Tahunan: OK ({len(r.data)} bytes)!")

    # 4. Test Slip Tabungan Bulanan
    print("\nTesting Slip Tabungan Bulanan Cetak ...")
    r = client.get(f'/cetak/slip-tabungan/{top_agt}/2025-12')
    assert r.status_code == 200
    assert b'SLIP MUTASI SETORAN TABUNGAN BULANAN' in r.data
    print("Cetak Slip Tabungan Bulanan: OK!")

    # 5. Test Monthly Slip with Settled / TopUp Note
    print("\nTesting Monthly Salary Deduction Slip with Special Settlement Note ...")
    r = client.get(f'/cetak/slip-bulanan/{top_agt}/2026-02')
    assert r.status_code == 200
    assert b'Catatan Khusus Pembebasan / Penyesuaian Angsuran' in r.data
    print("Slip Gaji Bulanan displays special note for Top Up / Settlement OK!")

    print("\n=======================================================")
    print("ALL NEW ENHANCEMENTS AND FEATURES PASSED 100%!")
    print("=======================================================")

if __name__ == '__main__':
    test_features()
