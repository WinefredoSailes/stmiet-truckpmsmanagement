import re

from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse, Http404
from pathlib import Path


def download_page(request):
    """Download page showing both editions with info about each."""
    return render(request, 'sop/download/download_page.html')


def view_en(request):
    """Render English SOP manual in browser (HTML/print view)."""
    return render(request, 'sop/sop_manual_en.html')


def view_tl(request):
    """Render Tagalog SOP manual in browser (HTML/print view)."""
    return render(request, 'sop/sop_manual_tl.html')


def _serve_pdf(request, filename):
    """Serve PDF with HTTP Range support; 404 if not generated."""
    pdf_path = Path(settings.BASE_DIR) / 'static' / 'sop' / filename
    if not pdf_path.exists():
        raise Http404('PDF not found. Run `python manage.py build_sop` to generate it.')

    file_size = pdf_path.stat().st_size
    data = pdf_path.read_bytes()

    def make_response(body, status=200):
        response = HttpResponse(body, status=status, content_type='application/pdf')
        response['Accept-Ranges'] = 'bytes'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = str(len(body))
        return response

    range_header = request.META.get('HTTP_RANGE')
    if range_header:
        match = re.match(r'bytes=(\d*)-(\d*)', range_header.strip())
        if match and (match.group(1) or match.group(2)):
            start = int(match.group(1)) if match.group(1) else 0
            end = int(match.group(2)) if match.group(2) else file_size - 1
            if start >= file_size or start > end:
                response = HttpResponse(status=416)
                response['Content-Range'] = f'bytes */{file_size}'
                return response
            end = min(end, file_size - 1)
            chunk = data[start:end + 1]
            response = make_response(chunk, status=206)
            response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            return response

    return make_response(data)


def download_en(request):
    return _serve_pdf(request, 'Truck_PMS_SOP_Manual_EN.pdf')


def download_tl(request):
    return _serve_pdf(request, 'Truck_PMS_SOP_Manual_TL.pdf')
