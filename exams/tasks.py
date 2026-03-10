"""
Celery Tasks للامتحانات
"""
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Avg


def _do_grade(attempt_id):
    """
    منطق التصحيح الفعلي — مستقل عن Celery عشان يشتغل sync أو async
    """
    from .models import ExamAttempt

    attempt = ExamAttempt.objects.get(id=attempt_id)

    if attempt.status not in ['submitted', 'expired', 'in_progress']:
        return f'المحاولة #{attempt_id} ليست جاهزة للتصحيح'

    total_points  = attempt.exam.total_points
    earned_points = 0

    for sa in attempt.student_answers.all():
        sa.check_answer()
        earned_points += sa.points_earned

    score  = (earned_points / total_points * 100) if total_points > 0 else 0
    passed = score >= attempt.exam.passing_score

    attempt.score         = round(score, 2)
    attempt.points_earned = earned_points
    attempt.passed        = passed
    attempt.status        = 'graded'
    if not attempt.submitted_at:
        attempt.submitted_at = timezone.now()
    attempt.save()

    # مسح الكاش
    cache.delete(f'exam_detail_{attempt.exam.id}_s{attempt.student.id}')

    # إشعار النتيجة
    try:
        from notifications.utils import notify_exam_result
        notify_exam_result(attempt)
    except Exception:
        pass

    return f'تم تصحيح المحاولة #{attempt_id} — الدرجة: {score:.2f}%'


@shared_task
def grade_exam_attempt(attempt_id):
    try:
        result = _do_grade(attempt_id)
        # إشعار بالبريد (اختياري، fail_silently)
        try:
            send_exam_result_notification.delay(attempt_id)
        except Exception:
            pass
        return result
    except Exception as e:
        return f'خطأ في التصحيح: {str(e)}'


@shared_task
def auto_submit_attempt(attempt_id):
    try:
        from .models import ExamAttempt
        attempt = ExamAttempt.objects.get(id=attempt_id)

        if attempt.status != 'in_progress':
            return f'المحاولة #{attempt_id} ليست جارية'

        attempt.status       = 'expired'
        attempt.submitted_at = attempt.expires_at
        attempt.save()

        grade_exam_attempt.delay(attempt_id)
        return f'تم التسليم التلقائي للمحاولة #{attempt_id}'

    except Exception as e:
        return f'خطأ: {str(e)}'


@shared_task
def send_exam_result_notification(attempt_id):
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from .models import ExamAttempt

        attempt = ExamAttempt.objects.get(id=attempt_id)
        student = attempt.student
        exam    = attempt.exam

        send_mail(
            subject=f'نتيجة امتحان {exam.title}',
            message=f'الدرجة: {attempt.score}% — {"ناجح ✅" if attempt.passed else "راسب ❌"}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.user.email],
            fail_silently=True,
        )
        return f'أُرسل الإشعار إلى {student.user.email}'
    except Exception as e:
        return f'خطأ في الإشعار: {str(e)}'


@shared_task
def cleanup_expired_attempts():
    from .models import ExamAttempt
    expired = ExamAttempt.objects.filter(status='in_progress', expires_at__lt=timezone.now())
    count   = 0
    for attempt in expired:
        auto_submit_attempt.delay(attempt.id)
        count += 1
    return f'تم تسليم {count} محاولة منتهية تلقائياً'


@shared_task
def calculate_exam_statistics(exam_id):
    """حساب إحصائيات الامتحان وحفظها في الكاش"""
    try:
        from .models import Exam, ExamAttempt
        exam     = Exam.objects.get(id=exam_id)
        attempts = ExamAttempt.objects.filter(exam=exam, status='graded')
        if not attempts.exists():
            return 'لا توجد محاولات مصححة'
        stats = {
            'total_attempts': attempts.count(),
            'passed_count':   attempts.filter(passed=True).count(),
            'avg_score':      float(attempts.aggregate(Avg('score'))['score__avg'] or 0),
        }
        cache.set(f'exam_stats_{exam_id}', stats, 3600)
        return f'تم حساب إحصائيات الامتحان #{exam_id}'
    except Exception as e:
        return f'خطأ: {str(e)}'
