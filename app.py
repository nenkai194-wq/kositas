import os
import socket
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, send_file, abort
)
import database
import models
import excel_service

def get_local_ip():
    """Mendeteksi IP lokal mesin di jaringan LAN / Wi-Fi"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '192.168.200.9'

app = Flask(__name__)
app.secret_key = 'kositas-bps-tasikmalaya-secret-key-2026'

# Ensure database exists
if not os.path.exists(database.DB_PATH):
    import seed_data
    seed_data.run_seed()

# ----------------- CUSTOM JINJA TEMPLATE FILTERS -----------------
@app.template_filter('rupiah')
def rupiah_filter(val):
    if val is None:
        return 'Rp 0'
    try:
        val = float(val)
        return f"Rp {val:,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return 'Rp 0'

@app.template_filter('format_date')
def format_date_filter(val):
    if not val:
        return '-'
    try:
        if isinstance(val, str):
            dt = datetime.strptime(val[:10], '%Y-%m-%d')
        else:
            dt = val
        bulan_nama = [
            '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ]
        return f"{dt.day} {bulan_nama[dt.month]} {dt.year}"
    except Exception:
        return str(val)

@app.template_filter('bulan_indo')
def bulan_indo_filter(val):
    if not val:
        return '-'
    try:
        parts = val.split('-')
        tahun = parts[0]
        bln_idx = int(parts[1])
        bulan_nama = [
            '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ]
        return f"{bulan_nama[bln_idx]} {tahun}"
    except Exception:
        return str(val)

@app.template_filter('terbilang')
def terbilang_filter(val):
    return models.terbilang(val)

# ----------------- AUTHENTICATION HELPERS -----------------
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return models.get_anggota_by_id(user_id)

def is_ketua_koperasi_user(user):
    """
    Memeriksa apakah pengguna memiliki hak verifikasi pinjaman & pengajuan:
    Wajib berstatus Superadmin DAN menjabat sebagai Ketua Koperasi.
    """
    if not user:
        return False
    if user.get('role') != 'superadmin':
        return False
    jab = (user.get('jabatan') or '').strip().lower()
    # Harus memiliki jabatan sebagai Ketua Koperasi (bukan Ketua Badan Pemeriksa/Pengawas)
    if 'pemeriksa' in jab or 'pengawas' in jab:
        return False
    return 'ketua' in jab

@app.context_processor
def inject_global_data():
    user = get_current_user()
    all_members = models.get_all_anggota(status_filter='Aktif')
    now = datetime.now()
    local_ip = get_local_ip()
    return {
        'current_user': user,
        'is_ketua_koperasi': is_ketua_koperasi_user(user),
        'current_year': now.year,
        'current_month': now.strftime('%Y-%m'),
        'all_active_members': all_members,
        'server_ip': local_ip,
        'server_port': 5000,
        'server_url': f"http://{local_ip}:5000"
    }

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu untuk mengakses sistem.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        user = get_current_user()
        if not user or user.get('role') not in ['admin', 'superadmin']:
            flash('Akses ditolak! Halaman ini hanya untuk Pengurus / Administrator KOSITAS.', 'danger')
            return redirect(url_for('anggota_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        user = get_current_user()
        if not user or user.get('role') != 'superadmin':
            flash('Akses ditolak! Fitur konfigurasi ini hanya untuk Superadmin (Ketua Koperasi / SysAdmin).', 'danger')
            if user and user.get('role') == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('anggota_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def ketua_koperasi_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        user = get_current_user()
        if not is_ketua_koperasi_user(user):
            flash('Akses ditolak! Menu verifikasi dan penetapan pinjaman hanya untuk Superadmin dengan jabatan Ketua Koperasi.', 'danger')
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ----------------- AUTH ROUTES & USER SWITCHER -----------------
@app.route('/')
def index():
    if 'user_id' in session:
        user = get_current_user()
        if user and user.get('role') in ['admin', 'superadmin']:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('anggota_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Admin / Superadmin login by username 'admin' or 'superadmin'
        if username.lower() in ['admin', 'superadmin']:
            conn = database.get_db()
            cursor = conn.cursor()
            target_role = 'superadmin' if username.lower() == 'superadmin' else 'admin'
            cursor.execute("SELECT * FROM anggota WHERE role = ? LIMIT 1", (target_role,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT * FROM anggota WHERE role IN ('admin', 'superadmin') LIMIT 1")
                row = cursor.fetchone()
            conn.close()
            if row and (password in [row['password'], 'admin', '123456']):
                session['user_id'] = row['id']
                session['role'] = row['role']
                flash(f"Selamat datang, {row['nama']} (Akses: {row['role'].upper()})!", 'success')
                return redirect(url_for('admin_dashboard'))
        
        # Anggota login by No Anggota or NIP or Nama
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM anggota 
        WHERE (no_anggota = ? OR nip = ? OR nama LIKE ?) AND status = 'Aktif'
        LIMIT 1
        ''', (username, username, f"%{username}%"))
        row = cursor.fetchone()
        conn.close()

        if row and (password == row['password'] or password == '123456'):
            session['user_id'] = row['id']
            session['role'] = row['role']
            flash(f"Selamat datang, {row['nama']}!", 'success')
            if row['role'] in ['admin', 'superadmin']:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('anggota_dashboard'))

        flash('Username / No Anggota atau Password salah!', 'danger')

    # Suggested sample accounts for demo
    sample_members = models.get_all_anggota(status_filter='Aktif')[:8]
    return render_template('login.html', sample_members=sample_members)

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah berhasil keluar dari sistem KOSITAS.', 'info')
    return redirect(url_for('login'))

@app.route('/switch-user/<int:user_id>')
def switch_user(user_id):
    """
    Fitur beralih akun.
    Jika sedang login sebagai Admin operasional, tidak diperbolehkan login sebagai akun anggota lain.
    Hanya Superadmin yang berwenang login sebagai anggota dari form master data anggota.
    """
    curr = get_current_user()
    target_user = models.get_anggota_by_id(user_id)
    if not target_user:
        flash('User tidak ditemukan!', 'danger')
        return redirect(url_for('login'))

    # Proteksi: Jika sedang login sebagai Admin (bukan Superadmin) dan mencoba switch ke anggota lain
    if curr and curr.get('role') == 'admin':
        if target_user['id'] != curr['id'] and target_user.get('role') == 'anggota':
            flash('Akses ditolak! Fitur login sebagai anggota ini hanya dapat dilakukan oleh Superadmin (Ketua Koperasi / SysAdmin).', 'danger')
            return redirect(url_for('admin_anggota_list'))

    session['user_id'] = target_user['id']
    session['role'] = target_user['role']
    flash(f"Beralih akun sebagai: {target_user['nama']} ({target_user['jabatan']} - Role: {target_user['role'].upper()})", 'info')
    if target_user['role'] in ['admin', 'superadmin']:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('anggota_dashboard'))

# ----------------- ADMIN ROUTES -----------------
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    stats = models.get_dashboard_stats()
    recent_savings = models.get_all_transaksi_simpanan(limit=5)
    active_loans = models.get_all_pinjaman(status_filter='Aktif')[:5]
    
    # Pengajuan online yang menunggu
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota, a.jabatan
    FROM pengajuan_online p
    JOIN anggota a ON p.anggota_id = a.id
    WHERE p.status = 'Menunggu'
    ORDER BY p.tanggal_pengajuan ASC
    ''')
    pengajuan_pending = [dict(r) for r in cursor.fetchall()]

    # Riwayat pengajuan online yang baru disetujui (terkoneksi dengan pinjaman bila jenis PINJAMAN)
    cursor.execute('''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota, a.jabatan,
           pj.id as pinjaman_id_real, pj.no_pinjaman, pj.saldo_pokok as pj_saldo_pokok,
           pj.angsuran_ke as pj_angsuran_ke, pj.margin_persen as pj_margin_persen,
           pj.margin_nominal as pj_margin_nominal, pj.total_angsuran_bulanan as pj_total_angsuran
    FROM pengajuan_online p
    JOIN anggota a ON p.anggota_id = a.id
    LEFT JOIN pinjaman pj ON (p.pinjaman_id = pj.id OR pj.pengajuan_id = p.id OR pj.keterangan LIKE '%' || p.no_pengajuan || '%')
    WHERE p.status = 'Disetujui'
    ORDER BY p.tanggal_diproses DESC, p.id DESC
    LIMIT 15
    ''')
    pengajuan_disetujui = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # Hitung ringkasan pembagian SHU estimasi
    shu = models.hitung_shu_koperasi()

    return render_template(
        'admin/dashboard.html',
        stats=stats,
        recent_savings=recent_savings,
        active_loans=active_loans,
        pengajuan_pending=pengajuan_pending,
        pengajuan_disetujui=pengajuan_disetujui,
        shu=shu
    )

# --- MASTER DATA ANGGOTA ---
@app.route('/admin/anggota')
@admin_required
def admin_anggota_list():
    status = request.args.get('status', 'Semua')
    search = request.args.get('search', '').strip()
    members = models.get_all_anggota(status_filter=status, search=search)
    return render_template('admin/anggota_list.html', members=members, current_status=status, search=search)

@app.route('/admin/anggota/tambah', methods=['GET', 'POST'])
@admin_required
def admin_anggota_tambah():
    if request.method == 'POST':
        try:
            new_id = models.create_anggota(request.form)
            flash('Data anggota baru berhasil ditambahkan beserta Simpanan Pokok awal.', 'success')
            return redirect(url_for('admin_anggota_detail', id=new_id))
        except Exception as e:
            flash(f'Gagal menambahkan anggota: {str(e)}', 'danger')

    return render_template('admin/anggota_form.html', member=None, title='Tambah Anggota Baru KOSITAS')

@app.route('/admin/anggota/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_anggota_edit(id):
    member = models.get_anggota_by_id(id)
    if not member:
        flash('Anggota tidak ditemukan!', 'danger')
        return redirect(url_for('admin_anggota_list'))

    if request.method == 'POST':
        try:
            models.update_anggota(id, request.form)
            flash('Data anggota berhasil diperbarui.', 'success')
            return redirect(url_for('admin_anggota_detail', id=id))
        except Exception as e:
            flash(f'Gagal memperbarui anggota: {str(e)}', 'danger')

    return render_template('admin/anggota_form.html', member=member, title=f"Edit Data - {member['nama']}")

@app.route('/admin/anggota/<int:id>')
@admin_required
def admin_anggota_detail(id):
    member = models.get_anggota_by_id(id)
    if not member:
        flash('Anggota tidak ditemukan!', 'danger')
        return redirect(url_for('admin_anggota_list'))

    simpanan_history = models.get_transaksi_simpanan_by_anggota(id)
    loans = models.get_pinjaman_by_anggota(id)
    monthly_history = models.get_rekap_bulanan_anggota(id)

    return render_template(
        'admin/anggota_detail.html',
        member=member,
        simpanan_history=simpanan_history,
        loans=loans,
        monthly_history=monthly_history
    )

# --- TRANSAKSI SIMPANAN ---
@app.route('/admin/simpanan', methods=['GET', 'POST'])
@admin_required
def admin_simpanan():
    if request.method == 'POST':
        success, message = models.tambah_transaksi_simpanan(request.form)
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
        return redirect(url_for('admin_simpanan'))

    bulan_filter = request.args.get('bulan', '')
    transactions = models.get_all_transaksi_simpanan(limit=100, bulan_filter=bulan_filter if bulan_filter else None)
    members = models.get_all_anggota(status_filter='Aktif')
    return render_template('admin/simpanan_entry.html', transactions=transactions, members=members, bulan_filter=bulan_filter)

# --- PENGELOLAAN TABUNGAN HARI RAYA (LEBARAN & QURBAN) ---
@app.route('/admin/tabungan-khusus', methods=['GET'])
@admin_required
def admin_tabungan_khusus():
    jenis = request.args.get('jenis', 'Semua')
    status = request.args.get('status', 'Semua')
    tahun = request.args.get('tahun', 'Semua')

    rekap = models.get_rekap_tabungan_khusus_dashboard()
    riwayat_komitmen = models.get_all_komitmen_tabungan(jenis_filter=jenis, status_filter=status, tahun_filter=tahun)
    members = models.get_all_anggota(status_filter='Aktif')

    return render_template(
        'admin/tabungan_khusus.html',
        rekap=rekap,
        riwayat_komitmen=riwayat_komitmen,
        members=members,
        current_jenis=jenis,
        current_status=status,
        current_tahun=tahun
    )

@app.route('/admin/tabungan-khusus/komitmen', methods=['POST'])
@admin_required
def admin_tabungan_khusus_komitmen():
    user = get_current_user()
    created_by = user['nama'] if user else 'Pengurus'
    success, message = models.daftar_komitmen_tabungan_baru(request.form, created_by=f"Admin ({created_by})")
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin_tabungan_khusus'))

@app.route('/admin/tabungan-khusus/bagikan', methods=['POST'])
@admin_required
def admin_tabungan_khusus_bagikan():
    user = get_current_user()
    created_by = user['nama'] if user else 'Pengurus'

    jenis_tabungan = request.form.get('jenis_tabungan', 'Lebaran')
    tahun_periode = int(request.form.get('tahun_periode', datetime.now().year))
    anggota_id_val = request.form.get('anggota_id', 'Semua')
    tanggal_cair = request.form.get('tanggal_cair') or datetime.now().strftime('%Y-%m-%d')

    anggota_id_list = [int(anggota_id_val)] if (anggota_id_val and anggota_id_val != 'Semua') else None

    success, message, detail = models.bagikan_tabungan_khusus(
        jenis_tabungan=jenis_tabungan,
        tahun_periode=tahun_periode,
        anggota_id_list=anggota_id_list,
        tanggal_cair=tanggal_cair,
        created_by=created_by
    )
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin_tabungan_khusus'))

@app.route('/admin/tabungan-khusus/status/<int:id>/<status_baru>', methods=['POST'])
@admin_required
def admin_tabungan_khusus_toggle_status(id, status_baru):
    models.update_status_komitmen(id, status_baru)
    flash(f'Status komitmen berhasil diubah menjadi {status_baru}.', 'info')
    return redirect(url_for('admin_tabungan_khusus'))

# --- TRANSAKSI PINJAMAN ---
@app.route('/admin/pinjaman')
@admin_required
def admin_pinjaman_list():
    status = request.args.get('status', 'Semua')
    jenis = request.args.get('jenis', 'Semua')
    loans = models.get_all_pinjaman(status_filter=status, jenis_filter=jenis)
    return render_template('admin/pinjaman_list.html', loans=loans, current_status=status, current_jenis=jenis)

@app.route('/admin/pinjaman/tambah', methods=['GET', 'POST'])
@admin_required
def admin_pinjaman_tambah():
    if request.method == 'POST':
        try:
            new_id = models.tambah_pinjaman(request.form)
            flash('Pembiayaan/Pinjaman baru berhasil disetujui & dicairkan.', 'success')
            return redirect(url_for('admin_pinjaman_detail', id=new_id))
        except Exception as e:
            flash(f'Gagal membuat pinjaman: {str(e)}', 'danger')

    members = models.get_all_anggota(status_filter='Aktif')
    selected_member_id = request.args.get('anggota_id', type=int)
    return render_template('admin/pinjaman_form.html', members=members, selected_member_id=selected_member_id)

@app.route('/admin/pinjaman/<int:id>')
@admin_required
def admin_pinjaman_detail(id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota, a.nip, a.jabatan, a.no_hp
    FROM pinjaman p
    JOIN anggota a ON p.anggota_id = a.id
    WHERE p.id = ?
    ''', (id,))
    loan = cursor.fetchone()
    if not loan:
        conn.close()
        flash('Pinjaman tidak ditemukan!', 'danger')
        return redirect(url_for('admin_pinjaman_list'))

    loan = dict(loan)
    cursor.execute('''
    SELECT * FROM angsuran_pinjaman
    WHERE pinjaman_id = ?
    ORDER BY angsuran_ke ASC
    ''', (id,))
    installments = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # Hitung persentase lunas
    if loan['plafon_pokok'] > 0:
        persen = ((loan['plafon_pokok'] - loan['saldo_pokok']) / loan['plafon_pokok']) * 100
        loan['persen_lunas'] = min(100.0, max(0.0, round(persen, 1)))
    else:
        loan['persen_lunas'] = 100.0

    return render_template('admin/pinjaman_detail.html', loan=loan, installments=installments)

@app.route('/admin/pinjaman/<int:id>/bayar', methods=['GET', 'POST'])
@admin_required
def admin_pinjaman_bayar(id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota
    FROM pinjaman p
    JOIN anggota a ON p.anggota_id = a.id
    WHERE p.id = ?
    ''', (id,))
    loan = cursor.fetchone()
    conn.close()
    if not loan:
        flash('Pinjaman tidak ditemukan!', 'danger')
        return redirect(url_for('admin_pinjaman_list'))

    loan = dict(loan)
    if request.method == 'POST':
        success, message = models.bayar_angsuran(request.form)
        if success:
            flash(message, 'success')
            return redirect(url_for('admin_pinjaman_detail', id=id))
        else:
            flash(message, 'danger')

    return render_template('admin/pinjaman_bayar.html', loan=loan)

# --- PELUNASAN DIPERCEPAT (EARLY SETTLEMENT) ---
@app.route('/admin/pinjaman/<int:id>/pelunasan-dipercepat', methods=['GET', 'POST'])
@admin_required
def admin_pinjaman_pelunasan_dipercepat(id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota, a.jabatan, a.nip
    FROM pinjaman p
    JOIN anggota a ON p.anggota_id = a.id
    WHERE p.id = ?
    ''', (id,))
    loan = cursor.fetchone()
    conn.close()
    if not loan:
        flash('Pinjaman tidak ditemukan!', 'danger')
        return redirect(url_for('admin_pinjaman_list'))

    loan = dict(loan)
    if loan['status'] == 'Lunas':
        flash('Pinjaman ini sudah lunas sebelumnya!', 'warning')
        return redirect(url_for('admin_pinjaman_detail', id=id))

    if request.method == 'POST':
        diskon_margin = float(request.form.get('diskon_margin', 0))
        tanggal_lunas = request.form.get('tanggal_lunas')
        metode_bayar = request.form.get('metode_bayar', 'Tunai')
        keterangan = request.form.get('keterangan', '')
        user = get_current_user()
        created_by = user['nama'] if user else 'Admin'

        success, message = models.proses_pelunasan_dipercepat(
            id, diskon_margin=diskon_margin, tanggal_lunas=tanggal_lunas,
            metode_bayar=metode_bayar, keterangan=keterangan, created_by=created_by
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('admin_pinjaman_detail', id=id))
        else:
            flash(message, 'danger')

    return render_template('admin/pinjaman_pelunasan.html', loan=loan)

# --- TOP UP PINJAMAN (REFINANCING) ---
@app.route('/admin/pinjaman/<int:id>/topup', methods=['GET', 'POST'])
@admin_required
def admin_pinjaman_topup(id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota, a.jabatan, a.nip
    FROM pinjaman p
    JOIN anggota a ON p.anggota_id = a.id
    WHERE p.id = ?
    ''', (id,))
    loan = cursor.fetchone()
    conn.close()
    if not loan:
        flash('Pinjaman tidak ditemukan!', 'danger')
        return redirect(url_for('admin_pinjaman_list'))

    loan = dict(loan)
    if loan['status'] != 'Aktif':
        flash('Hanya pinjaman aktif yang dapat di-Top Up!', 'warning')
        return redirect(url_for('admin_pinjaman_detail', id=id))

    if request.method == 'POST':
        data = dict(request.form)
        data['pinjaman_lama_id'] = id
        user = get_current_user()
        created_by = user['nama'] if user else 'Admin'

        success, message, new_id = models.proses_topup_pinjaman(data, created_by=created_by)
        if success:
            flash(message, 'success')
            return redirect(url_for('admin_pinjaman_detail', id=new_id))
        else:
            flash(message, 'danger')

    return render_template('admin/pinjaman_topup.html', loan=loan)

# --- REKAP BULANAN KOLEKTIF & POTONG GAJI ADMIN ---
@app.route('/admin/rekap-bulanan')
@admin_required
def admin_rekap_bulanan():
    now = datetime.now()
    periode_type = request.args.get('periode_type', 'bulanan')

    if periode_type == 'tahunan':
        tahun = request.args.get('tahun', str(now.year))
        rekap = models.hitung_rekap_tahunan(tahun)
        return render_template(
            'admin/rekap_bulanan.html',
            rekap=rekap,
            periode_type='tahunan',
            tahun=tahun,
            bulan_buku=None,
            billing_log=None
        )

    bulan_buku = request.args.get('bulan', now.strftime('%Y-%m'))
    rekap = models.hitung_rekap_bulanan(bulan_buku)

    # Cek log apakah bulan ini sudah dieksekusi
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM billing_bulanan_log WHERE bulan_buku = ?", (bulan_buku,))
    billing_log = cursor.fetchone()
    conn.close()

    return render_template(
        'admin/rekap_bulanan.html',
        rekap=rekap,
        periode_type='bulanan',
        bulan_buku=bulan_buku,
        tahun=now.year,
        billing_log=dict(billing_log) if billing_log else None
    )

@app.route('/admin/rekap-tahunan/export-excel')
@admin_required
def admin_rekap_tahunan_export():
    tahun = request.args.get('tahun', str(datetime.now().year))
    rekap = models.hitung_rekap_tahunan(tahun)
    output = excel_service.export_rekap_tahunan_excel(rekap)
    filename = f"Rekap_Tahunan_KOSITAS_{tahun}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@app.route('/admin/rekap-bulanan/proses', methods=['POST'])
@admin_required
def admin_rekap_bulanan_proses():
    bulan_buku = request.form.get('bulan_buku')
    if not bulan_buku:
        flash('Bulan buku tidak valid!', 'danger')
        return redirect(url_for('admin_rekap_bulanan'))

    user = get_current_user()
    created_by = user['nama'] if user else 'Admin'
    success, message = models.eksekusi_potong_gaji_bulanan(bulan_buku, created_by=created_by)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('admin_rekap_bulanan', bulan=bulan_buku))

@app.route('/admin/rekap-bulanan/export-excel')
@admin_required
def admin_rekap_bulanan_export():
    bulan = request.args.get('bulan', datetime.now().strftime('%Y-%m'))
    rekap = models.hitung_rekap_bulanan(bulan)
    output = excel_service.export_rekap_bulanan_excel(rekap)
    filename = f"Rekap_Potongan_KOSITAS_{bulan}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

# --- LAPORAN RESMI KOSITAS (RAT FORMAT) ---
@app.route('/admin/laporan/simpanan')
@admin_required
def admin_laporan_simpanan():
    members = models.get_all_anggota(status_filter='Semua')
    return render_template('admin/laporan_simpanan.html', members=members)

@app.route('/admin/laporan/simpanan/export-excel')
@admin_required
def admin_laporan_simpanan_export():
    members = models.get_all_anggota(status_filter='Semua')
    output = excel_service.export_rekap_simpanan_excel(members)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="Rekapitulasi_Simpanan_KOSITAS.xlsx"
    )

@app.route('/admin/laporan/piutang')
@admin_required
def admin_laporan_piutang():
    members = models.get_all_anggota(status_filter='Semua')
    return render_template('admin/laporan_piutang.html', members=members)

@app.route('/admin/laporan/piutang/export-excel')
@admin_required
def admin_laporan_piutang_export():
    members = models.get_all_anggota(status_filter='Semua')
    output = excel_service.export_data_piutang_excel(members)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="Data_Piutang_KOSITAS.xlsx"
    )

@app.route('/admin/laporan/shu')
@admin_required
def admin_laporan_shu():
    tahun = request.args.get('tahun', default=None, type=int)
    daftar_tahun = models.get_daftar_tahun_dana_shu()
    if tahun is None:
        tahun = daftar_tahun[0] if daftar_tahun else 2026

    total_shu_input = request.args.get('total_shu', type=float)
    if total_shu_input and total_shu_input > 0:
        shu_data = models.hitung_shu_koperasi(total_shu_input, tahun=tahun)
    else:
        shu_data = models.hitung_shu_koperasi(tahun=tahun)

    return render_template('admin/laporan_shu.html', shu=shu_data, daftar_tahun=daftar_tahun, selected_tahun=tahun)

@app.route('/admin/laporan/shu/export-excel')
@admin_required
def admin_laporan_shu_export():
    tahun = request.args.get('tahun', default=2026, type=int)
    shu_data = models.hitung_shu_koperasi(tahun=tahun)
    output = excel_service.export_shu_excel(shu_data)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Daftar_Pembagian_SHU_KOSITAS_{tahun}.xlsx"
    )

# --- PENGATURAN & MONITORING DANA-DANA SHU HASIL RAT ---
@app.route('/admin/dana-shu')
@admin_required
def admin_dana_shu():
    daftar_tahun = models.get_daftar_tahun_dana_shu()
    tahun = request.args.get('tahun', default=None, type=int)
    if tahun is None:
        tahun = daftar_tahun[0] if daftar_tahun else 2026

    total_shu_input = request.args.get('total_shu', default=38706812.69, type=float)
    if not total_shu_input or total_shu_input <= 0:
        total_shu_input = 38706812.69

    shu_data = models.hitung_shu_koperasi(total_shu_input, tahun=tahun)
    current_user = get_current_user()
    is_superadmin = (current_user.get('role') == 'superadmin')

    return render_template(
        'admin/dana_shu.html',
        shu=shu_data,
        tahun=tahun,
        daftar_tahun=daftar_tahun,
        total_shu=total_shu_input,
        is_superadmin=is_superadmin
    )

@app.route('/superadmin/dana-shu/tambah', methods=['POST'])
@superadmin_required
def superadmin_dana_shu_tambah():
    tahun = request.form.get('tahun', default=2026, type=int)
    kat = request.form.get('kategori', 'DANA')
    data = {
        'tahun': tahun,
        'nama_dana': request.form.get('nama_dana'),
        'persentase': request.form.get('persentase', type=float),
        'kategori': kat,
        'is_bagian_anggota': 1 if kat == 'ANGGOTA' else 0,
        'porsi_jasa_modal': request.form.get('porsi_jasa_modal', default=50.0, type=float),
        'porsi_jasa_pinjaman': request.form.get('porsi_jasa_pinjaman', default=50.0, type=float),
        'keterangan': request.form.get('keterangan', ''),
        'warna_badge': request.form.get('warna_badge', 'slate'),
        'urutan': request.form.get('urutan', default=99, type=int)
    }
    models.tambah_dana_shu(data)
    flash(f"Alokasi '{data['nama_dana']}' ({data['persentase']}%) berhasil ditambahkan untuk Tahun Buku {tahun}.", 'success')
    return redirect(url_for('admin_dana_shu', tahun=tahun))

@app.route('/superadmin/dana-shu/edit/<int:id>', methods=['POST'])
@superadmin_required
def superadmin_dana_shu_edit(id):
    tahun = request.form.get('tahun', default=2026, type=int)
    kat = request.form.get('kategori', 'DANA')
    data = {
        'tahun': tahun,
        'nama_dana': request.form.get('nama_dana'),
        'persentase': request.form.get('persentase', type=float),
        'kategori': kat,
        'is_bagian_anggota': 1 if kat == 'ANGGOTA' else 0,
        'porsi_jasa_modal': request.form.get('porsi_jasa_modal', default=50.0, type=float),
        'porsi_jasa_pinjaman': request.form.get('porsi_jasa_pinjaman', default=50.0, type=float),
        'keterangan': request.form.get('keterangan', ''),
        'warna_badge': request.form.get('warna_badge', 'slate'),
        'urutan': request.form.get('urutan', default=99, type=int)
    }
    models.update_dana_shu(id, data)
    flash(f"Perubahan alokasi '{data['nama_dana']}' berhasil disimpan.", 'success')
    return redirect(url_for('admin_dana_shu', tahun=tahun))

@app.route('/superadmin/dana-shu/hapus/<int:id>', methods=['POST'])
@superadmin_required
def superadmin_dana_shu_hapus(id):
    tahun = request.form.get('tahun', default=2026, type=int)
    dana = models.get_dana_shu_by_id(id)
    nama = dana['nama_dana'] if dana else f"ID {id}"
    models.hapus_dana_shu(id)
    flash(f"Alokasi '{nama}' berhasil dihapus dari Tahun Buku {tahun}.", 'info')
    return redirect(url_for('admin_dana_shu', tahun=tahun))

@app.route('/superadmin/dana-shu/salin-tahun', methods=['POST'])
@superadmin_required
def superadmin_dana_shu_salin():
    tahun_asal = request.form.get('tahun_asal', type=int)
    tahun_tujuan = request.form.get('tahun_tujuan', type=int)
    if not tahun_asal or not tahun_tujuan or tahun_asal == tahun_tujuan:
        flash('Tahun asal dan tujuan harus valid dan berbeda!', 'warning')
        return redirect(url_for('admin_dana_shu', tahun=tahun_asal))
    
    success, msg = models.salin_alokasi_dana_tahun(tahun_asal, tahun_tujuan)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('admin_dana_shu', tahun=tahun_tujuan))

# --- MANAJEMEN HAK AKSES & LEVEL ROLE (SUPERADMIN ONLY) ---
@app.route('/superadmin/manajemen-role', methods=['GET', 'POST'])
@superadmin_required
def superadmin_manajemen_role():
    current_user = get_current_user()
    if request.method == 'POST':
        anggota_id = request.form.get('anggota_id', type=int)
        new_role = request.form.get('new_role', '').strip().lower()

        # Pencegahan: Superadmin tidak boleh mendegradasi akunnya sendiri agar tidak terkunci
        if anggota_id == current_user['id'] and new_role != 'superadmin':
            flash('Anda tidak dapat mengubah level role akun Anda sendiri saat sedang login!', 'danger')
            return redirect(url_for('superadmin_manajemen_role'))

        target_user = models.get_anggota_by_id(anggota_id)
        if not target_user:
            flash('Anggota tidak ditemukan!', 'warning')
            return redirect(url_for('superadmin_manajemen_role'))

        success, msg = models.update_user_role(anggota_id, new_role)
        if success:
            flash(f"Hak akses {target_user['nama']} ({target_user['no_anggota']}) berhasil diubah menjadi: {new_role.upper()}.", 'success')
        else:
            flash(msg, 'danger')
        return redirect(url_for('superadmin_manajemen_role'))

    # GET request
    keyword = request.args.get('q', '').strip()
    filter_role = request.args.get('role', 'Semua')

    all_members = models.get_all_anggota(status_filter='Semua')
    
    # Filter by keyword
    if keyword:
        all_members = [
            m for m in all_members 
            if keyword.lower() in m['nama'].lower() 
            or keyword.lower() in m['no_anggota'].lower() 
            or keyword.lower() in (m['jabatan'] or '').lower()
            or keyword.lower() in (m['nip'] or '').lower()
        ]

    # Filter by role
    if filter_role and filter_role != 'Semua':
        all_members = [m for m in all_members if m['role'] == filter_role.lower()]

    role_stats = models.get_user_roles_stats()

    return render_template(
        'admin/manajemen_role.html',
        members=all_members,
        role_stats=role_stats,
        keyword=keyword,
        filter_role=filter_role
    )

# --- APPROVAL PENGAJUAN ONLINE ANGGOTA (KHUSUS SUPERADMIN KETUA KOPERASI) ---
@app.route('/admin/pengajuan/<int:id>/proses', methods=['POST'])
@ketua_koperasi_required
def admin_pengajuan_proses(id):
    action = request.form.get('action') # 'TERIMA' / 'TOLAK'
    catatan = request.form.get('catatan_admin', '').strip()
    
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pengajuan_online WHERE id = ?", (id,))
    req = cursor.fetchone()
    if not req:
        conn.close()
        flash('Pengajuan tidak ditemukan!', 'danger')
        return redirect(url_for('admin_dashboard'))

    req = dict(req)
    tgl_now = datetime.now().strftime('%Y-%m-%d')

    if action == 'TERIMA':
        plafon_pokok = float(req['nominal'])
        tenor_bulan = int(req.get('tenor_bulan') or 1)
        margin_persen = 0.0
        margin_nominal = 0.0

        if req['jenis'] == 'PINJAMAN':
            # Pertimbangan Ketua Koperasi: Plafon, Tenor, dan Margin yang mengikuti lama waktu cicilan
            plafon_pokok = float(request.form.get('plafon_pokok') or req['nominal'])
            tenor_bulan = int(request.form.get('tenor_bulan') or req['tenor_bulan'] or 1)
            margin_per_bulan = float(request.form.get('margin_per_bulan') or 0.0)
            margin_persen = float(request.form.get('margin_persen') or 0.0)
            margin_nominal = float(request.form.get('margin_nominal') or 0.0)

            # Jika margin_persen belum diisi atau 0, hitung otomatis dari margin_per_bulan * tenor_bulan
            if margin_persen <= 0 and margin_per_bulan > 0:
                margin_persen = round(margin_per_bulan * tenor_bulan, 2)

            # Suku margin default bila input kosong
            if margin_persen <= 0:
                if req['kategori'] == 'Bon Putih':
                    margin_persen = round(2.0 * tenor_bulan, 2)
                elif req['kategori'] == 'JAPAN':
                    margin_persen = round(1.0 * tenor_bulan, 2)
                elif req['kategori'] == 'JAPEN':
                    margin_persen = round(1.0 * tenor_bulan, 2)
                else:
                    margin_persen = 20.0

            if margin_nominal <= 0:
                margin_nominal = round((plafon_pokok * margin_persen) / 100.0, 2)

        # Update status dan data final pengajuan online
        cursor.execute('''
        UPDATE pengajuan_online
        SET status = 'Disetujui', catatan_admin = ?, tanggal_diproses = ?, nominal = ?, tenor_bulan = ?
        WHERE id = ?
        ''', (catatan, tgl_now, plafon_pokok, tenor_bulan, id))
        conn.commit()
        conn.close()

        # Eksekusi sesuai jenis
        if req['jenis'] == 'PINJAMAN':
            ket_lengkap = f"Persetujuan Ketua Koperasi #{req['no_pengajuan']}"
            if catatan:
                ket_lengkap += f": {catatan}"

            new_pinjaman_id = models.tambah_pinjaman({
                'anggota_id': req['anggota_id'],
                'jenis_pinjaman': req['kategori'],
                'plafon_pokok': plafon_pokok,
                'tenor_bulan': tenor_bulan,
                'margin_persen': margin_persen,
                'margin_nominal': margin_nominal,
                'keperluan': req['alasan'],
                'keterangan': ket_lengkap,
                'pengajuan_id': id
            })

            # Hubungkan pinjaman_id ke pengajuan_online
            conn_link = database.get_db()
            cur_link = conn_link.cursor()
            cur_link.execute("UPDATE pengajuan_online SET pinjaman_id = ? WHERE id = ?", (new_pinjaman_id, id))
            conn_link.commit()
            conn_link.close()

            flash(f"Pengajuan {req['no_pengajuan']} ({req['kategori']}) BERHASIL DISETUJUI Ketua Koperasi! Plafon: Rp {plafon_pokok:,.0f}, Tenor: {tenor_bulan} bln, Total Margin: {margin_persen:.1f}%. Pinjaman aktif diterbitkan.", 'success')

        elif req['jenis'] == 'PENARIKAN_SIMPANAN':
            if req['kategori'] == 'Pokok_Wajib':
                bal = models.get_anggota_balance(req['anggota_id'])
                # Tarik simpanan pokok dan simpanan wajib sekaligus
                if bal['simpanan_pokok'] > 0:
                    models.tambah_transaksi_simpanan({
                        'anggota_id': req['anggota_id'],
                        'jenis_simpanan': 'Pokok',
                        'tipe': 'TARIK',
                        'nominal': bal['simpanan_pokok'],
                        'alasan_khusus': req['alasan'],
                        'keterangan': f"Pencairan Simpanan Pokok online #{req['no_pengajuan']}: {req['alasan']}",
                        'metode_bayar': 'Transfer',
                        'update_status_keluar': True
                    })
                if bal['simpanan_wajib'] > 0:
                    models.tambah_transaksi_simpanan({
                        'anggota_id': req['anggota_id'],
                        'jenis_simpanan': 'Wajib',
                        'tipe': 'TARIK',
                        'nominal': bal['simpanan_wajib'],
                        'alasan_khusus': req['alasan'],
                        'keterangan': f"Pencairan Simpanan Wajib online #{req['no_pengajuan']}: {req['alasan']}",
                        'metode_bayar': 'Transfer',
                        'update_status_keluar': True
                    })
                flash(f"Pengajuan penarikan khusus #{req['no_pengajuan']} disetujui & seluruh simpanan pokok & wajib telah dicairkan.", 'success')
            else:
                success, msg = models.tambah_transaksi_simpanan({
                    'anggota_id': req['anggota_id'],
                    'jenis_simpanan': req['kategori'],
                    'tipe': 'TARIK',
                    'nominal': req['nominal'],
                    'alasan_khusus': req['alasan'],
                    'keterangan': f"Pencairan Simpanan online #{req['no_pengajuan']}: {req['alasan']}",
                    'metode_bayar': 'Transfer',
                    'update_status_keluar': True if req['kategori'] in ['Pokok', 'Wajib'] else False
                })
                if success:
                    flash(f"Pengajuan penarikan #{req['no_pengajuan']} disetujui & saldo simpanan telah didebit.", 'success')
                else:
                    flash(f"Peringatan: {msg}", 'warning')

    else:
        cursor.execute('''
        UPDATE pengajuan_online
        SET status = 'Ditolak', catatan_admin = ?, tanggal_diproses = ?
        WHERE id = ?
        ''', (catatan or 'Tidak memenuhi persyaratan pertimbangan pengurus', tgl_now, id))
        conn.commit()
        conn.close()
        flash(f"Pengajuan {req['no_pengajuan']} telah DITOLAK.", 'warning')

    return redirect(url_for('admin_dashboard'))

# --- KOREKSI & PEMBATALAN PERSETUJUAN PINJAMAN / MARGIN (HANYA SUPERADMIN) ---
@app.route('/admin/pinjaman/<int:id>/koreksi', methods=['POST'])
@superadmin_required
def superadmin_pinjaman_koreksi(id):
    """
    Koreksi Suku Margin & Nilai Pinjaman bila ada salah hitung setelah disetujui.
    HANYA DAPAT DIAKSES OLEH SUPERADMIN.
    """
    plafon_pokok = float(request.form.get('plafon_pokok', 0))
    tenor_bulan = max(1, int(request.form.get('tenor_bulan', 1)))
    margin_per_bulan = float(request.form.get('margin_per_bulan', 0.0))
    margin_persen = float(request.form.get('margin_persen', 0.0))
    margin_nominal = float(request.form.get('margin_nominal', 0.0))
    alasan_koreksi = request.form.get('alasan_koreksi', '').strip()

    if margin_persen <= 0 and margin_per_bulan > 0:
        margin_persen = round(margin_per_bulan * tenor_bulan, 2)
    if margin_nominal <= 0 and margin_persen > 0:
        margin_nominal = round((plafon_pokok * margin_persen) / 100.0, 2)

    data_koreksi = {
        'plafon_pokok': plafon_pokok,
        'tenor_bulan': tenor_bulan,
        'margin_persen': margin_persen,
        'margin_nominal': margin_nominal,
        'alasan_koreksi': alasan_koreksi
    }

    user = get_current_user()
    success, msg = models.koreksi_pinjaman_margin(id, data_koreksi, user_id=user['id'])
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    next_url = request.form.get('next_url') or url_for('admin_pinjaman_detail', id=id)
    return redirect(next_url)

@app.route('/admin/pinjaman/<int:id>/batalkan', methods=['POST'])
@superadmin_required
def superadmin_pinjaman_batalkan(id):
    """
    Batalkan Persetujuan Pinjaman yang salah terbentuk bila belum ada cicilan berjalan.
    HANYA DAPAT DIAKSES OLEH SUPERADMIN.
    """
    alasan_batal = request.form.get('alasan_batal', '').strip()
    kembalikan_ke_menunggu = request.form.get('kembalikan_ke_menunggu', '1') == '1'
    user = get_current_user()

    success, msg = models.batalkan_persetujuan_pinjaman(id, alasan_batal, kembalikan_ke_menunggu=kembalikan_ke_menunggu, user_id=user['id'])
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    next_url = request.form.get('next_url') or url_for('admin_dashboard')
    return redirect(next_url)

@app.route('/admin/pengajuan/<int:id>/batalkan', methods=['POST'])
@superadmin_required
def superadmin_pengajuan_batalkan(id):
    """
    Batalkan Pengajuan Online yang telah disetujui (PINJAMAN / PENARIKAN_SIMPANAN).
    HANYA DAPAT DIAKSES OLEH SUPERADMIN.
    """
    alasan_batal = request.form.get('alasan_batal', '').strip()
    kembalikan_ke_menunggu = request.form.get('kembalikan_ke_menunggu', '1') == '1'
    user = get_current_user()

    success, msg = models.batalkan_pengajuan_online(id, alasan_batal, kembalikan_ke_menunggu=kembalikan_ke_menunggu, user_id=user['id'])
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    next_url = request.form.get('next_url') or url_for('admin_dashboard')
    return redirect(next_url)

# ----------------- PORTAL ANGGOTA ROUTES -----------------
@app.route('/anggota/dashboard')
@login_required
def anggota_dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    user_id = user['id']
    simpanan_history = models.get_transaksi_simpanan_by_anggota(user_id)[:5]
    loans = models.get_pinjaman_by_anggota(user_id)
    monthly_rekap = models.get_rekap_bulanan_anggota(user_id)[:3]
    tab_status = models.get_status_tabungan_khusus_anggota(user_id)

    # Hitung estimasi bagian SHU untuk anggota ini
    shu_data = models.hitung_shu_koperasi()
    my_shu = next((r for r in shu_data['rincian_anggota'] if r['anggota_id'] == user_id), None)

    return render_template(
        'anggota/dashboard.html',
        member=user,
        simpanan_history=simpanan_history,
        loans=loans,
        monthly_rekap=monthly_rekap,
        my_shu=my_shu,
        tab_status=tab_status
    )

@app.route('/anggota/simpanan')
@login_required
def anggota_simpanan():
    user = get_current_user()
    jenis = request.args.get('jenis', 'Semua')
    history = models.get_transaksi_simpanan_by_anggota(user['id'], jenis_filter=jenis)
    tab_status = models.get_status_tabungan_khusus_anggota(user['id'])
    return render_template('anggota/simpanan.html', member=user, history=history, current_jenis=jenis, tab_status=tab_status)

@app.route('/anggota/komitmen-tabungan', methods=['GET', 'POST'])
@login_required
def anggota_komitmen_tabungan():
    user = get_current_user()
    if request.method == 'POST':
        data = dict(request.form)
        data['anggota_id'] = user['id']
        success, message = models.daftar_komitmen_tabungan_baru(data, created_by=f"Anggota ({user['nama']})")
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
        return redirect(url_for('anggota_komitmen_tabungan'))

    tab_status = models.get_status_tabungan_khusus_anggota(user['id'])
    return render_template('anggota/komitmen_tabungan.html', member=user, tab_status=tab_status)

@app.route('/anggota/pinjaman')
@login_required
def anggota_pinjaman():
    user = get_current_user()
    status = request.args.get('status', 'Semua')
    loans = models.get_pinjaman_by_anggota(user['id'], status_filter=status)
    return render_template('anggota/pinjaman.html', member=user, loans=loans, current_status=status)

@app.route('/anggota/rekap-bulanan')
@login_required
def anggota_rekap_bulanan():
    user = get_current_user()
    history = models.get_rekap_bulanan_anggota(user['id'])
    return render_template('anggota/rekap_bulanan.html', member=user, history=history)

@app.route('/anggota/pengajuan', methods=['GET', 'POST'])
@login_required
def anggota_pengajuan():
    user = get_current_user()
    if request.method == 'POST':
        jenis = request.form.get('jenis') # 'PINJAMAN' / 'PENARIKAN_SIMPANAN'
        kategori = request.form.get('kategori_simp') if jenis == 'PENARIKAN_SIMPANAN' else request.form.get('kategori')
        nominal = float(request.form.get('nominal', 0))
        tenor = int(request.form.get('tenor_bulan', 1))
        alasan = request.form.get('alasan', '')

        # Validasi batas pinjaman sesuai aturan KOSITAS 2026
        if jenis == 'PINJAMAN':
            sumber_potongan = request.form.get('sumber_potongan', 'Potong Gaji')
            alasan = f"{alasan} [Sumber Pemotongan: {sumber_potongan}]"
            if kategori == 'JAPAN' and nominal > 30000000:
                flash('Plafon Pinjaman Jangka Panjang (JAPAN) maksimal Rp 30.000.000,-', 'danger')
                return redirect(url_for('anggota_pengajuan'))
            elif kategori == 'JAPEN' and (nominal > 7000000 or tenor > 10):
                flash('Pinjaman Jangka Pendek (JAPEN) maksimal Rp 7.000.000,- dan tenor 10 bulan', 'danger')
                return redirect(url_for('anggota_pengajuan'))
            elif kategori == 'Bon Putih' and nominal > 1000000:
                flash('Pinjaman Bon Putih Kas maksimal Rp 1.000.000,-', 'danger')
                return redirect(url_for('anggota_pengajuan'))
            elif kategori == 'Barang' and nominal > 7500000:
                flash('Pinjaman Barang maksimal Rp 7.500.000,-', 'danger')
                return redirect(url_for('anggota_pengajuan'))

        # Validasi saldo & alasan jika penarikan simpanan
        if jenis == 'PENARIKAN_SIMPANAN':
            bal = models.get_anggota_balance(user['id'])
            s_map = {
                'Lebaran': bal['simpanan_lebaran'],
                'Qurban': bal['simpanan_qurban'],
                'Manasuka': bal['simpanan_manasuka'],
                'Pokok': bal['simpanan_pokok'],
                'Wajib': bal['simpanan_wajib'],
                'Pokok_Wajib': bal['simpanan_pokok'] + bal['simpanan_wajib']
            }

            # ATURAN KOSITAS: Pokok & Wajib terkunci kecuali Pensiun, Meninggal Dunia, atau Pindah Kantor
            if kategori in ['Pokok_Wajib', 'Pokok', 'Wajib']:
                alasan_khusus = request.form.get('alasan_khusus', '')
                alasan_gabung = f"{alasan_khusus} {alasan}".lower()
                valid_reasons = ['pensiun', 'meninggal', 'pindah kantor', 'mutasi']
                if not any(vr in alasan_gabung for vr in valid_reasons):
                    flash('Simpanan Pokok & Wajib TERKUNCI dan TIDAK DAPAT ditarik! Sesuai ketentuan KOSITAS, pencairan hanya diizinkan apabila berhenti karena alasan Pensiun, Meninggal Dunia, atau Pindah Kantor/Mutasi.', 'danger')
                    return redirect(url_for('anggota_pengajuan'))
                if alasan_khusus:
                    alasan = f"[BERHENTI: {alasan_khusus.upper()}] {alasan}"

            saldo_tersedia = s_map.get(kategori, 0)
            if nominal > saldo_tersedia:
                flash(f'Saldo {kategori} Anda tidak mencukupi untuk ditarik sebesar {nominal:,.0f}! Saldo tersedia: Rp {saldo_tersedia:,.0f}', 'danger')
                return redirect(url_for('anggota_pengajuan'))

        no_pengajuan = models.generate_code('REQ')
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO pengajuan_online (no_pengajuan, anggota_id, jenis, kategori, nominal, tenor_bulan, alasan)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (no_pengajuan, user['id'], jenis, kategori, nominal, tenor, alasan))
        conn.commit()
        conn.close()

        flash(f'Pengajuan #{no_pengajuan} berhasil dikirim ke pengurus KOSITAS.', 'success')
        return redirect(url_for('anggota_pengajuan'))

    # Ambil riwayat pengajuan anggota ini
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM pengajuan_online
    WHERE anggota_id = ?
    ORDER BY tanggal_pengajuan DESC
    ''', (user['id'],))
    my_requests = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return render_template('anggota/pengajuan.html', member=user, requests=my_requests)

# --- ESTIMASI PENERIMAAN SHU ANGGOTA (BULAN & TAHUN BERJALAN) ---
@app.route('/anggota/shu')
@login_required
def anggota_shu():
    user = get_current_user()
    now = datetime.now()
    tahun = request.args.get('tahun', type=int) or now.year
    bulan = request.args.get('bulan', type=int) or now.month
    mode = request.args.get('mode', 'berjalan')  # 'berjalan' (s/d bulan berjalan) atau 'tahunan' (1 tahun penuh)
    
    total_shu_input = request.args.get('total_shu', type=float)
    if total_shu_input and total_shu_input > 0:
        shu_est = models.hitung_estimasi_shu_anggota(user['id'], tahun=tahun, bulan_ke=bulan, total_shu_bruto=total_shu_input)
    else:
        shu_est = models.hitung_estimasi_shu_anggota(user['id'], tahun=tahun, bulan_ke=bulan)

    daftar_tahun = models.get_daftar_tahun_dana_shu()
    return render_template(
        'anggota/shu.html',
        member=user,
        shu=shu_est,
        current_tahun=tahun,
        current_bulan=bulan,
        current_mode=mode,
        daftar_tahun=daftar_tahun
    )

# ----------------- PRINT SLIP & KUITANSI RESMI -----------------
@app.route('/cetak/slip-bulanan/<int:anggota_id>/<bulan_buku>')
@login_required
def cetak_slip_bulanan(anggota_id, bulan_buku):
    user = get_current_user()
    # Anggota hanya bisa cetak slip miliknya sendiri kecuali admin & superadmin
    if user['role'] not in ['admin', 'superadmin'] and user['id'] != anggota_id:
        abort(403)

    target_member = models.get_anggota_by_id(anggota_id)
    if not target_member:
        abort(404)

    # Ambil rincian mutasi simpanan dan pinjaman anggota di bulan tersebut
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM transaksi_simpanan
    WHERE anggota_id = ? AND bulan_buku = ?
    ''', (anggota_id, bulan_buku))
    simpanan_list = [dict(r) for r in cursor.fetchall()]

    cursor.execute('''
    SELECT a.*, p.jenis_pinjaman, p.no_pinjaman, p.plafon_pokok
    FROM angsuran_pinjaman a
    JOIN pinjaman p ON a.pinjaman_id = p.id
    WHERE a.anggota_id = ? AND a.bulan_buku = ?
    ''', (anggota_id, bulan_buku))
    angsuran_list = [dict(r) for r in cursor.fetchall()]

    # Cek apakah ada pinjaman yang dilunasi dipercepat atau topup pada bulan ini
    cursor.execute('''
    SELECT * FROM pinjaman 
    WHERE anggota_id = ? AND strftime('%Y-%m', tanggal_lunas) = ?
    ''', (anggota_id, bulan_buku))
    settled_in_month = [dict(r) for r in cursor.fetchall()]

    conn.close()

    total_simpanan = sum(s['nominal'] for s in simpanan_list if s['tipe'] == 'SETOR')
    total_angsuran = sum(a['total_bayar'] for a in angsuran_list)
    grand_total = total_simpanan + total_angsuran

    return render_template(
        'print/slip_bulanan.html',
        member=target_member,
        bulan_buku=bulan_buku,
        simpanan_list=simpanan_list,
        angsuran_list=angsuran_list,
        settled_in_month=settled_in_month,
        total_simpanan=total_simpanan,
        total_angsuran=total_angsuran,
        grand_total=grand_total
    )

@app.route('/cetak/kuitansi-simpanan/<int:id>')
@login_required
def cetak_kuitansi_simpanan(id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT t.*, a.nama as nama_anggota, a.no_anggota, a.nip, a.jabatan
    FROM transaksi_simpanan t
    JOIN anggota a ON t.anggota_id = a.id
    WHERE t.id = ?
    ''', (id,))
    trx = cursor.fetchone()
    conn.close()
    if not trx:
        abort(404)

    trx = dict(trx)
    user = get_current_user()
    if user['role'] not in ['admin', 'superadmin'] and user['id'] != trx['anggota_id']:
        abort(403)

    return render_template('print/kuitansi_simpanan.html', trx=trx)

@app.route('/cetak/kuitansi-angsuran/<int:id>')
@login_required
def cetak_kuitansi_angsuran(id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT a.*, p.jenis_pinjaman, p.no_pinjaman, agt.nama as nama_anggota, agt.no_anggota, agt.nip
    FROM angsuran_pinjaman a
    JOIN pinjaman p ON a.pinjaman_id = p.id
    JOIN anggota agt ON a.anggota_id = agt.id
    WHERE a.id = ?
    ''', (id,))
    ang = cursor.fetchone()
    conn.close()
    if not ang:
        abort(404)

    ang = dict(ang)
    user = get_current_user()
    if user['role'] not in ['admin', 'superadmin'] and user['id'] != ang['anggota_id']:
        abort(403)

    return render_template('print/kuitansi_angsuran.html', angsuran=ang)

@app.route('/cetak/slip-tabungan/<int:anggota_id>/<bulan_buku>')
@login_required
def cetak_slip_tabungan(anggota_id, bulan_buku):
    user = get_current_user()
    if user['role'] not in ['admin', 'superadmin'] and user['id'] != anggota_id:
        abort(403)

    target_member = models.get_anggota_by_id(anggota_id)
    if not target_member:
        abort(404)

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM transaksi_simpanan
    WHERE anggota_id = ? AND bulan_buku = ?
    ORDER BY tanggal ASC
    ''', (anggota_id, bulan_buku))
    trx_list = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_setor = sum(t['nominal'] for t in trx_list if t['tipe'] == 'SETOR')
    total_tarik = sum(t['nominal'] for t in trx_list if t['tipe'] == 'TARIK')

    return render_template(
        'print/slip_tabungan.html',
        member=target_member,
        bulan_buku=bulan_buku,
        trx_list=trx_list,
        total_setor=total_setor,
        total_tarik=total_tarik,
        net_setor=(total_setor - total_tarik)
    )

@app.route('/cetak/slip-pelunasan/<int:id>')
@login_required
def cetak_slip_pelunasan(id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota, a.nip, a.jabatan
    FROM pinjaman p
    JOIN anggota a ON p.anggota_id = a.id
    WHERE p.id = ?
    ''', (id,))
    loan = cursor.fetchone()
    conn.close()
    if not loan:
        abort(404)

    loan = dict(loan)
    user = get_current_user()
    if user['role'] not in ['admin', 'superadmin'] and user['id'] != loan['anggota_id']:
        abort(403)

    return render_template('print/slip_pelunasan.html', loan=loan)

@app.route('/cetak/slip-topup/<int:id>')
@login_required
def cetak_slip_topup(id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT p.*, a.nama as nama_anggota, a.no_anggota, a.nip, a.jabatan,
           pl.no_pinjaman as no_pinjaman_lama, pl.sisa_pokok_dilunasi
    FROM pinjaman p
    JOIN anggota a ON p.anggota_id = a.id
    LEFT JOIN pinjaman pl ON p.ref_pinjaman_lama_id = pl.id
    WHERE p.id = ?
    ''', (id,))
    loan = cursor.fetchone()
    conn.close()
    if not loan:
        abort(404)

    loan = dict(loan)
    user = get_current_user()
    if user['role'] not in ['admin', 'superadmin'] and user['id'] != loan['anggota_id']:
        abort(403)

    # Dana Bersih Diterima = Plafon Baru - Sisa Pokok Lama - Provisi - DRK
    sisa_lama = float(loan.get('sisa_pokok_dilunasi') or 0.0)
    provisi = float(loan.get('biaya_provisi') or 0.0)
    drk = float(loan.get('biaya_drk') or 0.0)
    dana_bersih = float(loan['plafon_pokok']) - sisa_lama - provisi - drk

    return render_template(
        'print/slip_topup.html',
        loan=loan,
        sisa_lama=sisa_lama,
        dana_bersih=dana_bersih
    )

@app.route('/cetak/slip-pembagian-tabungan/<int:id>')
@login_required
def cetak_slip_pembagian_tabungan(id):
    komitmen = models.get_komitmen_by_id(id)
    if not komitmen:
        abort(404)
    user = get_current_user()
    if user['role'] not in ['admin', 'superadmin'] and user['id'] != komitmen['anggota_id']:
        abort(403)
    return render_template('print/slip_pembagian_tabungan.html', komitmen=komitmen)

@app.route('/cetak/form-shu/<int:anggota_id>')
@login_required
def cetak_form_shu(anggota_id):
    user = get_current_user()
    if user['role'] not in ['admin', 'superadmin'] and user['id'] != anggota_id:
        abort(403)

    now = datetime.now()
    tahun = request.args.get('tahun', type=int) or now.year
    bulan = request.args.get('bulan', type=int) or now.month
    mode = request.args.get('mode', 'berjalan')
    total_shu_input = request.args.get('total_shu', type=float)

    if total_shu_input and total_shu_input > 0:
        shu_est = models.hitung_estimasi_shu_anggota(anggota_id, tahun=tahun, bulan_ke=bulan, total_shu_bruto=total_shu_input)
    else:
        shu_est = models.hitung_estimasi_shu_anggota(anggota_id, tahun=tahun, bulan_ke=bulan)

    if not shu_est:
        abort(404)

    return render_template(
        'print/form_penerimaan_shu.html',
        shu=shu_est,
        mode=mode,
        tahun=tahun,
        bulan=bulan
    )

# ----------------- AJAX API ENDPOINTS -----------------
@app.route('/api/anggota-info/<int:id>')
@login_required
def api_anggota_info(id):
    member = models.get_anggota_by_id(id)
    if not member:
        return jsonify({'error': 'Anggota tidak ditemukan'}), 404
    return jsonify(member)

@app.route('/api/simulasi-pinjaman', methods=['POST'])
def api_simulasi_pinjaman():
    data = request.json or {}
    try:
        plafon = float(data.get('plafon', 0))
        tenor = int(data.get('tenor', 10))
        jenis = data.get('jenis', 'JAPEN')

        if jenis == 'JAPAN':
            margin_p = 25.0
            provisi = plafon * 0.01
            drk = plafon * 0.005
        elif jenis == 'JAPEN':
            margin_p = 10.0
            provisi = plafon * 0.01
            drk = 0.0
        elif jenis == 'Bon Putih':
            margin_p = 2.0 * tenor
            provisi = 0.0
            drk = 0.0
        else: # Barang
            margin_p = 20.0
            provisi = 0.0
            drk = 0.0

        margin_nominal = (plafon * margin_p) / 100.0
        total_pinjaman = plafon + margin_nominal
        angsuran_pokok = round(plafon / tenor, 2)
        angsuran_margin = round(margin_nominal / tenor, 2)
        total_angsuran = angsuran_pokok + angsuran_margin
        dana_cair = plafon - provisi - drk

        return jsonify({
            'plafon': plafon,
            'tenor': tenor,
            'margin_persen': margin_p,
            'margin_nominal': margin_nominal,
            'total_pinjaman': total_pinjaman,
            'angsuran_pokok': angsuran_pokok,
            'angsuran_margin': angsuran_margin,
            'total_angsuran': total_angsuran,
            'provisi': provisi,
            'drk': drk,
            'dana_cair': dana_cair
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    # Initialize DB if not present
    database.init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
