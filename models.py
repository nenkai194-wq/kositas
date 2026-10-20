import sqlite3
import uuid
from datetime import datetime
from database import get_db

# Helper to generate unique transaction and loan codes
def generate_code(prefix):
    now = datetime.now()
    return f"{prefix}-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

# ----------------- MASTER ANGGOTA -----------------
def get_all_anggota(status_filter=None, search=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM anggota WHERE 1=1"
    params = []

    if status_filter and status_filter != 'Semua':
        query += " AND status = ?"
        params.append(status_filter)

    if search:
        query += " AND (nama LIKE ? OR no_anggota LIKE ? OR nip LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY id ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    members = [dict(row) for row in rows]

    # Attach summary balances for each member
    for m in members:
        balances = get_anggota_balance(m['id'])
        m.update(balances)

    conn.close()
    return members

def get_anggota_by_id(anggota_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM anggota WHERE id = ?", (anggota_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    member = dict(row)
    member.update(get_anggota_balance(anggota_id))
    return member

def create_anggota(data):
    conn = get_db()
    cursor = conn.cursor()
    
    # Auto-generate no_anggota if not provided
    no_anggota = data.get('no_anggota')
    if not no_anggota:
        cursor.execute("SELECT MAX(id) FROM anggota")
        max_id = cursor.fetchone()[0] or 0
        no_anggota = f"KST-{(max_id + 1):03d}"

    cursor.execute('''
    INSERT INTO anggota (no_anggota, nama, nip, jabatan, jenis_kelamin, no_hp, email, alamat, tanggal_masuk, status, password, role)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        no_anggota,
        data.get('nama'),
        data.get('nip', ''),
        data.get('jabatan', 'Anggota'),
        data.get('jenis_kelamin', 'Pria'),
        data.get('no_hp', ''),
        data.get('email', ''),
        data.get('alamat', ''),
        data.get('tanggal_masuk', datetime.now().strftime('%Y-%m-%d')),
        data.get('status', 'Aktif'),
        data.get('password', '123456'),
        data.get('role', 'anggota')
    ))
    new_id = cursor.lastrowid

    # If new member, record initial Simpanan Pokok (Rp 25,000)
    setor_pokok = float(data.get('simpanan_pokok_awal', 25000))
    if setor_pokok > 0:
        no_trx = generate_code('TRX-SP')
        cursor.execute('''
        INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
        VALUES (?, ?, ?, 'Pokok', 'SETOR', ?, 'Setoran Simpanan Pokok Awal Anggota', 'Tunai', ?, 'Admin')
        ''', (no_trx, new_id, datetime.now().strftime('%Y-%m-%d'), setor_pokok, datetime.now().strftime('%Y-%m')))

    conn.commit()
    conn.close()
    return new_id

def update_anggota(anggota_id, data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE anggota
    SET no_anggota = ?, nama = ?, nip = ?, jabatan = ?, jenis_kelamin = ?, no_hp = ?, email = ?, alamat = ?, status = ?, role = ?
    WHERE id = ?
    ''', (
        data.get('no_anggota'),
        data.get('nama'),
        data.get('nip', ''),
        data.get('jabatan', 'Anggota'),
        data.get('jenis_kelamin', 'Pria'),
        data.get('no_hp', ''),
        data.get('email', ''),
        data.get('alamat', ''),
        data.get('status', 'Aktif'),
        data.get('role', 'anggota'),
        anggota_id
    ))
    conn.commit()
    conn.close()

# ----------------- BALANCES & REKAP ANGGOTA -----------------
def get_anggota_balance(anggota_id):
    conn = get_db()
    cursor = conn.cursor()

    # Hitung simpanan per jenis
    cursor.execute('''
    SELECT jenis_simpanan,
           SUM(CASE WHEN tipe = 'SETOR' THEN nominal ELSE -nominal END) as saldo
    FROM transaksi_simpanan
    WHERE anggota_id = ?
    GROUP BY jenis_simpanan
    ''', (anggota_id,))
    simpanan_rows = cursor.fetchall()
    
    simpanan = {
        'pokok': 0.0,
        'wajib': 0.0,
        'lebaran': 0.0,
        'qurban': 0.0,
        'manasuka': 0.0
    }
    for row in simpanan_rows:
        jenis = row['jenis_simpanan'].lower()
        if 'pokok' in jenis:
            simpanan['pokok'] = float(row['saldo'] or 0)
        elif 'wajib' in jenis:
            simpanan['wajib'] = float(row['saldo'] or 0)
        elif 'lebaran' in jenis:
            simpanan['lebaran'] = float(row['saldo'] or 0)
        elif 'qurban' in jenis:
            simpanan['qurban'] = float(row['saldo'] or 0)
        elif 'manasuka' in jenis or 'sukarela' in jenis or 'lainnya' in jenis:
            simpanan['manasuka'] = float(row['saldo'] or 0)

    simpanan['total_simpanan'] = sum(simpanan.values())

    # Hitung saldo pinjaman berjalan
    cursor.execute('''
    SELECT jenis_pinjaman,
           SUM(saldo_pokok) as sisa_pokok,
           SUM(saldo_margin) as sisa_margin
    FROM pinjaman
    WHERE anggota_id = ? AND status = 'Aktif'
    GROUP BY jenis_pinjaman
    ''', (anggota_id,))
    pinjaman_rows = cursor.fetchall()

    pinjaman_data = {
        'piutang_japan': 0.0,
        'piutang_japen': 0.0,
        'piutang_bon_putih': 0.0,
        'piutang_barang': 0.0,
        'total_piutang_pokok': 0.0,
        'total_piutang_margin': 0.0
    }
    for row in pinjaman_rows:
        jenis = row['jenis_pinjaman']
        pokok = float(row['sisa_pokok'] or 0)
        margin = float(row['sisa_margin'] or 0)
        pinjaman_data['total_piutang_pokok'] += pokok
        pinjaman_data['total_piutang_margin'] += margin

        if 'JAPAN' in jenis.upper():
            pinjaman_data['piutang_japan'] += pokok
        elif 'JAPEN' in jenis.upper():
            pinjaman_data['piutang_japen'] += pokok
        elif 'BON' in jenis.upper() or 'PUTIH' in jenis.upper() or 'LAINNYA' in jenis.upper():
            pinjaman_data['piutang_bon_putih'] += pokok
        elif 'BARANG' in jenis.upper():
            pinjaman_data['piutang_barang'] += pokok

    pinjaman_data['total_piutang'] = pinjaman_data['total_piutang_pokok']

    # Total jasa / margin pinjaman yang telah dibayar (untuk perhitungan SHU)
    cursor.execute('''
    SELECT SUM(angsuran_margin) as total_jasa_dibayar
    FROM angsuran_pinjaman
    WHERE anggota_id = ?
    ''', (anggota_id,))
    jasa_row = cursor.fetchone()
    total_jasa = float(jasa_row['total_jasa_dibayar'] or 0) if jasa_row else 0.0

    conn.close()
    return {
        'simpanan_pokok': simpanan['pokok'],
        'simpanan_wajib': simpanan['wajib'],
        'simpanan_lebaran': simpanan['lebaran'],
        'simpanan_qurban': simpanan['qurban'],
        'simpanan_manasuka': simpanan['manasuka'],
        'total_simpanan': simpanan['total_simpanan'],
        'piutang_japan': pinjaman_data['piutang_japan'],
        'piutang_japen': pinjaman_data['piutang_japen'],
        'piutang_bon_putih': pinjaman_data['piutang_bon_putih'],
        'piutang_barang': pinjaman_data['piutang_barang'],
        'total_piutang': pinjaman_data['total_piutang'],
        'total_piutang_margin': pinjaman_data['total_piutang_margin'],
        'total_jasa_pinjaman_dibayar': total_jasa
    }

# ----------------- TRANSAKSI SIMPANAN -----------------
def tambah_transaksi_simpanan(data):
    conn = get_db()
    cursor = conn.cursor()
    
    no_transaksi = data.get('no_transaksi') or generate_code('TRX-SIMP')
    tanggal = data.get('tanggal') or datetime.now().strftime('%Y-%m-%d')
    bulan_buku = data.get('bulan_buku') or tanggal[:7]
    tipe = data.get('tipe', 'SETOR').upper()
    nominal = float(data.get('nominal', 0))
    anggota_id = int(data.get('anggota_id'))
    jenis = data.get('jenis_simpanan')
    metode_bayar = data.get('metode_bayar', 'Tunai')
    keterangan = (data.get('keterangan') or '').strip()
    alasan_khusus = (data.get('alasan_khusus') or '').strip()
    update_status_keluar = data.get('update_status_keluar')

    bal = get_anggota_balance(anggota_id)

    # 1. ATURAN SIMPANAN POKOK: Disetor 1x saat pertama masuk keanggotaan koperasi KOSITAS
    if tipe == 'SETOR' and 'pokok' in jenis.lower():
        if bal['simpanan_pokok'] >= 25000 and not data.get('force_setor_pokok'):
            conn.close()
            return False, f"Anggota sudah melunasi Simpanan Pokok (Saldo: Rp {bal['simpanan_pokok']:,.0f}). Sesuai aturan KOSITAS, Simpanan Pokok hanya dibayar 1x saat awal masuk keanggotaan."

    # 2. VALIDASI PENARIKAN (TARIK)
    if tipe == 'TARIK':
        current_bal = 0.0
        is_pokok_wajib = False
        if 'pokok' in jenis.lower():
            current_bal = bal['simpanan_pokok']
            is_pokok_wajib = True
        elif 'wajib' in jenis.lower():
            current_bal = bal['simpanan_wajib']
            is_pokok_wajib = True
        elif 'lebaran' in jenis.lower():
            current_bal = bal['simpanan_lebaran']
        elif 'qurban' in jenis.lower():
            current_bal = bal['simpanan_qurban']
        else:
            current_bal = bal['simpanan_manasuka']

        # ATURAN KOSITAS: Simpanan Pokok & Wajib TIDAK BISA ditarik kecuali alasan Pensiun, Meninggal Dunia, atau Pindah Kantor
        if is_pokok_wajib:
            valid_reasons = ['pensiun', 'meninggal', 'pindah kantor', 'mutasi']
            found_reason = False
            for vr in valid_reasons:
                if vr in alasan_khusus.lower() or vr in keterangan.lower():
                    found_reason = True
                    break
            
            if not found_reason:
                conn.close()
                return False, f"Simpanan {jenis} TIDAK DAPAT ditarik! Sesuai AD/ART KOSITAS, Simpanan Pokok & Wajib terkunci dan hanya dapat dicairkan apabila anggota keluar karena alasan Pensiun, Meninggal Dunia, atau Pindah Kantor/Mutasi."

            if alasan_khusus:
                keterangan = f"[PENARIKAN KHUSUS - {alasan_khusus.upper()}] {keterangan}".strip()

        if nominal > current_bal:
            conn.close()
            return False, f"Saldo {jenis} tidak mencukupi! Saldo saat ini: Rp {current_bal:,.0f}"

        # Jika penarikan simpanan pokok / wajib dengan alasan khusus dan diminta update status keanggotaan
        if is_pokok_wajib and (update_status_keluar or (nominal >= current_bal and 'pokok' in jenis.lower())):
            cursor.execute("UPDATE anggota SET status = 'Keluar' WHERE id = ?", (anggota_id,))

    cursor.execute('''
    INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        no_transaksi,
        anggota_id,
        tanggal,
        jenis,
        tipe,
        nominal,
        keterangan,
        metode_bayar,
        bulan_buku,
        data.get('created_by', 'Admin')
    ))
    conn.commit()
    conn.close()
    return True, "Transaksi simpanan berhasil dicatat."

def get_transaksi_simpanan_by_anggota(anggota_id, jenis_filter=None):
    conn = get_db()
    cursor = conn.cursor()
    query = '''
    SELECT t.*, a.nama as nama_anggota, a.no_anggota
    FROM transaksi_simpanan t
    JOIN anggota a ON t.anggota_id = a.id
    WHERE t.anggota_id = ?
    '''
    params = [anggota_id]

    if jenis_filter and jenis_filter != 'Semua':
        query += " AND t.jenis_simpanan = ?"
        params.append(jenis_filter)

    query += " ORDER BY t.tanggal DESC, t.id DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_all_transaksi_simpanan(limit=100, bulan_filter=None):
    conn = get_db()
    cursor = conn.cursor()
    query = '''
    SELECT t.*, a.nama as nama_anggota, a.no_anggota
    FROM transaksi_simpanan t
    JOIN anggota a ON t.anggota_id = a.id
    WHERE 1=1
    '''
    params = []
    if bulan_filter:
        query += " AND t.bulan_buku = ?"
        params.append(bulan_filter)

    query += " ORDER BY t.tanggal DESC, t.id DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

# ----------------- TRANSAKSI PINJAMAN -----------------
def tambah_pinjaman(data):
    conn = get_db()
    cursor = conn.cursor()

    no_pinjaman = data.get('no_pinjaman') or generate_code('PJ')
    anggota_id = int(data.get('anggota_id'))
    jenis_pinjaman = data.get('jenis_pinjaman')
    plafon_pokok = float(data.get('plafon_pokok', 0))
    tenor_bulan = int(data.get('tenor_bulan', 10))
    margin_persen = float(data.get('margin_persen', 0.0))
    
    # Hitung margin dan biaya provisi/DRK sesuai ketentuan KOSITAS
    # JAPAN: Provisi 1%, DRK 0.5%, margin kl 25-30% atau disepakati per tenor
    # JAPEN: Provisi 1%, tenor maks 10 bln
    # Bon Putih: 2% tetap / bln
    # Pinjaman Barang: margin min 20%
    if 'margin_nominal' in data and float(data.get('margin_nominal', 0)) > 0:
        margin_nominal = float(data['margin_nominal'])
    else:
        margin_nominal = (plafon_pokok * margin_persen) / 100.0

    total_pinjaman = plafon_pokok + margin_nominal
    angsuran_pokok_bulanan = round(plafon_pokok / tenor_bulan, 2)
    angsuran_margin_bulanan = round(margin_nominal / tenor_bulan, 2)
    total_angsuran_bulanan = angsuran_pokok_bulanan + angsuran_margin_bulanan

    biaya_provisi = round((plafon_pokok * 1.0) / 100.0, 2)
    biaya_drk = round((plafon_pokok * 0.5) / 100.0, 2) if 'JAPAN' in jenis_pinjaman.upper() else 0.0

    tanggal_cair = data.get('tanggal_cair') or datetime.now().strftime('%Y-%m-%d')
    tanggal_pengajuan = data.get('tanggal_pengajuan') or datetime.now().strftime('%Y-%m-%d')
    status = data.get('status', 'Aktif')

    cursor.execute('''
    INSERT INTO pinjaman (
        no_pinjaman, anggota_id, jenis_pinjaman, tanggal_pengajuan, tanggal_cair,
        plafon_pokok, margin_persen, margin_nominal, total_pinjaman, tenor_bulan,
        angsuran_pokok_bulanan, angsuran_margin_bulanan, total_angsuran_bulanan,
        biaya_provisi, biaya_drk, saldo_pokok, saldo_margin, angsuran_ke,
        status, keperluan, keterangan
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        no_pinjaman,
        anggota_id,
        jenis_pinjaman,
        tanggal_pengajuan,
        tanggal_cair,
        plafon_pokok,
        margin_persen,
        margin_nominal,
        total_pinjaman,
        tenor_bulan,
        angsuran_pokok_bulanan,
        angsuran_margin_bulanan,
        total_angsuran_bulanan,
        biaya_provisi,
        biaya_drk,
        plafon_pokok, # Saldo pokok awal = plafon
        margin_nominal, # Saldo margin awal
        0, # Angsuran ke awal
        status,
        data.get('keperluan', ''),
        data.get('keterangan', '')
    ))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def bayar_angsuran(data):
    conn = get_db()
    cursor = conn.cursor()

    pinjaman_id = int(data.get('pinjaman_id'))
    cursor.execute("SELECT * FROM pinjaman WHERE id = ?", (pinjaman_id,))
    pj = cursor.fetchone()
    if not pj:
        conn.close()
        return False, "Pinjaman tidak ditemukan!"

    pj = dict(pj)
    if pj['status'] == 'Lunas':
        conn.close()
        return False, "Pinjaman ini sudah lunas!"

    angsuran_pokok = float(data.get('angsuran_pokok', pj['angsuran_pokok_bulanan']))
    angsuran_margin = float(data.get('angsuran_margin', pj['angsuran_margin_bulanan']))
    total_bayar = angsuran_pokok + angsuran_margin

    # Update sisa saldo pinjaman
    sisa_pokok = max(0.0, pj['saldo_pokok'] - angsuran_pokok)
    sisa_margin = max(0.0, pj['saldo_margin'] - angsuran_margin)
    angsuran_ke = pj['angsuran_ke'] + 1
    status_baru = 'Lunas' if (sisa_pokok <= 100) else 'Aktif' # toleransi pembulatan

    no_angsuran = data.get('no_angsuran') or generate_code('ANGS')
    tanggal_bayar = data.get('tanggal_bayar') or datetime.now().strftime('%Y-%m-%d')
    bulan_buku = data.get('bulan_buku') or tanggal_bayar[:7]

    # Catat ke angsuran_pinjaman
    cursor.execute('''
    INSERT INTO angsuran_pinjaman (
        no_angsuran, pinjaman_id, anggota_id, tanggal_bayar, angsuran_ke,
        angsuran_pokok, angsuran_margin, total_bayar, sisa_pokok_setelah,
        bulan_buku, metode_bayar, keterangan
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        no_angsuran,
        pj['id'],
        pj['anggota_id'],
        tanggal_bayar,
        angsuran_ke,
        angsuran_pokok,
        angsuran_margin,
        total_bayar,
        sisa_pokok,
        bulan_buku,
        data.get('metode_bayar', 'Potong Gaji'),
        data.get('keterangan', f"Pembayaran angsuran ke-{angsuran_ke}")
    ))

    # Update tabel pinjaman
    cursor.execute('''
    UPDATE pinjaman
    SET saldo_pokok = ?, saldo_margin = ?, angsuran_ke = ?, status = ?
    WHERE id = ?
    ''', (sisa_pokok, sisa_margin, angsuran_ke, status_baru, pinjaman_id))

    conn.commit()
    conn.close()
    return True, f"Angsuran ke-{angsuran_ke} berhasil dicatat. Sisa pokok: Rp {sisa_pokok:,.0f}"

def get_pinjaman_by_anggota(anggota_id, status_filter=None):
    conn = get_db()
    cursor = conn.cursor()
    query = '''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota
    FROM pinjaman p
    JOIN anggota a ON p.anggota_id = a.id
    WHERE p.anggota_id = ?
    '''
    params = [anggota_id]
    if status_filter and status_filter != 'Semua':
        query += " AND p.status = ?"
        params.append(status_filter)

    query += " ORDER BY p.tanggal_pengajuan DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]

    for r in rows:
        # Ambil riwayat angsuran untuk setiap pinjaman
        cursor.execute('''
        SELECT * FROM angsuran_pinjaman
        WHERE pinjaman_id = ?
        ORDER BY angsuran_ke ASC
        ''', (r['id'],))
        r['riwayat_angsuran'] = [dict(ang) for ang in cursor.fetchall()]
        # Persentase lunas
        if r['plafon_pokok'] > 0:
            persen = ((r['plafon_pokok'] - r['saldo_pokok']) / r['plafon_pokok']) * 100
            r['persen_lunas'] = min(100.0, max(0.0, round(persen, 1)))
        else:
            r['persen_lunas'] = 100.0

    conn.close()
    return rows

def get_all_pinjaman(status_filter=None, jenis_filter=None):
    conn = get_db()
    cursor = conn.cursor()
    query = '''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota, a.nip, a.jabatan
    FROM pinjaman p
    JOIN anggota a ON p.anggota_id = a.id
    WHERE 1=1
    '''
    params = []
    if status_filter and status_filter != 'Semua':
        query += " AND p.status = ?"
        params.append(status_filter)
    if jenis_filter and jenis_filter != 'Semua':
        query += " AND p.jenis_pinjaman = ?"
        params.append(jenis_filter)

    query += " ORDER BY p.id DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    
    for r in rows:
        if r['plafon_pokok'] > 0:
            persen = ((r['plafon_pokok'] - r['saldo_pokok']) / r['plafon_pokok']) * 100
            r['persen_lunas'] = min(100.0, max(0.0, round(persen, 1)))
        else:
            r['persen_lunas'] = 100.0

    conn.close()
    return rows

# ----------------- PELUNASAN DIPERCEPAT & TOP UP PINJAMAN -----------------
def proses_pelunasan_dipercepat(pinjaman_id, diskon_margin=0.0, tanggal_lunas=None, metode_bayar='Tunai', keterangan='', created_by='Admin'):
    """
    Melunasi sisa angsuran pinjaman sekaligus sebelum jatuh tempo (Early Settlement).
    Pinjaman otomatis menjadi LUNAS dan tidak akan dipotong lagi pada payroll bulanan berikutnya.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pinjaman WHERE id = ?", (pinjaman_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "Pinjaman tidak ditemukan!"

    pj = dict(row)
    if pj['status'] == 'Lunas':
        conn.close()
        return False, "Pinjaman ini sudah lunas sebelumnya!"

    sisa_pokok = float(pj['saldo_pokok'])
    sisa_margin = float(pj['saldo_margin'])
    diskon = min(sisa_margin, float(diskon_margin or 0.0))
    margin_bayar = max(0.0, sisa_margin - diskon)
    total_bayar = sisa_pokok + margin_bayar
    angsuran_ke = pj['angsuran_ke'] + 1

    tgl = tanggal_lunas or datetime.now().strftime('%Y-%m-%d')
    bln = tgl[:7]
    no_angs = generate_code('ANGS-LUNAS')

    # Catat angsuran pelunasan
    cursor.execute('''
    INSERT INTO angsuran_pinjaman (
        no_angsuran, pinjaman_id, anggota_id, tanggal_bayar, angsuran_ke,
        angsuran_pokok, angsuran_margin, total_bayar, sisa_pokok_setelah,
        bulan_buku, metode_bayar, keterangan
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?)
    ''', (
        no_angs, pj['id'], pj['anggota_id'], tgl, angsuran_ke,
        sisa_pokok, margin_bayar, total_bayar, bln, metode_bayar,
        keterangan or f"Pelunasan Dipercepat Pinjaman {pj['no_pinjaman']}"
    ))

    # Update pinjaman
    cursor.execute('''
    UPDATE pinjaman
    SET saldo_pokok = 0.0, saldo_margin = 0.0, angsuran_ke = ?, status = 'Lunas',
        pelunasan_tipe = 'Pelunasan Dipercepat', tanggal_lunas = ?,
        sisa_pokok_dilunasi = ?, diskon_margin = ?
    WHERE id = ?
    ''', (angsuran_ke, tgl, sisa_pokok, diskon, pinjaman_id))

    conn.commit()
    conn.close()
    return True, f"Pinjaman {pj['no_pinjaman']} berhasil dilunasi dipercepat! Pembayaran pokok: Rp {sisa_pokok:,.0f}, margin: Rp {margin_bayar:,.0f}."

def proses_topup_pinjaman(data, created_by='Admin'):
    """
    Proses peminjaman ulang (Top Up) dengan melunasi sisa pokok pinjaman sebelumnya.
    Sesuai AD/ART KOSITAS: Sisa pokok pinjaman lama dipotong langsung dari pencairan plafon baru.
    Pinjaman lama otomatis ditutup (Lunas), pinjaman baru mulai berjalan.
    """
    conn = get_db()
    cursor = conn.cursor()

    pinjaman_lama_id = int(data.get('pinjaman_lama_id'))
    cursor.execute("SELECT * FROM pinjaman WHERE id = ?", (pinjaman_lama_id,))
    row_lama = cursor.fetchone()
    if not row_lama:
        conn.close()
        return False, "Pinjaman lama tidak ditemukan!", None

    pj_lama = dict(row_lama)
    if pj_lama['status'] != 'Aktif':
        conn.close()
        return False, "Hanya pinjaman berstatus aktif yang dapat di-Top Up!", None

    sisa_pokok_lama = float(pj_lama['saldo_pokok'])
    anggota_id = pj_lama['anggota_id']

    # Data pinjaman baru
    jenis_pinjaman = data.get('jenis_pinjaman', pj_lama['jenis_pinjaman'])
    plafon_baru = float(data.get('plafon_pokok', 0))
    tenor_baru = int(data.get('tenor_bulan', 10))
    margin_persen = float(data.get('margin_persen', 0.0))

    if plafon_baru <= sisa_pokok_lama:
        conn.close()
        return False, f"Plafon pinjaman baru (Rp {plafon_baru:,.0f}) harus lebih besar dari sisa pokok pinjaman lama (Rp {sisa_pokok_lama:,.0f})!", None

    if 'margin_nominal' in data and float(data.get('margin_nominal', 0)) > 0:
        margin_nominal = float(data['margin_nominal'])
    else:
        margin_nominal = (plafon_baru * margin_persen) / 100.0

    total_pinjaman = plafon_baru + margin_nominal
    angsuran_pokok_bulanan = round(plafon_baru / tenor_baru, 2)
    angsuran_margin_bulanan = round(margin_nominal / tenor_baru, 2)
    total_angsuran_bulanan = angsuran_pokok_bulanan + angsuran_margin_bulanan

    biaya_provisi = round((plafon_baru * 1.0) / 100.0, 2)
    biaya_drk = round((plafon_baru * 0.5) / 100.0, 2) if 'JAPAN' in jenis_pinjaman.upper() else 0.0

    # Dana Bersih Diterima Anggota = Plafon Baru - Sisa Pokok Lama - Provisi - DRK
    dana_cair = plafon_baru - sisa_pokok_lama - biaya_provisi - biaya_drk

    tgl_cair = data.get('tanggal_cair') or datetime.now().strftime('%Y-%m-%d')
    bln_cair = tgl_cair[:7]

    # 1. Lunaskan pinjaman lama
    no_angs_lama = generate_code('ANGS-TOPUP')
    cursor.execute('''
    INSERT INTO angsuran_pinjaman (
        no_angsuran, pinjaman_id, anggota_id, tanggal_bayar, angsuran_ke,
        angsuran_pokok, angsuran_margin, total_bayar, sisa_pokok_setelah,
        bulan_buku, metode_bayar, keterangan
    ) VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, 0.0, ?, 'Top Up Refinancing', ?)
    ''', (
        no_angs_lama, pj_lama['id'], anggota_id, tgl_cair, pj_lama['angsuran_ke'] + 1,
        sisa_pokok_lama, sisa_pokok_lama, bln_cair,
        f"Pelunasan otomatis melalui fasilitas Top Up ke Pinjaman Baru"
    ))

    cursor.execute('''
    UPDATE pinjaman
    SET saldo_pokok = 0.0, saldo_margin = 0.0, status = 'Lunas',
        pelunasan_tipe = 'Top Up', tanggal_lunas = ?,
        sisa_pokok_dilunasi = ?
    WHERE id = ?
    ''', (tgl_cair, sisa_pokok_lama, pj_lama['id']))

    # 2. Buat pinjaman baru dengan referensi pinjaman lama
    no_pinjaman_baru = generate_code('PJ')
    cursor.execute('''
    INSERT INTO pinjaman (
        no_pinjaman, anggota_id, jenis_pinjaman, tanggal_pengajuan, tanggal_cair,
        plafon_pokok, margin_persen, margin_nominal, total_pinjaman, tenor_bulan,
        angsuran_pokok_bulanan, angsuran_margin_bulanan, total_angsuran_bulanan,
        biaya_provisi, biaya_drk, saldo_pokok, saldo_margin, angsuran_ke,
        status, keperluan, keterangan, is_topup, ref_pinjaman_lama_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'Aktif', ?, ?, 1, ?)
    ''', (
        no_pinjaman_baru, anggota_id, jenis_pinjaman, tgl_cair, tgl_cair,
        plafon_baru, margin_persen, margin_nominal, total_pinjaman, tenor_baru,
        angsuran_pokok_bulanan, angsuran_margin_bulanan, total_angsuran_bulanan,
        biaya_provisi, biaya_drk, plafon_baru, margin_nominal,
        data.get('keperluan', f"Top Up Pembiayaan melunasi {pj_lama['no_pinjaman']}"),
        f"Pinjaman Top Up: Melunasi pinjaman lama #{pj_lama['no_pinjaman']} (Sisa Pokok Rp {sisa_pokok_lama:,.0f}). Dana cair bersih Rp {dana_cair:,.0f}",
        pj_lama['id']
    ))
    new_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return True, f"Proses Top Up berhasil! Pinjaman lama #{pj_lama['no_pinjaman']} dilunasi. Pinjaman baru #{no_pinjaman_baru} aktif. Dana cair bersih ke anggota: Rp {dana_cair:,.0f}.", new_id

# ----------------- REKAP TRANSAKSI BULANAN (ADMIN & ANGGOTA) -----------------
def hitung_rekap_bulanan(bulan_buku):
    """
    Menghitung rekap transaksi bulanan pemotongan gaji / setoran koperasi
    untuk seluruh anggota aktif pada bulan buku yang ditentukan (misal '2026-02').
    """
    conn = get_db()
    cursor = conn.cursor()

    # Ambil semua anggota aktif
    cursor.execute("SELECT * FROM anggota WHERE status = 'Aktif' ORDER BY id ASC")
    anggota_list = [dict(r) for r in cursor.fetchall()]

    rekap_items = []
    total_wajib = 0.0
    total_lebaran = 0.0
    total_qurban = 0.0
    total_manasuka = 0.0
    total_simpanan_semua = 0.0
    total_angsuran_pokok = 0.0
    total_angsuran_margin = 0.0
    total_pemotongan_semua = 0.0

    for a in anggota_list:
        aid = a['id']
        # Simpanan wajib bulanan default Rp 100,000 (aturan RAT 2026)
        simp_wajib = 100000.0

        # Cek partisipasi tabungan rutin bulanan Lebaran & Qurban via Komitmen Tabungan Khusus
        # 1. Simpanan Lebaran
        cursor.execute('''
        SELECT nominal_per_bulan FROM komitmen_tabungan_khusus
        WHERE anggota_id = ? AND jenis_tabungan = 'Lebaran' AND status = 'Aktif'
        ORDER BY id DESC LIMIT 1
        ''', (aid,))
        leb_komit = cursor.fetchone()
        if leb_komit:
            simp_lebaran = float(leb_komit['nominal_per_bulan'])
        else:
            # Cek jika tabungan periode sebelumnya sudah dibagikan dan anggota belum mendaftar komitmen baru
            cursor.execute('''
            SELECT id FROM komitmen_tabungan_khusus
            WHERE anggota_id = ? AND jenis_tabungan = 'Lebaran' AND status = 'Selesai Dibagikan'
            ORDER BY id DESC LIMIT 1
            ''', (aid,))
            if cursor.fetchone():
                simp_lebaran = 0.0
            else:
                # Fallback data awal RAT: cek jika ada setoran rutin bulanan sebelumnya
                cursor.execute('''
                SELECT nominal FROM transaksi_simpanan 
                WHERE anggota_id = ? AND jenis_simpanan = 'Lebaran' AND tipe = 'SETOR' AND keterangan LIKE '%Bulan%'
                ORDER BY id DESC LIMIT 1
                ''', (aid,))
                leb_row = cursor.fetchone()
                if leb_row:
                    simp_lebaran = float(leb_row['nominal'])
                else:
                    cursor.execute("SELECT SUM(nominal) FROM transaksi_simpanan WHERE anggota_id = ? AND jenis_simpanan = 'Lebaran' AND tipe = 'SETOR'", (aid,))
                    tot_leb = cursor.fetchone()[0] or 0
                    simp_lebaran = 100000.0 if tot_leb > 0 else 0.0

        # 2. Simpanan Qurban
        cursor.execute('''
        SELECT nominal_per_bulan FROM komitmen_tabungan_khusus
        WHERE anggota_id = ? AND jenis_tabungan = 'Qurban' AND status = 'Aktif'
        ORDER BY id DESC LIMIT 1
        ''', (aid,))
        qur_komit = cursor.fetchone()
        if qur_komit:
            simp_qurban = float(qur_komit['nominal_per_bulan'])
        else:
            # Cek jika tabungan periode sebelumnya sudah dibagikan dan anggota belum mendaftar komitmen baru
            cursor.execute('''
            SELECT id FROM komitmen_tabungan_khusus
            WHERE anggota_id = ? AND jenis_tabungan = 'Qurban' AND status = 'Selesai Dibagikan'
            ORDER BY id DESC LIMIT 1
            ''', (aid,))
            if cursor.fetchone():
                simp_qurban = 0.0
            else:
                # Fallback data awal RAT: cek jika ada setoran rutin bulanan sebelumnya
                cursor.execute('''
                SELECT nominal FROM transaksi_simpanan 
                WHERE anggota_id = ? AND jenis_simpanan = 'Qurban' AND tipe = 'SETOR' AND keterangan LIKE '%Bulan%'
                ORDER BY id DESC LIMIT 1
                ''', (aid,))
                qur_row = cursor.fetchone()
                if qur_row:
                    simp_qurban = float(qur_row['nominal'])
                else:
                    cursor.execute("SELECT SUM(nominal) FROM transaksi_simpanan WHERE anggota_id = ? AND jenis_simpanan = 'Qurban' AND tipe = 'SETOR'", (aid,))
                    tot_qur = cursor.fetchone()[0] or 0
                    simp_qurban = 100000.0 if tot_qur > 0 else 0.0

        cursor.execute('''
        SELECT nominal FROM transaksi_simpanan 
        WHERE anggota_id = ? AND jenis_simpanan = 'Manasuka' AND tipe = 'SETOR' AND keterangan LIKE '%Bulan%'
        ORDER BY id DESC LIMIT 1
        ''', (aid,))
        man_row = cursor.fetchone()
        if man_row:
            simp_manasuka = float(man_row['nominal'])
        else:
            cursor.execute("SELECT SUM(nominal) FROM transaksi_simpanan WHERE anggota_id = ? AND jenis_simpanan = 'Manasuka'", (aid,))
            tot_man = cursor.fetchone()[0] or 0
            simp_manasuka = 50000.0 if tot_man > 0 else 0.0

        total_simpanan_anggota = simp_wajib + simp_lebaran + simp_qurban + simp_manasuka

        # Pinjaman aktif anggota
        cursor.execute('''
        SELECT SUM(angsuran_pokok_bulanan) as total_pokok,
               SUM(angsuran_margin_bulanan) as total_margin,
               COUNT(id) as jml_pinjaman
        FROM pinjaman
        WHERE anggota_id = ? AND status = 'Aktif'
        ''', (aid,))
        pj_row = cursor.fetchone()
        angs_pokok = float(pj_row['total_pokok'] or 0)
        angs_margin = float(pj_row['total_margin'] or 0)
        jml_pinjaman = int(pj_row['jml_pinjaman'] or 0)
        total_angsuran_anggota = angs_pokok + angs_margin

        total_potongan_anggota = total_simpanan_anggota + total_angsuran_anggota

        # Cek apakah transaksi bulan ini sudah tereksekusi
        cursor.execute('''
        SELECT COUNT(id) FROM transaksi_simpanan
        WHERE anggota_id = ? AND bulan_buku = ?
        ''', (aid, bulan_buku))
        is_simpanan_done = cursor.fetchone()[0] > 0

        cursor.execute('''
        SELECT COUNT(id) FROM angsuran_pinjaman
        WHERE anggota_id = ? AND bulan_buku = ?
        ''', (aid, bulan_buku))
        is_angsuran_done = cursor.fetchone()[0] > 0

        status_bulan = "Sudah Diproses" if (is_simpanan_done or (jml_pinjaman > 0 and is_angsuran_done)) else "Belum Diproses"

        # Cek apakah ada pinjaman yang baru dilunasi dipercepat atau topup pada bulan buku ini
        cursor.execute('''
        SELECT pelunasan_tipe, no_pinjaman, tanggal_lunas
        FROM pinjaman
        WHERE anggota_id = ? AND strftime('%Y-%m', tanggal_lunas) = ? AND status = 'Lunas'
        ''', (aid, bulan_buku))
        settled_loans = cursor.fetchall()

        catatan_khusus = []
        for sl in settled_loans:
            if sl['pelunasan_tipe'] == 'Pelunasan Dipercepat':
                catatan_khusus.append(f"Pinjaman {sl['no_pinjaman']} telah dilunasi dipercepat pada {sl['tanggal_lunas']}.")
            elif sl['pelunasan_tipe'] == 'Top Up':
                catatan_khusus.append(f"Pinjaman lama {sl['no_pinjaman']} ditutup (Top Up).")

        # Cek apakah ada pinjaman baru top up pada bulan ini
        cursor.execute('''
        SELECT no_pinjaman FROM pinjaman
        WHERE anggota_id = ? AND strftime('%Y-%m', tanggal_cair) = ? AND is_topup = 1
        ''', (aid, bulan_buku))
        topup_new = cursor.fetchall()
        for tn in topup_new:
            catatan_khusus.append(f"Mulai angsuran pinjaman Top Up baru #{tn['no_pinjaman']}.")

        item = {
            'anggota_id': aid,
            'no_anggota': a['no_anggota'],
            'nama': a['nama'],
            'jabatan': a['jabatan'],
            'simpanan_wajib': simp_wajib,
            'simpanan_lebaran': simp_lebaran,
            'simpanan_qurban': simp_qurban,
            'simpanan_manasuka': simp_manasuka,
            'total_simpanan': total_simpanan_anggota,
            'angsuran_pokok': angs_pokok,
            'angsuran_margin': angs_margin,
            'total_angsuran': total_angsuran_anggota,
            'total_potongan': total_potongan_anggota,
            'status_bulan': status_bulan,
            'jml_pinjaman_aktif': jml_pinjaman,
            'catatan_khusus': " • ".join(catatan_khusus)
        }

        rekap_items.append(item)

        total_wajib += simp_wajib
        total_lebaran += simp_lebaran
        total_qurban += simp_qurban
        total_manasuka += simp_manasuka
        total_simpanan_semua += total_simpanan_anggota
        total_angsuran_pokok += angs_pokok
        total_angsuran_margin += angs_margin
        total_pemotongan_semua += total_potongan_anggota

    conn.close()

    summary = {
        'bulan_buku': bulan_buku,
        'total_anggota': len(anggota_list),
        'total_wajib': total_wajib,
        'total_lebaran': total_lebaran,
        'total_qurban': total_qurban,
        'total_manasuka': total_manasuka,
        'total_simpanan': total_simpanan_semua,
        'total_angsuran_pokok': total_angsuran_pokok,
        'total_angsuran_margin': total_angsuran_margin,
        'total_angsuran': total_angsuran_pokok + total_angsuran_margin,
        'total_pemotongan': total_pemotongan_semua,
        'anggota_list': rekap_items
    }
    return summary

def hitung_rekap_tahunan(tahun):
    """
    Menghitung rekapitulasi transaksi tahunan pemotongan gaji / setoran koperasi
    untuk seluruh anggota selama satu tahun penuh (misal '2025' atau '2026').
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM anggota WHERE status = 'Aktif' ORDER BY id ASC")
    anggota_list = [dict(r) for r in cursor.fetchall()]

    rekap_items = []
    tot_wajib = tot_lebaran = tot_qurban = tot_manasuka = tot_simpanan = 0.0
    tot_pokok = tot_margin = tot_potongan = 0.0

    for a in anggota_list:
        aid = a['id']

        # Simpanan masuk dalam tahun ini
        cursor.execute('''
        SELECT 
            SUM(CASE WHEN jenis_simpanan = 'Wajib' AND tipe = 'SETOR' THEN nominal ELSE 0 END) as wajib,
            SUM(CASE WHEN jenis_simpanan = 'Lebaran' AND tipe = 'SETOR' THEN nominal ELSE 0 END) as lebaran,
            SUM(CASE WHEN jenis_simpanan = 'Qurban' AND tipe = 'SETOR' THEN nominal ELSE 0 END) as qurban,
            SUM(CASE WHEN jenis_simpanan = 'Manasuka' AND tipe = 'SETOR' THEN nominal ELSE 0 END) as manasuka,
            SUM(CASE WHEN tipe = 'SETOR' THEN nominal ELSE 0 END) as total_simpanan
        FROM transaksi_simpanan
        WHERE anggota_id = ? AND strftime('%Y', tanggal) = ?
        ''', (aid, str(tahun)))
        simp_row = cursor.fetchone()
        
        sw = float(simp_row['wajib'] or 0)
        sl = float(simp_row['lebaran'] or 0)
        sq = float(simp_row['qurban'] or 0)
        sm = float(simp_row['manasuka'] or 0)
        st = float(simp_row['total_simpanan'] or 0)

        # Angsuran dibayar dalam tahun ini
        cursor.execute('''
        SELECT 
            SUM(angsuran_pokok) as pokok,
            SUM(angsuran_margin) as margin,
            SUM(total_bayar) as total_angsuran
        FROM angsuran_pinjaman
        WHERE anggota_id = ? AND strftime('%Y', tanggal_bayar) = ?
        ''', (aid, str(tahun)))
        ang_row = cursor.fetchone()

        ap = float(ang_row['pokok'] or 0)
        am = float(ang_row['margin'] or 0)
        at = float(ang_row['total_angsuran'] or 0)

        total_potongan_thn = st + at

        # Catatan pelunasan dipercepat / topup tahun ini
        cursor.execute('''
        SELECT pelunasan_tipe, no_pinjaman FROM pinjaman
        WHERE anggota_id = ? AND strftime('%Y', tanggal_lunas) = ?
        ''', (aid, str(tahun)))
        settled = [f"{r['pelunasan_tipe']} ({r['no_pinjaman']})" for r in cursor.fetchall()]

        cursor.execute('''
        SELECT no_pinjaman FROM pinjaman
        WHERE anggota_id = ? AND strftime('%Y', tanggal_cair) = ? AND is_topup = 1
        ''', (aid, str(tahun)))
        topups = [f"Top Up Baru ({r['no_pinjaman']})" for r in cursor.fetchall()]

        catatan = " • ".join(settled + topups)

        item = {
            'anggota_id': aid,
            'no_anggota': a['no_anggota'],
            'nama': a['nama'],
            'jabatan': a['jabatan'],
            'simpanan_wajib': sw,
            'simpanan_lebaran': sl,
            'simpanan_qurban': sq,
            'simpanan_manasuka': sm,
            'total_simpanan': st,
            'angsuran_pokok': ap,
            'angsuran_margin': am,
            'total_angsuran': at,
            'total_potongan': total_potongan_thn,
            'catatan_khusus': catatan
        }
        rekap_items.append(item)

        tot_wajib += sw
        tot_lebaran += sl
        tot_qurban += sq
        tot_manasuka += sm
        tot_simpanan += st
        tot_pokok += ap
        tot_margin += am
        tot_potongan += total_potongan_thn

    conn.close()

    return {
        'tahun': str(tahun),
        'total_anggota': len(anggota_list),
        'total_wajib': tot_wajib,
        'total_lebaran': tot_lebaran,
        'total_qurban': tot_qurban,
        'total_manasuka': tot_manasuka,
        'total_simpanan': tot_simpanan,
        'total_angsuran_pokok': tot_pokok,
        'total_angsuran_margin': tot_margin,
        'total_angsuran': tot_pokok + tot_margin,
        'total_pemotongan': tot_potongan,
        'anggota_list': rekap_items
    }

def eksekusi_potong_gaji_bulanan(bulan_buku, created_by='Admin'):
    """
    Eksekusi serentak pemotongan gaji bulanan (simpanan wajib & angsuran pinjaman).
    """
    conn = get_db()
    cursor = conn.cursor()

    rekap = hitung_rekap_bulanan(bulan_buku)
    tgl_proses = datetime.now().strftime('%Y-%m-%d')
    count_trx = 0

    for item in rekap.get('anggota_list', []):
        aid = item['anggota_id']

        # 1. Simpanan Wajib (Rp 100,000)
        cursor.execute('''
        SELECT id FROM transaksi_simpanan 
        WHERE anggota_id = ? AND jenis_simpanan = 'Wajib' AND bulan_buku = ?
        ''', (aid, bulan_buku))
        if not cursor.fetchone() and item['simpanan_wajib'] > 0:
            no_trx = generate_code('TRX-WJB')
            cursor.execute('''
            INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
            VALUES (?, ?, ?, 'Wajib', 'SETOR', ?, ?, 'Potong Gaji', ?, ?)
            ''', (no_trx, aid, tgl_proses, item['simpanan_wajib'], f"Simpanan Wajib Bulan {bulan_buku}", bulan_buku, created_by))
            count_trx += 1

        # 2. Simpanan Lebaran (jika ada komitmen rutin)
        if item['simpanan_lebaran'] > 0:
            cursor.execute('''
            SELECT id FROM transaksi_simpanan 
            WHERE anggota_id = ? AND jenis_simpanan = 'Lebaran' AND bulan_buku = ?
            ''', (aid, bulan_buku))
            if not cursor.fetchone():
                cursor.execute('''
                SELECT metode_setor FROM komitmen_tabungan_khusus
                WHERE anggota_id = ? AND jenis_tabungan = 'Lebaran' AND status = 'Aktif'
                ORDER BY id DESC LIMIT 1
                ''', (aid,))
                km_leb = cursor.fetchone()
                metode_leb = km_leb['metode_setor'] if km_leb and km_leb['metode_setor'] else 'Potong Gaji'

                no_trx = generate_code('TRX-LBR')
                cursor.execute('''
                INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
                VALUES (?, ?, ?, 'Lebaran', 'SETOR', ?, ?, ?, ?, ?)
                ''', (no_trx, aid, tgl_proses, item['simpanan_lebaran'], f"Simpanan Lebaran Bulan {bulan_buku}", metode_leb, bulan_buku, created_by))
                count_trx += 1

        # 3. Simpanan Qurban (jika ada komitmen rutin)
        if item['simpanan_qurban'] > 0:
            cursor.execute('''
            SELECT id FROM transaksi_simpanan 
            WHERE anggota_id = ? AND jenis_simpanan = 'Qurban' AND bulan_buku = ?
            ''', (aid, bulan_buku))
            if not cursor.fetchone():
                cursor.execute('''
                SELECT metode_setor FROM komitmen_tabungan_khusus
                WHERE anggota_id = ? AND jenis_tabungan = 'Qurban' AND status = 'Aktif'
                ORDER BY id DESC LIMIT 1
                ''', (aid,))
                km_qur = cursor.fetchone()
                metode_qur = km_qur['metode_setor'] if km_qur and km_qur['metode_setor'] else 'Potong Gaji'

                no_trx = generate_code('TRX-QRB')
                cursor.execute('''
                INSERT INTO transaksi_simpanan (no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe, nominal, keterangan, metode_bayar, bulan_buku, created_by)
                VALUES (?, ?, ?, 'Qurban', 'SETOR', ?, ?, ?, ?, ?)
                ''', (no_trx, aid, tgl_proses, item['simpanan_qurban'], f"Simpanan Qurban Bulan {bulan_buku}", metode_qur, bulan_buku, created_by))
                count_trx += 1

        # 4. Angsuran Pinjaman Aktif
        cursor.execute("SELECT * FROM pinjaman WHERE anggota_id = ? AND status = 'Aktif'", (aid,))
        active_loans = cursor.fetchall()
        for pl in active_loans:
            pl_dict = dict(pl)
            cursor.execute('''
            SELECT id FROM angsuran_pinjaman
            WHERE pinjaman_id = ? AND bulan_buku = ?
            ''', (pl_dict['id'], bulan_buku))
            if not cursor.fetchone():
                # Bayar angsuran bulanan
                angs_pokok = min(pl_dict['saldo_pokok'], pl_dict['angsuran_pokok_bulanan'])
                angs_margin = min(pl_dict['saldo_margin'], pl_dict['angsuran_margin_bulanan'])
                sisa_pokok = max(0.0, pl_dict['saldo_pokok'] - angs_pokok)
                sisa_margin = max(0.0, pl_dict['saldo_margin'] - angs_margin)
                angsuran_ke = pl_dict['angsuran_ke'] + 1
                status_pj = 'Lunas' if (sisa_pokok <= 100) else 'Aktif'

                no_angs = generate_code('ANGS-PG')
                cursor.execute('''
                INSERT INTO angsuran_pinjaman (
                    no_angsuran, pinjaman_id, anggota_id, tanggal_bayar, angsuran_ke,
                    angsuran_pokok, angsuran_margin, total_bayar, sisa_pokok_setelah,
                    bulan_buku, metode_bayar, keterangan
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Potong Gaji', ?)
                ''', (
                    no_angs, pl_dict['id'], aid, tgl_proses, angsuran_ke,
                    angs_pokok, angs_margin, (angs_pokok + angs_margin), sisa_pokok,
                    bulan_buku, f"Potong Gaji Bulan {bulan_buku} Angsuran ke-{angsuran_ke}"
                ))

                cursor.execute('''
                UPDATE pinjaman
                SET saldo_pokok = ?, saldo_margin = ?, angsuran_ke = ?, status = ?
                WHERE id = ?
                ''', (sisa_pokok, sisa_margin, angsuran_ke, status_pj, pl_dict['id']))
                count_trx += 1

    # Catat log billing
    cursor.execute('''
    INSERT OR REPLACE INTO billing_bulanan_log (
        bulan_buku, tanggal_proses, total_anggota, total_simpanan,
        total_angsuran_pokok, total_angsuran_margin, total_keseluruhan,
        status, created_by
    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Selesai', ?)
    ''', (
        bulan_buku, tgl_proses, rekap['total_anggota'],
        rekap['total_simpanan'], rekap['total_angsuran_pokok'],
        rekap['total_angsuran_margin'], rekap['total_pemotongan'],
        created_by
    ))

    conn.commit()
    conn.close()
    return True, f"Proses pemotongan gaji bulan {bulan_buku} berhasil diselesaikan ({count_trx} transaksi dicatat)."

def get_rekap_bulanan_anggota(anggota_id):
    """
    Mengambil riwayat mutasi bulanan (potongan simpanan & pinjaman)
    spesifik untuk 1 anggota dari berbagai bulan buku.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Ambil daftar unik bulan buku dari transaksi simpanan atau angsuran
    cursor.execute('''
    SELECT DISTINCT bulan_buku FROM (
        SELECT bulan_buku FROM transaksi_simpanan WHERE anggota_id = ?
        UNION
        SELECT bulan_buku FROM angsuran_pinjaman WHERE anggota_id = ?
    ) WHERE bulan_buku IS NOT NULL ORDER BY bulan_buku DESC
    ''', (anggota_id, anggota_id))
    bulan_rows = cursor.fetchall()

    history = []
    for b in bulan_rows:
        bln = b['bulan_buku']
        
        # Simpanan di bulan ini
        cursor.execute('''
        SELECT jenis_simpanan, tipe, SUM(nominal) as total
        FROM transaksi_simpanan
        WHERE anggota_id = ? AND bulan_buku = ?
        GROUP BY jenis_simpanan, tipe
        ''', (anggota_id, bln))
        simpanan_rows = cursor.fetchall()
        
        detail_simp = {'Wajib': 0.0, 'Lebaran': 0.0, 'Qurban': 0.0, 'Manasuka': 0.0, 'Pokok': 0.0}
        total_setor_simp = 0.0
        for sr in simpanan_rows:
            if sr['tipe'] == 'SETOR':
                detail_simp[sr['jenis_simpanan']] = float(sr['total'] or 0)
                total_setor_simp += float(sr['total'] or 0)

        # Angsuran di bulan ini
        cursor.execute('''
        SELECT SUM(angsuran_pokok) as pokok, SUM(angsuran_margin) as margin, SUM(total_bayar) as total
        FROM angsuran_pinjaman
        WHERE anggota_id = ? AND bulan_buku = ?
        ''', (anggota_id, bln))
        ang_row = cursor.fetchone()
        angs_pokok = float(ang_row['pokok'] or 0) if ang_row else 0.0
        angs_margin = float(ang_row['margin'] or 0) if ang_row else 0.0
        total_angs = float(ang_row['total'] or 0) if ang_row else 0.0

        history.append({
            'bulan_buku': bln,
            'simpanan_wajib': detail_simp.get('Wajib', 0.0),
            'simpanan_lebaran': detail_simp.get('Lebaran', 0.0),
            'simpanan_qurban': detail_simp.get('Qurban', 0.0),
            'simpanan_manasuka': detail_simp.get('Manasuka', 0.0),
            'total_simpanan': total_setor_simp,
            'angsuran_pokok': angs_pokok,
            'angsuran_margin': angs_margin,
            'total_angsuran': total_angs,
            'total_potongan': total_setor_simp + total_angs
        })

    conn.close()
    return history

# ----------------- LAPORAN & KALKULASI SHU KOSITAS -----------------
def hitung_shu_koperasi(total_shu_bruto=38706812.69):
    """
    Kalkulasi Pembagian SHU sesuai Anggaran Dasar KOSITAS (Halaman 13, 24, 25 RAT):
    - Alokasi SHU Bruto:
      * Dana Pendidikan: 2%
      * Dana Rekreasi: 8%
      * Dana Sosial: 6%
      * Dana Cadangan: 6%
      * Dana Resiko Kredit: 3%
      * Dana Pensiun: 3%
      * Insentif Pengurus & Pengawas: 32%
      * SHU Bagian Anggota: 40% (50% Jasa Modal, 50% Jasa Pinjaman)
    """
    dana_pendidikan = round(total_shu_bruto * 0.02, 2)
    dana_rekreasi = round(total_shu_bruto * 0.08, 2)
    dana_sosial = round(total_shu_bruto * 0.06, 2)
    dana_cadangan = round(total_shu_bruto * 0.06, 2)
    dana_resiko_kredit = round(total_shu_bruto * 0.03, 2)
    dana_pensiun = round(total_shu_bruto * 0.03, 2)
    insentif_pengurus = round(total_shu_bruto * 0.32, 2)
    shu_anggota = round(total_shu_bruto * 0.40, 2)

    jasa_modal_total = round(shu_anggota * 0.50, 2)
    jasa_pinjaman_total = round(shu_anggota * 0.50, 2)

    # Ambil rincian seluruh anggota
    members = get_all_anggota(status_filter='Semua')
    
    # Hitung total simpanan koperasi & total jasa pinjaman terbayar
    total_simpanan_koperasi = sum(m['total_simpanan'] for m in members if m['total_simpanan'] > 0)
    total_jasa_koperasi = sum(m['total_jasa_pinjaman_dibayar'] for m in members if m['total_jasa_pinjaman_dibayar'] > 0)

    # Antisipasi division by zero
    if total_simpanan_koperasi == 0:
        total_simpanan_koperasi = 1.0
    if total_jasa_koperasi == 0:
        # Gunakan jasa pinjaman dari data RAT bila database baru
        total_jasa_koperasi = 43892830.0

    rincian_anggota = []
    total_shu_dibagikan = 0.0

    for m in members:
        simp = m['total_simpanan']
        jasa = m['total_jasa_pinjaman_dibayar']

        shu_modal = round((simp / total_simpanan_koperasi) * jasa_modal_total, 0)
        shu_pinjaman = round((jasa / total_jasa_koperasi) * jasa_pinjaman_total, 0) if total_jasa_koperasi > 0 else 0.0
        total_shu = shu_modal + shu_pinjaman
        total_shu_dibagikan += total_shu

        rincian_anggota.append({
            'anggota_id': m['id'],
            'no_anggota': m['no_anggota'],
            'nama': m['nama'],
            'status': m['status'],
            'total_simpanan': simp,
            'total_jasa_pinjaman': jasa,
            'shu_jasa_modal': shu_modal,
            'shu_jasa_pinjaman': shu_pinjaman,
            'shu_total_diterima': total_shu
        })

    return {
        'total_shu_bruto': total_shu_bruto,
        'alokasi': {
            'dana_pendidikan': dana_pendidikan,
            'dana_rekreasi': dana_rekreasi,
            'dana_sosial': dana_sosial,
            'dana_cadangan': dana_cadangan,
            'dana_resiko_kredit': dana_resiko_kredit,
            'dana_pensiun': dana_pensiun,
            'insentif_pengurus': insentif_pengurus,
            'shu_bagian_anggota': shu_anggota,
            'jasa_modal_total': jasa_modal_total,
            'jasa_pinjaman_total': jasa_pinjaman_total
        },
        'total_simpanan_koperasi': total_simpanan_koperasi,
        'total_jasa_koperasi': total_jasa_koperasi,
        'rincian_anggota': rincian_anggota,
        'total_shu_dibagikan': total_shu_dibagikan
    }

def terbilang(n):
    """Mengubah angka rupiah menjadi kalimat terbilang Bahasa Indonesia."""
    try:
        n = int(round(float(n or 0)))
    except (ValueError, TypeError):
        return "Nol Rupiah"
    if n <= 0:
        return "Nol Rupiah"
    satuan = ["", "Satu", "Dua", "Tiga", "Empat", "Lima", "Enam", "Tujuh", "Delapan", "Sembilan", "Sepuluh", "Sebelas"]
    def _terbilang(x):
        if x < 12:
            return satuan[x]
        elif x < 20:
            return _terbilang(x - 10) + " Belas"
        elif x < 100:
            return _terbilang(x // 10) + " Puluh " + _terbilang(x % 10)
        elif x < 200:
            return "Seratus " + _terbilang(x - 100)
        elif x < 1000:
            return _terbilang(x // 100) + " Ratus " + _terbilang(x % 100)
        elif x < 2000:
            return "Seribu " + _terbilang(x - 1000)
        elif x < 1000000:
            return _terbilang(x // 1000) + " Ribu " + _terbilang(x % 1000)
        elif x < 1000000000:
            return _terbilang(x // 1000000) + " Juta " + _terbilang(x % 1000000)
        elif x < 1000000000000:
            return _terbilang(x // 1000000000) + " Miliar " + _terbilang(x % 1000000000)
        else:
            return _terbilang(x // 1000000000000) + " Triliun " + _terbilang(x % 1000000000000)
    return " ".join(_terbilang(n).split()) + " Rupiah"

def hitung_estimasi_shu_anggota(anggota_id, tahun=None, bulan_ke=None, total_shu_bruto=38706812.69):
    """
    Menghitung estimasi rincian penerimaan Sisa Hasil Usaha (SHU) untuk akun anggota
    pada periode tahun berjalan dan bulan berjalan.
    Sesuai Anggaran Dasar KOSITAS BPS Kabupaten Tasikmalaya:
    - 40% SHU Bruto dialokasikan untuk Anggota
    - 50% Jasa Modal (berdasarkan simpanan anggota)
    - 50% Jasa Pinjaman / Usaha (berdasarkan margin pinjaman yang disetor anggota)
    """
    now = datetime.now()
    thn = int(tahun or now.year)
    bln = int(bulan_ke if bulan_ke is not None else now.month)
    if bln < 1:
        bln = 1
    if bln > 12:
        bln = 12

    member = get_anggota_by_id(anggota_id)
    if not member:
        return None

    # Kalkulasi SHU global koperasi
    shu_global = hitung_shu_koperasi(total_shu_bruto=total_shu_bruto)
    rincian_member = next((r for r in shu_global['rincian_anggota'] if r['anggota_id'] == anggota_id), None)

    if not rincian_member:
        bal = get_anggota_balance(anggota_id)
        simp = float(bal['total_simpanan'] or 0)
        jasa = float(bal['total_jasa_pinjaman_dibayar'] or 0)
        tot_simp_kop = shu_global['total_simpanan_koperasi']
        tot_jasa_kop = shu_global['total_jasa_koperasi']
        jasa_modal_tot = shu_global['alokasi']['jasa_modal_total']
        jasa_pinjaman_tot = shu_global['alokasi']['jasa_pinjaman_total']

        shu_modal = round((simp / tot_simp_kop) * jasa_modal_tot, 0) if tot_simp_kop > 0 else 0.0
        shu_pinjaman = round((jasa / tot_jasa_kop) * jasa_pinjaman_tot, 0) if tot_jasa_kop > 0 else 0.0
        rincian_member = {
            'anggota_id': anggota_id,
            'no_anggota': member['no_anggota'],
            'nama': member['nama'],
            'status': member['status'],
            'total_simpanan': simp,
            'total_jasa_pinjaman': jasa,
            'shu_jasa_modal': shu_modal,
            'shu_jasa_pinjaman': shu_pinjaman,
            'shu_total_diterima': shu_modal + shu_pinjaman
        }

    shu_tahunan = float(rincian_member['shu_total_diterima'])
    modal_tahunan = float(rincian_member['shu_jasa_modal'])
    pinjaman_tahunan = float(rincian_member['shu_jasa_pinjaman'])

    # Rasio s/d bulan berjalan (contoh: 10/12 untuk Oktober)
    rasio_sd_bulan = bln / 12.0
    rasio_per_bulan = 1.0 / 12.0

    shu_sd_bulan = round(shu_tahunan * rasio_sd_bulan, 0)
    modal_sd_bulan = round(modal_tahunan * rasio_sd_bulan, 0)
    pinjaman_sd_bulan = round(pinjaman_tahunan * rasio_sd_bulan, 0)

    shu_per_bulan = round(shu_tahunan * rasio_per_bulan, 0)
    modal_per_bulan = round(modal_tahunan * rasio_per_bulan, 0)
    pinjaman_per_bulan = round(pinjaman_tahunan * rasio_per_bulan, 0)

    persen_modal = (member['total_simpanan'] / shu_global['total_simpanan_koperasi'] * 100) if shu_global['total_simpanan_koperasi'] > 0 else 0.0
    persen_pinjaman = (member['total_jasa_pinjaman_dibayar'] / shu_global['total_jasa_koperasi'] * 100) if shu_global['total_jasa_koperasi'] > 0 else 0.0

    nama_bulan = [
        '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ]

    return {
        'member': member,
        'tahun': thn,
        'bulan_ke': bln,
        'nama_bulan': nama_bulan[bln],
        'periode_label': f"{nama_bulan[bln]} {thn}",
        'shu_tahunan': {
            'jasa_modal': modal_tahunan,
            'jasa_pinjaman': pinjaman_tahunan,
            'total_shu': shu_tahunan,
            'terbilang': terbilang(shu_tahunan)
        },
        'shu_sd_bulan': {
            'jasa_modal': modal_sd_bulan,
            'jasa_pinjaman': pinjaman_sd_bulan,
            'total_shu': shu_sd_bulan,
            'terbilang': terbilang(shu_sd_bulan)
        },
        'shu_per_bulan': {
            'jasa_modal': modal_per_bulan,
            'jasa_pinjaman': pinjaman_per_bulan,
            'total_shu': shu_per_bulan,
            'terbilang': terbilang(shu_per_bulan)
        },
        'partisipasi': {
            'simpanan_anggota': member['total_simpanan'],
            'total_simpanan_koperasi': shu_global['total_simpanan_koperasi'],
            'persen_modal': round(persen_modal, 4),
            'jasa_pinjaman_anggota': member['total_jasa_pinjaman_dibayar'],
            'total_jasa_koperasi': shu_global['total_jasa_koperasi'],
            'persen_pinjaman': round(persen_pinjaman, 4)
        },
        'koperasi_alokasi': shu_global['alokasi'],
        'total_shu_bruto': shu_global['total_shu_bruto']
    }

# ----------------- DASHBOARD STATISTIK UTAMA -----------------
def get_dashboard_stats():
    conn = get_db()
    cursor = conn.cursor()

    # Anggota
    cursor.execute("SELECT COUNT(*) FROM anggota WHERE status = 'Aktif'")
    total_anggota_aktif = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM anggota")
    total_anggota_semua = cursor.fetchone()[0]

    # Simpanan
    cursor.execute('''
    SELECT 
        SUM(CASE WHEN tipe = 'SETOR' THEN nominal ELSE -nominal END) as total_simpanan,
        SUM(CASE WHEN jenis_simpanan = 'Pokok' THEN (CASE WHEN tipe = 'SETOR' THEN nominal ELSE -nominal END) ELSE 0 END) as pokok,
        SUM(CASE WHEN jenis_simpanan = 'Wajib' THEN (CASE WHEN tipe = 'SETOR' THEN nominal ELSE -nominal END) ELSE 0 END) as wajib,
        SUM(CASE WHEN jenis_simpanan = 'Lebaran' THEN (CASE WHEN tipe = 'SETOR' THEN nominal ELSE -nominal END) ELSE 0 END) as lebaran,
        SUM(CASE WHEN jenis_simpanan = 'Qurban' THEN (CASE WHEN tipe = 'SETOR' THEN nominal ELSE -nominal END) ELSE 0 END) as qurban,
        SUM(CASE WHEN jenis_simpanan = 'Manasuka' THEN (CASE WHEN tipe = 'SETOR' THEN nominal ELSE -nominal END) ELSE 0 END) as manasuka
    FROM transaksi_simpanan
    ''')
    row_simp = cursor.fetchone()

    total_simpanan = float(row_simp['total_simpanan'] or 0)
    simp_breakdown = {
        'pokok': float(row_simp['pokok'] or 0),
        'wajib': float(row_simp['wajib'] or 0),
        'lebaran': float(row_simp['lebaran'] or 0),
        'qurban': float(row_simp['qurban'] or 0),
        'manasuka': float(row_simp['manasuka'] or 0)
    }

    # Pinjaman Aktif
    cursor.execute('''
    SELECT 
        COUNT(*) as jml_pinjaman_aktif,
        SUM(saldo_pokok) as total_piutang_pokok,
        SUM(saldo_margin) as total_piutang_margin,
        SUM(CASE WHEN jenis_pinjaman LIKE '%JAPAN%' THEN saldo_pokok ELSE 0 END) as japan,
        SUM(CASE WHEN jenis_pinjaman LIKE '%JAPEN%' THEN saldo_pokok ELSE 0 END) as japen,
        SUM(CASE WHEN jenis_pinjaman LIKE '%BON%' OR jenis_pinjaman LIKE '%LAIN%' THEN saldo_pokok ELSE 0 END) as bon_putih,
        SUM(CASE WHEN jenis_pinjaman LIKE '%BARANG%' THEN saldo_pokok ELSE 0 END) as barang
    FROM pinjaman
    WHERE status = 'Aktif'
    ''')
    row_pj = cursor.fetchone()

    total_piutang = float(row_pj['total_piutang_pokok'] or 0)
    piutang_breakdown = {
        'japan': float(row_pj['japan'] or 0),
        'japen': float(row_pj['japen'] or 0),
        'bon_putih': float(row_pj['bon_putih'] or 0),
        'barang': float(row_pj['barang'] or 0)
    }

    # Kas & Bank Estimasi (Dari RAT 2025: Kas Rp 108.119.000, Bank Rp 131.916.303,72)
    # Ditambah arus masuk simpanan baru & angsuran baru
    cursor.execute("SELECT SUM(total_bayar) FROM angsuran_pinjaman")
    total_angsuran_masuk = cursor.fetchone()[0] or 0.0

    kas_estimasi = 108119000.0 + (total_simpanan * 0.1) # sebagian di kas
    bank_estimasi = 131916303.72 + (total_simpanan * 0.9) - (total_piutang * 0.2)

    # Pengajuan online pending
    cursor.execute("SELECT COUNT(*) FROM pengajuan_online WHERE status = 'Menunggu'")
    pengajuan_pending = cursor.fetchone()[0]

    # Transaksi terbaru
    cursor.execute('''
    SELECT t.*, a.nama as nama_anggota 
    FROM transaksi_simpanan t
    JOIN anggota a ON t.anggota_id = a.id
    ORDER BY t.tanggal DESC, t.id DESC LIMIT 5
    ''')
    transaksi_terbaru = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        'total_anggota_aktif': total_anggota_aktif,
        'total_anggota_semua': total_anggota_semua,
        'total_simpanan': total_simpanan,
        'simpanan_breakdown': simp_breakdown,
        'total_piutang': total_piutang,
        'piutang_breakdown': piutang_breakdown,
        'jml_pinjaman_aktif': int(row_pj['jml_pinjaman_aktif'] or 0),
        'kas_estimasi': max(0, kas_estimasi),
        'bank_estimasi': max(0, bank_estimasi),
        'pengajuan_pending': pengajuan_pending,
        'transaksi_terbaru': transaksi_terbaru
    }

# ----------------- KOMITMEN TABUNGAN KHUSUS (LEBARAN & QURBAN) -----------------
def get_komitmen_tabungan_anggota(anggota_id):
    """
    Mengambil seluruh riwayat komitmen tabungan khusus (Lebaran/Qurban) milik seorang anggota.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT k.*, a.nama as nama_anggota, a.no_anggota, a.nip, a.jabatan
    FROM komitmen_tabungan_khusus k
    JOIN anggota a ON k.anggota_id = a.id
    WHERE k.anggota_id = ?
    ORDER BY k.tahun_periode DESC, k.id DESC
    ''', (anggota_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_komitmen_by_id(komitmen_id):
    """
    Mengambil data detail satu komitmen tabungan khusus berdasarkan ID.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT k.*, a.nama as nama_anggota, a.no_anggota, a.nip, a.jabatan
    FROM komitmen_tabungan_khusus k
    JOIN anggota a ON k.anggota_id = a.id
    WHERE k.id = ?
    ''', (komitmen_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_komitmen_tabungan(jenis_filter=None, status_filter=None, tahun_filter=None):
    """
    Mengambil daftar komitmen tabungan khusus seluruh anggota untuk kebutuhan panel admin/pengurus.
    """
    conn = get_db()
    cursor = conn.cursor()
    query = '''
    SELECT k.*, a.nama as nama_anggota, a.no_anggota, a.nip, a.jabatan
    FROM komitmen_tabungan_khusus k
    JOIN anggota a ON k.anggota_id = a.id
    WHERE 1=1
    '''
    params = []
    if jenis_filter and jenis_filter != 'Semua':
        query += " AND k.jenis_tabungan = ?"
        params.append(jenis_filter)
    if status_filter and status_filter != 'Semua':
        query += " AND k.status = ?"
        params.append(status_filter)
    if tahun_filter and str(tahun_filter) != 'Semua':
        query += " AND k.tahun_periode = ?"
        params.append(int(tahun_filter))

    query += " ORDER BY k.tahun_periode DESC, k.id DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def daftar_komitmen_tabungan_baru(data, created_by='Anggota'):
    """
    Mendaftarkan atau memperbarui siklus komitmen tabungan khusus (Lebaran / Qurban)
    baru setelah pembagian/pencairan periode sebelumnya.
    Form ini dapat diakses oleh Anggota maupun Admin/Pengurus.
    """
    conn = get_db()
    cursor = conn.cursor()

    anggota_id = int(data.get('anggota_id'))
    jenis_tabungan = data.get('jenis_tabungan')  # 'Lebaran' atau 'Qurban'
    tahun_periode = int(data.get('tahun_periode', datetime.now().year))
    nominal_per_bulan = float(data.get('nominal_per_bulan', 0))
    setoran_awal = float(data.get('setoran_awal', 0) or 0)
    metode_setor = data.get('metode_setor', 'Potong Gaji')
    keterangan = data.get('keterangan', '')
    tgl_daftar = data.get('tanggal_daftar') or datetime.now().strftime('%Y-%m-%d')

    if nominal_per_bulan < 50000:
        conn.close()
        return False, "Nominal komitmen tabungan minimal Rp 50.000,- per bulan sesuai aturan RAT KOSITAS."

    # ATURAN KOSITAS:
    # Komitmen Tabungan Lebaran dan Tabungan Qurban TIDAK BISA diajukan apabila belum dibagikan,
    # KECUALI untuk anggota yang baru masuk maka pengaturan komitmen bisa dilakukan.
    status_tab = get_status_tabungan_khusus_anggota(anggota_id)
    can_commit = status_tab['can_commit_lebaran'] if jenis_tabungan == 'Lebaran' else status_tab['can_commit_qurban']

    if not can_commit and not data.get('force_admin'):
        conn.close()
        return False, f"Komitmen Tabungan {jenis_tabungan} TIDAK BISA diajukan karena tabungan periode saat ini belum dibagikan oleh koperasi! Pengaturan komitmen periode berikutnya hanya dapat dilakukan setelah tabungan dibagikan menjelang hari raya (kecuali untuk anggota baru)."

    # Periksa dan arsipkan komitmen lama yang berstatus 'Aktif' untuk jenis yang sama
    cursor.execute('''
    UPDATE komitmen_tabungan_khusus
    SET status = 'Digantikan'
    WHERE anggota_id = ? AND jenis_tabungan = ? AND status = 'Aktif'
    ''', (anggota_id, jenis_tabungan))

    # Masukkan komitmen baru siklus pasca pembagian
    cursor.execute('''
    INSERT INTO komitmen_tabungan_khusus (
        anggota_id, jenis_tabungan, tahun_periode, nominal_per_bulan,
        setoran_awal, metode_setor, status, tanggal_daftar, keterangan
    ) VALUES (?, ?, ?, ?, ?, ?, 'Aktif', ?, ?)
    ''', (
        anggota_id, jenis_tabungan, tahun_periode, nominal_per_bulan,
        setoran_awal, metode_setor, tgl_daftar,
        keterangan or f"Komitmen {jenis_tabungan} Periode {tahun_periode} (Didaftarkan oleh {created_by})"
    ))
    new_komitmen_id = cursor.lastrowid

    # Jika ada setoran awal tunai atau transfer saat pendaftaran, catat mutasi setor simpanan
    if setoran_awal > 0:
        no_trx = generate_code('TRX-AWAL')
        cursor.execute('''
        INSERT INTO transaksi_simpanan (
            no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe,
            nominal, keterangan, metode_bayar, bulan_buku, created_by
        ) VALUES (?, ?, ?, ?, 'SETOR', ?, ?, ?, ?, ?)
        ''', (
            no_trx, anggota_id, tgl_daftar, jenis_tabungan, setoran_awal,
            f"Setoran Awal Komitmen {jenis_tabungan} {tahun_periode}",
            metode_setor if metode_setor != 'Potong Gaji' else 'Tunai',
            tgl_daftar[:7], created_by
        ))

    conn.commit()
    conn.close()
    return True, f"Komitmen Tabungan {jenis_tabungan} Periode {tahun_periode} sebesar Rp {nominal_per_bulan:,.0f}/bulan berhasil didaftarkan!"

def update_status_komitmen(komitmen_id, status_baru):
    """
    Mengubah status komitmen (Aktif, Nonaktif, Selesai Dibagikan).
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE komitmen_tabungan_khusus
    SET status = ?
    WHERE id = ?
    ''', (status_baru, komitmen_id))
    conn.commit()
    conn.close()
    return True

def bagikan_tabungan_khusus(jenis_tabungan, tahun_periode, anggota_id_list=None, tanggal_cair=None, created_by='Admin'):
    """
    Eksekusi pembagian / pencairan akumulasi Tabungan Lebaran atau Tabungan Qurban
    menjelang hari raya kepada anggota koperasi.
    - Mencatat transaksi TARIK simpanan untuk mencairkan saldo ke anggota
    - Menandai komitmen periode terkait menjadi 'Selesai Dibagikan'
    - Setelah proses ini selesai, form input komitmen baru harus diisi untuk siklus berikutnya!
    """
    conn = get_db()
    cursor = conn.cursor()

    tgl = tanggal_cair or datetime.now().strftime('%Y-%m-%d')
    bln = tgl[:7]

    if anggota_id_list:
        placeholders = ','.join(['?'] * len(anggota_id_list))
        cursor.execute(f"SELECT * FROM anggota WHERE id IN ({placeholders})", anggota_id_list)
    else:
        cursor.execute("SELECT * FROM anggota WHERE status = 'Aktif'")
    anggota_target = [dict(r) for r in cursor.fetchall()]

    total_dana_dibagikan = 0.0
    jml_anggota_dibagikan = 0
    rincian_pencairan = []

    for a in anggota_target:
        aid = a['id']
        cursor.execute('''
        SELECT 
            COALESCE(SUM(CASE WHEN tipe = 'SETOR' THEN nominal ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN tipe = 'TARIK' THEN nominal ELSE 0 END), 0) as saldo
        FROM transaksi_simpanan
        WHERE anggota_id = ? AND jenis_simpanan = ?
        ''', (aid, jenis_tabungan))
        saldo_row = cursor.fetchone()
        saldo = float(saldo_row['saldo'] or 0)

        if saldo > 0:
            no_trx = generate_code('TRX-BAGI')
            ket = f"Pembagian/Pencairan Akumulasi Tabungan {jenis_tabungan} Menjelang Hari Raya Periode {tahun_periode}"
            cursor.execute('''
            INSERT INTO transaksi_simpanan (
                no_transaksi, anggota_id, tanggal, jenis_simpanan, tipe,
                nominal, keterangan, metode_bayar, bulan_buku, created_by
            ) VALUES (?, ?, ?, ?, 'TARIK', ?, ?, 'Transfer', ?, ?)
            ''', (no_trx, aid, tgl, jenis_tabungan, saldo, ket, bln, created_by))

            # Update komitmen aktif menjadi 'Selesai Dibagikan'
            cursor.execute('''
            UPDATE komitmen_tabungan_khusus
            SET status = 'Selesai Dibagikan', tanggal_dibagikan = ?, total_dibagikan = ?
            WHERE anggota_id = ? AND jenis_tabungan = ? AND status = 'Aktif'
            ''', (tgl, saldo, aid, jenis_tabungan))

            # Jika belum tercatat komitmen resmi di tabel baru, buat catatan riwayatnya
            if cursor.rowcount == 0:
                cursor.execute('''
                INSERT INTO komitmen_tabungan_khusus (
                    anggota_id, jenis_tabungan, tahun_periode, nominal_per_bulan,
                    status, tanggal_daftar, tanggal_dibagikan, total_dibagikan, keterangan
                ) VALUES (?, ?, ?, 0, 'Selesai Dibagikan', ?, ?, ?, ?)
                ''', (aid, jenis_tabungan, tahun_periode, tgl, tgl, saldo, ket))

            total_dana_dibagikan += saldo
            jml_anggota_dibagikan += 1
            rincian_pencairan.append({
                'anggota_id': aid,
                'no_anggota': a['no_anggota'],
                'nama': a['nama'],
                'saldo_dibagikan': saldo,
                'no_transaksi': no_trx
            })

    conn.commit()
    conn.close()

    msg = f"Pembagian Tabungan {jenis_tabungan} Periode {tahun_periode} berhasil! Total {jml_anggota_dibagikan} anggota menerima pencairan sebesar Rp {total_dana_dibagikan:,.0f}."
    return True, msg, {
        'jml_anggota': jml_anggota_dibagikan,
        'total_dana': total_dana_dibagikan,
        'rincian': rincian_pencairan
    }

def get_status_tabungan_khusus_anggota(anggota_id):
    """
    Mengambil status lengkap tabungan Lebaran dan Qurban untuk satu anggota:
    - Saldo terkumpul saat ini
    - Komitmen aktif berjalan (nominal/bulan)
    - Status apakah baru saja dibagikan, sedang berjalan (belum dibagikan), atau anggota baru
    - Kelayakan mengajukan komitmen baru (can_commit_lebaran, can_commit_qurban)
    """
    bal = get_anggota_balance(anggota_id)
    conn = get_db()
    cursor = conn.cursor()

    # 1. Komitmen aktif Lebaran
    cursor.execute('''
    SELECT * FROM komitmen_tabungan_khusus
    WHERE anggota_id = ? AND jenis_tabungan = 'Lebaran' AND status = 'Aktif'
    ORDER BY id DESC LIMIT 1
    ''', (anggota_id,))
    leb_row = cursor.fetchone()
    komit_lebaran = dict(leb_row) if leb_row else None

    # 2. Komitmen aktif Qurban
    cursor.execute('''
    SELECT * FROM komitmen_tabungan_khusus
    WHERE anggota_id = ? AND jenis_tabungan = 'Qurban' AND status = 'Aktif'
    ORDER BY id DESC LIMIT 1
    ''', (anggota_id,))
    qur_row = cursor.fetchone()
    komit_qurban = dict(qur_row) if qur_row else None

    # 3. Riwayat pembagian terakhir Lebaran
    cursor.execute('''
    SELECT * FROM komitmen_tabungan_khusus
    WHERE anggota_id = ? AND jenis_tabungan = 'Lebaran' AND status = 'Selesai Dibagikan'
    ORDER BY tanggal_dibagikan DESC LIMIT 1
    ''', (anggota_id,))
    last_bagikan_leb = cursor.fetchone()

    # 4. Riwayat pembagian terakhir Qurban
    cursor.execute('''
    SELECT * FROM komitmen_tabungan_khusus
    WHERE anggota_id = ? AND jenis_tabungan = 'Qurban' AND status = 'Selesai Dibagikan'
    ORDER BY tanggal_dibagikan DESC LIMIT 1
    ''', (anggota_id,))
    last_bagikan_qur = cursor.fetchone()

    # 5. Riwayat transaksi penarikan pembagian tabungan
    cursor.execute('''
    SELECT COUNT(*) FROM transaksi_simpanan
    WHERE anggota_id = ? AND jenis_simpanan = 'Lebaran' AND tipe = 'TARIK'
    AND (keterangan LIKE '%Pembagian%' OR keterangan LIKE '%Pencairan%' OR keterangan LIKE '%Hari Raya%')
    ''', (anggota_id,))
    has_disbursed_trx_leb = cursor.fetchone()[0] > 0

    cursor.execute('''
    SELECT COUNT(*) FROM transaksi_simpanan
    WHERE anggota_id = ? AND jenis_simpanan = 'Qurban' AND tipe = 'TARIK'
    AND (keterangan LIKE '%Pembagian%' OR keterangan LIKE '%Pencairan%' OR keterangan LIKE '%Hari Raya%')
    ''', (anggota_id,))
    has_disbursed_trx_qur = cursor.fetchone()[0] > 0

    # Riwayat komitmen lengkap
    cursor.execute('''
    SELECT * FROM komitmen_tabungan_khusus
    WHERE anggota_id = ?
    ORDER BY id DESC
    ''', (anggota_id,))
    all_komitmen = [dict(r) for r in cursor.fetchall()]

    conn.close()

    saldo_leb = bal['simpanan_lebaran']
    saldo_qur = bal['simpanan_qurban']

    # --- EVALUASI TABUNGAN LEBARAN ---
    # Aturan KOSITAS: Komitmen tidak bisa diajukan apabila belum dibagikan, kecuali anggota baru masuk
    if komit_lebaran is not None:
        can_commit_leb = False
        status_code_leb = 'AKTIF'
        status_text_leb = 'Aktif'
        badge_class_leb = 'bg-emerald-100 text-emerald-800'
        badge_icon_leb = 'fa-circle-check text-[10px]'
        message_leb = f"Komitmen Periode {komit_lebaran['tahun_periode']} aktif sebesar Rp {komit_lebaran['nominal_per_bulan']:,.0f}/bulan melalui {komit_lebaran['metode_setor']}. Tabungan sedang berjalan dan belum dibagikan."
    elif saldo_leb > 0:
        can_commit_leb = False
        status_code_leb = 'BELUM_DIBAGIKAN'
        status_text_leb = 'Belum Dibagikan'
        badge_class_leb = 'bg-blue-100 text-blue-800 border border-blue-200'
        badge_icon_leb = 'fa-lock text-[10px]'
        message_leb = f"Tabungan Lebaran periode berjalan sebesar Rp {saldo_leb:,.0f} sedang dihimpun dan BELUM DIBAGIKAN oleh koperasi. Komitmen periode berikutnya belum bisa diajukan sebelum tabungan dibagikan menjelang 1 Syawal."
    elif (last_bagikan_leb is not None or has_disbursed_trx_leb):
        can_commit_leb = True
        status_code_leb = 'PERLU_INPUT_BARU'
        status_text_leb = 'Perlu Input Baru'
        badge_class_leb = 'bg-amber-100 text-amber-800 border border-amber-200'
        badge_icon_leb = 'fa-triangle-exclamation text-[10px]'
        message_leb = "Tabungan Lebaran periode sebelumnya telah selesai dibagikan. Silakan isi form di bawah untuk mendaftarkan komitmen tabungan periode baru Anda!"
    else:
        # Anggota baru masuk / belum pernah mendaftar
        can_commit_leb = True
        status_code_leb = 'BELUM_TERDAFTAR'
        status_text_leb = '- Belum Terdaftar'
        badge_class_leb = 'bg-slate-100 text-slate-600 border border-slate-200'
        badge_icon_leb = 'fa-minus text-[10px]'
        message_leb = "Anda belum mendaftarkan komitmen Tabungan Lebaran periode ini. Sebagai anggota baru/belum terdaftar, Anda dapat mendaftarkannya sekarang untuk persiapan Idul Fitri."

    # --- EVALUASI TABUNGAN QURBAN ---
    if komit_qurban is not None:
        can_commit_qur = False
        status_code_qur = 'AKTIF'
        status_text_qur = 'Aktif'
        badge_class_qur = 'bg-teal-100 text-teal-800'
        badge_icon_qur = 'fa-circle-check text-[10px]'
        message_qur = f"Komitmen Qurban Periode {komit_qurban['tahun_periode']} aktif sebesar Rp {komit_qurban['nominal_per_bulan']:,.0f}/bulan melalui {komit_qurban['metode_setor']}. Tabungan sedang berjalan dan belum dibagikan."
    elif saldo_qur > 0:
        can_commit_qur = False
        status_code_qur = 'BELUM_DIBAGIKAN'
        status_text_qur = 'Belum Dibagikan'
        badge_class_qur = 'bg-blue-100 text-blue-800 border border-blue-200'
        badge_icon_qur = 'fa-lock text-[10px]'
        message_qur = f"Tabungan Qurban periode berjalan sebesar Rp {saldo_qur:,.0f} sedang dihimpun dan BELUM DIBAGIKAN oleh koperasi. Komitmen periode berikutnya belum bisa diajukan sebelum tabungan dibagikan menjelang 10 Dzulhijjah."
    elif (last_bagikan_qur is not None or has_disbursed_trx_qur):
        can_commit_qur = True
        status_code_qur = 'PERLU_INPUT_BARU'
        status_text_qur = 'Perlu Input Baru'
        badge_class_qur = 'bg-amber-100 text-amber-800 border border-amber-200'
        badge_icon_qur = 'fa-triangle-exclamation text-[10px]'
        message_qur = "Tabungan Qurban periode sebelumnya telah selesai dibagikan. Silakan isi form di bawah untuk mendaftarkan komitmen tabungan periode baru Anda!"
    else:
        # Anggota baru masuk / belum pernah mendaftar
        can_commit_qur = True
        status_code_qur = 'BELUM_TERDAFTAR'
        status_text_qur = '- Belum Terdaftar'
        badge_class_qur = 'bg-slate-100 text-slate-600 border border-slate-200'
        badge_icon_qur = 'fa-minus text-[10px]'
        message_qur = "Anda belum mendaftarkan komitmen Tabungan Qurban periode ini. Sebagai anggota baru/belum terdaftar, Anda dapat mendaftarkannya sekarang untuk persiapan hewan qurban tahun depan."

    return {
        # Lebaran
        'saldo_lebaran': saldo_leb,
        'komit_lebaran': komit_lebaran,
        'can_commit_lebaran': can_commit_leb,
        'perlu_komitmen_lebaran': (status_code_leb == 'PERLU_INPUT_BARU'),
        'status_code_leb': status_code_leb,
        'status_text_leb': status_text_leb,
        'badge_class_leb': badge_class_leb,
        'badge_icon_leb': badge_icon_leb,
        'message_leb': message_leb,
        'last_bagikan_leb': dict(last_bagikan_leb) if last_bagikan_leb else None,

        # Qurban
        'saldo_qurban': saldo_qur,
        'komit_qurban': komit_qurban,
        'can_commit_qurban': can_commit_qur,
        'perlu_komitmen_qurban': (status_code_qur == 'PERLU_INPUT_BARU'),
        'status_code_qur': status_code_qur,
        'status_text_qur': status_text_qur,
        'badge_class_qur': badge_class_qur,
        'badge_icon_qur': badge_icon_qur,
        'message_qur': message_qur,
        'last_bagikan_qur': dict(last_bagikan_qur) if last_bagikan_qur else None,

        # General
        'all_komitmen': all_komitmen
    }

def get_rekap_tabungan_khusus_dashboard():
    """
    Rekapitulasi tabungan Lebaran dan Qurban untuk dashboard Admin:
    daftar saldo, komitmen aktif, dan histori pembagian seluruh anggota aktif.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM anggota WHERE status = 'Aktif' ORDER BY no_anggota ASC")
    anggota_list = [dict(r) for r in cursor.fetchall()]

    total_saldo_lebaran = 0.0
    total_saldo_qurban = 0.0
    total_komitmen_lebaran = 0.0
    total_komitmen_qurban = 0.0
    anggota_data = []

    for a in anggota_list:
        aid = a['id']
        # Saldo Lebaran
        cursor.execute('''
        SELECT 
            COALESCE(SUM(CASE WHEN tipe = 'SETOR' THEN nominal ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN tipe = 'TARIK' THEN nominal ELSE 0 END), 0)
        FROM transaksi_simpanan WHERE anggota_id = ? AND jenis_simpanan = 'Lebaran'
        ''', (aid,))
        saldo_leb = float(cursor.fetchone()[0] or 0)

        # Saldo Qurban
        cursor.execute('''
        SELECT 
            COALESCE(SUM(CASE WHEN tipe = 'SETOR' THEN nominal ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN tipe = 'TARIK' THEN nominal ELSE 0 END), 0)
        FROM transaksi_simpanan WHERE anggota_id = ? AND jenis_simpanan = 'Qurban'
        ''', (aid,))
        saldo_qur = float(cursor.fetchone()[0] or 0)

        # Komitmen Lebaran
        cursor.execute('''
        SELECT * FROM komitmen_tabungan_khusus
        WHERE anggota_id = ? AND jenis_tabungan = 'Lebaran' AND status = 'Aktif'
        ORDER BY id DESC LIMIT 1
        ''', (aid,))
        kl = cursor.fetchone()
        komit_leb = dict(kl) if kl else None

        # Komitmen Qurban
        cursor.execute('''
        SELECT * FROM komitmen_tabungan_khusus
        WHERE anggota_id = ? AND jenis_tabungan = 'Qurban' AND status = 'Aktif'
        ORDER BY id DESC LIMIT 1
        ''', (aid,))
        kq = cursor.fetchone()
        komit_qur = dict(kq) if kq else None

        total_saldo_lebaran += saldo_leb
        total_saldo_qurban += saldo_qur
        if komit_leb:
            total_komitmen_lebaran += float(komit_leb['nominal_per_bulan'])
        if komit_qur:
            total_komitmen_qurban += float(komit_qur['nominal_per_bulan'])

        # Cek status Lebaran
        if komit_leb:
            status_leb = 'Aktif'
            status_class_leb = 'text-emerald-700 bg-emerald-50 border-emerald-200'
        elif saldo_leb > 0:
            status_leb = 'Belum Dibagikan'
            status_class_leb = 'text-blue-700 bg-blue-50 border-blue-200'
        else:
            status_leb = 'Belum Terdaftar'
            status_class_leb = 'text-slate-500 bg-slate-100 border-slate-200'

        # Cek status Qurban
        if komit_qur:
            status_qur = 'Aktif'
            status_class_qur = 'text-teal-700 bg-teal-50 border-teal-200'
        elif saldo_qur > 0:
            status_qur = 'Belum Dibagikan'
            status_class_qur = 'text-blue-700 bg-blue-50 border-blue-200'
        else:
            status_qur = 'Belum Terdaftar'
            status_class_qur = 'text-slate-500 bg-slate-100 border-slate-200'

        anggota_data.append({
            'anggota': a,
            'saldo_lebaran': saldo_leb,
            'komit_lebaran': komit_leb,
            'status_leb': status_leb,
            'status_class_leb': status_class_leb,
            'saldo_qurban': saldo_qur,
            'komit_qurban': komit_qur,
            'status_qur': status_qur,
            'status_class_qur': status_class_qur
        })

    conn.close()

    return {
        'total_saldo_lebaran': total_saldo_lebaran,
        'total_saldo_qurban': total_saldo_qurban,
        'total_komitmen_lebaran': total_komitmen_lebaran,
        'total_komitmen_qurban': total_komitmen_qurban,
        'anggota_data': anggota_data
    }

