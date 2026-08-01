from django.db import migrations


TEMPLATES = [
    ('Tie Rod Ends Inspection', 'MILEAGE', 10000, False, '', 0.4),
    ('Ball Joint Inspection', 'MILEAGE', 10000, False, '', 0.4),
    ('Steering King Pin & Bushing Inspection', 'MILEAGE', 10000, False, '', 0.5),
    ('Lubricate Steering King Pins & Tie Rod Ends', 'MILEAGE', 5000, False, '', 0.3),
    ('Tie Rod End Replacement', 'VISUAL', None, False, '', 1.5),
    ('Ball Joint Replacement', 'VISUAL', None, False, '', 2.0),
    ('King Pin Bushing Replacement', 'VISUAL', None, False, '', 3.0),
]


def create_steering_templates(apps, schema_editor):
    TaskCategory = apps.get_model('pms', 'TaskCategory')
    TaskTemplate = apps.get_model('pms', 'TaskTemplate')
    cat, _ = TaskCategory.objects.get_or_create(
        name='Suspension',
        defaults={'description': 'Suspension and steering components'},
    )
    for name, interval_type, interval_value, req_spec, spec_trade, hours in TEMPLATES:
        TaskTemplate.objects.get_or_create(
            category=cat,
            name=name,
            defaults={
                'interval_type': interval_type,
                'interval_value': interval_value,
                'requires_specialist': req_spec,
                'specialist_trade': spec_trade,
                'estimated_labor_hours': hours,
            },
        )


def remove_steering_templates(apps, schema_editor):
    TaskTemplate = apps.get_model('pms', 'TaskTemplate')
    TaskTemplate.objects.filter(name__in=[t[0] for t in TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pms', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_steering_templates, remove_steering_templates),
    ]
