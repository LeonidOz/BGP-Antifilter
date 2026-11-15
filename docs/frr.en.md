# Connecting FRRouting

[General BGP guide](bgp.en.md) | [Application installation](../README.en.md) | [Русский](frr.md)

The example is exercised by an integration test with FRR 10.7.1 and BIRD 3.4.0. It checks prefix acceptance and withdrawal, community, default-route rejection, next-hop rewriting, and installation in Linux. Test your actual VPN separately.

## Example addresses

| Side | Address | AS |
| --- | --- | --- |
| BGP Antifilter / BIRD | `192.168.55.5` | `64500` |
| FRR router | `192.168.55.1` | `65455` |
| VPN gateway reachable from FRR | `10.10.10.1` | — |

Set `PEER_IP=192.168.55.1`, `PEER_AS=65455`, `BIRD_IP=192.168.55.5`, `MY_AS=64500`, and `BGP_COMMUNITY=65432,500` in the application. Replace addresses and AS numbers for your network. Allow TCP 179 between BIRD and FRR.

## Configure FRR

1. Install FRRouting on the router and enable `bgpd=yes` in `/etc/frr/daemons`. Zebra must run to install routes in Linux.
2. Open the [complete configuration example](examples/frr.conf). Replace addresses, AS numbers, community, and VPN gateway. Merge the relevant blocks into an existing FRR configuration: the complete file is an example for a new installation.
3. Apply the configuration using your operating system's usual procedure. On Debian/Ubuntu, enabling a new daemon requires `sudo systemctl restart frr`; this also restarts other FRR sessions.

The example's import policy is:

```frr
ip prefix-list ANTIFILTER-V4 seq 5 deny 0.0.0.0/0
ip prefix-list ANTIFILTER-V4 seq 10 permit 0.0.0.0/0 ge 8 le 32
bgp community-list standard ANTIFILTER permit 65432:500
route-map ANTIFILTER-IN permit 10
 match ip address prefix-list ANTIFILTER-V4
 match community ANTIFILTER
 set ip next-hop 10.10.10.1
exit
route-map ANTIFILTER-IN deny 100
exit
```

Attach this policy to the neighbor in the `in` direction; `ANTIFILTER-OUT` rejects every outbound announcement. The complete configuration also sets the remote AS, update-source, multihop, and IPv4 activation. If your application intentionally permits prefixes shorter than /8, align this prefix-list with your policy.

The Linux routing table must resolve `10.10.10.1` through the VPN interface. Enable IPv4 forwarding and check firewall rules, VPN routes/AllowedIPs, and NAT where required. The application does not configure these on the FRR host.

## Verify

```bash
sudo vtysh -c 'show bgp ipv4 unicast summary'
sudo vtysh -c 'show bgp ipv4 unicast community 65432:500'
sudo vtysh -c 'show ip route bgp'
ip route get <listed_IP>
```

The peer should show received prefixes instead of Idle/Active or `(Policy)`. For a selected prefix, inspect `show bgp ipv4 unicast <prefix>`: the community should be `65432:500` and the next hop should be your VPN gateway. Verify the same route in the system table, then test HTTPS from a device behind the router.

If BGP sees a prefix but Linux does not install it, check zebra, VPN next-hop reachability, and competing routes. If `(Policy)` appears, check route-map assignment in both directions. FRR does not use the `.rsc` export.

Official documentation: [BGP and communities](https://docs.frrouting.org/en/latest/bgp.html), [route-maps and set ip next-hop](https://docs.frrouting.org/en/latest/routemap.html), [FRR images](https://frrouting.org/release/).
