"""
URLs للامتحانات
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExamViewSet, InstructorExamViewSet

app_name = 'exams'

# ── Router للطلاب ──
student_router = DefaultRouter()
student_router.register(r'', ExamViewSet, basename='exam')

# ── Router للمدرب ── (منفصل عشان مفيش تعارض في الـ URL)
instructor_router = DefaultRouter()
instructor_router.register(r'', InstructorExamViewSet, basename='instructor-exam')

urlpatterns = [
    # مسارات المدرب تيجي أولاً عشان /instructor/ ميتطابقش مع /{pk}/
    path('instructor/', include(instructor_router.urls)),
    # مسارات الطالب
    path('', include(student_router.urls)),
]
