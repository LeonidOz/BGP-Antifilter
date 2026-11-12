"""HTTP transport, custom DNS, retry policy and source cache handling."""

import hashlib
import http.client
import ipaddress
import os
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit

from .. import dns_resolver, generate_routes
from ..logging import progress

DEFAULT_DNS_HTTP_REDIRECTS = 5


class CustomDnsHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, connect_host, connect_port, *, server_hostname, timeout):
        super().__init__(server_hostname, connect_port, timeout=timeout)
        self._connect_host = connect_host

    def connect(self):
        sock = socket.create_connection((self._connect_host, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def cache_path(cache_dir, namespace, value, suffix=".cache"):
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{namespace}-{digest}{suffix}"


def cache_age(cache_file, now):
    if not cache_file.exists():
        return None
    return max(0, int(now - cache_file.stat().st_mtime))


def read_cache(cache_file, now, max_age):
    age = cache_age(cache_file, now)
    if age is None or age > max_age or cache_file.stat().st_size == 0:
        return None, age
    return cache_file.read_text(encoding="utf-8"), age


def fetch_via_custom_dns(url, *, timeout, nameservers):
    current_url = url
    headers = {"User-Agent": "BGP-Antifilter/1.0"}

    for _ in range(DEFAULT_DNS_HTTP_REDIRECTS + 1):
        parts = urlsplit(current_url)
        if parts.scheme not in {"http", "https"}:
            raise RuntimeError(f"unsupported URL scheme: {parts.scheme}")
        if not parts.hostname:
            raise RuntimeError("URL hostname is required")

        port = parts.port or (443 if parts.scheme == "https" else 80)
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"

        addresses = dns_resolver.resolve_ipv4_addresses(parts.hostname, nameservers=nameservers, timeout=timeout)
        if not addresses:
            raise RuntimeError(f"no IPv4 addresses returned for {parts.hostname}")
        address = addresses[0]

        if parts.scheme == "https":
            connection = CustomDnsHTTPSConnection(
                address,
                port,
                server_hostname=parts.hostname,
                timeout=timeout,
            )
        else:
            connection = http.client.HTTPConnection(address, port, timeout=timeout)
        try:
            connection.putrequest("GET", path, skip_host=True)
            host_header = parts.hostname if parts.port is None else f"{parts.hostname}:{parts.port}"
            connection.putheader("Host", host_header)
            for key, value in headers.items():
                connection.putheader(key, value)
            connection.endheaders()
            response = connection.getresponse()
            status = response.status

            if status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                response.read()
                if not location:
                    raise RuntimeError(f"redirect {status} without Location header")
                current_url = urljoin(current_url, location)
                continue

            if status >= 400:
                body = response.read(200).decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP Error {status}: {body or response.reason}")

            return response.read().decode("utf-8", errors="replace").replace("\r", "")
        finally:
            connection.close()

    raise RuntimeError("too many HTTP redirects")


def fetch_url(url, timeout=None, attempts=None, delay=None, progress_callback=None, dns_nameservers=None):
    timeout = int(os.environ.get("FETCH_TIMEOUT", "30")) if timeout is None else timeout
    attempts = int(os.environ.get("FETCH_ATTEMPTS", "5")) if attempts is None else attempts
    delay = float(os.environ.get("FETCH_RETRY_DELAY", "5")) if delay is None else delay
    last_error = None
    request = urllib.request.Request(url, headers={"User-Agent": "BGP-Antifilter/1.0"})

    for attempt in range(attempts):
        if progress_callback is not None:
            progress_callback(attempt + 1, attempts)
        try:
            if dns_nameservers:
                return fetch_via_custom_dns(url, timeout=timeout, nameservers=dns_nameservers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace").replace("\r", "")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        except RuntimeError as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(delay)

    raise RuntimeError(str(last_error))


def count_source_routes(text, *, extract=True):
    count = 0
    for line in text.splitlines():
        values = generate_routes.IPV4_RE.findall(line) if extract else [line.strip()]
        for value in values:
            if not value:
                continue
            if "/" not in value:
                value = f"{value}/32"
            try:
                ipaddress.ip_network(value, strict=False)
            except ValueError:
                continue
            count += 1
    return count


def fetch_text_source(kind, name, url, cache_file, now, max_age, progress_callback=None, dns_nameservers=None):
    record = {
        "kind": kind,
        "name": name,
        "url": url,
        "cache_file": str(cache_file),
        "status": "unknown",
        "cache_age_seconds": None,
        "error": None,
        "bytes": 0,
        "routes": 0,
    }

    try:
        text = fetch_url(url, progress_callback=progress_callback, dns_nameservers=dns_nameservers)
        cache_file.write_text(text, encoding="utf-8")
        record["status"] = "fresh"
        record["bytes"] = len(text.encode("utf-8"))
        record["routes"] = count_source_routes(text)
        record["cache_age_seconds"] = 0
        progress("fetched source", kind=kind, name=name, status="fresh")
        return text, record, True
    except RuntimeError as exc:
        text, age = read_cache(cache_file, now, max_age)
        record["cache_age_seconds"] = age

        if text is not None:
            record["status"] = "cache"
            record["error"] = str(exc)
            record["bytes"] = len(text.encode("utf-8"))
            record["routes"] = count_source_routes(text)
            progress("using cached source", kind=kind, name=name, status="cache", cache_age_seconds=age)
            return text, record, True

        record["status"] = "failed"
        record["error"] = str(exc) if age is None else f"{exc}; cache expired after {age} seconds"
        progress("source failed without usable cache", kind=kind, name=name, status="failed")
        return "", record, False
