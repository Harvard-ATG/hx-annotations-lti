# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hx_lti_assignment', '0003_auto_20150727_1821'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignmenttargets',
            name='prompt',
            field=models.TextField(default='', verbose_name=b'Directions', blank=True),
            preserve_default=True,
        ),
    ]
