from django.shortcuts import render


def handler404(request, exception):
    context = {"breadcrumbs": [{"url": "", "text": "Error code 404"}]}

    return render(request, "404.html", context, status=404)
