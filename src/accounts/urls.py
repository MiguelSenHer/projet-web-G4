from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("forgot-password/", views.forgot_password_view, name="forgot-password"),
    path("forgot-password/sent/", views.password_reset_sent_view, name="password-reset-sent"),
    path("reset-password/<uuid:reset_id>/", views.reset_password_view, name="reset-password"),

    path("profile/", views.profile_view, name="profile"),
    path("teams/", views.teams_view, name="teams"),
    path("teams/create/", views.teams_create_view, name="teams_create"),
]
