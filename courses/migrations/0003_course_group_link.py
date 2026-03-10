from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0002_coursecomment'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='group_link',
            field=models.URLField(blank=True, null=True, verbose_name='رابط الجروب (واتساب/تيليجرام)'),
        ),
    ]
