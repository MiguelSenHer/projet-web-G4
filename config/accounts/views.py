from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from .forms import SignUpForm


def signup_view(request):
    """Handle user registration."""
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('profile')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Automatically log in the user after registration
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, 'Account created successfully!')
                return redirect('profile')
        else:
            return render(
                request,
                "accounts/signup.html",
                {
                    'form': form,
                    'errors': form.errors,
                    'active_page': 'profile',
                },
            )
    else:
        form = SignUpForm()

    return render(
        request,
        "accounts/signup.html",
        {
            'form': form,
            'active_page': 'profile',
        },
    )


@login_required
def profile_view(request):
    """Display and handle profile updates."""
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        # ======================
        # Change password
        # ======================
        if form_type == 'change_password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(
                    request,
                    'Your password has been successfully updated!'
                )
                return redirect('profile')
            else:
                for field, errors in password_form.errors.items():
                    for error in errors:
                        messages.error(request, f'Password error: {error}')

                return render(
                    request,
                    "accounts/profile.html",
                    {
                        'user': request.user,
                        'password_form': password_form,
                        'active_page': 'profile',
                    },
                )

        # ======================
        # Update personal info
        # ======================
        elif form_type == 'personal_info':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip().lower()

            # Validate email uniqueness
            if email != request.user.email:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                if User.objects.filter(email__iexact=email).exists():
                    messages.error(
                        request,
                        'This email is already in use. '
                        'Please choose a different one.'
                    )
                    return redirect('profile')

            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.username = email
            request.user.save()

            messages.success(
                request,
                'Your personal information has been successfully updated!'
            )
            return redirect('profile')

    # ======================
    # GET request
    # ======================
    return render(
        request,
        "accounts/profile.html",
        {
            'user': request.user,
            'active_page': 'profile',
        },
    )
