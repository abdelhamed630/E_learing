"""
Celery Tasks للحسابات
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import secrets


@shared_task
def send_verification_email(user_id):
    """
    إرسال إيميل توثيق + ترحيب للمستخدم الجديد
    """
    try:
        from .models import User, EmailVerification
        from django.core.mail import EmailMultiAlternatives

        user = User.objects.get(id=user_id)

        # إنشاء رمز التوثيق
        token      = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(days=7)
        EmailVerification.objects.create(user=user, token=token, expires_at=expires_at)

        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        name = user.full_name or user.username

        subject = f'مرحباً {name}! وثّق حسابك في EduVerse 🎓'

        text_body = f"""مرحباً {name}،

شكراً لتسجيلك في EduVerse!

لتفعيل حسابك وبدء رحلتك التعليمية، يرجى توثيق بريدك الإلكتروني:
{verification_url}

هذا الرابط صالح لمدة 7 أيام.

إذا لم تقم بإنشاء هذا الحساب، تجاهل هذه الرسالة.

مع تحياتنا،
فريق EduVerse"""

        html_body = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0e1a;font-family:'Segoe UI',Arial,sans-serif;direction:rtl">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e1a;padding:40px 20px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#12172b,#1a2040);border:1px solid rgba(79,140,255,.2);border-radius:20px;overflow:hidden;max-width:600px;width:100%">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#4f8cff,#7c5cfc);padding:40px;text-align:center">
    <div style="font-size:48px;margin-bottom:10px">🎓</div>
    <h1 style="color:white;margin:0;font-size:28px;font-weight:900">EduVerse</h1>
    <p style="color:rgba(255,255,255,.8);margin:8px 0 0;font-size:14px">منصتك التعليمية العربية</p>
  </td></tr>

  <!-- Body -->
  <tr><td style="padding:40px">
    <h2 style="color:#e2e8f0;font-size:22px;margin:0 0 16px">أهلاً وسهلاً، {name}! 👋</h2>
    <p style="color:#94a3b8;line-height:1.8;margin:0 0 24px;font-size:15px">
      شكراً لانضمامك إلى EduVerse! نحن سعداء بوجودك معنا.<br>
      لتفعيل حسابك وبدء رحلتك التعليمية، يرجى الضغط على الزر أدناه:
    </p>

    <!-- CTA Button -->
    <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:10px 0 30px">
      <a href="{verification_url}"
        style="display:inline-block;background:linear-gradient(135deg,#4f8cff,#7c5cfc);color:white;text-decoration:none;padding:16px 40px;border-radius:12px;font-size:16px;font-weight:700;letter-spacing:.5px">
        ✅ تفعيل حسابي الآن
      </a>
    </td></tr></table>

    <!-- Features -->
    <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(79,140,255,.06);border:1px solid rgba(79,140,255,.15);border-radius:12px;margin-bottom:24px">
    <tr><td style="padding:20px">
      <p style="color:#7c5cfc;font-weight:700;margin:0 0 12px;font-size:14px">بعد التفعيل ستقدر:</p>
      <p style="color:#94a3b8;margin:6px 0;font-size:14px">📚 &nbsp;تصفح مئات الكورسات المتخصصة</p>
      <p style="color:#94a3b8;margin:6px 0;font-size:14px">🏆 &nbsp;تحصل على شهادات معتمدة</p>
      <p style="color:#94a3b8;margin:6px 0;font-size:14px">📝 &nbsp;تحل امتحانات وتتبع تقدمك</p>
      <p style="color:#94a3b8;margin:6px 0;font-size:14px">🎓 &nbsp;تتعلم من أفضل المدربين العرب</p>
    </td></tr></table>

    <p style="color:#64748b;font-size:12px;margin:0">
      إذا لم تنشئ هذا الحساب، تجاهل هذه الرسالة.<br>
      الرابط صالح لمدة 7 أيام.
    </p>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background:rgba(0,0,0,.3);padding:20px;text-align:center;border-top:1px solid rgba(255,255,255,.05)">
    <p style="color:#475569;font-size:12px;margin:0">© 2025 EduVerse · جميع الحقوق محفوظة</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

        msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)

        return f'تم إرسال إيميل التوثيق إلى {user.email}'

    except Exception as e:
        return f'خطأ في إرسال الإيميل: {str(e)}'



@shared_task
def send_password_reset_email(user_id, token):
    """
    إرسال إيميل إعادة تعيين كلمة المرور
    """
    try:
        from .models import User
        
        user = User.objects.get(id=user_id)
        
        # رابط إعادة التعيين
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        
        subject = 'إعادة تعيين كلمة المرور - E-Learning'
        message = f'''
        مرحباً {user.full_name}،
        
        تلقينا طلباً لإعادة تعيين كلمة المرور لحسابك.
        
        الرجاء الضغط على الرابط التالي لإعادة تعيين كلمة المرور:
        {reset_url}
        
        هذا الرابط صالح لمدة 24 ساعة.
        
        إذا لم تطلب إعادة تعيين كلمة المرور، يمكنك تجاهل هذه الرسالة.
        
        مع تحياتنا،
        فريق E-Learning
        '''
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return f'تم إرسال إيميل إعادة التعيين إلى {user.email}'
    
    except Exception as e:
        return f'خطأ في إرسال الإيميل: {str(e)}'


@shared_task
def send_welcome_email(user_id):
    """
    إرسال إيميل ترحيبي للمستخدم الجديد
    """
    try:
        from .models import User
        
        user = User.objects.get(id=user_id)
        
        subject = f'مرحباً بك في E-Learning يا {user.full_name}!'
        message = f'''
        مرحباً {user.full_name}،
        
        نحن سعداء جداً بانضمامك إلى منصة E-Learning!
        
        يمكنك الآن:
        • تصفح مئات الكورسات المتاحة
        • التسجيل في الكورسات التي تهمك
        • تتبع تقدمك في التعلم
        • الحصول على شهادات إتمام
        
        ابدأ رحلتك التعليمية الآن!
        
        نتمنى لك تجربة تعليمية ممتعة ومفيدة.
        
        مع تحياتنا،
        فريق E-Learning
        '''
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return f'تم إرسال إيميل ترحيبي إلى {user.email}'
    
    except Exception as e:
        return f'خطأ في إرسال الإيميل: {str(e)}'


@shared_task
def cleanup_expired_tokens():
    """
    تنظيف الرموز المنتهية (مهمة دورية)
    """
    from .models import EmailVerification, PasswordReset
    from django.utils import timezone
    
    now = timezone.now()
    
    # حذف رموز التوثيق المنتهية
    expired_verifications = EmailVerification.objects.filter(expires_at__lt=now)
    ver_count = expired_verifications.count()
    expired_verifications.delete()
    
    # حذف رموز إعادة التعيين المنتهية
    expired_resets = PasswordReset.objects.filter(expires_at__lt=now)
    reset_count = expired_resets.count()
    expired_resets.delete()
    
    return f'تم حذف {ver_count} رمز توثيق و {reset_count} رمز إعادة تعيين'


@shared_task
def cleanup_login_history():
    """
    تنظيف سجل تسجيل الدخول القديم (مهمة دورية)
    يحتفظ بآخر 6 أشهر فقط
    """
    from .models import LoginHistory
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=180)
    old_logs = LoginHistory.objects.filter(created_at__lt=cutoff_date)
    
    count = old_logs.count()
    old_logs.delete()
    
    return f'تم حذف {count} سجل قديم'


@shared_task
def deactivate_unverified_accounts():
    """
    تعطيل الحسابات غير الموثقة بعد 30 يوم (مهمة دورية)
    """
    from .models import User
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=30)
    
    unverified_users = User.objects.filter(
        is_verified=False,
        is_active=True,
        created_at__lt=cutoff_date
    )
    
    count = unverified_users.count()
    unverified_users.update(is_active=False)
    
    return f'تم تعطيل {count} حساب غير موثق'
