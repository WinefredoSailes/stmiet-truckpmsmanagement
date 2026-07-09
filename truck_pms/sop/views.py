from django.shortcuts import render
from django.conf import settings
from django.http import FileResponse, Http404
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
    """Serve PDF file directly; 404 if not found."""
    pdf_path = Path(settings.BASE_DIR) / 'static' / 'sop' / filename
    if pdf_path.exists():
        return FileResponse(
            open(pdf_path, 'rb'),
            as_attachment=True,
            filename=filename,
            content_type='application/pdf',
        )
    raise Http404('PDF not found. Run `python manage.py build_sop` to generate it.')


def download_en(request):
    return _serve_pdf(request, 'Truck_PMS_SOP_Manual_EN.pdf')


def download_tl(request):
    return _serve_pdf(request, 'Truck_PMS_SOP_Manual_TL.pdf')
