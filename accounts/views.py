"""
Views للحسابات والمصادقة
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings

from rest_framework_simplejwt.tokens import RefreshToken

from .models import Profile, EmailVerification, PasswordReset, LoginHistory
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,
    ChangePasswordSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, UpdateProfileSerializer,
    LoginHistorySerializer,
)

import secrets
from datetime import timedelta

User = get_user_model()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access':  str(refresh.access_token),
        'refresh': str(refresh),
    }


def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


# ─── Register ────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """تسجيل مستخدم جديد"""
    serializer = RegisterSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.save()

    # إنشاء الملف الشخصي
    Profile.objects.get_or_create(user=user)

    # إرسال إيميل توثيق (Celery)
    try:
        from .tasks import send_verification_email
        send_verification_email.delay(user.id)
    except Exception:
        pass

    tokens = get_tokens_for_user(user)
    user_data = UserSerializer(user, context={'request': request}).data
    return Response({
        'user':   user_data,
        'tokens': tokens,
        'message': 'تم إنشاء حسابك بنجاح! تحقق من بريدك الإلكتروني.',
    }, status=status.HTTP_201_CREATED)


# ─── Login ───────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """تسجيل الدخول"""
    serializer = LoginSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.validated_data['user']

    # تسجيل سجل الدخول
    try:
        LoginHistory.objects.create(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            is_successful=True,
        )
    except Exception:
        pass

    tokens = get_tokens_for_user(user)
    user_data = UserSerializer(user, context={'request': request}).data
    return Response({
        'user':   user_data,
        'tokens': tokens,
        'message': 'تم تسجيل الدخول بنجاح',
    })


# ─── Logout ──────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """تسجيل الخروج وإبطال الـ refresh token"""
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
    except Exception:
        pass
    return Response({'message': 'تم تسجيل الخروج بنجاح'})


# ─── Profile ─────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """جلب بيانات المستخدم الحالي"""
    serializer = UserSerializer(request.user, context={'request': request})
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """تحديث الملف الشخصي"""
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer = UpdateProfileSerializer(
        request.user, data=request.data, partial=True, context={'request': request}
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.save()
    user_data = UserSerializer(user, context={'request': request}).data
    return Response({'user': user_data, 'message': 'تم تحديث الملف الشخصي بنجاح'})


# ─── Password ────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """تغيير كلمة المرور"""
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(serializer.validated_data['new_password'])
    request.user.save()
    return Response({'message': 'تم تغيير كلمة المرور بنجاح'})


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """طلب إعادة تعيين كلمة المرور"""
    serializer = PasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    try:
        user = User.objects.get(email=email)
        token = secrets.token_urlsafe(32)
        PasswordReset.objects.create(
            user=user, token=token,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        try:
            from .tasks import send_password_reset_email
            send_password_reset_email.delay(user.id, token)
        except Exception:
            pass
    except User.DoesNotExist:
        pass  # لا نكشف إن الإيميل مش موجود

    return Response({'message': 'إذا كان البريد مسجلاً، ستصل رسالة إعادة التعيين.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """تأكيد إعادة تعيين كلمة المرور"""
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    token = serializer.validated_data['token']
    try:
        reset = PasswordReset.objects.get(token=token, is_used=False)
    except PasswordReset.DoesNotExist:
        return Response({'detail': 'رمز غير صالح'}, status=status.HTTP_400_BAD_REQUEST)

    if reset.expires_at < timezone.now():
        return Response({'detail': 'انتهت صلاحية الرمز'}, status=status.HTTP_400_BAD_REQUEST)

    reset.user.set_password(serializer.validated_data['new_password'])
    reset.user.save()
    reset.is_used = True
    reset.save()
    return Response({'message': 'تم إعادة تعيين كلمة المرور بنجاح'})


# ─── Email Verify ─────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """توثيق البريد الإلكتروني"""
    token = request.data.get('token')
    if not token:
        return Response({'detail': 'الرمز مطلوب'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        verification = EmailVerification.objects.get(token=token, is_used=False)
    except EmailVerification.DoesNotExist:
        return Response({'detail': 'رمز غير صالح'}, status=status.HTTP_400_BAD_REQUEST)

    if verification.expires_at < timezone.now():
        return Response({'detail': 'انتهت صلاحية الرمز'}, status=status.HTTP_400_BAD_REQUEST)

    verification.user.is_verified = True
    verification.user.save()
    verification.is_used = True
    verification.save()
    return Response({'message': 'تم توثيق البريد الإلكتروني بنجاح'})


# ─── Token Refresh ────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh(request):
    """تجديد الـ access token"""
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'detail': 'refresh token مطلوب'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        token = RefreshToken(refresh_token)
        return Response({
            'access':  str(token.access_token),
            'refresh': str(token),
        })
    except Exception:
        return Response({'detail': 'refresh token غير صالح'}, status=status.HTTP_401_UNAUTHORIZED)


# ─── Login History ────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def login_history(request):
    """جلب سجل تسجيل الدخول"""
    history = LoginHistory.objects.filter(user=request.user)[:20]
    serializer = LoginHistorySerializer(history, many=True)
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_login_history(request):
    """مسح سجل تسجيل الدخول"""
    LoginHistory.objects.filter(user=request.user).delete()
    return Response({'message': 'تم مسح السجل'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_login_entry(request, entry_id):
    """حذف سجل دخول محدد"""
    try:
        entry = LoginHistory.objects.get(id=entry_id, user=request.user)
        entry.delete()
        return Response({'message': 'تم الحذف'})
    except LoginHistory.DoesNotExist:
        return Response({'detail': 'السجل غير موجود'}, status=status.HTTP_404_NOT_FOUND)


# ─── Delete Account ───────────────────────────────────────────
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_account(request):
    """حذف الحساب نهائياً"""
    request.user.delete()
    return Response({'message': 'تم حذف الحساب نهائياً'})
