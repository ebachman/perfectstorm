import logging
import time


logger = logging.getLogger('stormcore.request')


class RequestLogMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        request_time = time.time() - start

        if response.status_code < 400:
            level = logging.DEBUG
        elif response.status_code < 500:
            level = logging.WARNING
        else:
            level = logging.ERROR

        logger.log(
            level, '%s %s %s (%s) %.2fms',
            response.status_code, request.method, request.get_full_path(),
            request.META['REMOTE_ADDR'], request_time * 1000)
        return response
