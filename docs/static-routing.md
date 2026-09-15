# IPv4 Static Routing Architecture & Operation Guide (Phase 3.5)

## 1. Overview & Architecture

Static Routing provides deterministic, administrator-configured path selection for IPv4 traffic across the Network Simulator. It integrates directly with Layer 3 Routers, Router Subinterfaces (802.1Q VLAN Trunking), Switches, SVIs, ARP tables, TTL decrement logic, ACLs, NAT, and Stateful Firewalls.

```
                    +-----------------------------+
                    |        Incoming Packet      |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | Ingress ACL & Reverse NAT   |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    |  Destination IP Lookup      |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | Longest Prefix Match (LPM)  |
                    | (/32 > /24 > /16 > /8 > /0) |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | Administrative Distance     |
                    | (Connected: 0, Static: 1)   |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | Next-Hop Resolution         |
                    | - Directly Connected: Target|
                    | - Static Hop: Gateway IP    |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | ARP Cache / Probe Next-Hop  |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | Egress ACL & Forward NAT    |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | TTL Decrement (TTL = TTL-1) |
                    +--------------+--------------+
                                   |
                                   v
                    +-----------------------------+
                    | Transmit Packet across Link |
                    +-----------------------------+
```

---

## 2. Routing Table & Route Types

The Routing Information Base (RIB) on each Router stores directly connected subnets and configured static routes.

| Code | Type | Administrative Distance (AD) | Description |
| :--- | :--- | :---: | :--- |
| **C** | Connected | 0 | Automatically populated when an interface or subinterface has an assigned IP address, valid subnet mask, and is link UP (cabled to active peer). |
| **S** | Static | 1 | Manually configured route pointing to a next-hop IP or egress interface. |
| **S\*** | Candidate Default | 1 | Default route matching `0.0.0.0/0`, used as fallback for all unknown destinations. |

---

## 3. Longest Prefix Match (LPM) & Route Selection

When forwarding packets, the router searches all active routes for subnets containing the destination IP:

$$\text{Match Condition: } (\text{Destination IP} \ \& \ \text{Mask}) == (\text{Network} \ \& \ \text{Mask})$$

1. **Prefix Length Prioritization**: The route with the highest number of contiguous network mask bits wins.
   - Example: `/24` (255.255.255.0) takes precedence over `/16` (255.255.0.0), which takes precedence over `/8` (255.0.0.0), which takes precedence over `/0` (0.0.0.0/0).
2. **Administrative Distance Precedence**: If two routes match the same prefix length (e.g. `C 192.168.10.0/24` and `S 192.168.10.0/24`), Connected routes ($\text{AD} = 0$) strictly win over Static routes ($\text{AD} = 1$). Traffic targeting directly connected devices is never misrouted to external next-hops.

---

## 4. Next-Hop Resolution & ARP

When a static route specifies a next-hop IP (e.g., `via 10.0.12.2`):
1. **Exit Interface Resolution**: The router looks up the next-hop IP in its routing table or directly connected subnets to determine the egress physical interface or subinterface.
2. **Next-Hop MAC Resolution**: The packet's destination MAC address is set to the MAC address of the next-hop gateway (resolved via ARP cache or ARP request/reply probe on the transit link).
3. **No Destination MAC Confusion**: The router does **not** broadcast ARP for the end host's remote IP address on transit links; it specifically queries and caches the next-hop router's MAC address.

---

## 5. Multihop Routing & TTL Tracking

In topologies spanning multiple routers (such as `PC1 | SW1 | R1 | R2 | R3 | SW2 | PC2`):
- **Layer 3 Hops**: Each router traversed decrements the IPv4 Time-to-Live field by 1 ($TTL_{\text{out}} = TTL_{\text{in}} - 1$).
- **Layer 2 Transparency**: Intermediate Layer 2 switches (SW1, SW2) forward frames based on MAC address tables and VLAN tagging without modifying the IP header or decrementing TTL.
- **Return Path Requirement**: Static routing is directional. For bidirectional connectivity (e.g. ICMP Echo Request and Echo Reply), all intermediate routers must have valid routing entries in both forward and reverse directions. Missing return routes cause immediate `U` (Destination Unreachable) drops without silent blackholing.

---

## 6. CLI Command Reference

### Add Static Route
```cisco
Router(config)# ip route <network> <subnet_mask> <next_hop_ip | interface_name>
```
*Example:*
```cisco
Router(config)# ip route 192.168.20.0 255.255.255.0 10.0.12.2
Router(config)# ip route 0.0.0.0 0.0.0.0 10.0.12.2
```

### Remove Static Route
```cisco
Router(config)# no ip route <network> <subnet_mask> [next_hop_ip | interface_name]
```
*Example:*
```cisco
Router(config)# no ip route 192.168.20.0 255.255.255.0 10.0.12.2
```

### Display Routing Table
```cisco
Router# show ip route
```
*Example Output:*
```text
Codes: C - connected, S - static, R - RIP, O - OSPF, * - candidate default
Gateway of last resort is 10.0.12.2 to network 0.0.0.0

C    192.168.10.0/24 is directly connected, GigabitEthernet0/0
C    10.0.12.0/30 is directly connected, GigabitEthernet0/1
S    192.168.20.0/24 [1/0] via 10.0.12.2
S*   0.0.0.0/0 [1/0] via 10.0.12.2
```

### Configuration Persistence
Static routes are automatically saved in the device configuration:
```cisco
Router# show running-config
...
ip route 192.168.20.0 255.255.255.0 10.0.12.2
...
```

---

## 7. Integration with Subsystems

1. **Router Subinterfaces (802.1Q)**: Static routes can point to subinterfaces (e.g. `g0/0.10`) or route between subinterfaces and physical interfaces.
2. **Switch & SVI**: Switches routing to default gateways forward frames seamlessly to router ports.
3. **Access Control Lists (ACL)**: Ingress and egress ACLs are evaluated before routing and after egress interface selection respectively. Static routes never bypass ACL permit/deny filters (`A` drop code).
4. **NAT / PAT**: Outbound packets across static routes trigger NAT translation on designated outside interfaces; return traffic is de-NATted prior to route lookup.
5. **Stateful Firewall**: Static routes across intermediate Firewalls maintain state table inspection and permit returning replies statefully.
6. **DHCP**: Hosts leasing network configuration from a router DHCP pool (IP, subnet mask, default router) immediately leverage static routes on the gateway.

---

## 8. Limitations & Exclusions (Strict Scope)

- **Duplicate Static Route Behavior**: Adding a static route with the exact same network prefix and subnet mask as an existing route deterministically **replaces** the previous next-hop/interface.
- **Recursive Next-Hop Lookup**: Direct (1-level) next-hop resolution to a connected interface is supported. Multi-level indirect recursive routing lookups are **Not Supported** and drop with status `U` (Destination Unreachable) to guarantee loop prevention.
- **Equal-Cost Multi-Path (ECMP)**: **Not Supported**. A single deterministic route is selected.
- **Dynamic Routing Protocols**: OSPF, RIP, EIGRP, BGP, IS-IS, VRF, and MPLS are out of scope for Phase 3.5.
