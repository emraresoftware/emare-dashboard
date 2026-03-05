from flask import Flask, render_template
import json
import pathlib

app = Flask(__name__)

ROOT = pathlib.Path(__file__).parent.parent
EMAREAPI = ROOT / 'emareapi'
PROJECTS_JSON = ROOT / 'projects.json'
DERVISLER = EMAREAPI / 'Dervisler'
DERGAH = EMAREAPI / 'Dergah'

@app.route('/')
def dashboard():
    # Projeleri oku
    with open(PROJECTS_JSON, encoding='utf-8') as f:
        projects = json.load(f)
    # Derviş klasörlerini ve eksikleri bul
    dervish_folders = {p.name: p for p in DERVISLER.iterdir() if p.is_dir()}
    dergah_links = {p.name: p for p in DERGAH.iterdir() if p.is_symlink()}
    # Eksik dervişleri bul
    missing_dervish = []
    for p in projects:
        owner = pathlib.Path(p['path']).name
        if f'{owner} Dervishi' not in dervish_folders:
            missing_dervish.append(owner)
    return render_template('dashboard.html', projects=projects, dervish_folders=dervish_folders, dergah_links=dergah_links, missing_dervish=missing_dervish)

if __name__ == '__main__':
    app.run(debug=True)