from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.conf import settings
from pathlib import Path


class Command(BaseCommand):
    help = 'Generate SOP manual PDFs'

    def handle(self, *args, **options):
        try:
            from weasyprint import HTML
        except ImportError:
            raise CommandError(
                'WeasyPrint is not installed. Run: pip install weasyprint\n'
                'On Windows, GTK runtime is also required. '
                'See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html'
            )
        except OSError:
            raise CommandError(
                'WeasyPrint could not load system libraries (GTK/Pango).\n'
                'On Windows: install GTK3 runtime from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer\n'
                'On Linux: apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0\n'
                'On Render (Linux): works out of the box.'
            )

        output_dir = Path(settings.BASE_DIR) / 'static' / 'sop'
        output_dir.mkdir(parents=True, exist_ok=True)

        editions = [
            ('en', 'sop/sop_manual_en.html', 'Truck_PMS_SOP_Manual_EN.pdf'),
        ]

        for lang_code, template_name, filename in editions:
            self.stdout.write(f'Rendering {lang_code.upper()} manual...')
            html_string = render_to_string(template_name)

            # Write intermediate HTML for debug/browser-print fallback
            html_path = output_dir / f'{lang_code}.html'
            html_path.write_text(html_string, encoding='utf-8')

            pdf_path = output_dir / filename
            self.stdout.write(f'  Generating PDF: {pdf_path}...')
            HTML(string=html_string, encoding='utf-8').write_pdf(str(pdf_path))

            file_size = pdf_path.stat().st_size
            self.stdout.write(self.style.SUCCESS(
                f'  ✓ {filename} generated ({file_size / 1024:.0f} KB)'
            ))

        self.stdout.write(self.style.SUCCESS('\nSOP manual generation complete.'))
