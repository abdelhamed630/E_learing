"""
نماذج الحسابات والمستخدمين
"""
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """مدير المستخدمين المخصص"""

    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('يجب إدخال البريد الإلكتروني')
        if not username:
            raise ValueError('يجب إدخال اسم المستخدم')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """نموذج المستخدم المخصص"""

    ROLE_CHOICES = [
        ('student',    'طالب'),
        ('instructor', 'مدرس'),
        ('admin',      'مدير'),
    ]

    username   = models.CharField(max_length=150, unique=True, verbose_name='اسم المستخدم')
    email      = models.EmailField(max_length=254, unique=True, verbose_name='البريد الإلكتروني')
    first_name = models.CharField(max_length=150, blank=True, verbose_name='first name')
    last_name  = models.CharField(max_length=150, blank=True, verbose_name='last name')
    phone      = models.CharField(
        max_length=17, blank=True, null=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="رقم الهاتف يجب أن يكون بالصيغة: '+999999999'. حتى 15 رقم."
        )],
        verbose_name='رقم الهاتف'
    )
    avatar      = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='الصورة الشخصية')
    bio         = models.TextField(blank=True, null=True, verbose_name='نبذة تعريفية')
    role        = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student', verbose_name='الدور')
    is_verified = models.BooleanField(default=False, verbose_name='موثق')
    is_active   = models.BooleanField(default=True, verbose_name='نشط')
    is_staff    = models.BooleanField(default=False, verbose_name='staff status')
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='date joined')
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ التسجيل')
    updated_at  = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    objects = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name        = 'مستخدم'
        verbose_name_plural = 'المستخدمون'
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.username} ({self.email})'

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.username

    def get_short_name(self):
        return self.first_name or self.username

    @property
    def full_name(self):
        return self.get_full_name()


class Profile(models.Model):
    """الملف الشخصي الإضافي للمستخدم"""

    GENDER_CHOICES = [
        ('male',   'ذكر'),
        ('female', 'أنثى'),
        ('other',  'آخر'),
    ]

    user         = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile', verbose_name='المستخدم')
    birth_date   = models.DateField(blank=True, null=True, verbose_name='تاريخ الميلاد')
    gender       = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True, verbose_name='الجنس')
    country      = models.CharField(max_length=100, blank=True, null=True, verbose_name='الدولة')
    city         = models.CharField(max_length=100, blank=True, null=True, verbose_name='المدينة')
    address      = models.TextField(blank=True, null=True, verbose_name='العنوان')
    facebook_url = models.URLField(blank=True, null=True, verbose_name='فيسبوك')
    twitter_url  = models.URLField(blank=True, null=True, verbose_name='تويتر')
    linkedin_url = models.URLField(blank=True, null=True, verbose_name='لينكدإن')
    website_url  = models.URLField(blank=True, null=True, verbose_name='الموقع الإلكتروني')
    show_email   = models.BooleanField(default=False, verbose_name='إظهار البريد')
    show_phone   = models.BooleanField(default=False, verbose_name='إظهار الهاتف')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'ملف شخصي'
        verbose_name_plural = 'ملفات شخصية'

    def __str__(self):
        return f'Profile of {self.user}'


class EmailVerification(models.Model):
    """توثيق البريد الإلكتروني"""

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_verifications', verbose_name='المستخدم')
    token      = models.CharField(max_length=100, unique=True, verbose_name='الرمز')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    expires_at = models.DateTimeField(verbose_name='تاريخ الانتهاء')
    is_used    = models.BooleanField(default=False, verbose_name='مستخدم')

    class Meta:
        verbose_name        = 'توثيق بريد إلكتروني'
        verbose_name_plural = 'توثيقات البريد الإلكتروني'
        ordering            = ['-created_at']

    def __str__(self):
        return f'Verification for {self.user}'


class PasswordReset(models.Model):
    """إعادة تعيين كلمة المرور"""

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='password_resets', verbose_name='المستخدم')
    token      = models.CharField(max_length=100, unique=True, verbose_name='الرمز')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    expires_at = models.DateTimeField(verbose_name='تاريخ الانتهاء')
    is_used    = models.BooleanField(default=False, verbose_name='مستخدم')

    class Meta:
        verbose_name        = 'إعادة تعيين كلمة مرور'
        verbose_name_plural = 'إعادة تعيين كلمات المرور'
        ordering            = ['-created_at']

    def __str__(self):
        return f'PasswordReset for {self.user}'


class LoginHistory(models.Model):
    """سجل تسجيل الدخول"""

    user          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='login_history', verbose_name='المستخدم')
    ip_address    = models.GenericIPAddressField(verbose_name='عنوان IP')
    user_agent    = models.TextField(blank=True, null=True, verbose_name='متصفح المستخدم')
    device_info   = models.CharField(max_length=200, blank=True, null=True, verbose_name='معلومات الجهاز')
    location      = models.CharField(max_length=200, blank=True, null=True, verbose_name='الموقع')
    is_successful = models.BooleanField(default=True, verbose_name='نجح')
    created_at    = models.DateTimeField(auto_now_add=True, verbose_name='التاريخ')

    class Meta:
        verbose_name        = 'سجل تسجيل دخول'
        verbose_name_plural = 'سجلات تسجيل الدخول'
        ordering            = ['-created_at']

    def __str__(self):
        return f'Login by {self.user} at {self.created_at}'
