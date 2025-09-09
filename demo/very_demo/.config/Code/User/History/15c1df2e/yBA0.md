# RFKilla Usage Guide

This document summarizes the command-line interface that ships with RFKilla. It lists the installed entry points, available commands and subcommands, key options, and a few quick examples.

## Entry points

These executables are installed by the package:

- `rfkilla` — primary CLI (also available via `python -m rfkilla`)
- `wifi-blocker` — Wi‑Fi blocker (Windows/aircrack-ng oriented)
- `bluetooth-kill` — Bluetooth monitor/whitelist manager

## Top-level rfkilla commands

- `discover` — Discover RF networks and devices
- `attack` — Launch active RF attacks
- `block` — Block local RF connections
- `observations` — Show recent RF observations
- `features` — Show advanced feature/dependency status
- `whitelist` — Manage trusted devices
- `malicious` — Manage malicious devices
- `confusion` — Confusion & deception attacks (experimental)
- `monitor` — Interface monitoring and health checks
- `enhanced` — Integrated advanced modes

Global options:
- `-v, --verbose` — verbose logging
- `--no-banner` — skip banner
- `--keep-data` — do not auto-reset discovered data on startup

## Subcommands overview

### whitelist
- `add <wifi|bluetooth> <identifier> [--name <str>]`
- `list [wifi|bluetooth]`
- `remove <wifi|bluetooth> <identifier>`

### malicious
- `add <wifi|bluetooth> <identifier> [--name <str>] [--reason <str>]`
- `list [wifi|bluetooth]`
- `remove <wifi|bluetooth> <identifier>`
- `clear <wifi|bluetooth> [--force]`

### discover
- Flags: `--wifi/--no-wifi` (default on), `--bluetooth/--no-bluetooth` (default on), `--time <sec>`, `--interval <sec>`, `--advanced`, `--live`

### attack
- Flags: `--wifi/--no-wifi` (default on), `--bluetooth/--no-bluetooth` (default off), `--time <sec|-1>`, `--interval <sec>`, `--confuse`, `--aggressive`, `--dry-run`

### block
- Flags: `--wifi/--no-wifi` (default on), `--bluetooth/--no-bluetooth` (default on), `--whitelist-only`

### observations
- Flags: `--limit <n>`, `--rf-type <wifi|bluetooth>`, `--live`

### features
- Shows feature flags and missing dependencies with install hints.

### confusion (experimental)
- `fake-aps` — create fake APs; flags: `--band <2.4ghz|5ghz|6ghz>`, `--count <n>`, `--duration <sec>`, `--ssid-prefix <str>`, `--dry-run`
- `deauth` — deauthentication loop; flags: `--interval <sec>`, `--duration <sec|-1>`, `--target <bssid>`, `--dry-run`
- `tag` — interactive tagging (placeholder; currently prints not implemented)

### monitor
- `adaptive` — continuous health monitoring; flags: `--check-interval <sec>`, `--discovery-interval <sec>`, `--max-failures <n>`, `--auto-recovery/--no-auto-recovery`, `--comprehensive/--quick`
- `health` — one-shot interface health check

### enhanced
- `tooling` — professional tooling attack; flags: `--wifi/--no-wifi`, `--bluetooth/--no-bluetooth`, `--duration <sec>`
- `bluetooth` — ultra‑aggressive Bluetooth mode; flags: `--duration <sec>`
- `monitor` — continuous interface monitoring; flags: `--duration <sec>`
- `nuclear` — full spectrum warfare; flags: `--duration <sec>`, `--confirm-nuclear`
- `guardian` — periodic assessment/auto‑response; flags: `--interval <sec>`

## Quick examples

> Note: Many actions require root/administrator privileges and optional tools (see Requirements).

- Show help and top-level commands

```bash
rfkilla --help
```

- Quick discovery (Wi‑Fi + Bluetooth) for 60s

```bash
rfkilla discover --time 60 --interval 10
```

- Plan an attack without executing it

```bash
rfkilla attack --wifi --bluetooth --time 120 --dry-run
```

- Add a device to whitelist and list current entries

```bash
rfkilla whitelist add wifi AA:BB:CC:DD:EE:FF --name "Office AP"
rfkilla whitelist list wifi
```

- Mark a device as malicious and view the list

```bash
rfkilla malicious add bluetooth 01:23:45:67:89:AB --name "Suspicious"
rfkilla malicious list
```

- Launch confusion fake APs (dry run)

```bash
rfkilla confusion fake-aps --count 5 --dry-run
```

- Start adaptive monitor

```bash
rfkilla monitor adaptive --check-interval 30 --discovery-interval 120
```

- Use enhanced Bluetooth mode for 20 minutes

```bash
rfkilla enhanced bluetooth --duration 1200
```

## wifi-blocker and bluetooth-kill

- `wifi-blocker` targets Windows flows (uses `netsh` and `aireplay-ng.exe`); writes logs to `rfkilla/logs/wifi-blocker.log`.
- `bluetooth-kill` lists devices or manages a Bluetooth whitelist (`--manage-whitelist --interval <sec>`), uses `bleak` when available.

## Requirements and privileges

- Many features require elevated privileges (Linux root/sudo; Windows admin).
- Optional packages unlock advanced capabilities (examples):
  - Wi‑Fi packet work: `scapy`, external tools like aircrack‑ng
  - Bluetooth: `bleak`
  - Advanced/AI: `psutil`, `netifaces`, `cryptography`, `pyshark`, ML libs
- Feature flags expose what’s enabled/missing:

```bash
rfkilla features
```

## Notes

- `confusion tag` is currently a placeholder (no interactive flow).
- The CLI auto‑resets auto‑discovered data on startup unless `--keep-data` is used.
- `python -m rfkilla` is equivalent to invoking `rfkilla` directly.
