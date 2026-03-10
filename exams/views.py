"""
Views للامتحانات — نسخة نهائية مُصلحة
"""
import random
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction, models as dj_models
from django.core.cache import cache
from datetime import timedelta
from students.models import Student
from enrollments.models import Enrollment
from .models import Exam, Question, Answer, ExamAttempt, StudentAnswer
from .serializers import (
    ExamSerializer, ExamDetailSerializer,
    ExamAttemptSerializer, ExamResultSerializer,
    SubmitExamSerializer,
)


def get_student(user):
    student, _ = Student.objects.get_or_create(user=user)
    return student


def _shuffle_exam_data(exam, data):
    """يخلط الأسئلة والإجابات في الـ data dict"""
    if exam.shuffle_questions:
        qs = list(data.get('questions', []))
        random.shuffle(qs)
        if exam.shuffle_answers:
            for q in qs:
                ans = list(q.get('answers', []))
                random.shuffle(ans)
                q['answers'] = ans
        data['questions'] = qs
    return data


def _grade_sync(attempt_id):
    """تصحيح فوري synchronous (fallback لو Celery مش شغال)"""
    from .tasks import _do_grade
    try:
        _do_grade(attempt_id)
    except Exception:
        pass


def _try_grade(attempt_id):
    """يحاول Celery أولاً، ولو فشل يصحح sync"""
    from .tasks import grade_exam_attempt
    try:
        grade_exam_attempt.delay(attempt_id)
    except Exception:
        _grade_sync(attempt_id)


# ═══════════════════════════════════════════════════
#  ExamViewSet — للطالب
# ═══════════════════════════════════════════════════
class ExamViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return ExamDetailSerializer if self.action == 'retrieve' else ExamSerializer

    def get_queryset(self):
        user = self.request.user

        # المدرب يشوف كل امتحانات كورساته
        if user.role == 'instructor':
            return Exam.objects.filter(
                course__instructor=user
            ).select_related('course').prefetch_related('questions__answers')

        # الطالب يشوف الامتحانات المتاحة فقط
        student = get_student(user)
        enrolled_courses = Enrollment.objects.filter(
            student=student, status='active'
        ).values_list('course_id', flat=True)

        now = timezone.now()
        return Exam.objects.filter(
            course__in=enrolled_courses,
            status='published',
            is_open=True,
        ).filter(
            dj_models.Q(available_from__isnull=True) | dj_models.Q(available_from__lte=now)
        ).filter(
            dj_models.Q(available_until__isnull=True) | dj_models.Q(available_until__gte=now)
        ).select_related('course').prefetch_related('questions__answers')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def retrieve(self, request, *args, **kwargs):
        exam = self.get_object()

        if request.user.role == 'instructor':
            return Response(ExamDetailSerializer(exam, context={'request': request}).data)

        student   = get_student(request.user)
        cache_key = f'exam_detail_{exam.id}_s{student.id}'
        cached    = cache.get(cache_key)
        if cached:
            return Response(cached)

        data = ExamDetailSerializer(exam, context={'request': request}).data
        data = _shuffle_exam_data(exam, data)
        cache.set(cache_key, data, 300)
        return Response(data)

    # ── بدء الامتحان ──
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def start(self, request, pk=None):
        if request.user.role == 'instructor':
            return Response({'error': 'المدربون لا يمكنهم حل الامتحانات.'}, status=status.HTTP_403_FORBIDDEN)

        exam    = self.get_object()
        student = get_student(request.user)

        # التحقق من التسجيل
        try:
            enrollment = Enrollment.objects.get(student=student, course=exam.course, status='active')
        except Enrollment.DoesNotExist:
            return Response({'error': 'يجب التسجيل في الكورس أولاً'}, status=status.HTTP_403_FORBIDDEN)

        # عدد المحاولات المكتملة
        done_count = ExamAttempt.objects.filter(
            student=student, exam=exam
        ).exclude(status='in_progress').count()

        if exam.max_attempts > 0 and done_count >= exam.max_attempts:
            return Response({'error': 'لقد استنفذت جميع محاولاتك'}, status=status.HTTP_403_FORBIDDEN)

        # محاولة جارية؟
        active = ExamAttempt.objects.filter(student=student, exam=exam, status='in_progress').first()
        if active:
            if active.is_expired:
                _try_grade(active.id)
            else:
                exam_data = _shuffle_exam_data(exam, ExamDetailSerializer(exam, context={'request': request}).data)
                return Response({
                    'message': 'لديك محاولة جارية بالفعل',
                    'attempt': ExamAttemptSerializer(active).data,
                    'exam':    exam_data,
                    'time_limit_minutes': exam.duration,
                }, status=status.HTTP_200_OK)

        attempt = ExamAttempt.objects.create(
            student=student,
            exam=exam,
            enrollment=enrollment,
            attempt_number=done_count + 1,
            expires_at=timezone.now() + timedelta(minutes=exam.duration),
            status='in_progress',
        )

        exam_data = _shuffle_exam_data(exam, ExamDetailSerializer(exam, context={'request': request}).data)
        return Response({
            'message': 'تم بدء الامتحان بنجاح',
            'attempt': ExamAttemptSerializer(attempt).data,
            'exam':    exam_data,
            'time_limit_minutes': exam.duration,
        }, status=status.HTTP_201_CREATED)

    # ── تسليم الامتحان ──
    @action(detail=False, methods=['post'],
            url_path='attempts/(?P<attempt_id>[^/.]+)/submit',
            permission_classes=[IsAuthenticated])
    def submit(self, request, attempt_id=None):
        student = get_student(request.user)

        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student=student)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'المحاولة غير موجودة'}, status=status.HTTP_404_NOT_FOUND)

        if attempt.status != 'in_progress':
            return Response({'error': 'هذه المحاولة تم تسليمها بالفعل'}, status=status.HTTP_400_BAD_REQUEST)

        if attempt.is_expired:
            _try_grade(attempt.id)
            return Response({'error': 'انتهى وقت الامتحان وتم التسليم تلقائياً'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SubmitExamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            for ans_data in serializer.validated_data['answers']:
                try:
                    question = Question.objects.get(id=ans_data['question_id'], exam=attempt.exam)
                    answers  = Answer.objects.filter(id__in=ans_data['answer_ids'], question=question)
                    sa, _    = StudentAnswer.objects.get_or_create(attempt=attempt, question=question)
                    sa.selected_answers.set(answers)
                    sa.save()
                except Question.DoesNotExist:
                    continue

            attempt.status       = 'submitted'
            attempt.submitted_at = timezone.now()
            attempt.save()

        # تصحيح فوري — يضمن النتيجة حتى لو Celery مش شغال
        _try_grade(attempt.id)

        return Response({'message': 'تم تسليم الامتحان بنجاح', 'attempt_id': attempt.id})

    # ── نتيجة محاولة ──
    @action(detail=False, methods=['get'],
            url_path='attempts/(?P<attempt_id>[^/.]+)/result',
            permission_classes=[IsAuthenticated])
    def result(self, request, attempt_id=None):
        student = get_student(request.user)

        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student=student)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'المحاولة غير موجودة'}, status=status.HTTP_404_NOT_FOUND)

        # لو لسه submitted → نصحح sync الآن
        if attempt.status == 'submitted':
            _grade_sync(attempt.id)
            attempt.refresh_from_db()

        if attempt.status not in ['graded', 'submitted', 'expired']:
            return Response({'error': 'النتيجة غير جاهزة بعد'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ExamResultSerializer(attempt, context={'request': request}).data)

    # ── كل محاولاتي ──
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_attempts(self, request):
        if request.user.role == 'instructor':
            return Response([])

        student  = get_student(request.user)
        attempts = ExamAttempt.objects.filter(student=student)\
                       .select_related('exam', 'exam__course').order_by('-started_at')

        exam_id = request.query_params.get('exam_id')
        if exam_id:
            attempts = attempts.filter(exam_id=exam_id)

        return Response(ExamAttemptSerializer(attempts, many=True).data)

    # ── إحصائياتي ──
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def my_stats(self, request, pk=None):
        exam    = self.get_object()
        student = get_student(request.user)
        attempts = ExamAttempt.objects.filter(student=student, exam=exam).exclude(status='in_progress')

        if not attempts.exists():
            return Response({'message': 'لا توجد محاولات سابقة'})

        best   = attempts.order_by('-score').first()
        latest = attempts.order_by('-started_at').first()
        return Response({
            'total_attempts': attempts.count(),
            'attempts_left':  max(0, exam.max_attempts - attempts.count()),
            'best_score':     float(best.score)   if best.score   else 0,
            'best_passed':    best.passed,
            'latest_score':   float(latest.score) if latest.score else 0,
            'average_score':  float(attempts.filter(score__isnull=False).aggregate(
                dj_models.Avg('score'))['score__avg'] or 0),
            'passed_count':   attempts.filter(passed=True).count(),
        })


# ═══════════════════════════════════════════════════
#  InstructorExamViewSet
# ═══════════════════════════════════════════════════
class InstructorExamViewSet(viewsets.ModelViewSet):
    from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from .serializers import InstructorExamSerializer
        return InstructorExamSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def get_queryset(self):
        return Exam.objects.filter(
            course__instructor=self.request.user
        ).select_related('course').prefetch_related('questions__answers', 'attempts').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, pk=None):
        exam = self.get_object()
        if exam.status == 'published':
            exam.status = 'draft'
            msg = 'تم إلغاء نشر الامتحان'
        else:
            if not exam.questions.exists():
                return Response({'error': 'لا يمكن نشر امتحان بدون أسئلة'}, status=status.HTTP_400_BAD_REQUEST)
            exam.status = 'published'
            msg = 'تم نشر الامتحان بنجاح'
        exam.save()
        # مسح كاش كل الطلاب المرتبطين بالامتحان ده
        for student_id in exam.attempts.values_list('student_id', flat=True).distinct():
            cache.delete(f'exam_detail_{exam.id}_s{student_id}')
        return Response({'message': msg, 'status': exam.status})

    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        exam     = self.get_object()
        attempts = ExamAttempt.objects.filter(exam=exam).exclude(status='in_progress')
        passed   = attempts.filter(passed=True).count()
        total    = attempts.count()
        scores   = [float(a.score or 0) for a in attempts]
        return Response({
            'total_attempts': total,
            'passed':         passed,
            'failed':         total - passed,
            'pass_rate':      round(passed / total * 100, 1) if total else 0,
            'avg_score':      round(sum(scores) / len(scores), 1) if scores else 0,
            'max_score':      max(scores) if scores else 0,
            'min_score':      min(scores) if scores else 0,
        })

    @action(detail=True, methods=['post'], url_path='questions')
    def add_question(self, request, pk=None):
        from .serializers import QuestionWriteSerializer, QuestionSerializer
        exam = self.get_object()
        serializer = QuestionWriteSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            question = serializer.save(exam=exam)
            return Response(QuestionSerializer(question).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch', 'delete'], url_path='questions/(?P<question_id>[^/.]+)')
    def manage_question(self, request, pk=None, question_id=None):
        from .serializers import QuestionWriteSerializer, QuestionSerializer
        exam = self.get_object()
        try:
            question = Question.objects.get(id=question_id, exam=exam)
        except Question.DoesNotExist:
            return Response({'error': 'السؤال غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'DELETE':
            question.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = QuestionWriteSerializer(question, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(QuestionSerializer(question).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='results')
    def results(self, request, pk=None):
        from .serializers import InstructorAttemptSerializer
        exam     = self.get_object()
        attempts = ExamAttempt.objects.filter(exam=exam).exclude(status='in_progress')\
                       .select_related('student__user')\
                       .prefetch_related('student_answers__selected_answers', 'student_answers__question__answers')\
                       .order_by('-score')
        return Response(InstructorAttemptSerializer(attempts, many=True).data)

    @action(detail=True, methods=['get'], url_path='results/(?P<attempt_id>[^/.]+)')
    def attempt_detail(self, request, pk=None, attempt_id=None):
        from .serializers import InstructorAttemptSerializer
        exam = self.get_object()
        try:
            attempt = ExamAttempt.objects.select_related('student__user')\
                          .prefetch_related('student_answers__selected_answers', 'student_answers__question__answers')\
                          .get(id=attempt_id, exam=exam)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'المحاولة غير موجودة'}, status=status.HTTP_404_NOT_FOUND)
        return Response(InstructorAttemptSerializer(attempt).data)
