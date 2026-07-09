from pathlib import Path
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.staticfiles.storage import StaticFilesStorage


class Command(BaseCommand):
    help = 'Generate SOP manual HTML and PDFs'

    def handle(self, *args, **options):
        # Override static storage to avoid manifest requirement
        import django.contrib.staticfiles.storage as storage_mod
        orig_storage = storage_mod.staticfiles_storage
        storage_mod.staticfiles_storage = StaticFilesStorage()

        # Try to load WeasyPrint — optional, HTML generation works without it
        WeasyprintHTML = None
        try:
            from weasyprint import HTML as WeasyprintHTML
        except (ImportError, OSError):
            self.stdout.write(self.style.WARNING(
                'WeasyPrint not available — skipping PDF generation. '
                'HTML files will still be generated.'
            ))

        try:
            output_dir = Path(settings.BASE_DIR) / 'static' / 'sop'
            output_dir.mkdir(parents=True, exist_ok=True)

            editions = [
                ('en', 'sop/sop_manual_en.html', 'Truck_PMS_SOP_Manual_EN.pdf'),
                ('tl', 'sop/sop_manual_tl.html', 'Truck_PMS_SOP_Manual_TL.pdf'),
            ]

            for lang_code, template_name, filename in editions:
                self.stdout.write(f'Rendering {lang_code.upper()} manual...')
                html_string = render_to_string(template_name)

                # Write intermediate HTML for browser viewing / debug fallback
                html_path = output_dir / f'{lang_code}.html'
                html_path.write_text(html_string, encoding='utf-8')
                self.stdout.write(self.style.SUCCESS(f'  ok {lang_code}.html generated'))

                if WeasyprintHTML is None:
                    continue

                # Resolve static URLs to absolute file:// paths for WeasyPrint
                static_url = settings.STATIC_URL
                static_dir = str((settings.BASE_DIR / 'static').resolve())
                file_prefix = 'file:///' + static_dir.replace('\\', '/')
                pdf_html = html_string.replace(static_url, file_prefix + '/')

                pdf_path = output_dir / filename
                self.stdout.write(f'  Generating PDF: {pdf_path}...')
                WeasyprintHTML(string=pdf_html, encoding='utf-8').write_pdf(str(pdf_path))

                file_size = pdf_path.stat().st_size
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ {filename} generated ({file_size / 1024:.0f} KB)'
                ))

            self.stdout.write(self.style.SUCCESS('\nSOP manual generation complete.'))
        finally:
            storage_mod.staticfiles_storage = orig_storage
