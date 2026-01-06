from django.shortcuts import render
from django.http import HttpResponse

def simulator_home(request):
    options = [
        {"label": "LOAD YOUR PLASMID ASSEMBLY TEMPLATE", "url": "/campaigns/simulator/load/"},
        {"label": "BROWSE PLASMID ASSEMBLY TEMPLATE", "url": "/campaigns/simulator/browse/"},
    ]
    return render(request, "campaigns/template.html", {"options": options})

def load_template(request):
    # Page placeholder (on fera l'upload ensuite)
    return render(request, "campaigns/load.html")

def browse_templates(request):
    # Page placeholder (on fera la liste ensuite)
    return render(request, "campaigns/browse.html")
