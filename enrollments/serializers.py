"""
Serializers للتسجيلات
"""
from rest_framework import serializers
from .models import Enrollment, VideoProgress, CourseNote, Certificate, LearningStreak


class EnrollmentSerializer(serializers.ModelSerializer):
    student_name              = serializers.CharField(source='student.user.username', read_only=True)
    student_full_name         = serializers.SerializerMethodField()
    student_email             = serializers.CharField(source='student.user.email', read_only=True)
    course_id                 = serializers.IntegerField(source='course.id', read_only=True)
    course_title              = serializers.CharField(source='course.title', read_only=True)
    course_thumbnail          = serializers.SerializerMethodField()
    course_instructor         = serializers.SerializerMethodField()   # اسم المدرب الكامل
    course_instructor_avatar  = serializers.SerializerMethodField()   # صورة المدرب
    is_completed              = serializers.SerializerMethodField()
    days_since_enrollment     = serializers.SerializerMethodField()

    def get_is_completed(self, obj):          return obj.is_completed
    def get_days_since_enrollment(self, obj): return obj.days_since_enrollment
    def get_student_full_name(self, obj):
        return obj.student.user.get_full_name() or obj.student.user.username

    def get_course_thumbnail(self, obj):
        request = self.context.get('request')
        thumb   = obj.course.thumbnail
        if thumb and hasattr(thumb, 'url'):
            try:
                return request.build_absolute_uri(thumb.url) if request else thumb.url
            except Exception:
                pass
        return None

    def get_course_instructor(self, obj):
        u = obj.course.instructor
        return u.get_full_name() or u.username

    def get_course_instructor_avatar(self, obj):
        request = self.context.get('request')
        avatar  = getattr(obj.course.instructor, 'avatar', None)
        if avatar and hasattr(avatar, 'url'):
            try:
                return request.build_absolute_uri(avatar.url) if request else avatar.url
            except Exception:
                pass
        return None

    course_group_link = serializers.SerializerMethodField()

    def get_course_group_link(self, obj):
        # Only expose group link to active enrollments
        if obj.status != 'active' and obj.status != 'completed':
            return None
        return obj.course.group_link if hasattr(obj.course, 'group_link') else None

    class Meta:
        model  = Enrollment
        fields = [
            'id', 'course_id', 'student_name', 'student_full_name', 'student_email',
            'course_title', 'course_thumbnail', 'course_instructor', 'course_instructor_avatar',
            'status', 'progress', 'total_time_spent',
            'certificate_issued', 'certificate_url',
            'instructor_note',
            'enrolled_at', 'started_at', 'completed_at', 'last_accessed',
            'reviewed_at',
            'is_completed', 'days_since_enrollment', 'course_group_link',
        ]
        read_only_fields = [
            'id', 'enrolled_at', 'started_at', 'completed_at',
            'last_accessed', 'certificate_issued', 'certificate_url',
            'reviewed_at',
        ]


class EnrollmentDetailSerializer(EnrollmentSerializer):
    videos_completed = serializers.SerializerMethodField()
    total_videos     = serializers.SerializerMethodField()

    class Meta(EnrollmentSerializer.Meta):
        fields = EnrollmentSerializer.Meta.fields + ['videos_completed', 'total_videos']

    def get_videos_completed(self, obj):
        return VideoProgress.objects.filter(enrollment=obj, completed=True).count()

    def get_total_videos(self, obj):
        return obj.course.videos.count()


class VideoProgressSerializer(serializers.ModelSerializer):
    video_title           = serializers.CharField(source='video.title', read_only=True)
    video_duration        = serializers.IntegerField(source='video.duration', read_only=True)
    completion_percentage = serializers.SerializerMethodField()

    def get_completion_percentage(self, obj): return obj.completion_percentage

    class Meta:
        model  = VideoProgress
        fields = [
            'id', 'video', 'video_title', 'video_duration',
            'watched_duration', 'last_position', 'completed',
            'completion_percentage', 'view_count',
            'first_watched', 'last_watched', 'completed_at',
        ]
        read_only_fields = ['id', 'first_watched', 'last_watched', 'completed_at', 'view_count']


class UpdateVideoProgressSerializer(serializers.Serializer):
    watched_duration = serializers.IntegerField(required=True, min_value=0)
    last_position    = serializers.IntegerField(required=True, min_value=0)
    completed        = serializers.BooleanField(default=False)


class CourseNoteSerializer(serializers.ModelSerializer):
    video_title = serializers.CharField(source='video.title', read_only=True, allow_null=True)

    class Meta:
        model  = CourseNote
        fields = ['id', 'video', 'video_title', 'title', 'content', 'timestamp', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class CreateCourseNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CourseNote
        fields = ['video', 'title', 'content', 'timestamp']

    def validate_timestamp(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("الموضع يجب أن يكون 0 أو أكبر")
        return value


class CertificateSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='enrollment.student.user.get_full_name', read_only=True)
    course_title = serializers.CharField(source='enrollment.course.title', read_only=True)

    class Meta:
        model  = Certificate
        fields = ['id', 'certificate_number', 'student_name', 'course_title',
                  'issued_at', 'certificate_file', 'verification_url', 'final_grade']
        read_only_fields = ['id', 'certificate_number', 'issued_at']


class EnrollmentStatsSerializer(serializers.Serializer):
    total_enrollments     = serializers.IntegerField()
    active_enrollments    = serializers.IntegerField()
    completed_enrollments = serializers.IntegerField()
    average_progress      = serializers.FloatField()
    total_time_spent      = serializers.IntegerField()
    certificates_earned   = serializers.IntegerField()
    current_streak        = serializers.IntegerField()
    longest_streak        = serializers.IntegerField()
