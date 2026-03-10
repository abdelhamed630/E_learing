from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]
    operations = [
        migrations.AddField(model_name='loginhistory', name='device_fingerprint',
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name='بصمة الجهاز')),
        migrations.AddField(model_name='loginhistory', name='device_name',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='اسم الجهاز')),
        migrations.AddField(model_name='loginhistory', name='is_suspicious',
            field=models.BooleanField(default=False, verbose_name='مشبوه')),
    ]
