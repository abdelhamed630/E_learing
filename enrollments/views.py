"""
Views للتسجيلات — المدرب يقبل / يرفض / يتحكم في طلابه
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes as pc
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Avg, Sum
from django.utils import timezone
from datetime import timedelta

from courses.models import Course, Video
from students.models import Student
from .models import Enrollment, VideoProgress, CourseNote, Certificate, LearningStreak
from .serializers import (
    EnrollmentSerializer, EnrollmentDetailSerializer,
    VideoProgressSerializer, UpdateVideoProgressSerializer,
    CourseNoteSerializer, CreateCourseNoteSerializer,
    CertificateSerializer, EnrollmentStatsSerializer,
)
from .tasks import (
    calculate_enrollment_progress,
    generate_certificate,
    update_learning_streak,
)


def get_student(user):
    student, _ = Student.objects.get_or_create(user=user)
    return student


# ═══════════════════════════════════════════════════
#  ENROLLMENT — الطالب
# ═══════════════════════════════════════════════════
class EnrollmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return EnrollmentDetailSerializer if self.action == 'retrieve' else EnrollmentSerializer

    def get_queryset(self):
        student = get_student(self.request.user)
        return Enrollment.objects.filter(student=student).select_related(
            'course', 'course__instructor', 'course__category'
        )

    # ── طلب التسجيل ──
    @action(detail=False, methods=['post'])
    def enroll(self, request):
        course_id = request.data.get('course_id')
        if not course_id:
            return Response({'error': 'يجب تحديد الكورس'}, status=status.HTTP_400_BAD_REQUEST)

        if request.user.role not in ('student', 'instructor'):
            return Response({'error': 'غير مصرح'}, status=status.HTTP_403_FORBIDDEN)

        try:
            course = Course.objects.get(id=course_id, is_published=True)
        except Course.DoesNotExist:
            return Response({'error': 'الكورس غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        # المدرب لا يسجل في كورسه
        if request.user.role == 'instructor' and course.instructor == request.user:
            return Response({'error': 'لا يمكنك التسجيل في كورسك'}, status=status.HTTP_400_BAD_REQUEST)

        student = get_student(request.user)
        existing = Enrollment.objects.filter(student=student, course=course).first()
        if existing:
            return Response({
                'message': 'طلب تسجيلك موجود بالفعل',
                'already_enrolled': True,
                'status': existing.status,
                'enrollment': EnrollmentSerializer(existing).data,
            }, status=status.HTTP_200_OK)

        enrollment = Enrollment.objects.create(student=student, course=course, status='pending')
        return Response({
            'message': 'تم إرسال طلب التسجيل — في انتظار موافقة المدرب',
            'enrollment': EnrollmentSerializer(enrollment).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        enrollment = self.get_object()
        if enrollment.status != 'active':
            return Response({'error': 'التسجيل غير نشط'}, status=status.HTTP_400_BAD_REQUEST)
        enrollment.mark_as_started()
        return Response({'message': 'تم بدء الكورس', 'started_at': enrollment.started_at})

    @action(detail=True, methods=['post'])
    def drop(self, request, pk=None):
        enrollment = self.get_object()
        if enrollment.status == 'completed':
            return Response({'error': 'لا يمكن الانسحاب من كورس مكتمل'}, status=status.HTTP_400_BAD_REQUEST)
        enrollment.status = 'dropped'
        enrollment.save()
        return Response({'message': 'تم الانسحاب من الكورس'})

    @action(detail=False, methods=['get'])
    def active(self, request):
        student = get_student(request.user)
        qs = Enrollment.objects.filter(student=student, status='active').select_related('course')
        return Response(EnrollmentSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        student = get_student(request.user)
        enrollments = Enrollment.objects.filter(student=student)
        data = {
            'total_enrollments':     enrollments.count(),
            'active_enrollments':    enrollments.filter(status='active').count(),
            'completed_enrollments': enrollments.filter(status='completed').count(),
            'average_progress':      enrollments.aggregate(Avg('progress'))['progress__avg'] or 0,
            'total_time_spent':      enrollments.aggregate(Sum('total_time_spent'))['total_time_spent__sum'] or 0,
            'certificates_earned':   Certificate.objects.filter(enrollment__student=student).count(),
            'current_streak':        self._current_streak(student),
            'longest_streak':        self._longest_streak(student),
        }
        return Response(EnrollmentStatsSerializer(data).data)

    def _current_streak(self, student):
        today, streak = timezone.now().date(), 0
        while LearningStreak.objects.filter(student=student, date=today - timedelta(days=streak)).exists():
            streak += 1
        return streak

    def _longest_streak(self, student):
        streaks = LearningStreak.objects.filter(student=student).order_by('date')
        if not streaks.exists(): return 0
        max_s, cur_s, prev = 0, 1, streaks.first().date
        for s in streaks[1:]:
            cur_s = cur_s + 1 if (s.date - prev).days == 1 else (max_s := max(max_s, cur_s)) or 1
            prev = s.date
        return max(max_s, cur_s)


# ═══════════════════════════════════════════════════
#  INSTRUCTOR ENROLLMENT MANAGEMENT
# ═══════════════════════════════════════════════════
class InstructorEnrollmentViewSet(viewsets.ViewSet):
    """المدرب يدير طلاب كورساته — قبول / رفض / حظر / إكمال"""
    permission_classes = [IsAuthenticated]

    def _check_instructor(self, request):
        if request.user.role != 'instructor':
            return Response({'error': 'للمدربين فقط'}, status=status.HTTP_403_FORBIDDEN)
        return None

    def _get_enrollment(self, request, pk):
        """يجيب التسجيل ويتحقق إنه تبع كورس المدرب"""
        try:
            return Enrollment.objects.select_related('student__user', 'course').get(
                id=pk, course__instructor=request.user
            )
        except Enrollment.DoesNotExist:
            return None

    # ── قائمة الطلاب ──
    def list(self, request):
        err = self._check_instructor(request)
        if err: return err

        course_id  = request.query_params.get('course_id')
        status_    = request.query_params.get('status')          # pending | active | rejected | blocked ...
        search     = request.query_params.get('search', '').strip()

        qs = Enrollment.objects.filter(
            course__instructor=request.user
        ).select_related('student__user', 'course').order_by('-enrolled_at')

        if course_id: qs = qs.filter(course_id=course_id)
        if status_:   qs = qs.filter(status=status_)
        if search:
            qs = qs.filter(
                student__user__username__icontains=search
            ) | qs.filter(student__user__email__icontains=search) \
              | qs.filter(student__user__first_name__icontains=search) \
              | qs.filter(student__user__last_name__icontains=search)
            qs = qs.distinct()

        limit  = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        total  = qs.count()
        page   = qs[offset:offset + limit]

        data = [_enrollment_row(e) for e in page]

        # إحصائيات سريعة
        all_qs  = Enrollment.objects.filter(course__instructor=request.user)
        summary = {
            'pending':  all_qs.filter(status='pending').count(),
            'active':   all_qs.filter(status='active').count(),
            'rejected': all_qs.filter(status='rejected').count(),
            'blocked':  all_qs.filter(status='blocked').count(),
            'total':    all_qs.count(),
        }
        if course_id:
            cq = all_qs.filter(course_id=course_id)
            summary = {
                'pending':  cq.filter(status='pending').count(),
                'active':   cq.filter(status='active').count(),
                'rejected': cq.filter(status='rejected').count(),
                'blocked':  cq.filter(status='blocked').count(),
                'total':    cq.count(),
            }

        return Response({'count': total, 'summary': summary, 'results': data})

    # ── قبول طلب تسجيل ──
    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        err = self._check_instructor(request)
        if err: return err

        enrollment = self._get_enrollment(request, pk)
        if not enrollment:
            return Response({'error': 'التسجيل غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        if enrollment.status == 'active':
            return Response({'error': 'الطالب مقبول بالفعل'}, status=status.HTTP_400_BAD_REQUEST)

        if enrollment.status == 'blocked':
            return Response({'error': 'الطالب محظور — قم برفع الحظر أولاً'}, status=status.HTTP_400_BAD_REQUEST)

        enrollment.status          = 'active'
        enrollment.instructor_note = request.data.get('note', '')
        enrollment.reviewed_by     = request.user
        enrollment.reviewed_at     = timezone.now()
        enrollment.save()

        # إشعار الطالب بالقبول
        try:
            from notifications.models import Notification
            Notification.objects.create(
                user=enrollment.student.user,
                notification_type='course_enrolled',
                title=f'تم قبولك في كورس {enrollment.course.title} ✅',
                message=f'مبروك! تم قبول طلب تسجيلك في كورس "{enrollment.course.title}". يمكنك البدء في التعلم الآن.',
                link=f'/courses/{enrollment.course.id}',
                data={'course_id': enrollment.course.id},
            )
        except Exception:
            pass

        return Response({'message': f'تم قبول {enrollment.student.user.get_full_name() or enrollment.student.user.username}', 'enrollment': _enrollment_row(enrollment)})

    # ── رفض طلب تسجيل ──
    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        err = self._check_instructor(request)
        if err: return err

        enrollment = self._get_enrollment(request, pk)
        if not enrollment:
            return Response({'error': 'التسجيل غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        if enrollment.status == 'blocked':
            return Response({'error': 'الطالب محظور بالفعل'}, status=status.HTTP_400_BAD_REQUEST)

        enrollment.status          = 'rejected'
        enrollment.instructor_note = request.data.get('note', '')
        enrollment.reviewed_by     = request.user
        enrollment.reviewed_at     = timezone.now()
        enrollment.save()

        return Response({'message': 'تم رفض الطلب', 'enrollment': _enrollment_row(enrollment)})

    # ── حظر طالب (يمنعه من الكورس) ──
    @action(detail=True, methods=['post'], url_path='block')
    def block(self, request, pk=None):
        err = self._check_instructor(request)
        if err: return err

        enrollment = self._get_enrollment(request, pk)
        if not enrollment:
            return Response({'error': 'التسجيل غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        enrollment.status          = 'blocked'
        enrollment.instructor_note = request.data.get('note', '')
        enrollment.reviewed_by     = request.user
        enrollment.reviewed_at     = timezone.now()
        enrollment.save()

        return Response({'message': f'تم حظر {enrollment.student.user.get_full_name() or enrollment.student.user.username}', 'enrollment': _enrollment_row(enrollment)})

    # ── رفع الحظر ──
    @action(detail=True, methods=['post'], url_path='unblock')
    def unblock(self, request, pk=None):
        err = self._check_instructor(request)
        if err: return err

        enrollment = self._get_enrollment(request, pk)
        if not enrollment:
            return Response({'error': 'التسجيل غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        if enrollment.status != 'blocked':
            return Response({'error': 'الطالب غير محظور'}, status=status.HTTP_400_BAD_REQUEST)

        enrollment.status          = 'active'
        enrollment.instructor_note = request.data.get('note', '')
        enrollment.reviewed_by     = request.user
        enrollment.reviewed_at     = timezone.now()
        enrollment.save()

        return Response({'message': 'تم رفع الحظر', 'enrollment': _enrollment_row(enrollment)})

    # ── تعديل تقدم الطالب يدوياً ──
    @action(detail=True, methods=['patch'], url_path='progress')
    def set_progress(self, request, pk=None):
        err = self._check_instructor(request)
        if err: return err

        enrollment = self._get_enrollment(request, pk)
        if not enrollment:
            return Response({'error': 'التسجيل غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        progress = request.data.get('progress')
        if progress is None or not (0 <= int(progress) <= 100):
            return Response({'error': 'نسبة الإنجاز يجب أن تكون بين 0 و 100'}, status=status.HTTP_400_BAD_REQUEST)

        enrollment.progress = int(progress)
        if int(progress) == 100:
            enrollment.mark_as_completed()
        else:
            enrollment.save(update_fields=['progress'])

        return Response({'message': 'تم تحديث التقدم', 'progress': enrollment.progress})

    # ── إضافة ملاحظة على طالب ──
    @action(detail=True, methods=['patch'], url_path='note')
    def add_note(self, request, pk=None):
        err = self._check_instructor(request)
        if err: return err

        enrollment = self._get_enrollment(request, pk)
        if not enrollment:
            return Response({'error': 'التسجيل غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        enrollment.instructor_note = request.data.get('note', '')
        enrollment.save(update_fields=['instructor_note'])
        return Response({'message': 'تم حفظ الملاحظة'})

    # ── تفاصيل طالب واحد ──
    def retrieve(self, request, pk=None):
        err = self._check_instructor(request)
        if err: return err

        enrollment = self._get_enrollment(request, pk)
        if not enrollment:
            return Response({'error': 'التسجيل غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        row = _enrollment_row(enrollment)
        # إضافة تقدم الفيديوهات
        vp = VideoProgress.objects.filter(enrollment=enrollment).select_related('video')
        row['video_progress'] = [{
            'video_title': v.video.title,
            'completed':   v.completed,
            'percentage':  v.completion_percentage,
            'last_watched': v.last_watched,
        } for v in vp]

        return Response(row)


def _enrollment_row(e):
    """بيانات تسجيل طالب — يستخدمه list و approve و reject"""
    return {
        'id':               e.id,
        'student':          e.student.id,
        'student_name':     e.student.user.get_full_name() or e.student.user.username,
        'student_email':    e.student.user.email,
        'student_username': e.student.user.username,
        'course':           e.course.id,
        'course_title':     e.course.title,
        'status':           e.status,
        'progress':         e.progress,
        'instructor_note':  e.instructor_note or '',
        'enrolled_at':      e.enrolled_at,
        'reviewed_at':      e.reviewed_at,
        'last_accessed':    e.last_accessed,
        'is_completed':     e.is_completed,
    }


# ═══════════════════════════════════════════════════
#  VIDEO PROGRESS
# ═══════════════════════════════════════════════════
class VideoProgressViewSet(viewsets.ModelViewSet):
    serializer_class   = VideoProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        student = get_student(self.request.user)
        return VideoProgress.objects.filter(student=student).select_related('video')

    @action(detail=False, methods=['post'])
    def update_progress(self, request):
        video_id = request.data.get('video_id')
        if not video_id:
            return Response({'error': 'يجب تحديد الفيديو'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return Response({'error': 'الفيديو غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        student = get_student(request.user)
        try:
            enrollment = Enrollment.objects.get(student=student, course=video.course, status='active')
        except Enrollment.DoesNotExist:
            return Response({'error': 'يجب التسجيل في الكورس أولاً'}, status=status.HTTP_403_FORBIDDEN)

        enrollment.mark_as_started()
        serializer = UpdateVideoProgressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        progress, created = VideoProgress.objects.get_or_create(
            student=student, video=video, enrollment=enrollment,
            defaults={
                'watched_duration': serializer.validated_data['watched_duration'],
                'last_position':    serializer.validated_data['last_position'],
                'completed':        serializer.validated_data.get('completed', False),
                'view_count':       1,
            }
        )
        if not created:
            progress.watched_duration = max(progress.watched_duration, serializer.validated_data['watched_duration'])
            progress.last_position    = serializer.validated_data['last_position']
            progress.view_count      += 1
            if serializer.validated_data.get('completed') and not progress.completed:
                progress.mark_as_completed()
            progress.save()

        try:
            calculate_enrollment_progress.delay(enrollment.id)
            update_learning_streak.delay(student.id)
        except Exception:
            pass

        return Response(VideoProgressSerializer(progress).data)


# ═══════════════════════════════════════════════════
#  NOTES / CERTIFICATES
# ═══════════════════════════════════════════════════
class CourseNoteViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return CreateCourseNoteSerializer if self.action in ['create', 'update', 'partial_update'] else CourseNoteSerializer

    def get_queryset(self):
        student = get_student(self.request.user)
        return CourseNote.objects.filter(student=student).select_related('video')

    def perform_create(self, serializer):
        student = get_student(self.request.user)
        video   = serializer.validated_data.get('video')
        enrollment = Enrollment.objects.get(student=student, course=video.course if video else None, status='active')
        serializer.save(student=student, enrollment=enrollment)

    @action(detail=False, methods=['get'])
    def by_course(self, request):
        course_id = request.query_params.get('course_id')
        if not course_id:
            return Response({'error': 'يجب تحديد الكورس'}, status=status.HTTP_400_BAD_REQUEST)
        student = get_student(request.user)
        notes   = CourseNote.objects.filter(student=student, enrollment__course_id=course_id)
        return Response(CourseNoteSerializer(notes, many=True).data)


class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class   = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        student = get_student(self.request.user)
        return Certificate.objects.filter(enrollment__student=student).select_related('enrollment__course')

    @action(detail=False, methods=['get'])
    def verify(self, request):
        cert_number = request.query_params.get('certificate_number')
        if not cert_number:
            return Response({'error': 'يجب إدخال رقم الشهادة'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            cert = Certificate.objects.get(certificate_number=cert_number)
            return Response({'valid': True, 'certificate': CertificateSerializer(cert).data})
        except Certificate.DoesNotExist:
            return Response({'valid': False, 'message': 'شهادة غير صالحة'}, status=status.HTTP_404_NOT_FOUND)
