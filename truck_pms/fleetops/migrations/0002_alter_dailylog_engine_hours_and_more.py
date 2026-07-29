from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fleetops', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dailylog',
            name='distance_traveled_km',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='dailylog',
            name='engine_hours',
            field=models.DecimalField(decimal_places=2, default=0, help_text='End-of-day engine hours', max_digits=10),
        ),
    ]
