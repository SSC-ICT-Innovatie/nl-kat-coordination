from django.shortcuts import render


def handler403(request, exception):
    context = {"breadcrumbs": [{"url": "", "text": "Error code 403"}]}

    return render(request, "403.html", context, status=403)
