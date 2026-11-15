"""Exercise the documented FRR policy with the shipped BIRD configuration."""
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
from string import Template
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
FRR_IMAGE = "quay.io/frrouting/frr:10.7.1@sha256:e995beaa50fdc9edb35eadcfefa29b7f062cc06f2b812613789b68fa541554d2"


@unittest.skipUnless(os.environ.get("RUN_DOCKER_FRR") == "1" and shutil.which("docker"), "Requires RUN_DOCKER_FRR=1 and Docker")
class FrrDockerTests(unittest.TestCase):
    def test_frr_import_policy_vpn_next_hop_and_route_replacement(self):
        suffix = uuid.uuid4().hex[:10]
        network, origin, peer = ["bgp-frr-" + suffix + label for label in ("-net", "-bird", "-frr")]

        def docker(*args, check=True, timeout=45, input=None):
            try:
                result = subprocess.run(["docker", *args], capture_output=True, timeout=timeout, input=input.encode("utf-8") if input is not None else None)
                result.stdout = result.stdout.decode("utf-8", errors="replace")
                result.stderr = result.stderr.decode("utf-8", errors="replace")
            except subprocess.TimeoutExpired as exc:
                raise AssertionError(f"Docker command timed out: {args[:5]}\n{exc.stdout!r}\n{exc.stderr!r}") from exc
            if check and result.returncode:
                raise AssertionError("docker " + " ".join(args[:5]) + "\n" + result.stdout + result.stderr)
            return result.stdout.strip()

        def wait_for(predicate, message):
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                try:
                    if predicate(): return
                except (AssertionError, ValueError, KeyError): pass
                time.sleep(0.3)
            self.fail(message + "\n" + docker("logs", peer, check=False) + "\n" + docker("exec", origin, "cat", "/tmp/bird.log", check=False))

        def cli(command):
            return json.loads(docker("exec", peer, "vtysh", "-c", command))

        def paths(prefix):
            return cli("show bgp ipv4 unicast " + prefix + " json").get("paths", [])

        try:
            docker("network", "create", network)
            subnet = json.loads(docker("network", "inspect", network))[0]["IPAM"]["Config"][0]["Subnet"]
            base = ipaddress.ip_network(subnet).network_address
            origin_ip, peer_ip = str(base + 2), str(base + 3)
            docker("run", "-d", "--name", origin, "--network", network, "--ip", origin_ip, "--entrypoint", "sleep",
                   os.environ.get("BGP_TEST_IMAGE", "ghcr.io/leonidoz/bgp-antifilter:dev"), "3600")
            docker("run", "-d", "--name", peer, "--network", network, "--ip", peer_ip, "--cap-add", "NET_ADMIN", "--cap-add", "SYS_ADMIN", "--ulimit", "nofile=1024:1024", "--entrypoint", "sleep",
                   os.environ.get("FRR_TEST_IMAGE", FRR_IMAGE), "3600")
            config = Template((ROOT / "deploy/bird.conf.template").read_text()).substitute(
                ROUTER_ID=origin_ip, MY_AS="64500", PEER_IP=peer_ip, PEER_AS="65455", BIRD_IP=origin_ip,
                BGP_COMMUNITY="65432,500", BGP_PROTOCOL="peer")
            config = config.replace("/etc/bird/generated/routes.conf", "/tmp/frr-routes.conf")
            config = config.replace("    multihop;", "    multihop;\n    connect retry time 1;")
            frr = (ROOT / "docs/examples/frr.conf").read_text().replace("192.168.55.5", origin_ip).replace("192.168.55.1", peer_ip)
            for content, container, destination in [
                (config, origin, "/tmp/bird.conf"),
                ("route 192.0.2.0/24 blackhole;\nroute 0.0.0.0/0 blackhole;\n", origin, "/tmp/frr-routes.conf"),
                (frr, peer, "/etc/frr/frr.conf"),
            ]:
                docker("exec", "-i", container, "sh", "-c", 'cat > "$1"', "sh", destination, input=content)
            docker("exec", peer, "sh", "-c", "sed -i 's/^bgpd=no/bgpd=yes/' /etc/frr/daemons; touch /etc/frr/vtysh.conf; chown frr:frr /etc/frr/frr.conf /etc/frr/vtysh.conf; chmod 640 /etc/frr/frr.conf")
            docker("exec", peer, "ip", "link", "add", "vpn-test", "type", "dummy")
            docker("exec", peer, "ip", "addr", "add", "10.10.10.2/24", "dev", "vpn-test")
            docker("exec", peer, "ip", "link", "set", "vpn-test", "up")
            docker("exec", peer, "/usr/lib/frr/frrinit.sh", "start")
            docker("exec", origin, "bird", "-p", "-c", "/tmp/bird.conf")
            docker("exec", origin, "sh", "-c", "bird -f -c /tmp/bird.conf -s /tmp/frr-bird.ctl -P /tmp/frr-bird.pid > /tmp/bird.log 2>&1 &")
            wait_for(lambda: bool(paths("192.0.2.0/24")), "FRR did not receive the initial prefix")
            first = paths("192.0.2.0/24")[0]
            self.assertIn("65432:500", first.get("community", {}).get("string", ""))
            self.assertIn("10.10.10.1", [hop["ip"] for hop in first.get("nexthops", [])])
            self.assertEqual(paths("0.0.0.0/0"), [], "The FRR policy accepted a default route")
            wait_for(lambda: any(route.get("gateway") == "10.10.10.1" for route in json.loads(docker("exec", peer, "ip", "-j", "route", "show", "exact", "192.0.2.0/24"))),
                     "The accepted prefix was not installed via the VPN next hop")
            advertised = cli("show bgp ipv4 unicast neighbors " + origin_ip + " advertised-routes json")
            self.assertIn("advertisedRoutes", advertised)
            self.assertFalse(advertised.get("advertisedRoutes"), "FRR leaked routes to the application")
            docker("exec", "-i", origin, "sh", "-c", "cat > /tmp/bird.conf", input=config.replace("65432,500", "65432,501"))
            self.assertIn("Reconfigured", docker("exec", origin, "birdc", "-s", "/tmp/frr-bird.ctl", "configure"))
            wait_for(lambda: not paths("192.0.2.0/24"), "FRR accepted a prefix with the wrong community")
            docker("exec", "-i", origin, "sh", "-c", "cat > /tmp/bird.conf", input=config)
            self.assertIn("Reconfigured", docker("exec", origin, "birdc", "-s", "/tmp/frr-bird.ctl", "configure"))
            wait_for(lambda: bool(paths("192.0.2.0/24")), "FRR did not accept the restored community")
            docker("exec", origin, "sh", "-c", "printf 'route 198.51.100.0/24 blackhole;\\n' > /tmp/frr-routes.conf")
            self.assertIn("Reconfigured", docker("exec", origin, "birdc", "-s", "/tmp/frr-bird.ctl", "configure"))
            wait_for(lambda: bool(paths("198.51.100.0/24")) and not paths("192.0.2.0/24"), "FRR did not replace and withdraw prefixes")
            wait_for(lambda: not json.loads(docker("exec", peer, "ip", "-j", "route", "show", "exact", "192.0.2.0/24"))
                     and any(route.get("gateway") == "10.10.10.1" for route in json.loads(docker("exec", peer, "ip", "-j", "route", "show", "exact", "198.51.100.0/24"))),
                     "Linux retained the old prefix or failed to install its replacement through the VPN")
            docker("exec", origin, "sh", "-c", "printf 'invalid configuration;\\n' > /tmp/frr-routes.conf")
            self.assertNotIn("Reconfigured", docker("exec", origin, "birdc", "-s", "/tmp/frr-bird.ctl", "configure", check=False))
            self.assertTrue(paths("198.51.100.0/24"), "FRR lost the previous routes after BIRD rejected a configuration")
        except Exception:
            print(docker("exec", peer, "sh", "-c", "ps; ls -l /var/run/frr; cat /var/log/frr/*.log 2>/dev/null", check=False))
            raise
        finally:
            docker("rm", "-f", origin, peer, check=False)
            docker("network", "rm", network, check=False)
