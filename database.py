import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'kositas.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Table Anggota
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS anggota (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        no_anggota TEXT UNIQUE NOT NULL,
        nama TEXT NOT NULL,
        nip TEXT,
        jabatan TEXT DEFAULT 'Anggota',
        jenis_kelamin TEXT DEFAULT 'Pria',
        no_hp TEXT,
        email TEXT,
        alamat TEXT,
        tanggal_masuk DATE DEFAULT (CURRENT_DATE),
        tanggal_keluar DATE,
        status TEXT DEFAULT 'Aktif',
        password TEXT DEFAULT '123456',
        role TEXT DEFAULT 'anggota',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Table Transaksi Simpanan
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transaksi_simpanan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        no_transaksi TEXT UNIQUE NOT NULL,
        anggota_id INTEGER NOT NULL,
        tanggal DATE NOT NULL,
        jenis_simpanan TEXT NOT NULL, -- 'Pokok', 'Wajib', 'Lebaran', 'Qurban', 'Manasuka'
        tipe TEXT NOT NULL, -- 'SETOR', 'TARIK'
        nominal REAL NOT NULL,
        keterangan TEXT,
        metode_bayar TEXT DEFAULT 'Potong Gaji', -- 'Potong Gaji', 'Tunai', 'Transfer'
        bulan_buku TEXT, -- 'YYYY-MM'
        created_by TEXT DEFAULT 'Admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (anggota_id) REFERENCES anggota (id) ON DELETE CASCADE
    )
    ''')

    # Table Pinjaman
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pinjaman (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        no_pinjaman TEXT UNIQUE NOT NULL,
        anggota_id INTEGER NOT NULL,
        jenis_pinjaman TEXT NOT NULL, -- 'JAPAN', 'JAPEN', 'Bon Putih', 'Barang'
        tanggal_pengajuan DATE NOT NULL,
        tanggal_cair DATE,
        plafon_pokok REAL NOT NULL,
        margin_persen REAL DEFAULT 0.0,
        margin_nominal REAL DEFAULT 0.0,
        total_pinjaman REAL NOT NULL,
        tenor_bulan INTEGER NOT NULL,
        angsuran_pokok_bulanan REAL NOT NULL,
        angsuran_margin_bulanan REAL NOT NULL,
        total_angsuran_bulanan REAL NOT NULL,
        biaya_provisi REAL DEFAULT 0.0, -- 1%
        biaya_drk REAL DEFAULT 0.0, -- 0.5% khusus JAPAN
        saldo_pokok REAL NOT NULL,
        saldo_margin REAL NOT NULL,
        angsuran_ke INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Aktif', -- 'Menunggu', 'Aktif', 'Lunas', 'Ditolak'
        keperluan TEXT,
        keterangan TEXT,
        is_topup INTEGER DEFAULT 0,
        ref_pinjaman_lama_id INTEGER,
        pelunasan_tipe TEXT DEFAULT 'Normal', -- 'Normal', 'Pelunasan Dipercepat', 'Top Up'
        tanggal_lunas DATE,
        sisa_pokok_dilunasi REAL DEFAULT 0.0,
        diskon_margin REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (anggota_id) REFERENCES anggota (id) ON DELETE CASCADE
    )
    ''')

    # Table Angsuran Pinjaman
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS angsuran_pinjaman (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        no_angsuran TEXT UNIQUE NOT NULL,
        pinjaman_id INTEGER NOT NULL,
        anggota_id INTEGER NOT NULL,
        tanggal_bayar DATE NOT NULL,
        angsuran_ke INTEGER NOT NULL,
        angsuran_pokok REAL NOT NULL,
        angsuran_margin REAL NOT NULL,
        total_bayar REAL NOT NULL,
        sisa_pokok_setelah REAL NOT NULL,
        bulan_buku TEXT, -- 'YYYY-MM'
        metode_bayar TEXT DEFAULT 'Potong Gaji',
        keterangan TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (pinjaman_id) REFERENCES pinjaman (id) ON DELETE CASCADE,
        FOREIGN KEY (anggota_id) REFERENCES anggota (id) ON DELETE CASCADE
    )
    ''')

    # Table Pengajuan Anggota Online (Self-service portal)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pengajuan_online (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        no_pengajuan TEXT UNIQUE NOT NULL,
        anggota_id INTEGER NOT NULL,
        jenis TEXT NOT NULL, -- 'PINJAMAN', 'PENARIKAN_SIMPANAN', 'SETORAN_SIMPANAN'
        kategori TEXT NOT NULL, -- 'JAPAN', 'JAPEN', 'Bon Putih', 'Barang', 'Lebaran', 'Qurban', 'Manasuka'
        nominal REAL NOT NULL,
        tenor_bulan INTEGER DEFAULT 1,
        tanggal_pengajuan DATE DEFAULT (CURRENT_DATE),
        alasan TEXT,
        status TEXT DEFAULT 'Menunggu', -- 'Menunggu', 'Disetujui', 'Ditolak'
        catatan_admin TEXT,
        tanggal_diproses DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (anggota_id) REFERENCES anggota (id) ON DELETE CASCADE
    )
    ''')

    # Table Rekap Tagihan Bulanan / Log Potong Gaji
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS billing_bulanan_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bulan_buku TEXT UNIQUE NOT NULL, -- 'YYYY-MM'
        tanggal_proses DATE NOT NULL,
        total_anggota INTEGER NOT NULL,
        total_simpanan REAL NOT NULL,
        total_angsuran_pokok REAL NOT NULL,
        total_angsuran_margin REAL NOT NULL,
        total_keseluruhan REAL NOT NULL,
        status TEXT DEFAULT 'Selesai',
        created_by TEXT DEFAULT 'Admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Table Komitmen Tabungan Khusus (Lebaran & Qurban Periode Baru Pasca Pembagian)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS komitmen_tabungan_khusus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anggota_id INTEGER NOT NULL,
        jenis_tabungan TEXT NOT NULL, -- 'Lebaran', 'Qurban'
        tahun_periode INTEGER NOT NULL, -- misal 2026, 2027
        nominal_per_bulan REAL NOT NULL, -- komitmen tabungan per bulan
        setoran_awal REAL DEFAULT 0.0,
        metode_setor TEXT DEFAULT 'Potong Gaji', -- 'Potong Gaji', 'Tunai', 'Transfer'
        status TEXT DEFAULT 'Aktif', -- 'Aktif', 'Selesai Dibagikan', 'Nonaktif'
        tanggal_daftar DATE DEFAULT (CURRENT_DATE),
        tanggal_dibagikan DATE,
        total_dibagikan REAL DEFAULT 0.0,
        keterangan TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (anggota_id) REFERENCES anggota (id) ON DELETE CASCADE
    )
    ''')

    # Table Alokasi Dana-Dana SHU (Konfigurasi Fleksibel per Tahun Buku Hasil RAT)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS alokasi_dana_shu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tahun INTEGER NOT NULL,
        nama_dana TEXT NOT NULL,
        persentase REAL NOT NULL,
        kategori TEXT DEFAULT 'DANA', -- 'DANA' (Dana Lembaga/Pengurus) atau 'ANGGOTA' (Bagian Anggota)
        is_bagian_anggota INTEGER DEFAULT 0, -- 1 jika ini porsi untuk anggota (Jasa Modal & Pinjaman)
        porsi_jasa_modal REAL DEFAULT 50.0,
        porsi_jasa_pinjaman REAL DEFAULT 50.0,
        keterangan TEXT,
        warna_badge TEXT DEFAULT 'slate',
        urutan INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Seed alokasi dana SHU default jika kosong
    cursor.execute("SELECT COUNT(*) FROM alokasi_dana_shu")
    if cursor.fetchone()[0] == 0:
        default_funds_template = [
            ("Dana Pendidikan", 2.0, "DANA", 0, 0.0, 0.0, "Pendidikan & pelatihan perkoperasian anggota dan pengurus", "cyan", 1),
            ("Dana Rekreasi", 8.0, "DANA", 0, 0.0, 0.0, "Kegiatan rekreasi dan family gathering koperasi", "emerald", 2),
            ("Dana Sosial", 6.0, "DANA", 0, 0.0, 0.0, "Bantuan sosial, santunan duka, dan kemasyarakatan", "rose", 3),
            ("Dana Cadangan", 6.0, "DANA", 0, 0.0, 0.0, "Pemupukan modal sendiri dan cadangan risiko koperasi", "amber", 4),
            ("Dana Risiko Kredit", 3.0, "DANA", 0, 0.0, 0.0, "Cadangan antisipasi risiko kredit macet pembiayaan", "orange", 5),
            ("Dana Pensiun", 3.0, "DANA", 0, 0.0, 0.0, "Santunan dan jaminan masa purnatugas anggota", "blue", 6),
            ("Insentif Pengurus & Pengawas", 32.0, "DANA", 0, 0.0, 0.0, "Jasa kinerja pengelolaan pengurus dan badan pengawas", "purple", 7),
            ("SHU Bagian Anggota", 40.0, "ANGGOTA", 1, 50.0, 50.0, "Dibagikan ke anggota (50% Jasa Modal & 50% Jasa Pinjaman)", "indigo", 8)
        ]
        for th in [2025, 2026]:
            for nama, persen, kat, is_agt, p_modal, p_pinj, ket, warna, urut in default_funds_template:
                cursor.execute('''
                INSERT INTO alokasi_dana_shu 
                (tahun, nama_dana, persentase, kategori, is_bagian_anggota, porsi_jasa_modal, porsi_jasa_pinjaman, keterangan, warna_badge, urutan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (th, nama, persen, kat, is_agt, p_modal, p_pinj, ket, warna, urut))

    # Migration role: set superadmin for ketua & sysadmin
    cursor.execute("UPDATE anggota SET role = 'superadmin' WHERE no_anggota = 'ADM-001' OR no_anggota = 'KST-007'")
    cursor.execute("UPDATE anggota SET role = 'admin' WHERE (no_anggota = 'KST-002' OR no_anggota = 'KST-019') AND role != 'superadmin'")

    # Table Pengaturan Koperasi
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pengaturan (
        kunci TEXT PRIMARY KEY,
        nilai TEXT NOT NULL,
        deskripsi TEXT
    )
    ''')

    # Initial settings
    pengaturan_default = [
        ('nama_koperasi', 'KOSITAS - Koperasi Statistik Tasikmalaya', 'Nama resmi lembaga'),
        ('institusi_induk', 'BPS Kabupaten Tasikmalaya', 'Instansi Pembina'),
        ('alamat', 'Jl. Raya Timur Singaparna KM. 4 Cintaraja - Tasikmalaya', 'Alamat kantor'),
        ('simpanan_pokok', '25000', 'Nominal simpanan pokok'),
        ('simpanan_wajib', '100000', 'Nominal simpanan wajib bulanan'),
        ('provisi_persen', '1.0', 'Biaya provisi kredit (%)'),
        ('drk_persen', '0.5', 'Dana Resiko Kredit pinjaman jangka panjang (%)'),
        ('shu_persen_anggota', '40.0', 'Persentase SHU dibagikan ke anggota (%)'),
        ('shu_persen_jasa_modal', '50.0', 'Porsi Jasa Modal dari SHU Anggota (%)'),
        ('shu_persen_jasa_pinjaman', '50.0', 'Porsi Jasa Pinjaman dari SHU Anggota (%)')
    ]

    for kunci, nilai, deskripsi in pengaturan_default:
        cursor.execute('''
        INSERT OR IGNORE INTO pengaturan (kunci, nilai, deskripsi)
        VALUES (?, ?, ?)
        ''', (kunci, nilai, deskripsi))

    # Migration for existing tables: ensure columns exist in pinjaman
    cursor.execute("PRAGMA table_info(pinjaman)")
    cols = [r[1] for r in cursor.fetchall()]
    new_cols = [
        ('is_topup', 'INTEGER DEFAULT 0'),
        ('ref_pinjaman_lama_id', 'INTEGER'),
        ('pelunasan_tipe', "TEXT DEFAULT 'Normal'"),
        ('tanggal_lunas', 'DATE'),
        ('sisa_pokok_dilunasi', 'REAL DEFAULT 0.0'),
        ('diskon_margin', 'REAL DEFAULT 0.0'),
        ('pengajuan_id', 'INTEGER')
    ]
    for col_name, col_type in new_cols:
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE pinjaman ADD COLUMN {col_name} {col_type}")

    # Migration for pengajuan_online: ensure pinjaman_id exists
    cursor.execute("PRAGMA table_info(pengajuan_online)")
    p_cols = [r[1] for r in cursor.fetchall()]
    if 'pinjaman_id' not in p_cols:
        cursor.execute("ALTER TABLE pengajuan_online ADD COLUMN pinjaman_id INTEGER")

    # Link existing approved online loan requests with loans
    cursor.execute('''
    UPDATE pengajuan_online 
    SET pinjaman_id = (
        SELECT id FROM pinjaman 
        WHERE keterangan LIKE '%' || pengajuan_online.no_pengajuan || '%' 
        ORDER BY id DESC LIMIT 1
    )
    WHERE pinjaman_id IS NULL AND jenis = 'PINJAMAN' AND status = 'Disetujui'
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database KOSITAS initialized successfully.")
