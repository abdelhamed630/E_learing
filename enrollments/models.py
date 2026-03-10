"""
نماذج التسجيل في الكورسات وتتبع التقدم
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

User = get_user_model()


class Enrollment(models.Model):
    STATUS_CHOICES = [
        ('pending',   'في انتظار الموافقة'),
        ('active',    'نشط'),
        ('rejected',  'مرفوض'),
        ('completed', 'مكتمل'),
        ('dropped',   'منسحب'),
        ('expired',   'منتهي'),
        ('blocked',   'محظور'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='enrollments')
    course  = models.ForeignKey('courses.Course',   on_delete=models.CASCADE, related_name='enrollments')

    status   = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # ملاحظة المدرب عند القبول أو الرفض
    instructor_note = models.TextField(blank=True, null=True, verbose_name='ملاحظة المدرب')

    total_time_spent   = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    certificate_issued = models.BooleanField(default=False)
    certificate_url    = models.URLField(blank=True, null=True)

    enrolled_at  = models.DateTimeField(auto_now_add=True)
    started_at   = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    expires_at   = models.DateTimeField(blank=True, null=True)
    last_accessed = models.DateTimeField(auto_now=True)

    # من قبِل / رفض
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_enrollments')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['student', 'course']
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course', 'status']),
        ]

    def __str__(self):
        return f"{self.student.user.username} - {self.course.title} [{self.status}]"

    def mark_as_started(self):
        if not self.started_at:
            self.started_at = timezone.now()
            self.save(update_fields=['started_at'])

    def mark_as_completed(self):
        if not self.completed_at:
            self.status      = 'completed'
            self.progress    = 100
            self.completed_at = timezone.now()
            self.save(update_fields=['status', 'progress', 'completed_at'])

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def is_completed(self):
        return self.status == 'completed'

    @property
    def days_since_enrollment(self):
        return (timezone.now() - self.enrolled_at).days


class VideoProgress(models.Model):
    student    = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='video_progress')
    video      = models.ForeignKey('courses.Video',    on_delete=models.CASCADE, related_name='student_progress')
    enrollment = models.ForeignKey(Enrollment,         on_delete=models.CASCADE, related_name='video_progress')

    watched_duration = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    last_position    = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    completed        = models.BooleanField(default=False)
    view_count       = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    first_watched = models.DateTimeField(auto_now_add=True)
    last_watched  = models.DateTimeField(auto_now=True)
    completed_at  = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ['student', 'video']
        ordering = ['-last_watched']

    def __str__(self):
        return f"{self.student.user.username} - {self.video.title}"

    @property
    def completion_percentage(self):
        if self.video.duration and self.video.duration > 0:
            return min(100, int((self.watched_duration / self.video.duration) * 100))
        return 0

    def mark_as_completed(self):
        if not self.completed:
            self.completed       = True
            self.completed_at    = timezone.now()
            self.watched_duration = self.video.duration
            self.save(update_fields=['completed', 'completed_at', 'watched_duration'])


class CourseNote(models.Model):
    student    = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='course_notes')
    enrollment = models.ForeignKey(Enrollment,         on_delete=models.CASCADE, related_name='notes')
    video      = models.ForeignKey('courses.Video',    on_delete=models.CASCADE, related_name='student_notes', blank=True, null=True)
    title      = models.CharField(max_length=200)
    content    = models.TextField()
    timestamp  = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.user.username} - {self.title}"


class Certificate(models.Model):
    enrollment          = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='certificate')
    certificate_number  = models.CharField(max_length=50, unique=True)
    issued_at           = models.DateTimeField(auto_now_add=True)
    certificate_file    = models.FileField(upload_to='certificates/', blank=True, null=True)
    verification_url    = models.URLField(blank=True, null=True)
    final_grade         = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True,
                                               validators=[MinValueValidator(0), MaxValueValidator(100)])

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f"شهادة #{self.certificate_number} - {self.enrollment.student.user.username}"


class LearningStreak(models.Model):
    student        = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='learning_streaks')
    date           = models.DateField()
    time_spent     = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    videos_watched = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    notes_added    = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'date']
        ordering = ['-date']
