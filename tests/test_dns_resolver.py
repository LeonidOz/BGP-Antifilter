from concurrent.futures import ThreadPoolExecutor
import threading
import time
import unittest
from unittest import mock

import dns.exception
import dns.message
import dns.rcode
import dns.resolver
import dns.rrset

from bgp_antifilter import dns_resolver


class CountingLimiter:
    def __init__(self, delay=0):
        self.calls = 0
        self.delay = delay

    def acquire(self):
        self.calls += 1
        started = time.monotonic()
        if self.delay:
            time.sleep(self.delay)
        return time.monotonic() - started


def address_response(request, *_args, **_kwargs):
    response = dns.message.make_response(request)
    response.answer.append(dns.rrset.from_text(request.question[0].name, 60, "IN", "A", "203.0.113.10"))
    return dns.message.from_wire(response.to_wire())


class DnsResolverTests(unittest.TestCase):
    def resolve(self, **kwargs):
        return dns_resolver.resolve_ipv4_addresses(
            "example.test", nameservers=["192.0.2.53"], **kwargs,
        )

    def test_cname_uses_only_the_matching_answer(self):
        def response(request, *_args, **_kwargs):
            result = dns.message.make_response(request)
            result.answer.extend([
                dns.rrset.from_text("example.test.", 60, "IN", "CNAME", "target.test."),
                dns.rrset.from_text("target.test.", 60, "IN", "A", "203.0.113.11", "203.0.113.10"),
            ])
            result.additional.append(dns.rrset.from_text("unrelated.test.", 60, "IN", "A", "192.0.2.99"))
            return dns.message.from_wire(result.to_wire())

        limiter = CountingLimiter()
        with mock.patch("dns.query.udp", side_effect=response):
            self.assertEqual(self.resolve(rate_limiter=limiter), ["203.0.113.10", "203.0.113.11"])
        self.assertEqual(limiter.calls, 1)

    def test_nxdomain_and_missing_a_record_keep_cache_failure_contract(self):
        for rcode, exception in [(dns.rcode.NXDOMAIN, dns.resolver.NXDOMAIN), (dns.rcode.NOERROR, dns.resolver.NoAnswer)]:
            with self.subTest(rcode=rcode):
                def response(request, *_args, **_kwargs):
                    result = dns.message.make_response(request)
                    result.set_rcode(rcode)
                    return result

                with mock.patch("dns.query.udp", side_effect=response):
                    with self.assertRaises(RuntimeError) as error:
                        self.resolve(rate_limiter=CountingLimiter())
                self.assertIsInstance(error.exception.__cause__, exception)

    def test_tcp_retry_of_truncated_udp_answer_consumes_another_slot(self):
        limiter = CountingLimiter()
        with mock.patch("dns.query.udp", side_effect=dns.message.Truncated) as udp:
            with mock.patch("dns.query.tcp", side_effect=address_response) as tcp:
                self.assertEqual(self.resolve(rate_limiter=limiter), ["203.0.113.10"])
        self.assertEqual((udp.call_count, tcp.call_count, limiter.calls), (1, 1, 2))

    def test_failed_nameserver_consumes_a_slot_before_failover(self):
        for failure in ("servfail", "timeout"):
            with self.subTest(failure=failure):
                limiter = CountingLimiter()
                calls = []

                def response(request, where, **kwargs):
                    calls.append(where)
                    if where == "192.0.2.53":
                        if failure == "timeout":
                            raise dns.exception.Timeout
                        result = dns.message.make_response(request)
                        result.set_rcode(dns.rcode.SERVFAIL)
                        return result
                    return address_response(request)

                with mock.patch("dns.query.udp", side_effect=response):
                    result = dns_resolver.resolve_ipv4_addresses(
                        "example.test", nameservers=["192.0.2.53", "192.0.2.54"], rate_limiter=limiter,
                    )
                self.assertEqual(result, ["203.0.113.10"])
                self.assertEqual(calls, ["192.0.2.53", "192.0.2.54"])
                self.assertEqual(limiter.calls, 2)

    def test_waiting_for_qps_does_not_exhaust_failover_timeout(self):
        limiter = CountingLimiter(delay=0.04)

        def response(request, where, **kwargs):
            if where == "192.0.2.53":
                result = dns.message.make_response(request)
                result.set_rcode(dns.rcode.SERVFAIL)
                return result
            return address_response(request)

        with mock.patch("dns.query.udp", side_effect=response):
            result = dns_resolver.resolve_ipv4_addresses(
                "example.test", nameservers=["192.0.2.53", "192.0.2.54"],
                timeout=0.01, rate_limiter=limiter,
            )
        self.assertEqual(result, ["203.0.113.10"])
        self.assertEqual(limiter.calls, 2)

    def test_system_resolver_uses_dnspython_and_same_limiter(self):
        system = dns.resolver.Resolver(configure=False)
        system.nameservers = ["192.0.2.53"]
        system.nameserver_ports = {"192.0.2.53": 5353}
        limiter = CountingLimiter()
        with mock.patch("dns.resolver.get_default_resolver", return_value=system):
            with mock.patch("dns.query.udp", side_effect=address_response) as query:
                with mock.patch("socket.getaddrinfo", side_effect=AssertionError("libc DNS was used")):
                    result = dns_resolver.resolve_ipv4_addresses("example.test", timeout=0.5, rate_limiter=limiter)
        self.assertEqual(result, ["203.0.113.10"])
        self.assertEqual(query.call_args.args[1], "192.0.2.53")
        self.assertEqual(query.call_args.kwargs["port"], 5353)
        self.assertLessEqual(query.call_args.kwargs["timeout"], 0.5)
        self.assertEqual(limiter.calls, 1)

    def test_literal_ipv4_skips_resolver_and_limiter(self):
        limiter = CountingLimiter()
        with mock.patch("dns.resolver.Resolver", side_effect=AssertionError("literal queried")):
            self.assertEqual(dns_resolver.resolve_ipv4_addresses("203.0.113.10", rate_limiter=limiter), ["203.0.113.10"])
        self.assertEqual(limiter.calls, 0)

    def test_thread_context_can_share_limiter_and_restores_outer_context(self):
        outer, inner = CountingLimiter(), CountingLimiter()
        with mock.patch("dns.query.udp", side_effect=address_response):
            with dns_resolver.use_rate_limiter(outer):
                self.resolve()
                with dns_resolver.use_rate_limiter(inner):
                    self.resolve()
                self.resolve()
        self.assertEqual((outer.calls, inner.calls), (2, 1))


class QueryRateLimiterTests(unittest.TestCase):
    def test_parallel_workers_share_one_query_budget(self):
        limiter = dns_resolver.QueryRateLimiter(20)
        starts = []
        lock = threading.Lock()

        def response(request, *_args, **_kwargs):
            with lock:
                starts.append(time.monotonic())
            return address_response(request)

        def worker(index):
            with dns_resolver.use_rate_limiter(limiter):
                return dns_resolver.resolve_ipv4_addresses(f"domain{index}.test", nameservers=["192.0.2.53"])

        with mock.patch("dns.query.udp", side_effect=response):
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(worker, range(8)))
        self.assertEqual(results, [["203.0.113.10"]] * 8)
        self.assertGreaterEqual(starts[-1] - starts[0], 0.34)
        self.assertTrue(all(right - left >= 0.04 for left, right in zip(starts, starts[1:])), starts)

    def test_idle_time_does_not_allow_a_burst(self):
        current = [0.0]
        def sleep(delay):
            current[0] += delay

        limiter = dns_resolver.QueryRateLimiter(50)
        with mock.patch.object(dns_resolver.time, "monotonic", side_effect=lambda: current[0]):
            with mock.patch.object(dns_resolver.time, "sleep", side_effect=sleep):
                self.assertEqual(limiter.acquire(), 0)
                self.assertAlmostEqual(limiter.acquire(), 0.02)
                current[0] = 10
                self.assertEqual(limiter.acquire(), 0)
                self.assertAlmostEqual(limiter.acquire(), 0.02)

    def test_invalid_qps_is_rejected(self):
        for qps in (0, -1, 1001, float("nan"), float("inf")):
            with self.subTest(qps=qps):
                with self.assertRaises(ValueError):
                    dns_resolver.QueryRateLimiter(qps)


if __name__ == "__main__":
    unittest.main()
