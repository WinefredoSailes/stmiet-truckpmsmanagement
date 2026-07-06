from django import forms


class BootstrapFormMixin:
    bootstrap_exclude = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in self.bootstrap_exclude:
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'form-select')
            elif isinstance(field.widget, forms.Textarea):
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'form-control {existing}'.strip()
            else:
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'form-control {existing}'.strip()
