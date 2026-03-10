from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(verbose_name='المحتوى')),
                ('is_pinned', models.BooleanField(default=False, verbose_name='مثبت')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='courses.course', verbose_name='الكورس')),
                ('likes', models.ManyToManyField(blank=True, related_name='liked_comments', to=settings.AUTH_USER_MODEL, verbose_name='الإعجابات')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='courses.coursecomment', verbose_name='التعليق الأصلي')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_comments', to=settings.AUTH_USER_MODEL, verbose_name='المستخدم')),
            ],
            options={
                'verbose_name': 'تعليق',
                'verbose_name_plural': 'التعليقات',
                'ordering': ['-is_pinned', '-created_at'],
                'indexes': [models.Index(fields=['course', 'parent'], name='courses_cou_course__idx')],
            },
        ),
    ]
