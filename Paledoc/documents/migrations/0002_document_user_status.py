# Generated migration — adds user FK, status, page_count, file_size, original_filename

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='documents',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='page_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='document',
            name='file_size',
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='document',
            name='original_filename',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
