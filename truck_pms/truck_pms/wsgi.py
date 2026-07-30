import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'truck_pms.settings')
application = get_wsgi_application()

# ── Diagnostic: log static root contents at startup ──────────
static_root = Path(settings.STATIC_ROOT)
print(f'[wsgi] STATIC_ROOT={static_root}', flush=True)
print(f'[wsgi] STATIC_ROOT exists={static_root.exists()}', flush=True)
if static_root.exists():
    for f in sorted(static_root.rglob('*')):
        if f.is_file():
            print(f'[wsgi]   {f.relative_to(static_root)} size={f.stat().st_size}', flush=True)
else:
    print(f'[wsgi] STATIC_ROOT does NOT exist', flush=True)
