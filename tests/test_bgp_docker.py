"""Real BIRD 3 peers verify the shipped export filter and route replacement."""

import os
import shutil
import subprocess
import unittest


SCENARIO = r'''
from pathlib import Path
import subprocess
import tempfile
import time
from string import Template

def run(*args, check=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    assert not check or result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    routes = root / 'routes.conf'
    routes.write_text('route 192.0.2.0/24 blackhole;\n')
    template = Path('/etc/bird/bird.conf.template').read_text()
    config = Template(template).substitute(ROUTER_ID='10.0.0.1', MY_AS='64500', PEER_AS='64501',
                                            PEER_IP='127.0.0.2', BIRD_IP='127.0.0.1', BGP_COMMUNITY='65432,500', BGP_PROTOCOL='peer')
    config = config.replace('/etc/bird/generated/routes.conf', str(routes))
    config = config.replace('local as MY_AS;', 'local port 1179 as MY_AS;')
    config = config.replace('neighbor PEER_IP as PEER_AS;', 'neighbor PEER_IP port 2179 as PEER_AS;')
    config = config.replace('    multihop;', '    multihop;\n    connect retry time 1;')
    (root / 'origin.conf').write_text(config)
    (root / 'peer.conf').write_text(r"""
router id 10.0.0.2;
protocol device {}
protocol static reachability { ipv4; route 127.0.0.1/32 via "lo"; }
protocol bgp antifilter {
  local 127.0.0.2 port 2179 as 64501;
  neighbor 127.0.0.1 port 1179 as 64500;
  multihop;
  connect retry time 1;
  ipv4 { import all; export none; };
}
""")
    processes = []
    logs = []
    def cli(name, *args, check=True):
        return run('birdc', '-s', str(root / (name + '.ctl')), *args, check=check)
    def wait_for(predicate, message):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return
            except AssertionError:
                pass
            time.sleep(0.2)
        raise AssertionError(message + '\n' + '\n'.join((root / (name + '.log')).read_text() for name in ['origin', 'peer']))
    try:
        assert 'version 3.' in run('bird', '--version')
        for name in ['origin', 'peer']:
            run('bird', '-p', '-c', str(root / (name + '.conf')))
            log = (root / (name + '.log')).open('w')
            logs.append(log)
            processes.append(subprocess.Popen(['bird', '-f', '-c', str(root / (name + '.conf')), '-s', str(root / (name + '.ctl')), '-P', str(root / (name + '.pid'))], stdout=log, stderr=log))
        wait_for(lambda: 'Established' in cli('origin', 'show', 'protocols', 'peer'), 'BGP did not establish')
        wait_for(lambda: '192.0.2.0/24' in cli('peer', 'show', 'route', 'all'), 'Initial route was not exported')
        output = cli('peer', 'show', 'route', 'all')
        assert '(65432,500)' in output, output
        assert '127.0.0.1' in output, output
        routes.write_text('route 198.51.100.0/24 blackhole;\n')
        assert 'Reconfigured' in cli('origin', 'configure')
        wait_for(lambda: '198.51.100.0/24' in cli('peer', 'show', 'route', 'all') and '192.0.2.0/24' not in cli('peer', 'show', 'route', 'all'), 'Route replacement was not propagated')
        routes.write_text('this is not a valid BIRD route;\n')
        rejected = cli('origin', 'configure', check=False)
        assert 'Reconfigured' not in rejected, rejected
        assert '198.51.100.0/24' in cli('peer', 'show', 'route', 'all')
        print('BIRD 3 BGP exchange, community, next hop, replacement and rejected-config retention passed')
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)
        for log in logs:
            log.close()
'''


@unittest.skipUnless(os.environ.get("RUN_DOCKER_BGP") == "1" and shutil.which("docker"), "Requires RUN_DOCKER_BGP=1 and Docker")
class BgpDockerTests(unittest.TestCase):
    def test_real_bird3_peer_export_and_reconfiguration(self):
        image = os.environ.get("BGP_TEST_IMAGE", "ghcr.io/leonidoz/bgp-antifilter:dev")
        result = subprocess.run(["docker", "run", "--rm", "-i", "--entrypoint", "python3", image, "-"],
                                input=SCENARIO, text=True, capture_output=True, timeout=100)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
