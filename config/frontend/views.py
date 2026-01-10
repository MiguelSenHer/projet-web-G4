from django.shortcuts import render


def home(request):
    return render(
        request,
        "frontend/template.html",
        {
            "active_page": "home",
        },
    )
