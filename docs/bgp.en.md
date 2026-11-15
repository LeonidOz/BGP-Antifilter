# Connecting a BGP peer

[Installation](../README.en.md) | [FRRouting](frr.en.md) | [MikroTik](mikrotik.en.md) | [Русский](bgp.md)

BGP Antifilter advertises IPv4 prefixes using standard BGP. The receiver can be a router or server with BGP, community filtering, and a way to send accepted routes through a VPN gateway. Examples are available for [FRR](frr.en.md) and [RouterOS](mikrotik.en.md). Other platforms need their own compatibility checks.

## Traffic path

```text
Sources → BGP Antifilter / BIRD → IPv4 BGP → your router → VPN
```

The application manages lists and announcements; the router forwards traffic. Configure the VPN first.

**Set the VPN next hop on the receiving side.** BIRD advertises its own `BIRD_IP` as the next hop. The application's local routes are `blackhole` routes: its Linux server is not a VPN gateway and does not forward this traffic into the VPN.

## Application settings

| Setting | Example | Purpose |
| --- | --- | --- |
| `MY_AS` | `64500` | Application AS |
| `PEER_AS` | `65455` | Receiving peer AS |
| `PEER_IP` | `192.168.55.1` | Reachable BGP peer address |
| `BIRD_IP` | `192.168.55.5` | Address already assigned to the Linux server |
| `ROUTER_ID` | `192.168.55.5` | BIRD router ID |
| `BGP_COMMUNITY` | `65432,500` | Route label, written as `65432:500` on the receiver |
| `BGP_PROTOCOL` | `mikrotik` | Internal BIRD session name retained for compatibility |

The `mikrotik` name does not restrict the peer platform. The shipped template supports a different name through `BGP_PROTOCOL`; a custom template must use the same name as health/status checks. Changes to BGP settings in the panel require container recreation.

The shipped template has one BGP peer. The examples use eBGP with different AS numbers; they do not test iBGP. It uses multihop, and TCP 179 must be reachable between the specified addresses. Restrict access to this port to the peer address. IPv6 announcements and multiple peers configured through the panel are not currently supported.

## Receiving policy

1. Accept only IPv4 prefixes carrying the configured community.
2. Reject a default route. The FRR example accepts /8 through /32, matching the generator's default prefix-length protection.
3. Replace `BIRD_IP` with the VPN next hop; the receiver must have a route to that gateway.
4. Reject all outbound advertisements to the application. BIRD also uses `import none`.
5. Configure IPv4 forwarding, VPN connectivity, firewall rules, and NAT where required. Ensure VPN peer address restrictions cover the desired prefixes.

## Verification

```bash
docker compose exec bgp-antifilter birdc show protocols
docker compose exec bgp-antifilter birdc show route count
```

Expect Established, nonempty routes, and healthy status. On the receiver, verify the community, VPN next hop, and installation in the system routing table. Then test real access from a device behind the router: an established BGP session alone does not prove VPN forwarding works.

## Settings compatibility

- `MT_IP` and `MT_AS` remain aliases for `PEER_IP` and `PEER_AS`.
- Within the same environment, `PEER_*` takes precedence over `MT_*`. Compose also passes matching `MT_*` values so the new stack can run the previous application image.
- Saved panel overrides take precedence over the container environment, including old saved `MT_*` settings. New saves use `PEER_*` names.
- Old JSON configuration backups are accepted and converted on import; conflicting legacy/canonical values are rejected.
- Command environments provide both sets of names with matching values, keeping old custom BIRD templates usable.
- The default session name `mikrotik` is retained for old templates, healthchecks, and external scripts.

RouterOS Address List `.rsc` export is a separate platform-specific option documented in the [MikroTik guide](mikrotik.en.md#address-list-instead-of-bgp).
