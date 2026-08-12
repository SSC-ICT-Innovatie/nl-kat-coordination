# utility functions for converting requests to HAR format


import urllib.parse
from collections.abc import Iterable, Sequence
from datetime import datetime
from http.cookiejar import Cookie
from http.cookies import SimpleCookie
from typing import Any, AnyStr

import requests
import requests.cookies


def create_har_object(response: requests.Response) -> dict:
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "kat_webpage_analysis", "version": "0.1"},
            "browser": {"name": "requests", "version": requests.__version__},
            "entries": [
                {
                    "startedDateTime": datetime.now().astimezone().isoformat(),
                    "time": 0,
                    "request": map_request(response.request),
                    "response": map_response(response),
                    "cache": {},
                    "timings": {"send": 0, "wait": 0, "receive": 0},
                }
            ],
        }
    }


def map_request(request: requests.PreparedRequest) -> dict:
    def cookies_from_request(cookies: str | None) -> Sequence[dict]:
        simple_cookie = SimpleCookie(cookies)
        return [{"name": key, "value": value.value} for key, value in simple_cookie.items()]

    def query_from_url(url: str) -> list[tuple[AnyStr, AnyStr]]:
        return urllib.parse.parse_qsl(urllib.parse.urlparse(url).query)  # type: ignore

    return_value: dict[str, Any] = {
        "method": request.method,
        "url": request.url,
        "httpVersion": "HTTP/1.1",
        "cookies": cookies_from_request(request.headers.get("Cookie")),
        "queryString": _name_value_pairs(query_from_url(str(request.url))),
        "headers": _name_value_pairs(request.headers.items()),
        "headersSize": -1,
        "bodySize": -1,
    }

    if request.body:
        mime_type = request.headers.get("Content-Type")
        if mime_type == "application/x-www-form-urlencoded":
            text = request.body
            params = urllib.parse.parse_qsl(str(text))
            return_value["postData"] = {"mimeType": mime_type, "params": _name_value_pairs(params), "text": text}

    return return_value


def map_response(response: requests.Response) -> dict:
    return {
        "status": response.status_code,
        "statusText": response.reason,
        "httpVersion": "HTTP/1.1",
        "cookies": [map_cookie(cookie) for cookie in response.cookies],
        "headers": _name_value_pairs(response.headers.items()),
        "content": {
            "size": len(response.content),
            "mimeType": response.headers.get("content-type", "text/html"),
            "text": response.text,
        },
        "redirectURL": response.url,
        "headersSize": -1,
        "bodySize": 0,
    }


def map_cookie(cookie: Cookie) -> dict:
    return {
        "name": cookie.name,
        "value": cookie.value,
        "path": cookie.path,
        "domain": cookie.domain,
        "expires": (datetime.fromtimestamp(cookie.expires).astimezone().isoformat() if cookie.expires else None),
        "httpOnly": cookie._rest.get("HttpOnly", False),  # type: ignore
        "secure": cookie.secure,
        "comment": cookie.comment or "",
    }


def _name_value_pairs(iterable: Iterable) -> Sequence[dict]:
    return [{"name": key, "value": value} for key, value in iterable]
