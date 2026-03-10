from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EnrollmentViewSet,
    InstructorEnrollmentViewSet,
    VideoProgressViewSet,
    CourseNoteViewSet,
    CertificateViewSet,
)

app_name = 'enrollments'

router = DefaultRouter()
router.register(r'enrollments',           EnrollmentViewSet,           basename='enrollment')
router.register(r'progress',              VideoProgressViewSet,         basename='video-progress')
router.register(r'notes',                 CourseNoteViewSet,            basename='note')
router.register(r'certificates',          CertificateViewSet,           basename='certificate')
router.register(r'instructor-enrollments', InstructorEnrollmentViewSet, basename='instructor-enrollment')

urlpatterns = [
    path('', include(router.urls)),
]
