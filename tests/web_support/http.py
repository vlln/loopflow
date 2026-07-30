from __future__ import annotations

import http.client
import json
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


class JsonHttpClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def request(self, method: str, path: str, body: Any = None) -> HttpResponse:
        headers = {"Accept": "application/json"}
        encoded = None
        if body is not None:
            encoded = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            connection.request(method, path, body=encoded, headers=headers)
            response = connection.getresponse()
            return HttpResponse(
                status=response.status,
                headers={key.lower(): value for key, value in response.getheaders()},
                body=response.read(),
            )
        finally:
            connection.close()


def parse_sse(lines: Iterable[bytes]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    data: list[str] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if current or data:
                if data:
                    current["data"] = "\n".join(data)
                events.append(current)
            current = {}
            data = []
        elif line.startswith(":"):
            continue
        else:
            field, separator, value = line.partition(":")
            if separator and value.startswith(" "):
                value = value[1:]
            if field == "data":
                data.append(value)
            elif field in {"id", "event", "retry"}:
                current[field] = value
    return events


def split_sse_buffer(buffer: bytes) -> tuple[list[dict[str, str]], bytes]:
    """Split a streaming SSE buffer into complete events and the incomplete tail.

    Events are framed by blank lines; the remainder (a partial event without its
    terminating blank line) is returned for the next chunk.
    """
    events: list[dict[str, str]] = []
    while True:
        indexes = [index for sep in (b"\r\n\r\n", b"\n\n") if (index := buffer.find(sep)) >= 0]
        if not indexes:
            return events, buffer
        index = min(indexes)
        frame = buffer[:index]
        buffer = buffer[index:].lstrip(b"\r\n")
        events.extend(parse_sse([*frame.splitlines(), b""]))
