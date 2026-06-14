import ipaddress
import random
import socket
import struct


DEFAULT_TIMEOUT = 3.0
MAX_DNS_PACKET_SIZE = 4096


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


def resolve_ipv4_addresses(domain, *, nameservers=None, timeout=DEFAULT_TIMEOUT):
    nameservers = list(nameservers or [])
    if not nameservers:
        return sorted({
            item[4][0]
            for item in socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
        })

    last_error = None
    for nameserver in nameservers:
        try:
            addresses = query_a_records(domain, nameserver, timeout=timeout)
        except (OSError, ValueError) as exc:
            last_error = exc
            continue
        if addresses:
            return addresses
        last_error = RuntimeError(f"{domain} has no IPv4 answers from {nameserver}")
    if last_error is None:
        raise RuntimeError("no DNS resolvers configured")
    raise last_error


def query_a_records(domain, nameserver, *, timeout=DEFAULT_TIMEOUT):
    qname = encode_qname(domain)
    query_id = random.randrange(0, 65536)
    header = struct.pack("!HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
    question = qname + struct.pack("!HH", 1, 1)
    packet = header + question

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(packet, (nameserver, 53))
        response, _ = sock.recvfrom(MAX_DNS_PACKET_SIZE)

    return parse_a_response(response, query_id)


def encode_qname(domain):
    labels = str(domain or "").strip().rstrip(".")
    if not labels:
        raise ValueError("domain is required")
    parts = labels.encode("idna").split(b".")
    encoded = bytearray()
    for part in parts:
        if not part:
            raise ValueError("domain contains an empty label")
        if len(part) > 63:
            raise ValueError("domain label is too long")
        encoded.append(len(part))
        encoded.extend(part)
    encoded.append(0)
    return bytes(encoded)


def parse_a_response(message, expected_id):
    if len(message) < 12:
        raise RuntimeError("short DNS response")
    response_id, flags, questions, answers, authority, additional = struct.unpack("!HHHHHH", message[:12])
    if response_id != expected_id:
        raise RuntimeError("mismatched DNS response id")
    if not flags & 0x8000:
        raise RuntimeError("invalid DNS response")

    rcode = flags & 0x000F
    if rcode == 3:
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
    if rcode != 0:
        raise RuntimeError(f"DNS server returned error code {rcode}")

    offset = 12
    for _ in range(questions):
        offset = skip_name(message, offset)
        if offset + 4 > len(message):
            raise RuntimeError("truncated DNS question")
        offset += 4

    addresses = set()
    total_records = answers + authority + additional
    for _ in range(total_records):
        offset = skip_name(message, offset)
        if offset + 10 > len(message):
            raise RuntimeError("truncated DNS record header")
        rr_type, rr_class, _, rdlength = struct.unpack("!HHIH", message[offset:offset + 10])
        offset += 10
        end = offset + rdlength
        if end > len(message):
            raise RuntimeError("truncated DNS record data")
        if rr_type == 1 and rr_class == 1 and rdlength == 4:
            addresses.add(socket.inet_ntoa(message[offset:end]))
        offset = end

    return sorted(addresses)


def skip_name(message, offset):
    steps = 0
    while True:
        if offset >= len(message):
            raise RuntimeError("truncated DNS name")
        length = message[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(message):
                raise RuntimeError("truncated DNS pointer")
            return offset + 2
        offset += 1 + length
        steps += 1
        if steps > 128:
            raise RuntimeError("DNS name is too deep")
