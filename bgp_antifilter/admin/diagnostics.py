"""Network diagnostics and target resolution independent of transport."""

import json
import os
from pathlib import Path
import socket
import time
import urllib.error
import urllib.request

from .. import dns_resolver, network_diagnostics
from .storage import text_load


IP_API_URL = (
    "http://ip-api.com/json/?fields="
    "status,message,query,country,countryCode,region,regionName,city,district,zip,"
    "lat,lon,timezone,offset,isp,org,as,asname,mobile,proxy,hosting"
)


def parse_resolv_conf(text):
    nameservers = []
    search = []
    domain = None
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        key, values = parts[0].lower(), parts[1:]
        if key == "nameserver":
            nameservers.extend(values)
        elif key == "search":
            search.extend(values)
        elif key == "domain":
            domain = values[0]
    return {
        "nameservers": nameservers,
        "search": search,
        "domain": domain,
    }


def local_ipv4_addresses():
    return network_diagnostics.local_ipv4_addresses()


def external_ip_summary(timeout=5):
    try:
        with urllib.request.urlopen(IP_API_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return {
            "ok": False,
            "source": "ip-api.com",
            "error": str(exc),
        }
    if payload.get("status") != "success":
        return {
            "ok": False,
            "source": "ip-api.com",
            "error": payload.get("message", "lookup failed"),
            "payload": payload,
        }
    return {
        "ok": True,
        "source": "ip-api.com",
        **payload,
    }


class DiagnosticsService:
    def __init__(self, settings):
        self.settings = settings

    def resolve_ipv4_targets(self, value):
        target = str(value or "").strip()
        if not target:
            return [], "target is required"
        try:
            address = socket.inet_pton(socket.AF_INET, target)
            return [socket.inet_ntop(socket.AF_INET, address)], None
        except OSError:
            pass
        if any(char.isspace() for char in target):
            return [], "target must be an IPv4 address or domain"
        try:
            settings = self.settings.effective_settings()
            addresses = dns_resolver.resolve_ipv4_addresses(
                target,
                nameservers=dns_resolver.parse_nameservers(settings.get("DNS_RESOLVERS", "")),
                timeout=float(settings.get("DNS_RESOLVE_TIMEOUT", dns_resolver.DEFAULT_TIMEOUT)),
            )
        except (socket.gaierror, OSError, RuntimeError, ValueError) as exc:
            return [], str(exc)
        if not addresses:
            return [], "domain has no IPv4 addresses"
        return addresses, None

    def network_summary(self):
        settings = self.settings.effective_settings()
        resolv = parse_resolv_conf(text_load(Path("/etc/resolv.conf")))
        custom_resolvers = dns_resolver.parse_nameservers(settings.get("DNS_RESOLVERS", ""))
        addresses = local_ipv4_addresses()
        return {
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
            "local_ipv4": addresses,
            "primary_ipv4": next((address for address in addresses if not address.startswith("127.")), addresses[0] if addresses else ""),
            "dns": resolv,
            "custom_dns": {
                "nameservers": custom_resolvers,
                "timeout_seconds": float(settings.get("DNS_RESOLVE_TIMEOUT", dns_resolver.DEFAULT_TIMEOUT)),
                "enabled": bool(custom_resolvers),
            },
            "bird": {
                "router_id": settings.get("ROUTER_ID", ""),
                "bird_ip": settings.get("BIRD_IP", ""),
                "mikrotik_ip": settings.get("MT_IP", ""),
                "bgp_protocol": settings.get("BGP_PROTOCOL", ""),
                "my_as": settings.get("MY_AS", ""),
                "mt_as": settings.get("MT_AS", ""),
                "bird_ip_check": network_diagnostics.bird_ip_diagnostic(settings.get("BIRD_IP", ""), addresses=addresses),
            },
            "admin": {
                "port": os.environ.get("ADMIN_PORT", "8080"),
            },
            "external": external_ip_summary(),
            "fetched_at": int(time.time()),
        }

    def login_network_payload(self):
        settings = self.settings.effective_settings()
        labels = []
        for key in ("ROUTER_ID", "BIRD_IP", "MT_IP"):
            value = settings.get(key, "").strip()
            if value and value not in labels:
                labels.append(value)
        for value in local_ipv4_addresses():
            if not value.startswith("127.") and value not in labels:
                labels.append(value)
        if not labels:
            labels.append("127.0.0.1")
        return {
            "labels": labels[:4],
        }
