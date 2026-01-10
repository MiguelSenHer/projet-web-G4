from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from . import views

def login_redirect_if_authenticated(view_func):
    """Decorator to redirect authenticated users away from login page."""
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('profile')
        return view_func(request, *args, **kwargs)
    return wrapper

class CustomLoginView(auth_views.LoginView):
    """Login view that redirects authenticated users."""
    template_name = "accounts/login.html"
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

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
]

