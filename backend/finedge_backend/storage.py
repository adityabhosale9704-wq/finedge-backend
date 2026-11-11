"""URLs for existing paths relative to MEDIA_ROOT."""
from django.conf import settings


def build_doc_url(request, file_path):
    if not file_path:
        return ""
    url = settings.MEDIA_URL + file_path
    if request is not None:
        return request.build_absolute_uri(url)
    return url
