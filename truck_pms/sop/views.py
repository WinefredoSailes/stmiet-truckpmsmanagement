from django.shortcuts import render
from django.conf import settings
from django.http import FileResponse, Http404
from pathlib import Path


def download_page(request):
    """Download page showing both editions with info about each."""
    return render(request, 'sop/download/download_page.html')


def _serve_pdf_or_html(request, filename, html_template):
    """Try PDF first, fall back to HTML browser-print view."""
    pdf_path = Path(settings.BASE_DIR) / 'static' / 'sop' / filename
    if pdf_path.exists():
        return FileResponse(
            open(pdf_path, 'rb'),
            as_attachment=True,
            filename=filename,
            content_type='application/pdf',
        )
    # Fallback: render HTML for browser printing
    return render(request, html_template)


def download_en(request):
    return _serve_pdf_or_html(
        request,
        'Truck_PMS_SOP_Manual_EN.pdf',
        'sop/sop_manual_en.html',
    )


def download_tl(request):
    return _serve_pdf_or_html(
        request,
        'Truck_PMS_SOP_Manual_TL.pdf',
        'sop/sop_manual_tl.html',
    )
