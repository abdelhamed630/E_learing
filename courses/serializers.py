from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum
from .models import Category, Course, Section, Video, Attachment, CourseReview

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name  = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'username', 'full_name', 'email', 'avatar_url']

    def get_full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name if name else obj.username

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        avatar  = getattr(obj, 'avatar', None)
        if avatar and hasattr(avatar, 'url'):
            try:
                return request.build_absolute_uri(avatar.url) if request else avatar.url
            except Exception:
                pass
        return None


class CategorySerializer(serializers.ModelSerializer):
    courses_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'icon', 'courses_count']

    def get_courses_count(self, obj):
        return obj.courses.filter(is_published=True).count()


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ['id', 'title', 'file', 'file_size', 'created_at']
        read_only_fields = ['id', 'created_at']


class VideoSerializer(serializers.ModelSerializer):
    # ✅ @property → SerializerMethodField دايمًا
    duration_formatted = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)
    is_watched = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            'id', 'title', 'description', 'video_file', 'video_url', 'thumbnail',
            'duration', 'duration_formatted', 'order', 'is_free', 'section',
            'is_downloadable', 'views_count', 'attachments', 'is_watched'
        ]
        read_only_fields = ['id', 'views_count']

    def get_duration_formatted(self, obj):
        return obj.duration_formatted

    def get_is_watched(self, obj):
        # ✅ نستخدم الـ context اللي حضّرناه في get_serializer_context
        watched_videos = self.context.get('watched_videos')
        if watched_videos is not None:
            return obj.id in watched_videos
        return False


class SectionSerializer(serializers.ModelSerializer):
    # ✅ SerializerMethodField عشان نمرر الـ context للـ VideoSerializer
    videos       = serializers.SerializerMethodField()
    videos_count = serializers.SerializerMethodField()
    total_duration = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = ['id', 'title', 'description', 'order', 'videos', 'videos_count', 'total_duration']
        read_only_fields = ['id']

    def get_videos(self, obj):
        # ✅ نمرر context الكامل للـ VideoSerializer عشان watched_videos توصل
        return VideoSerializer(
            obj.videos.order_by('order'),
            many=True,
            context=self.context
        ).data

    def get_videos_count(self, obj):
        return obj.videos.count()

    def get_total_duration(self, obj):
        return obj.total_duration


class CourseListSerializer(serializers.ModelSerializer):
    category            = CategorySerializer(read_only=True)
    instructor          = serializers.SerializerMethodField()
    thumbnail           = serializers.SerializerMethodField()   # ← absolute URL
    final_price         = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()
    is_enrolled         = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'thumbnail', 'category', 'instructor',
            'level', 'language', 'price', 'discount_price', 'final_price',
            'discount_percentage', 'duration_hours', 'students_count',
            'rating', 'is_featured', 'is_enrolled', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'students_count', 'rating', 'created_at']

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.thumbnail and hasattr(obj.thumbnail, 'url'):
            try:
                return request.build_absolute_uri(obj.thumbnail.url) if request else obj.thumbnail.url
            except Exception:
                pass
        return None

    def get_instructor(self, obj):
        return UserSerializer(obj.instructor, context=self.context).data

    def get_final_price(self, obj):
        return obj.final_price

    def get_discount_percentage(self, obj):
        return obj.discount_percentage

    def get_is_enrolled(self, obj):
        enrolled_courses = self.context.get('enrolled_courses')
        if enrolled_courses is not None:
            return obj.id in enrolled_courses
        return False


class CourseDetailSerializer(CourseListSerializer):
    sections          = serializers.SerializerMethodField()
    videos            = serializers.SerializerMethodField()
    total_videos      = serializers.SerializerMethodField()
    total_duration    = serializers.SerializerMethodField()
    reviews_count     = serializers.SerializerMethodField()
    enrollment_status = serializers.SerializerMethodField()
    group_link        = serializers.SerializerMethodField()

    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + [
            'description', 'trailer_url', 'requirements', 'what_will_learn',
            'sections', 'videos', 'total_videos', 'total_duration', 'views_count',
            'reviews_count', 'updated_at', 'enrollment_status', 'group_link'
        ]

    def get_sections(self, obj):
        return SectionSerializer(
            obj.sections.prefetch_related('videos__attachments').order_by('order'),
            many=True,
            context=self.context
        ).data

    def get_videos(self, obj):
        return VideoSerializer(
            obj.videos.filter(section__isnull=True).order_by('order'),
            many=True,
            context=self.context
        ).data

    def get_total_videos(self, obj):
        return obj.total_videos

    def get_total_duration(self, obj):
        return obj.total_duration

    def get_reviews_count(self, obj):
        return obj.reviews.count()

    def get_enrollment_status(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        user = request.user
        if hasattr(user, 'student_profile') and user.student_profile:
            from enrollments.models import Enrollment
            enr = Enrollment.objects.filter(student=user.student_profile, course=obj).first()
            return enr.status if enr else None
        return None

    def get_group_link(self, obj):
        """أعطِ رابط الجروب للطلاب المقبولين فقط"""
        if not obj.group_link:
            return None
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        user = request.user
        # المدرب يشوف الرابط دايماً
        if hasattr(user, 'role') and user.role == 'instructor':
            return obj.group_link
        if hasattr(user, 'student_profile') and user.student_profile:
            from enrollments.models import Enrollment
            enr = Enrollment.objects.filter(
                student=user.student_profile, course=obj, status='active'
            ).first()
            if enr:
                return obj.group_link
        return None


class CourseReviewSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_avatar = serializers.SerializerMethodField()

    class Meta:
        model = CourseReview
        fields = [
            'id', 'student_name', 'student_avatar', 'rating',
            'comment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_student_name(self, obj):
        # obj.student هو Student model → .user هو User
        user = obj.student.user if hasattr(obj.student, 'user') else obj.student
        return user.get_full_name() or user.username

    def get_student_avatar(self, obj):
        request = self.context.get('request')
        user = obj.student.user if hasattr(obj.student, 'user') else obj.student
        avatar = getattr(user, 'avatar', None)
        if avatar and request:
            try:
                return request.build_absolute_uri(avatar.url)
            except Exception:
                return None
        return None


class CreateCourseReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseReview
        fields = ['rating', 'comment']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("التقييم يجب أن يكون بين 1 و 5")
        return value


class InstructorCourseSerializer(serializers.ModelSerializer):
    """Serializer للمدرب - إنشاء وتعديل الكورسات"""
    category_detail = CategorySerializer(source='category', read_only=True)
    instructor_name = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'category', 'category_detail',
            'instructor', 'instructor_name', 'level', 'language',
            'price', 'discount_price', 'duration_hours',
            'requirements', 'what_will_learn', 'trailer_url',
            'thumbnail', 'is_published', 'is_featured',
            'students_count', 'rating', 'views_count',
            'created_at', 'updated_at', 'group_link',
        ]
        read_only_fields = [
            'id', 'slug', 'instructor', 'students_count',
            'rating', 'views_count', 'created_at', 'updated_at',
        ]

    def get_instructor_name(self, obj):
        return obj.instructor.get_full_name() or obj.instructor.username

    def create(self, validated_data):
        validated_data['instructor'] = self.context['request'].user
        return super().create(validated_data)
