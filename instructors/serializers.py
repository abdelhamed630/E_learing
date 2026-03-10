"""
Serializers للمدربين
"""
from rest_framework import serializers
from .models import Instructor


class InstructorSerializer(serializers.ModelSerializer):
    """Serializer للمدرب (عرض عام)"""
    full_name  = serializers.SerializerMethodField()
    email      = serializers.EmailField(source='user.email',    read_only=True)
    username   = serializers.CharField(source='user.username',  read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Instructor
        fields = [
            'id', 'username', 'full_name', 'email',
            'bio', 'specialization', 'years_of_experience',
            'avatar', 'avatar_url', 'website', 'linkedin', 'github',
            'total_courses', 'total_students', 'average_rating',
            'is_featured', 'created_at'
        ]
        read_only_fields = [
            'id', 'total_courses', 'total_students',
            'average_rating', 'created_at'
        ]

    def get_full_name(self, obj):
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name if name else obj.user.username

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        # أولاً: صورة المدرب من نموذج Instructor
        if obj.avatar and hasattr(obj.avatar, 'url'):
            try:
                return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url
            except Exception:
                pass
        # ثانياً: صورة المستخدم نفسه
        user_avatar = getattr(obj.user, 'avatar', None)
        if user_avatar and hasattr(user_avatar, 'url'):
            try:
                return request.build_absolute_uri(user_avatar.url) if request else user_avatar.url
            except Exception:
                pass
        return None
