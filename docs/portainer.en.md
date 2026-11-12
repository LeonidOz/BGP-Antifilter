# Install with Portainer

[Terminal installation](../README.en.md) | [Русский](portainer.md)

Use Docker Standalone on Linux. This example uses `192.168.55.1` for MikroTik
and `192.168.55.5` for the Linux server. Replace both with your addresses.

## 1. Create a stack

In Portainer, open **Stacks → Add stack**, name it `bgp-antifilter`,
and select **Web editor**. Paste the contents of the
[stack file](../deploy/portainer-stack.yml).
There is no need to clone the repository or build an image.

## 2. Set environment variables

Add these under **Environment variables**:

| Variable | Example | Purpose |
| --- | --- | --- |
| `BGP_ANTIFILTER_IMAGE` | `ghcr.io/leonidoz/bgp-antifilter:0.5.2` | Application image |
| `ADMIN_PASSWORD` | Your password | Web panel login |
| `MT_IP` | `192.168.55.1` | MikroTik address |
| `BIRD_IP` | `192.168.55.5` | Existing Linux server address |
| `ROUTER_ID` | `192.168.55.5` | Usually the same as `BIRD_IP` |
| `MY_AS` | `64500` | Application AS |
| `MT_AS` | `65455` | MikroTik AS |
| `BGP_COMMUNITY` | `65432,500` | Route label for the MikroTik filter |

To change the panel port, add `ADMIN_PORT`, for example `8081`.
The panel port and BGP port (TCP 179) must be available on the Linux server.
The stack already uses host networking; no separate port mapping is needed.

## 3. Deploy and connect the router

Click **Deploy the stack** and wait for the first route download.
Open **http://192.168.55.5:8080** and enter your password.
Then follow the [MikroTik setup](mikrotik.en.md).

The container may show `unhealthy` until MikroTik connects because its healthcheck
expects a BGP session. Once configured, expect routes in the panel and BGP state `Established`.

## Updates and data

To update, change the tag in `BGP_ANTIFILTER_IMAGE` and click **Update the stack**
with image re-pulling enabled. Manage application updates through Portainer for this installation.

In the new layout, lists, settings and their backups are stored in `bgp-antifilter-config`;
routes, cache and runtime state remain in `bgp-antifilter-data`.
Keep both volumes when updating or recreating the stack.
To attach an existing volume, set `BGP_DATA_VOLUME=<volume-name>`
and `BGP_DATA_EXTERNAL=true`. Data from an older `generated/` directory
must be moved into the volume separately; it is not migrated automatically.
For an existing configuration volume, set `BGP_CONFIG_VOLUME=<volume-name>`
and `BGP_CONFIG_EXTERNAL=true`; otherwise the new volume is created automatically.

When upgrading an older stack, update both the image and the YAML to the two-volume layout.
Automatic migration is available starting with [0.5.2](../CHANGELOG.md#052---2026-11-13); the `0.5.1` image does not include it.
The first startup copies configuration from the old volume, retaining originals and route snapshots.
Updating only the image with an old YAML continues to honor explicitly configured legacy paths.
Back up first; see the [migration steps](usage.en.md#moving-to-separate-config-storage).

[Managing lists and troubleshooting](usage.en.md).
