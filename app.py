from flask import Flask, render_template, redirect, url_for, request, jsonify
import json
import pathlib
import os
import subprocess
import sys
import datetime
import concurrent.futures
import time

app = Flask(__name__)

ROOT = pathlib.Path(__file__).parent.parent
EMAREAPI = ROOT / 'emareapi'
PROJECTS_JSON = ROOT / 'projects.json'
DERVISLER = EMAREAPI / 'Dervisler'
DERGAH = EMAREAPI / 'Dergah'
CEYIZ_SCRIPT    = ROOT / 'emarework' / 'ceyiz_hazirla.py'
API_KESFET      = ROOT / 'emareapi' / 'api_kesfet.py'
API_REGISTRY    = ROOT / 'emareapi' / 'api_registry.json'

SABLONLAR = {
    'fastapi':   {'label': 'FastAPI Backend',        'icon': '⚡', 'color': '#10b981', 'aciklama': 'FastAPI + SQLAlchemy backend API'},
    'flask':     {'label': 'Flask Web Uygulaması',   'icon': '🌶️', 'color': '#0ea5e9', 'aciklama': 'Flask web uygulaması'},
    'react':     {'label': 'React / Next.js',        'icon': '⚛️', 'color': '#6366f1', 'aciklama': 'React + Next.js frontend'},
    'cli':       {'label': 'CLI Aracı',              'icon': '🖥️', 'color': '#f59e0b', 'aciklama': 'Python CLI aracı'},
    'fullstack': {'label': 'Fullstack (API+React)',  'icon': '🚀', 'color': '#8b5cf6', 'aciklama': 'FastAPI + React tam yığın'},
    'library':   {'label': 'Python Kütüphanesi',     'icon': '📦', 'color': '#ec4899', 'aciklama': 'Yeniden kullanılabilir Python kütüphanesi'},
    'bos':       {'label': 'Boş İskelet',            'icon': '🗂️', 'color': '#64748b', 'aciklama': 'Sadece temel iskelet'},
}

KATEGORILER = [
    'SaaS Platform', 'Altyapı', 'Finans', 'E-ticaret', 'İletişim',
    'Güvenlik', 'Analiz', 'İçerik', 'Otomasyon', 'Mobil', 'Diğer'
]


def load_projects():
    with open(PROJECTS_JSON, encoding='utf-8') as f:
        return json.load(f)


def load_dervish_folders():
    if not DERVISLER.exists():
        return {}
    return {p.name: p for p in DERVISLER.iterdir() if p.is_dir()}


def load_dergah_links():
    if not DERGAH.exists():
        return {}
    return {p.name: p for p in DERGAH.iterdir() if p.is_symlink()}


def find_missing_dervish(projects, dervish_folders):
    missing = []
    for p in projects:
        owner = pathlib.Path(p['path']).name
        if f'{owner} Dervishi' not in dervish_folders:
            missing.append(owner)
    return missing


def get_folder_stats(path):
    """Klasördeki dosya/alt-klasör sayısını döndürür (sadece 1. seviye, hızlı)"""
    p = pathlib.Path(path)
    if not p.exists():
        return {'files': 0, 'dirs': 0, 'exists': False}
    skip = {'.git', '.venv', '__pycache__', 'node_modules', '.DS_Store'}
    files = 0
    dirs = 0
    try:
        for entry in p.iterdir():
            if entry.name in skip:
                continue
            if entry.is_file():
                files += 1
            elif entry.is_dir():
                dirs += 1
    except PermissionError:
        pass
    return {'files': files, 'dirs': dirs, 'exists': True}


# ─── DASHBOARD ───
@app.route('/')
def dashboard():
    projects = load_projects()
    dervish_folders = load_dervish_folders()
    dergah_links = load_dergah_links()
    missing_dervish = find_missing_dervish(projects, dervish_folders)

    # Durum sayaçları
    status_counts = {}
    category_counts = {}
    for p in projects:
        s = p.get('status', 'unknown')
        status_counts[s] = status_counts.get(s, 0) + 1
        c = p.get('category', 'Diğer')
        category_counts[c] = category_counts.get(c, 0) + 1

    return render_template('dashboard.html',
                           projects=projects,
                           dervish_folders=dervish_folders,
                           dergah_links=dergah_links,
                           missing_dervish=missing_dervish,
                           status_counts=status_counts,
                           category_counts=category_counts,
                           now=datetime.datetime.now())


# ─── PROJELER ───
@app.route('/projeler')
def projeler():
    projects = load_projects()
    dervish_folders = load_dervish_folders()
    # Her projeye ekstra bilgi ekle
    for p in projects:
        owner = pathlib.Path(p['path']).name
        p['_owner'] = owner
        p['_has_dervish'] = f'{owner} Dervishi' in dervish_folders
        p['_stats'] = get_folder_stats(p['path'])
    return render_template('projeler.html', projects=projects)


# ─── DERVİŞLER ───
@app.route('/dervisler')
def dervisler():
    dervish_folders = load_dervish_folders()
    dervish_list = []
    for name, path in sorted(dervish_folders.items()):
        profil_file = path / 'DERVISH_PROFIL.md'
        shortcut = path / 'PROJE_KISAYOLU'
        target = None
        if shortcut.is_symlink():
            target = str(shortcut.resolve())
        dervish_list.append({
            'name': name,
            'path': str(path),
            'has_profil': profil_file.exists(),
            'has_shortcut': shortcut.is_symlink(),
            'target': target,
        })
    return render_template('dervisler.html', dervisler=dervish_list)


# ─── DERGAH ───
@app.route('/dergah')
def dergah():
    dergah_links = load_dergah_links()
    link_list = []
    for name, path in sorted(dergah_links.items()):
        target = str(path.resolve()) if path.is_symlink() else str(path)
        link_list.append({
            'name': name,
            'target': target,
        })
    return render_template('dergah.html', links=link_list)


# ─── PROJE DETAY ───
@app.route('/proje/<project_id>')
def proje_detay(project_id):
    projects = load_projects()
    project = None
    for p in projects:
        if p.get('id') == project_id:
            project = p
            break
    if not project:
        return "Proje bulunamadı", 404
    project['_stats'] = get_folder_stats(project['path'])
    owner = pathlib.Path(project['path']).name
    project['_owner'] = owner
    dervish_path = DERVISLER / f'{owner} Dervishi'
    project['_has_dervish'] = dervish_path.exists()
    return render_template('proje_detay.html', project=project)


# ─── API: Sağlık kontrolü ───
@app.route('/api/health')
def api_health():
    projects = load_projects()
    dervish_folders = load_dervish_folders()
    dergah_links = load_dergah_links()
    missing = find_missing_dervish(projects, dervish_folders)
    return jsonify({
        'status': 'ok',
        'projects': len(projects),
        'dervish_folders': len(dervish_folders),
        'dergah_links': len(dergah_links),
        'missing_dervish': missing,
    })


# ─── API: Eksik dervişleri oluştur ───
@app.route('/api/fix-dervish', methods=['POST'])
def fix_dervish():
    projects = load_projects()
    dervish_folders = load_dervish_folders()
    created = []
    for p in projects:
        owner = pathlib.Path(p['path']).name
        dname = f'{owner} Dervishi'
        d = DERVISLER / dname
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            (d / 'DERVISH_PROFIL.md').write_text(
                f'# {dname}\n\n- Sorumlu: {owner}\n- Yol: {p["path"]}\n', encoding='utf-8')
            link = d / 'PROJE_KISAYOLU'
            if not link.exists():
                link.symlink_to(p['path'])
            dlink = DERGAH / dname
            if not dlink.exists():
                dlink.symlink_to(pathlib.Path('..') / 'Dervisler' / dname)
            created.append(owner)
    return jsonify({'created': created, 'count': len(created)})




# ─── ÇEYİZ ───
@app.route('/ceyiz')
def ceyiz():
    next_port = 8000
    try:
        projects = load_projects()
        used_ports = set()
        for p in projects:
            port = p.get('port')
            if isinstance(port, int):
                used_ports.add(port)
        # İlk boş portu bul 8000'den itibaren
        p = 8000
        while p in used_ports:
            p += 1
        next_port = p
    except Exception:
        pass
    return render_template('ceyiz.html', sablonlar=SABLONLAR, kategoriler=KATEGORILER, next_port=next_port)


@app.route('/api/ceyiz', methods=['POST'])
def api_ceyiz():
    data = request.get_json(silent=True) or {}
    ad = (data.get('ad') or '').strip().lower()
    gorunen_ad = (data.get('gorunen_ad') or '').strip()
    aciklama = (data.get('aciklama') or '').strip()
    sablon = (data.get('sablon') or 'bos').strip()
    kategori = (data.get('kategori') or 'Diğer').strip()
    try:
        port = int(data.get('port') or 8000)
    except (ValueError, TypeError):
        port = 8000

    # Validasyon
    errors = []
    if not ad:
        errors.append('Proje adı boş olamaz.')
    if not gorunen_ad:
        gorunen_ad = ad
    if sablon not in SABLONLAR:
        errors.append(f'Geçersiz şablon: {sablon}')
    if errors:
        return jsonify({'ok': False, 'errors': errors}), 400

    # Çeyiz scriptini subprocess ile çalıştır
    script = f"""
import sys
sys.path.insert(0, r'{str(CEYIZ_SCRIPT.parent)}')
from ceyiz_hazirla import ceyiz_hazirla
bilgi = {{
    'ad': {repr(ad)},
    'gorunen_ad': {repr(gorunen_ad)},
    'aciklama': {repr(aciklama)},
    'sablon': {repr(sablon)},
    'kategori': {repr(kategori)},
    'port': {port},
}}
sonuc = ceyiz_hazirla(bilgi)
import json
print('__RESULT__' + json.dumps(sonuc))
"""
    try:
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True, text=True, timeout=60,
            cwd=str(ROOT)
        )
        output = result.stdout + result.stderr
        # Sonucu parse et
        sonuc_data = {}
        for line in output.splitlines():
            if line.startswith('__RESULT__'):
                try:
                    sonuc_data = json.loads(line[len('__RESULT__'):])
                except Exception:
                    pass
        if result.returncode != 0 and not sonuc_data:
            return jsonify({'ok': False, 'errors': [result.stderr[-2000:] or 'Script hatası.']}), 500
        return jsonify({'ok': True, 'sonuc': sonuc_data, 'log': output[-3000:]})
    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'errors': ['Çeyiz scripti zaman aşımına uğradı.']}), 500
    except Exception as e:
        return jsonify({'ok': False, 'errors': [str(e)]}), 500




# ─── TOPLU ÇALIŞTIR ───
@app.route('/calistir')
def calistir():
    projects = load_projects()
    dervish_list = []
    for p in projects:
        path = pathlib.Path(p['path'])
        dervish_list.append({
            'name': path.name,
            'gorunen_ad': p.get('name', path.name),
            'path': str(path),
            'category': p.get('category', 'Diğer'),
            'status': p.get('status', 'unknown'),
            'exists': path.exists(),
        })
    categories = sorted(set(d['category'] for d in dervish_list))
    on_komutlar = [
        {'label': 'Git Durum',       'komut': 'git status --short'},
        {'label': 'Git Pull',        'komut': 'git pull'},
        {'label': 'Git Log (5)',      'komut': 'git log --oneline -5'},
        {'label': 'Git Branch',      'komut': 'git branch -a'},
        {'label': 'Dosya Listesi',   'komut': 'ls -la'},
        {'label': 'Python Versiyon', 'komut': 'python3 --version'},
        {'label': 'Pip Liste',       'komut': 'pip3 list --format=columns 2>/dev/null | head -20'},
        {'label': 'README Göster',   'komut': 'cat README.md 2>/dev/null | head -30'},
        {'label': 'Requirements',    'komut': 'cat requirements.txt 2>/dev/null || echo "requirements.txt yok"'},
        {'label': 'Disk Kullanımı',  'komut': 'du -sh . 2>/dev/null'},
        {'label': 'Git Remote',      'komut': 'git remote -v 2>/dev/null || echo "git repo yok"'},
        {'label': 'Son Commit',      'komut': 'git log -1 --format="%h %s (%cr)" 2>/dev/null || echo "git repo yok"'},
    ]
    return render_template('calistir.html',
                           dervish_list=dervish_list,
                           categories=categories,
                           on_komutlar=on_komutlar)


@app.route('/api/calistir', methods=['POST'])
def api_calistir():
    data = request.get_json(silent=True) or {}
    komut = (data.get('komut') or '').strip()
    secili = data.get('dervishler', [])
    timeout = min(int(data.get('timeout', 30)), 120)

    if not komut:
        return jsonify({'ok': False, 'error': 'Komut boş olamaz.'}), 400

    projects = load_projects()
    hedefler = []
    for p in projects:
        path = pathlib.Path(p['path'])
        if not path.exists():
            continue
        name = path.name
        if secili and name not in secili:
            continue
        hedefler.append({'name': name, 'path': str(path), 'gorunen_ad': p.get('name', name)})

    if not hedefler:
        return jsonify({'ok': False, 'error': 'Hiç Derviş seçilmedi veya proje klasörü bulunamadı.'}), 400

    def run_one(h):
        t0 = time.time()
        try:
            proc = subprocess.run(
                komut, shell=True, cwd=h['path'],
                capture_output=True, text=True,
                timeout=timeout,
                env={**os.environ, 'TERM': 'dumb'}
            )
            return {
                'name': h['name'],
                'gorunen_ad': h['gorunen_ad'],
                'path': h['path'],
                'stdout': proc.stdout[-4000:],
                'stderr': proc.stderr[-1000:],
                'returncode': proc.returncode,
                'duration': round(time.time() - t0, 2),
                'ok': proc.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {'name': h['name'], 'gorunen_ad': h['gorunen_ad'], 'path': h['path'],
                    'stdout': '', 'stderr': f'Zaman aşımı ({timeout}s)', 'returncode': -1,
                    'duration': round(time.time() - t0, 2), 'ok': False}
        except Exception as e:
            return {'name': h['name'], 'gorunen_ad': h['gorunen_ad'], 'path': h['path'],
                    'stdout': '', 'stderr': str(e), 'returncode': -2,
                    'duration': round(time.time() - t0, 2), 'ok': False}

    max_workers = min(len(hedefler), 12)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(run_one, hedefler))

    ok_count  = sum(1 for r in results if r['ok'])
    err_count = len(results) - ok_count
    return jsonify({
        'ok': True,
        'komut': komut,
        'toplam': len(results),
        'basarili': ok_count,
        'hatali': err_count,
        'results': results,
    })




# ─── API REGISTRY ───
def load_registry():
    if not API_REGISTRY.exists():
        return None
    try:
        return json.loads(API_REGISTRY.read_text(encoding='utf-8'))
    except Exception:
        return None


@app.route('/api-registry')
def api_registry_page():
    registry = load_registry()
    return render_template('api_registry.html', registry=registry)


@app.route('/api/kesfet', methods=['POST'])
def api_kesfet_route():
    """API keşif scriptini çalıştır ve sonucu döndür."""
    try:
        result = subprocess.run(
            [sys.executable, str(API_KESFET)],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT)
        )
        registry = load_registry()
        toplam = registry.get('toplam_route', 0) if registry else 0
        return jsonify({
            'ok': True,
            'log': result.stdout[-3000:],
            'errors': result.stderr[-1000:] if result.stderr else '',
            'toplam_route': toplam,
            'toplam_proje': registry.get('toplam_proje', 0) if registry else 0,
        })
    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'error': 'Keşif zaman aşımına uğradı (120s).'}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5050)