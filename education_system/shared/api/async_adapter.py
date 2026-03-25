"""Async API adapter for education system Flask apps.

Provides utilities to run blocking operations (DB queries, file I/O)
off the main thread, and an async-capable server runner.

Usage in route handlers:
    from education_system.shared.api.async_adapter import run_in_executor, async_route

    # Option 1: Wrap a specific blocking call
    @app.route("/api/v1/college/reports/full")
    def full_report():
        result = run_in_executor_sync(service.generate_large_report)
        return jsonify(result)

    # Option 2: Use the async runner for the entire app
    from education_system.shared.api.async_adapter import AsyncFlaskRunner
    runner = AsyncFlaskRunner(app, workers=8)
    runner.run(host="0.0.0.0", port=5000)
"""

import asyncio
import logging
import functools
from concurrent.futures import ThreadPoolExecutor, Future

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=8)


async def run_in_executor(func, *args, **kwargs):
    """Run a synchronous function in a thread pool (async version).

    Useful for wrapping blocking database calls in async routes.

    Usage:
        result = await run_in_executor(student_service.list_students)
    """
    loop = asyncio.get_event_loop()
    if kwargs:
        return await loop.run_in_executor(_executor, functools.partial(func, *args, **kwargs))
    return await loop.run_in_executor(_executor, func, *args)


def run_in_executor_sync(func, *args, **kwargs) -> Future:
    """Submit a blocking function to the thread pool (sync version).

    Returns a concurrent.futures.Future. Call .result() to get the value.
    Useful in standard Flask routes for CPU/IO-heavy operations.

    Usage:
        future = run_in_executor_sync(service.generate_report)
        # ... do other work ...
        result = future.result(timeout=30)
    """
    if kwargs:
        return _executor.submit(functools.partial(func, *args, **kwargs))
    return _executor.submit(func, *args)


def make_async_handler(sync_handler):
    """Wrap a synchronous Flask-style handler in an async wrapper.

    Usage:
        @app.route("/api/students")
        @make_async_handler
        def list_students():
            return jsonify(service.list_students())
    """
    async def wrapper(*args, **kwargs):
        return await run_in_executor(sync_handler, *args, **kwargs)
    wrapper.__name__ = sync_handler.__name__
    wrapper.__doc__ = sync_handler.__doc__
    return wrapper


def configure_executor(max_workers: int = 8) -> None:
    """Reconfigure the thread pool with a different worker count."""
    global _executor
    _executor.shutdown(wait=False)
    _executor = ThreadPoolExecutor(max_workers=max_workers)
    logger.info("Thread pool reconfigured with %d workers", max_workers)


class AsyncFlaskRunner:
    """Run a Flask app using aiohttp for better concurrency.

    Falls back to standard Flask dev server if aiohttp is unavailable.
    Useful for long-running operations like report generation and bulk exports.

    Usage:
        runner = AsyncFlaskRunner(app, workers=8)
        runner.run(host="0.0.0.0", port=5000)
    """

    def __init__(self, flask_app, workers: int = 8):
        self.flask_app = flask_app
        configure_executor(workers)

    def run(self, host: str = "127.0.0.1", port: int = 5000, **kwargs):
        """Run the app with async support if available."""
        try:
            from aiohttp import web

            async def aiohttp_handler(aio_request):
                """Bridge aiohttp requests to Flask WSGI."""
                import io
                import sys
                body = await aio_request.read()

                environ = {
                    "REQUEST_METHOD": aio_request.method,
                    "PATH_INFO": aio_request.path,
                    "QUERY_STRING": aio_request.query_string,
                    "CONTENT_TYPE": aio_request.content_type or "",
                    "CONTENT_LENGTH": str(len(body)),
                    "SERVER_NAME": host,
                    "SERVER_PORT": str(port),
                    "wsgi.input": io.BytesIO(body),
                    "wsgi.errors": sys.stderr,
                    "wsgi.url_scheme": "http",
                }
                for key, value in aio_request.headers.items():
                    environ[f"HTTP_{key.upper().replace('-', '_')}"] = value

                response_started = []
                response_body = []

                def start_response(status, headers, exc_info=None):
                    response_started.append((status, headers))

                result = self.flask_app(environ, start_response)
                for data in result:
                    response_body.append(data)

                if response_started:
                    status_code = int(response_started[0][0].split(" ")[0])
                    resp = web.Response(
                        body=b"".join(response_body),
                        status=status_code,
                    )
                    for name, value in response_started[0][1]:
                        resp.headers[name] = value
                    return resp

                return web.Response(text="Internal Error", status=500)

            app = web.Application()
            app.router.add_route("*", "/{path_info:.*}", aiohttp_handler)

            logger.info("Starting async server on %s:%d (aiohttp, %d workers)",
                        host, port, _executor._max_workers)
            print(f"  Async mode enabled (aiohttp, {_executor._max_workers} workers)")
            web.run_app(app, host=host, port=port, **kwargs)

        except ImportError:
            logger.info("aiohttp not available, falling back to Flask dev server")
            self.flask_app.run(host=host, port=port, **kwargs)
