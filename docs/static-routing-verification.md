# Static Routing Verification Report (Phase 3.5)

**Environment**: Windows, Python 3.11.9, Pygame 2.6.1  
**Execution Timestamp**: 2026-09-13T21:46:39+07:00  
**Test Suite**: `tests/test_static_routing.py`  
**Total Tests**: 22  
**Result**: **22/22 PASSED (100%)**

---

## Verification Test Matrix

| # | Test Name | Expected Result | Actual Result | Status |
| :-: | :--- | :--- | :--- | :-: |
| **1** | Add Static Route | Route is validated, stored in `Router.routes` with network, mask, next-hop IP/interface, `type='S'`, and `admin_distance=1`. | Route stored cleanly: `192.168.20.0/255.255.255.0` via `10.0.0.2` and `10.0.1.0/255.255.255.0` via `g0/1`. | **PASS** |
| **2** | Show Static Route | `show ip route` renders Cisco formatted codes (`C`, `S`), CIDR prefix (`/24`), next-hop, and interface. `show running-config` serializes command. | Rendered `C 192.168.10.0/24 directly connected, g0/0`, `S 192.168.20.0/24 [1/0] via 10.0.0.2`, `S 10.0.1.0/24 directly connected, g0/1`. Running-config matches. | **PASS** |
| **3** | Remove Static Route | `remove_static_route()` and CLI `no ip route` remove route from routing table and running-config. | Route removed from `routes`, `show ip route` no longer lists route, `show running-config` omits route. | **PASS** |
| **4** | Invalid Network | Rejects invalid IPv4 addresses (e.g. `999.999.1.1`) and incomplete CLI inputs. | Rejection returned `False`; CLI returned `"% Invalid prefix or next-hop address"` and `"% Incomplete command."`. | **PASS** |
| **5** | Invalid Subnet Mask | Rejects non-contiguous bitmasks (e.g. `255.255.255.123`) and malformed strings. | Rejection returned `False`; CLI returned `"% Invalid prefix or next-hop address"`. | **PASS** |
| **6** | Invalid Next-Hop | Rejects invalid IP addresses or non-existent interface names. | Rejection returned `False`; CLI returned `"% Invalid prefix or next-hop address"`. | **PASS** |
| **7** | Longest Prefix Match (LPM) | Selects the most specific route (`/24 > /16 > /8 > /0`) for matching destination IP. | `10.1.10.50` matched `/24` (`10.1.10.1`), `10.1.20.50` matched `/16` (`10.1.255.1`), `10.2.1.1` matched `/8` (`10.255.255.1`), `172.16.1.1` matched `/0` (`192.168.0.1`). | **PASS** |
| **8** | Connected vs Static Priority | Connected route ($\text{AD}=0$) strictly takes precedence over Static route ($\text{AD}=1$) for identical prefix length. | For destination `192.168.10.50`, lookup returned `type='C'`, `next_hop='directly connected'`, interface `g0/0`. | **PASS** |
| **9** | Default Route | `0.0.0.0 0.0.0.0 <gw>` installs as default fallback, displays `S*` and sets `Gateway of last resort`. | Lookup for `8.8.8.8` matched default route; `show ip route` displayed `Gateway of last resort is 10.0.0.1 to network 0.0.0.0` and `S* 0.0.0.0/0 [1/0] via 10.0.0.1`. | **PASS** |
| **10** | No Route / Unreachable | Traffic destined for unreachable subnet drops with status code `'U'` and descriptive error message without looping. | Ping to `192.168.50.10` yielded 100% loss, status codes `['U', 'U', 'U']`, error `"No route to destination 192.168.50.10 on Router-1"`. | **PASS** |
| **11** | Two-Router Static Routing | End-to-end ping between PC1 and PC2 across 2 static routers. | Ping succeeded with 0% loss, 4/4 packets received, all status `!`. | **PASS** |
| **12** | Three-Router Multihop | End-to-end routing across `PC1 \| SW1 \| R1 \| R2 \| R3 \| SW2 \| PC2`. | 5/5 packets received, 0% loss, all status codes `!`. | **PASS** |
| **13** | Forward Path Verification | Exact sequence of 7 devices traversed recorded in `hop_path`. | Hop path matched: `["PC-1", "Switch-1", "Router-1", "Router-2", "Router-3", "Switch-2", "PC-2"]`. | **PASS** |
| **14** | Return Path Verification | Reverse ping succeeds; breaking return route on R3 results in `'U'` drop; restoring route recovers 0% loss. | Reverse ping 0% loss; broken return route returned 100% loss (`'U'`); restored route returned 0% loss. | **PASS** |
| **15** | ARP Next-Hop Resolution | Each router resolves next-hop router MAC on transit links; no fake MACs or remote client IP ARP queries on transit links. | R1 resolved `192.168.10.10` & `10.0.12.2`; R2 resolved `10.0.12.1` & `10.0.23.2`; R3 resolved `10.0.23.1` & `192.168.20.10`. | **PASS** |
| **16** | TTL / L3 Hop Tracking | Initial TTL 64 decremented by 1 at each of 3 routers (64 -> 61); switches do not decrement TTL. | Echo Reply TTL received at PC1 is 61 across all replies (`[61, 61, 61]`). | **PASS** |
| **17** | Traceroute | `simulate_traceroute()` discovers intermediate Layer 3 router hops in sequential order. | Discovered hops: `Router-1` -> `Router-2` -> `Router-3` -> `PC-2` with realistic RTTs. | **PASS** |
| **18** | Static Route + DHCP | PC1 dynamically acquires IP, subnet mask, and default gateway via DHCP from R1, then reaches PC2 across static routes. | DHCP lease successful (`192.168.10.2`, GW `192.168.10.1`); ping to PC2 across R1-R2-R3 passed with 0% loss. | **PASS** |
| **19** | Static Route + ACL | Static route does not bypass standard ACL; denied traffic drops with status `'A'`. | Ping blocked with status code `'A'`; removing ACL restored 0% loss. | **PASS** |
| **20** | Static Route + NAT | Traffic across static route properly undergoes source NAT translation and de-NATting on return path. | Ping from inside host across NAT overload and static route passed with 0% loss. | **PASS** |
| **21** | Static Route + Firewall | Static route crossing intermediate Stateful Firewall permits return traffic statefully. | Ping across Firewall passed with 0% loss; state table tracked connections. | **PASS** |
| **22** | Duplicate Static Route Behavior | Adding identical network/mask with new next-hop deterministically replaces old entry (REPLACE policy). | Replaced route entry cleanly; route count remained 1; `next_hop` updated from `10.0.0.2` to `10.0.0.3`. | **PASS** |

---

## Full Regression Test Suite Results

Command executed:
```powershell
$env:PYTHONPATH="."
python -c "import os, subprocess, sys; files = sorted([f for f in os.listdir('tests') if f.startswith('test_') and f.endswith('.py')]); ..."
```

```text
PASS: test_acl.py
PASS: test_arp.py
PASS: test_cable_physics.py
PASS: test_camera_movement.py
PASS: test_cli.py
PASS: test_cli_help.py
PASS: test_dhcp.py
PASS: test_firewall.py
PASS: test_game_loop.py
PASS: test_icmp.py
PASS: test_isp_gateway.py
PASS: test_laptop_gui.py
PASS: test_menu_mouse.py
PASS: test_modes.py
PASS: test_multihop.py
PASS: test_nat.py
PASS: test_nat_firewall_crouch.py
PASS: test_network.py
PASS: test_packet_engine.py
PASS: test_raycast_occlusion.py
PASS: test_realistic_ping.py
PASS: test_router.py
PASS: test_static_routing.py
PASS: test_stp.py
PASS: test_svi.py
PASS: test_switch.py
PASS: test_terminal_layout.py
PASS: test_topology_2d.py
PASS: test_ttl.py
PASS: test_vlan.py
Summary: 30/30 passed (100%)
```
