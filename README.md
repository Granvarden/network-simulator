# NetEngineer 3D - Enterprise Network Simulator

> **Realistic First-Person 3D Network Engineer Simulator with Cisco IOS CLI, Datacenter Cabling, and Step-by-Step Training.**  
> Built with **Python, Pygame, and PyOpenGL**.

---

## Features

- **3D First-Person Datacenter Simulation**:
  - Walk around a high-tech datacenter room with 42U server racks, overhead cable trays, reflective tile floors, and an engineer's console workbench.
  - Realistic hardware models: Cisco Catalyst switches, Cisco ISR enterprise routers, Dell/HP servers, and workstations.
  - Dynamic status LEDs: Realistic blinking activity lights indicating physical link status (UP / DOWN / Negotiating) and live packet traffic.
  - Physical 3D Cables: Flexible, sagging 3D catenary curves for Cat6 UTP, Fiber Optic, and Console cables.

- **Realistic Cisco IOS CLI Console**:
  - Attached console terminal overlay with dark CRT aesthetic, font rendering, cursor, and scrollable history.
  - Authentic command modes: `Router>`, `Router#`, `Router(config)#`, `Router(config-if)#`, `Switch(config-vlan)#`.
  - Commands supported:
    - `enable`, `disable`
    - `configure terminal`
    - `interface <name>` (e.g. `int g0/1`)
    - `ip address <ip> <netmask>`
    - `no shutdown` / `shutdown`
    - `vlan <id>` -> `name <name>`
    - `switchport mode access / trunk`
    - `switchport access vlan <id>`
    - `ip route <network> <mask> <next_hop>`
    - `ip nat inside/outside`, `access-list <id> permit`, `ip nat inside source list ... overload`
    - `show ip interface brief`, `show running-config`, `show ip route`, `show ip arp`, `show vlan brief`, `show mac address-table`, `show ip nat translations`, `show access-list`
    - `ping <ip> [repeat N] [size N] [source INT]` (progressive real-time streaming, cold ARP drop `.!!!!`, Cisco codes `!`, `.`, `U`, `A`, synchronized 3D port LED blinks and per-packet audio)
    - `traceroute <ip>` (hop-by-hop latency and gateway probe)
    - `clear ip arp`, `clear ip nat translation *`, `clear conn`
    - **Tab autocompletion** and **? / help** support!

- **3 Distinct Game Modes**:
  1. **Tutorial Mode (Step-by-Step Training)**:
     - 5 guided onboarding lessons with dynamic objective checklist, pointers, and audio chimes.
     - Covers navigation, physical cabling, console access, Cisco port bringup, and ping tests.
  2. **Challenge Mode (Incident Troubleshooting)**:
     - NOC on-call incident tickets (P1 Critical Outages, VLAN Mismatches, Routing Failures).
     - Live timer, auto-grading checklist, and performance ratings.
  3. **Sandbox Mode (Datacenter Playground)**:
     - Freeform placement, cabling, and configuring.
     - 2D Logical Network Topology Map (Press `M`).
     - JSON Save (`K`) and Load (`L`) functionality.

- **Procedural Sound Engine**:
  - Datacenter ambient fan noise loop, mechanical keyboard typing clicks, RJ45 port snap clicks, and ICMP ping beeps synthesized via NumPy + Pygame Mixer (no external audio assets needed).

---

## Controls & Keybindings

| Key / Control | Action |
|---|---|
| **W, A, S, D** | Walk forward, left, backward, right in 3D |
| **Mouse Look** | Aim crosshair at racks, devices, and ports |
| **Left Shift** | Sprint / Walk faster |
| **[E]** | Open Cisco IOS Console Terminal for aimed device |
| **[F]** | Pick up cable / Plug cable into aimed port / Unplug |
| **[X]** | Cancel cable currently held in hand |
| **[M]** | Toggle 2D Logical Network Topology Blueprint |
| **[P] / [ESC]** | Detach CLI terminal or open Pause Menu |
| **[K] / [L]** | Save / Load topology (Sandbox mode) |
| **[N]** | Next incident ticket (Challenge mode) |
| **[F11]** | Toggle Fullscreen mode |

---

## How to Run

```bash
python main.py
```

### Running Automated Tests
```bash
python -m tests.test_network
python -m tests.test_cli
python -m tests.test_modes
python -m tests.test_game_loop
```
