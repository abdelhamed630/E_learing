"""
URLs للحسابات والمصادقة
"""
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # ─── Auth ───────────────────────────────────────────────
    path('register/',                   views.register,                name='register'),
    path('login/',                      views.login_view,              name='login'),
    path('logout/',                     views.logout_view,             name='logout'),
    path('token/refresh/',              views.token_refresh,           name='token-refresh'),

    # ─── Profile ────────────────────────────────────────────
    path('profile/',                    views.get_profile,             name='profile'),
    path('profile/update/',             views.update_profile,          name='profile-update'),

    # ─── Password ───────────────────────────────────────────
    path('password/change/',            views.change_password,         name='password-change'),
    path('password/reset/request/',     views.password_reset_request,  name='password-reset-request'),
    path('password/reset/confirm/',     views.password_reset_confirm,  name='password-reset-confirm'),

    # ─── Email Verification ──────────────────────────────────
    path('verify-email/',               views.verify_email,            name='verify-email'),

    # ─── Login History ──────────────────────────────────────
    path('login-history/',              views.login_history,           name='login-history'),
    path('login-history/clear/',        views.clear_login_history,     name='login-history-clear'),
    path('login-history/<int:entry_id>/delete/', views.delete_login_entry, name='login-history-delete'),

    # ─── Account Management ──────────────────────────────────
    path('delete/',                     views.delete_account,          name='delete-account'),
]
