"""Vendor-neutral BGP peer settings and backwards-compatible aliases."""

ALIASES = {"MT_IP": "PEER_IP", "MT_AS": "PEER_AS"}
PEER_DEFAULTS = {"PEER_IP": "192.168.55.1", "PEER_AS": "65455"}


def canonical_settings(values, *, reject_conflicts=False):
    result = dict(values)
    for legacy, canonical in ALIASES.items():
        if legacy not in result:
            continue
        old = result.pop(legacy)
        if canonical in result:
            if reject_conflicts and str(result[canonical]) != str(old):
                raise ValueError(f"{canonical} and legacy {legacy} must match when both are supplied")
        else:
            result[canonical] = old
    return result


def peer_environment(environ):
    """Canonical env names win; legacy aliases remain available to templates."""
    result = dict(environ)
    for legacy, canonical in ALIASES.items():
        value = environ.get(canonical) or environ.get(legacy) or PEER_DEFAULTS[canonical]
        result[canonical] = result[legacy] = str(value)
    # Keep the historic session name for external scripts and old templates.
    result.setdefault("BGP_PROTOCOL", "mikrotik")
    return result


def peer_source_key(environ, canonical):
    if environ.get(canonical):
        return canonical
    return next((legacy for legacy, key in ALIASES.items() if key == canonical and environ.get(legacy)), canonical)


def peer_base_environment(environ):
    """Panel defaults refer to Compose's base, before shell overrides loaded."""
    result = peer_environment(environ)
    for key in PEER_DEFAULTS:
        result[key] = environ.get("BGP_BASE_" + key) or result[key]
    return result
