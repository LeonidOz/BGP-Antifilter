"""Parse, validate and combine collected route fragments."""

from . import generate_routes
from .logging import progress
from .route_output import write_text


def subtract_networks(networks, excluded_networks):
    result = []

    for network in networks:
        remaining = [network]

        for excluded in excluded_networks:
            next_remaining = []

            for candidate in remaining:
                if not candidate.overlaps(excluded):
                    next_remaining.append(candidate)
                elif candidate.subnet_of(excluded):
                    continue
                elif excluded.subnet_of(candidate):
                    next_remaining.extend(candidate.address_exclude(excluded))
                else:
                    next_remaining.append(candidate)

            remaining = next_remaining

        result.extend(remaining)

    return generate_routes.collapse_routes(result)


def unsafe_broad_routes(networks, min_prefix_length):
    return [
        network
        for network in networks
        if network.version == 4 and network.prefixlen < min_prefix_length
    ]


def cleanup_paths(paths):
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def parse_and_build_routes(output, base_text, include_text, exclude_text, min_prefix_length, allow_broad_routes):
    tmp_dir = output.parent
    tmp_base = tmp_dir / ".routes-base.tmp"
    tmp_include = tmp_dir / ".routes-include.tmp"
    tmp_exclude = tmp_dir / ".routes-exclude.tmp"
    tmp_paths = (tmp_base, tmp_include, tmp_exclude)

    try:
        write_text(tmp_base, "\n".join(base_text))
        write_text(tmp_include, "\n".join(include_text))
        write_text(tmp_exclude, "\n".join(exclude_text))

        base, base_invalid = generate_routes.read_networks(tmp_base, extract=True)
        exclude, exclude_invalid = generate_routes.read_networks(tmp_exclude)
        extra, extra_invalid = generate_routes.read_networks(tmp_include)

        broad = unsafe_broad_routes(base + extra, min_prefix_length)
        if broad and not allow_broad_routes:
            examples = ", ".join(str(network) for network in broad[:5])
            raise RuntimeError(
                f"refusing broad IPv4 routes shorter than /{min_prefix_length}: {examples}"
            )

        progress("building final route set", base=len(base), include=len(extra), exclude=len(exclude))
        networks, applied, route_stats = generate_routes.build_routes_with_stats(base, exclude, extra)
        routes = {
            "base": len(base),
            "include": len(extra),
            "exclude": len(exclude),
            "candidate": route_stats["candidate"],
            "after_exclusions": route_stats["after_exclusions"],
            "final": len(networks),
            "collapsed_removed": route_stats["collapsed_removed"],
            "exclude_rules_applied": applied,
            "invalid": base_invalid + exclude_invalid + extra_invalid,
        }
        return networks, routes
    finally:
        cleanup_paths(tmp_paths)
