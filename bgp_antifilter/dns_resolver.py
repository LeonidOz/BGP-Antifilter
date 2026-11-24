"""IPv4 resolution with dnspython and a shared limit on DNS queries."""

from contextlib import contextmanager
import ipaddress
import math
import threading
import time

import dns.exception
import dns.nameserver
import dns.resolver


DEFAULT_TIMEOUT = 3.0
DEFAULT_QPS = 50


class QueryRateLimiter:
    """Space query starts across workers without accumulating idle bursts."""

    def __init__(self, qps=DEFAULT_QPS):
        qps = float(qps)
        if not math.isfinite(qps) or not 1 <= qps <= 1000:
            raise ValueError("DNS_QPS must be between 1 and 1000")
        self.interval = 1.0 / qps
        self._next_query = 0.0
        self._lock = threading.Lock()

    def acquire(self):
        started = time.monotonic()
        # Wait under the lock so delayed workers cannot reserve slots and then
        # send them together after a scheduler pause.
        with self._lock:
            delay = self._next_query - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._next_query = time.monotonic() + self.interval
        return time.monotonic() - started


_default_limiter = QueryRateLimiter()
_worker_state = threading.local()


@contextmanager
def use_rate_limiter(limiter):
    """Use one update's limiter for every DNS lookup in the current worker."""
    previous = getattr(_worker_state, "limiter", None)
    _worker_state.limiter = limiter
    try:
        yield
    finally:
        _worker_state.limiter = previous


class _RateLimitedNameserver(dns.nameserver.Do53Nameserver):
    def __init__(self, address, port, limiter, resolver):
        super().__init__(address, port)
        self._limiter = limiter
        self._resolver = resolver

    def query(self, *args, **kwargs):
        # dnspython calls query() separately for UDP, retries, failover and the
        # TCP retry of a truncated UDP answer, so each consumes one slot.
        waited = self._limiter.acquire()
        # The private resolver belongs to this lookup. Queueing for a QPS slot
        # must not consume its network timeout, particularly at low QPS with
        # many workers. Resolve reads this public lifetime value on each retry.
        self._resolver.lifetime += waited
        return super().query(*args, **kwargs)


def parse_nameservers(value):
    raw = str(value or "").replace(",", " ")
    result = []
    seen = set()
    for item in raw.split():
        address = str(ipaddress.IPv4Address(item))
        if address not in seen:
            seen.add(address)
            result.append(address)
    return result


def resolve_ipv4_addresses(domain, *, nameservers=None, timeout=DEFAULT_TIMEOUT, rate_limiter=None):
    """Resolve A records, preserving the updater's RuntimeError failure API."""
    try:
        return [str(ipaddress.IPv4Address(str(domain).strip()))]
    except ipaddress.AddressValueError:
        pass

    timeout = float(timeout)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("DNS timeout must be a positive finite number")
    limiter = rate_limiter or getattr(_worker_state, "limiter", None) or _default_limiter
    try:
        resolver = dns.resolver.Resolver(configure=False)
        if nameservers:
            addresses = [(str(ipaddress.ip_address(server)), 53) for server in nameservers]
        else:
            system = dns.resolver.get_default_resolver()
            addresses = [
                (server.address, server.port)
                if isinstance(server, dns.nameserver.Do53Nameserver)
                else (str(ipaddress.ip_address(server)), system.nameserver_ports.get(server, system.port))
                for server in system.nameservers
            ]
        resolver.timeout = timeout
        # Allow each configured server a network timeout. Queue waiting is
        # added by _RateLimitedNameserver, independently of this budget.
        resolver.lifetime = timeout * max(1, len(addresses))
        resolver.nameservers = [
            _RateLimitedNameserver(address, port, limiter, resolver)
            for address, port in addresses
        ]
        answer = resolver.resolve(domain, "A", search=False)
        return sorted({str(record.address) for record in answer})
    except (dns.exception.DNSException, OSError, ValueError) as exc:
        raise RuntimeError(str(exc)) from exc


def query_a_records(domain, nameserver, *, timeout=DEFAULT_TIMEOUT, rate_limiter=None):
    """Resolve through one explicit nameserver using the same transport."""
    return resolve_ipv4_addresses(
        domain, nameservers=[nameserver], timeout=timeout, rate_limiter=rate_limiter,
    )
