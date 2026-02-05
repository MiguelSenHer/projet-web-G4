from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Team

# Internal validation using django before views processing
# cleaning the data and raising ValidationError if needed
# =========================
# LOGIN
# =========================
class LoginForm(forms.Form):
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-input",
            "id": "id_username"
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "id": "id_password"
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        user = authenticate(
            username=cleaned_data.get("username"),
            password=cleaned_data.get("password")
        )
        if not user:
            raise forms.ValidationError("Invalid email or password.")
        cleaned_data["user"] = user
        return cleaned_data


# =========================
# SIGNUP
# =========================
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class SignUpForm(UserCreationForm):
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-input", "id": "id_first_name"})
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-input", "id": "id_last_name"})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-input", "id": "id_email"})
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-input", "id": "id_password1"})
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-input", "id": "id_password2"})
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)

        email = self.cleaned_data["email"].strip().lower()
        user.email = email
        user.username = email
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()

        if commit:
            user.save()

        return user

# =========================
# FORGOT PASSWORD
# =========================
class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-input",
            "id": "id_email"
        })
    )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("No account found with this email.")
        return email


# =========================
# RESET PASSWORD
# =========================
class ResetPasswordForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "id": "id_password"
        }),
        min_length=5
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "id": "id_confirm_password"
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


# =========================
# PROFILE – PERSONAL INFO
# =========================
class ProfileInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={
                "class": "form-input",
                "id": "profile_first_name"
            }),
            "last_name": forms.TextInput(attrs={
                "class": "form-input",
                "id": "profile_last_name"
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-input",
                "id": "profile_email"
            }),
        }


# =========================
# PROFILE – CHANGE PASSWORD
# =========================
class ProfilePasswordForm(forms.Form):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "id": "current_password"
        })
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "id": "new_password"
        }),
        min_length=5
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "id": "confirm_new_password"
        })
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data["old_password"]
        if not self.user.check_password(old_password):
            raise forms.ValidationError("Current password is incorrect.")
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("new_password1") != cleaned_data.get("new_password2"):
            raise forms.ValidationError("New passwords do not match.")
        return cleaned_data

# =========================
# TEAM CREATION FORM
# =========================
class TeamCreateForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name"]