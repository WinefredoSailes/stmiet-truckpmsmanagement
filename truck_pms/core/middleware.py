import time
from django.db import connection
from django.conf import settings


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration = (time.time() - start) * 1000
        if settings.DEBUG and connection.queries:
            db_time = sum(float(q['time']) for q in connection.queries) * 1000
            print(f'  [{duration:7.0f}ms | {db_time:5.0f}ms db | {len(connection.queries)} queries] {request.method} {request.path}')
        else:
            print(f'  [{duration:7.0f}ms] {request.method} {request.path}')
        return response
