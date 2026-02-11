from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Team

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
