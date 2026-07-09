from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.template.loader import render_to_string
from django.shortcuts import render


def render_pdf(request, template_name, context, filename):
    """Render a template as PDF via WeasyPrint.
    Falls back to browser print dialog if WeasyPrint is unavailable.
    """
    try:
        from weasyprint import HTML as WeasyprintHTML
    except (ImportError, OSError):
        context['pdf_fallback'] = True
        return render(request, template_name, context)

    html_string = render_to_string(template_name, context, request=request)

    static_url = settings.STATIC_URL
    static_dir = str((settings.BASE_DIR / 'static').resolve())
    file_prefix = 'file:///' + static_dir.replace('\\', '/')
    pdf_html = html_string.replace(static_url, file_prefix + '/')

    pdf_bytes = WeasyprintHTML(string=pdf_html, encoding='utf-8').write_pdf()
    return FileResponse(
        pdf_bytes, as_attachment=True,
        filename=filename, content_type='application/pdf',
    )
