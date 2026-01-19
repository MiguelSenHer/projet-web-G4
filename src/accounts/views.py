from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse

from .forms import SignUpForm  # your signup form that renders in template
from .models import PasswordReset

User = get_user_model()


# -----------------------
# SIGNUP
# -----------------------
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("profile")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():

            # (if username == email)
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password")
            user_auth = authenticate(request, username=email,
                                     password=password)
            if user_auth is not None:
                login(request, user_auth)
                messages.success(request, "Account created successfully!")
                return redirect("profile")

            messages.success(request, "Account created. Please login.")
            return redirect("login")

        return render(request, "accounts/signup.html", {"form": form})

    form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


# -----------------------
# LOGIN
# (your login.html uses raw inputs name=username/password)
# -----------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect("profile")

    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()  # you use email here
        password = request.POST.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get("next")
            return redirect(next_url) if next_url else redirect("profile")

        messages.error(request, "Invalid email or password. Please try again.")
        return redirect("login")

    return render(request, "accounts/login.html")


# -----------------------
# LOGOUT
# -----------------------
def logout_view(request):
    logout(request)
    return redirect("login")


# -----------------------
# FORGOT PASSWORD
# -----------------------
def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect("profile")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if not email:
            messages.error(request, "Please enter an email address.")
            return redirect("forgot-password")

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            messages.error(request, f"No account found with email '{email}'.")
            return redirect("forgot-password")

        reset = PasswordReset.objects.create(user=user)

        reset_url = request.build_absolute_uri(
            reverse("reset-password", kwargs={"reset_id": reset.reset_id})
        )

        EmailMessage(
            "Reset your password",
            f"Reset your password using the link below:\n\n{reset_url}\n\n"
            "This link expires in 10 minutes.",
            settings.EMAIL_HOST_USER,
            [email],
        ).send(fail_silently=False)

        return redirect("password-reset-sent")

    return render(request, "accounts/forgot_password.html")


# -----------------------
# RESET EMAIL SENT
# -----------------------
def password_reset_sent_view(request):
    return render(request, "accounts/password_reset_sent.html")


# -----------------------
# RESET PASSWORD
# -----------------------
def reset_password_view(request, reset_id):
    reset = PasswordReset.objects.filter(reset_id=reset_id).first()
    if not reset:
        messages.error(request, "Invalid reset link.")
        return redirect("forgot-password")

    if reset.is_expired(minutes=10):
        reset.delete()
        messages.error(request, "Reset link has expired. Please request a new one.")
        return redirect("forgot-password")

    if request.method == "POST":
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return redirect("reset-password", reset_id=reset_id)

        if len(password) < 5:
            messages.error(request,
                           "Password must be at least 5 characters long.")
            return redirect("reset-password", reset_id=reset_id)

        user = reset.user
        user.set_password(password)
        user.save()
        reset.delete()

        messages.success(request, "Password reset. Proceed to login.")
        return redirect("login")

    return render(request, "accounts/reset_password.html")


# -----------------------
# PROFILE (template has TWO raw forms with form_type)
# Important to signal which one is submitted to avoid confusion
# -----------------------
@login_required
def profile_view(request):
    if request.method == "POST":
        form_type = request.POST.get("form_type")

        # change password block (uses Django built-in form)
        if form_type == "change_password":
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # to keep session active
                messages.success(request, "Your password has been successfully updated!")
                return redirect("profile")

            for field, errs in password_form.errors.items():
                for err in errs:
                    messages.error(request, err)
            return redirect("profile")

        # personal info block
        if form_type == "personal_info":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip().lower()

            if not first_name or not last_name or not email:
                messages.error(request, "Please fill in all required fields.")
                return redirect("profile")

            # unique email check
            if email != request.user.email:
                if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
                    messages.error(request, "This email is already in use. Please choose a different one.")
                    return redirect("profile")

            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.username = email
            request.user.save()

            messages.success(request,
                            "Your personal information has been successfully updated!")
            return redirect("profile")

    return render(request, "accounts/profile.html", {"user": request.user})


# -----------------------
# TEAMS PAGES
# -----------------------
@login_required
def teams_view(request):
    return render(request, "accounts/teams.html")


@login_required
def teams_create_view(request):
    return render(request, "accounts/teams_create.html")
