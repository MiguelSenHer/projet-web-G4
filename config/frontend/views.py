from django.shortcuts import render


def home(request):
    return render(request, "frontend/template.html")

def assembly(request):
    return render(request, "frontend/assembly.html")
