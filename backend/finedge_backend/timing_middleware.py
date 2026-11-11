"""Diagnostic-only request timing middleware (perf/speed-up investigation).

Purpose: find out which endpoints are actually slow, with real numbers,
instead of guessing. This middleware does NOT change any request/response
behavior, URL, or JSON shape — it only:
  1. Logs "<method> <path> -> <status> in <ms> ms" to Django's logger
     (visible via `journalctl -u gunicorn` on the server).
  2. Adds a `Server-Timing: total;dur=<ms>` response header, which Chrome/
     Firefox DevTools' Network tab reads automatically and shows per-request
     — no extra tooling needed to see it.

Safe to deploy: purely additive, no behavior change, can be removed by
deleting one line from MIDDLEWARE in settings.py.
"""

import logging
import time

logger = logging.getLogger("finedge.timing")


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response["Server-Timing"] = f"total;dur={duration_ms:.1f}"
        logger.info(
            "%s %s -> %s in %.1f ms",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response
