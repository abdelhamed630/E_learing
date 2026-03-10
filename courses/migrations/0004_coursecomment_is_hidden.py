from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0003_course_group_link'),
    ]
    operations = [
        migrations.AddField(
            model_name='coursecomment',
            name='is_hidden',
            field=models.BooleanField(default=False, verbose_name='مخفي'),
        ),
    ]
