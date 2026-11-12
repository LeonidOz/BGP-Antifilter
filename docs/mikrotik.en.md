# Connecting MikroTik

[Application installation](../README.en.md) | [Русский](mikrotik.md)

Choose one method: **BGP** sends route updates to the router automatically;
**Address List** lets you download and import a list manually for your own rules.

## BGP

Example values:

| Purpose | Value |
| --- | --- |
| Linux application server | `192.168.55.5`, AS `64500` |
| MikroTik | `192.168.55.1`, AS `65455` |
| Route label | `65432:500` — written as `65432,500` in `.env` |
| VPN gateway | `10.10.10.1` — replace with yours |

The VPN must already work and its gateway must be reachable from MikroTik.
This example installs routes in the `main` table.
Adapt the filter and table if you use separate routing tables, routing marks,
or a VPN without an IP gateway.

**The input filter must select the VPN gateway.**
The application advertises its own address as the next hop by default.
The Linux server's BIRD routes are `blackhole` routes; it does not forward this traffic into a VPN.

### 1. Create filters

On MikroTik, replace `10.10.10.1` with your VPN gateway IP and run:

```routeros
/routing filter rule
add chain=antifilter-in rule="if (dst == 0.0.0.0/0) { reject }"
add chain=antifilter-in rule="if (bgp-communities includes 65432:500) { set gw 10.10.10.1; accept } else { reject }"
add chain=antifilter-out rule="reject"
```

The filters accept only routes with the expected label, reject the default route,
and prevent sending router routes to the application.

### 2. Add the BGP connection

For **RouterOS 7.20 and newer**:

```routeros
/routing bgp instance
add name=antifilter as=65455 router-id=192.168.55.1

/routing bgp connection
add name=antifilter-bird instance=antifilter \
    remote.address=192.168.55.5 remote.as=64500 \
    local.address=192.168.55.1 local.role=ebgp multihop=yes \
    input.filter=antifilter-in output.filter-chain=antifilter-out
```

For **RouterOS 7 before 7.20**, use this block instead:

```routeros
/routing bgp connection
add name=antifilter-bird as=65455 router-id=192.168.55.1 routing-table=main \
    remote.address=192.168.55.5 remote.as=64500 \
    local.address=192.168.55.1 local.role=ebgp multihop=yes \
    input.filter=antifilter-in output.filter-chain=antifilter-out
```

Addresses, AS numbers, and community must match the application's settings.
Allow TCP 179 between these addresses if a firewall blocks the connection.

### 3. Verify

```routeros
/routing bgp session print
/ip route print where bgp
```

Expect the session's `E` flag (Established) and your VPN gateway on accepted routes.
Test access to a listed resource from a device behind the router.
If BGP connects but traffic fails, check the gateway, NAT, FastTrack rules,
and the VPN peer's allowed addresses.

Examples were checked against MikroTik documentation:
[BGP sessions](https://manual.mikrotik.com/docs/user-guides/routing-and-networking-protocols/unicast/bgp/peering-sessions/),
[routing filters](https://manual.mikrotik.com/docs/user-guides/routing-and-networking-protocols/route-selection-and-filtering/).
The project's automated tests do not apply these commands on real RouterOS.

## Address List instead of BGP

1. Set `HEALTHCHECK_REQUIRE_BGP=0` in the application's settings and apply it.
2. Open **Tools → Load routes** in the panel.
3. Enter a list name, such as `bgp-antifilter`, and click **Download Address List .rsc**.
4. Upload the file to MikroTik **Files** and run:

```routeros
/import file-name=bgp-antifilter.rsc
```

If your RouterOS version supports import validation without applying changes, first run
`/import file-name=bgp-antifilter.rsc verbose=yes dry-run=yes`.

The file contains the last successfully applied set of IPv4 prefixes.
List names allow 1–64 ASCII letters, digits, or `_.-`.
Downloads are unavailable during updates or when no working route set exists.

Repeated imports update managed entries and remove stale ones.
Manual entries are preserved. Do not use the reserved comment prefix
`bgp-antifilter:managed:` for your own entries.
Import the complete file and do not run simultaneous imports into the same list.
Large imports may take time; errors can leave a partial result.

Download and import are manual: application updates do not refresh the router's Address List.
Configure firewall/mangle rules and VPN routing on MikroTik separately.
