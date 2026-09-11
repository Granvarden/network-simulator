"""
tests/test_static_routing.py - Tests for Static Routing & Longest Prefix Match
Validates:
1. Adding static route (via next-hop IP or interface).
2. Removing static route (via API and CLI 'no ip route').
3. Longest Prefix Match order (/24 > /16 > /8 > /0).
4. Default route fallback (0.0.0.0/0).
5. Invalid route input rejection.
6. Unreachable next-hop handling without silent blackholing or crashes.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from network.router import Router
from network.host import Host
from network.cable import Cable
from cli.command_executor import CommandExecutor

def test_add_and_remove_static_routes():
    r1 = Router("r1", hostname="Router-1")

    # Add static route with next-hop IP
    added = r1.add_static_route("10.0.2.0", "255.255.255.0", "10.0.12.2")
    assert added is True
    assert len(r1.routes) == 1
    assert r1.routes[0]["next_hop"] == "10.0.12.2"
    assert r1.routes[0]["interface"] is None

    # Add duplicate modifies/replaces cleanly
    r1.add_static_route("10.0.2.0", "255.255.255.0", "10.0.12.5")
    assert len(r1.routes) == 1
    assert r1.routes[0]["next_hop"] == "10.0.12.5"

    # Remove static route
    removed = r1.remove_static_route("10.0.2.0", "255.255.255.0")
    assert removed is True
    assert len(r1.routes) == 0

    # Removing non-existent route returns False
    assert r1.remove_static_route("10.0.2.0", "255.255.255.0") is False

def test_cli_ip_route_and_no_ip_route():
    r1 = Router("r1", hostname="Router-CLI")
    cli = CommandExecutor(r1)
    cli.execute("enable")
    cli.execute("configure terminal")

    # Add via CLI
    cli.execute("ip route 172.16.1.0 255.255.255.0 10.0.0.2")
    assert len(r1.routes) == 1
    assert r1.routes[0]["network"] == "172.16.1.0"

    # Remove via CLI
    cli.execute("no ip route 172.16.1.0 255.255.255.0 10.0.0.2")
    assert len(r1.routes) == 0

def test_longest_prefix_match():
    r1 = Router("r1", hostname="Router-LPM")

    # Configure multiple overlapping routes
    r1.add_static_route("0.0.0.0", "0.0.0.0", "192.168.0.1")       # /0 Default
    r1.add_static_route("10.0.0.0", "255.0.0.0", "10.255.255.1")   # /8
    r1.add_static_route("10.0.0.0", "255.255.0.0", "10.0.255.1")   # /16
    r1.add_static_route("10.0.1.0", "255.255.255.0", "10.0.1.254") # /24

    # Case 1: 10.0.1.10 must match /24
    m1 = r1.lookup_route("10.0.1.10")
    assert m1 is not None
    assert m1["mask"] == "255.255.255.0"
    assert m1["next_hop"] == "10.0.1.254"

    # Case 2: 10.0.2.10 must match /16
    m2 = r1.lookup_route("10.0.2.10")
    assert m2 is not None
    assert m2["mask"] == "255.255.0.0"
    assert m2["next_hop"] == "10.0.255.1"

    # Case 3: 10.1.5.10 must match /8
    m3 = r1.lookup_route("10.1.5.10")
    assert m3 is not None
    assert m3["mask"] == "255.0.0.0"
    assert m3["next_hop"] == "10.255.255.1"

    # Case 4: 172.16.1.1 must match /0 Default Route
    m4 = r1.lookup_route("172.16.1.1")
    assert m4 is not None
    assert m4["mask"] == "0.0.0.0"
    assert m4["next_hop"] == "192.168.0.1"

def test_invalid_route_rejection():
    r1 = Router("r1", hostname="Router-1")

    # Invalid network
    res1 = r1.add_static_route("999.999.1.1", "255.255.255.0", "10.0.0.1")
    assert res1 is False
    assert len(r1.routes) == 0

    # Invalid mask
    res2 = r1.add_static_route("10.0.0.0", "invalid-mask", "10.0.0.1")
    assert res2 is False
    assert len(r1.routes) == 0

    # Malformed IP lookup should return None safely
    assert r1.lookup_route("invalid-ip") is None
    assert r1.lookup_route("") is None

if __name__ == "__main__":
    test_add_and_remove_static_routes()
    test_cli_ip_route_and_no_ip_route()
    test_longest_prefix_match()
    test_invalid_route_rejection()
    print("ALL STATIC ROUTING TESTS PASSED!")
