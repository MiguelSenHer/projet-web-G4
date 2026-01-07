from django.shortcuts import render

def login_view(request):
    """Display the login page."""
    return render(request, "accounts/login.html")
