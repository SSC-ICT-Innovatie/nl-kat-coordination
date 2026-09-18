from account.models import KATUser
from django.conf import settings

from rocky.version import __version__


def feature_flags(request):
    context = {}
    for name in dir(settings):
        if name.startswith("FEATURE_"):
            context[name] = getattr(settings, name)
    return context


def languages(request):
    current = getattr(request, "LANGUAGE_CODE", settings.LANGUAGE_CODE)
    path = request.get_full_path()
    if path.startswith(f"/{current}/"):
        path = path[len(current) + 1 :]
    else:
        # Not a language-prefixed URL: link to the language root instead
        path = "/"
    return {"language_links": [(code, f"/{code}{path}") for code, _ in settings.LANGUAGES]}


def organizations_including_blocked(request):
    context = {}
    if isinstance(request.user, KATUser):
        context["organizations_including_blocked"] = request.user.organizations_including_blocked
    return context


def rocky_version(request):
    context = {"rocky_version": __version__}
    return context
