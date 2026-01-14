from django.urls import path
from django.contrib.auth import views as auth_views
from .views import CustomLoginView 
from . import views

urlpatterns = [
    path(
        "login/",
        CustomLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    path("signup/", views.signup_view, name="signup"),
    path("profile/", views.profile_view, name="profile"),
    path("teams/", views.teams, name="teams"),
    path("teams_create/", views.teams_create, name="teams_create"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
    template_name="accounts/password_reset.html"
    ), name="password_reset"),

]