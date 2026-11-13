"""Serve o build Vite na mesma origem da API Django."""
import json
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render


def index(request, route=''):
    manifest_path = Path(settings.BASE_DIR) / 'static/clientes-app/.vite/manifest.json'
    if not manifest_path.exists():
        return HttpResponse('Frontend ainda não compilado. Execute npm run build.', status=503)
    manifest = json.loads(manifest_path.read_text())
    entry = manifest['index.html']
    css, visited = [], set()

    def collect(key):
        if key in visited:
            return
        visited.add(key)
        for dependency in manifest[key].get('imports', []):
            collect(dependency)
        css.extend('clientes-app/' + name for name in manifest[key].get('css', []))

    collect('index.html')
    return render(request, 'clientes_app.html', {'js': 'clientes-app/' + entry['file'],
                                                'css': list(dict.fromkeys(css))})
