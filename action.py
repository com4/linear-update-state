#!/usr/bin/env python3
from dataclasses import dataclass
import json
import os
import ssl
import sys
from time import sleep
from typing import Optional
import urllib.error
import urllib.request

GH_TOKEN = os.getenv("GITHUB_TOKEN", None)
GH_API_URL_BASE = os.getenv("GITHUB_API_URL", None)
GH_REPO_PATH = os.getenv("GITHUB_REPOSITORY", None)

GH_API_URL = f"{GH_API_URL_BASE}/repos/{GH_REPO_PATH}"

class HttpError(Exception):
    """Describe an unrecoverable HTTP error."""

    def __init__(
        self,
        msg: str,
        status_code: Optional[int],
        body: bytes,
    ):
        self.status_code = status_code
        self.body = body
        super().__init__(msg)


@dataclass
class HttpResponse:
    """Describe the response from an HTTP request."""

    status_code: int
    headers: dict[str, str]
    body: bytes


def make_request(
    *,
    url: str,
    data: Optional[bytes] = None,
    headers: Optional[dict[str, str]] = None,
    method: Optional[str] = None,
    num_retries: int = 3,
    ssl_compat_mode: bool = False,
) -> HttpResponse:
    """Make an HTTP request.

    Args:
        url: The full URL to make the request to (including https://).
        data: The data to send with the request. (Note: this makes
            the default method ``POST``)
        headers: Dictionary of additional request headers to send. By
            default Content-Type is set to
            ``application/json; charset=utf8`` if it left undefined.
        method: The HTTP method to send. i.e. GET, POST, etc
            *Default is GET*
        num_retries: number of times to retry sending when the
            request fails
        ssl_compat_mode: If True, it'll use a less secure SSL for
            older servers.

    """
    if headers is None:
        headers = {}

    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json; charset=utf8"

    if ssl_compat_mode:
        # for our older or poorly configured server friends
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        ssl_context.set_ciphers("DEFAULT:!DH")
    else:
        ssl_context = ssl.create_default_context()

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl_context)
    )

    retry_count = 0
    while True:
        try:
            _r = opener.open(request)
            response = HttpResponse(
                status_code=_r.status,
                headers={k: v for k, v in _r.headers.items()},
                body=_r.read(),
            )
        except urllib.error.HTTPError as e:
            body = e.read()

            if e.status is None:
                raise HttpError(
                    f"Unknown HTTP error: {e}",
                    status_code=e.status,
                    body=body,
                ) from None

            if e.status == 429 or (e.status >= 500 and e.status < 600):
                # Server error (or rate limit), retry with exponential backoff
                retry_count += 1
                if retry_count > num_retries:
                    raise HttpError(
                        "Retries Exceeded",
                        status_code=e.status,
                        body=body,
                    ) from None

                wait_for = 2**retry_count

                sleep(wait_for * 60)
                continue
            elif e.status >= 400 and e.status < 500:
                # Unrecoverable client error.
                err_msg = f"HTTP Error {e.status}"
                if e.status == 404:
                    # It is helpful to see the requested url for a 404
                    err_msg = f"{err_msg} {url}"
                raise HttpError(
                    err_msg,
                    status_code=e.status,
                    body=body,
                ) from None
            else:
                # Unknown error. If a case is found by this block then it
                # probably needs to added.
                raise HttpError(
                    f"Unknown HTTP Error {e.status}",
                    status_code=e.status,
                    body=body,
                ) from None

        if response.status_code >= 300 and response.status_code < 400:
            # Location moved.
            return make_request(
                url=response.headers["Location"],
                data=data,
                headers=headers,
                method=method,
            )
        return response

if __name__ == "__main__":
    from pprint import pprint
    print(f"Requesting {GH_API_URL}/pulls?state=closed")
    response = make_request(
        url=f"{GH_API_URL}/pulls?state=closed"
    )
    pprint(response)
