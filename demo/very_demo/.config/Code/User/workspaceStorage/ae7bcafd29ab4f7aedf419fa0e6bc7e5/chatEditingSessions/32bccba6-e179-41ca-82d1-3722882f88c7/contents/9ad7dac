#!/usr/bin/env python3
"""Core Discovery Module - Central RF discovery and control system."""

import time
import json
import os
import logging
import threading
from . import bluetooth_stop, wifi_blocker, bluetooth_attack, advanced_confusion, aggressive_deny, json_store
# WiFi scanning is optional; provide graceful fallback if pywifi is unavailable
try:
    from .wifi_manager import scan_networks  # requires pywifi
except Exception:
    def scan_networks():  # type: ignore
        """Fallback WiFi scanner when pywifi is not installed.
        Returns an empty list to allow imports and non-WiFi features to work.
        """
        logger = logging.getLogger(__name__)
        logger.debug("pywifi not available; scan_networks fallback returning empty list")
        return []
from .bluetooth_kill import get_bt_devices
from .changeling_tracker import ChangelingTracker
from .feature_flags import get_feature_flags, is_feature_enabled, require_feature, warn_missing_dependencies

logger = logging.getLogger(__name__)

# Initialize feature flags
feature_flags = get_feature_flags()

# Conditional imports based on feature flags
AdvancedDiscovery = None
IntelligentAttacker = None 
intelligent_attacks_module = None
initialize_llm = lambda *a, **k: False
get_llm_analysis = lambda *a, **k: {"threat_level": "unknown", "analysis": "LLM not available"}
llm_intelligence = None

# Import enhanced modules from dev directory
PsychologicalRFWarfare = None
EnhancedRogueHunter = None
UltimateRFSecuritySystem = None
BluetoothAutoAnnihilator = None
InterfaceSanityMonitor = None

# Import advanced discovery if available
if is_feature_enabled('advanced_discovery'):
    try:
        from .advanced_discovery import AdvancedDiscovery
        logger.info("🔍 Advanced Discovery loaded successfully")
    except ImportError as e:
        logger.warning(f"⚠️  Advanced Discovery import failed: {e}")
        warn_missing_dependencies('advanced_discovery')

# Import intelligent attacks if available
if is_feature_enabled('intelligent_attacks'):
    try:
        from .intelligent_attacks import IntelligentAttacker
        from . import intelligent_attacks as intelligent_attacks_module
        logger.info("🧠 Intelligent Attacks loaded successfully")
    except ImportError as e:
        logger.warning(f"⚠️  Intelligent Attacks import failed: {e}")
        warn_missing_dependencies('intelligent_attacks')

# Import LLM intelligence if available
if is_feature_enabled('llm_intelligence'):
    try:
        from .llm_intelligence import initialize_llm, get_llm_analysis, llm_intelligence
        logger.info("🧠 LLM Intelligence loaded successfully")
    except ImportError as e:
        logger.warning(f"⚠️  LLM Intelligence import failed: {e}")
        warn_missing_dependencies('llm_intelligence')

# Try to import enhanced modules from dev directory
try:
    import sys
    # Get the parent directory of the rfkilla package (the main project root)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dev_path = os.path.join(project_root, 'dev')
    
    logger.debug(f"Looking for dev directory at: {dev_path}")
    if os.path.exists(dev_path) and dev_path not in sys.path:
        sys.path.insert(0, dev_path)
        logger.debug(f"Added dev path to sys.path: {dev_path}")
    
    # Import psychological warfare module (prefer packaged experimental shim)
    try:
        from .experimental.psychological_rf_warfare import PsychologicalRFWarfare
    except Exception:
        from psychological_rf_warfare import PsychologicalRFWarfare
        logger.info("🧠 Psychological RF Warfare loaded successfully")
    except ImportError as e:
        logger.debug(f"Psychological RF Warfare not available: {e}")
    
    # Import enhanced tooling integration (prefer packaged experimental shim)
    try:
        from .experimental.enhanced_tooling_integration import EnhancedRogueHunter
    except Exception:
        from enhanced_tooling_integration import EnhancedRogueHunter
        logger.info("🔧 Enhanced Tooling Integration loaded successfully")
    except ImportError as e:
        logger.debug(f"Enhanced Tooling Integration not available: {e}")
    
    # Import ultra-aggressive Bluetooth system (prefer packaged experimental shim)
    try:
        from .experimental.bt_auto_aggressive import BluetoothAutoAnnihilator
    except Exception:
        from bt_auto_aggressive import BluetoothAutoAnnihilator
        logger.info("📱 Ultra-Aggressive Bluetooth Auto-Annihilator loaded successfully")
    except ImportError as e:
        logger.debug(f"Bluetooth Auto-Annihilator not available: {e}")
    
    # Import interface sanity monitor (prefer packaged experimental shim)
    try:
        from .experimental.interface_sanity_monitor import InterfaceSanityMonitor
    except Exception:
        from interface_sanity_monitor import InterfaceSanityMonitor
        logger.info("🔍 Interface Sanity Monitor loaded successfully")
    except ImportError as e:
        logger.debug(f"Interface Sanity Monitor not available: {e}")
    
    # Import ultimate RF security system (left in dev/ only; experimental)
    try:
        from ultimate_rf_security import UltimateRFSecuritySystem
        logger.info("🛡️ Ultimate RF Security System loaded successfully")
    except ImportError as e:
        logger.debug(f"Ultimate RF Security System not available: {e}")
        
except Exception as e:
    logger.debug(f"Enhanced modules import failed: {e}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WIFI_WHITELIST_LEGACY = os.path.join(BASE_DIR, "wifi_whitelist.jsonl")
BT_WHITELIST_LEGACY = os.path.join(BASE_DIR, "bluetooth_whitelist.jsonl")
MALICIOUS_WIFI_LEGACY = os.path.join(BASE_DIR, "malicious_wifi.jsonl")
MALICIOUS_BT_LEGACY = os.path.join(BASE_DIR, "malicious_bluetooth.jsonl")

 # logger already defined above

def _migrate_legacy_lists_once():
    """Migrate legacy JSONL whitelist/malicious lists into json_store (idempotent)."""
    marker = os.path.join(BASE_DIR, ".legacy_migrated")
    if os.path.exists(marker):
        return
    migrated = 0
    def _ingest(path, add_fn, rf_type):
        nonlocal migrated
        if not os.path.isfile(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                    except Exception:
                        continue
                    ident = entry.get('id') or entry.get('bssid') or entry.get('mac')
                    name = entry.get('name', '')
                    if ident:
                        try:
                            add_fn(rf_type, ident, name)
                            migrated += 1
                        except Exception:
                            continue
            os.rename(path, path + '.migrated')
        except Exception:
            pass
    for rf_type, path in [('wifi', WIFI_WHITELIST_LEGACY), ('bluetooth', BT_WHITELIST_LEGACY)]:
        _ingest(path, json_store.add_whitelist, rf_type)
    for rf_type, path in [('wifi', MALICIOUS_WIFI_LEGACY), ('bluetooth', MALICIOUS_BT_LEGACY)]:
        _ingest(path, json_store.add_malicious, rf_type)
    with open(marker, 'w') as m:
        m.write(str(migrated))
    if migrated:
        logger.info(f"Migrated {migrated} legacy whitelist/malicious entries into json_store")

def prompt_with_timeout(message, timeout=10, default="n"):
    """Prompt user with timeout, return default if timeout."""
    import select
    import sys
    
    print(f"{message} (timeout in {timeout}s, default: {default}): ", end='', flush=True)
    
    # Windows doesn't have select for stdin, use threading
    result = [default]
    
    def get_input():
        try:
            result[0] = input().strip().lower()
        except:
            pass
    
    thread = threading.Thread(target=get_input)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        print(f"\nTimeout! Using default: {default}")
        return default
    
    return result[0] if result[0] else default

def _scan_with_iw(interface):
    """Scan WiFi networks using iw command."""
    import subprocess
    import re
    
    try:
        # Run iw scan
        result = subprocess.run(['sudo', 'iw', 'dev', interface, 'scan'], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"iw scan failed: {result.stderr}")
            return []
        
        networks = []
        current_network = {}
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            
            if line.startswith('BSS '):
                # Save previous network if complete
                if current_network.get('bssid'):
                    networks.append(current_network)
                
                # Start new network
                bssid_match = re.search(r'BSS ([0-9a-f:]{17})', line)
                current_network = {
                    'bssid': bssid_match.group(1).upper() if bssid_match else '',
                    'ssid': '<Hidden>',
                    'signal': 0,
                    'channel': 'Unknown'
                }
            
            elif 'SSID:' in line:
                ssid = line.split('SSID: ', 1)[1] if 'SSID: ' in line else '<Hidden>'
                current_network['ssid'] = ssid if ssid else '<Hidden>'
            
            elif 'signal:' in line:
                signal_match = re.search(r'signal: ([+-]?\d+)', line)
                if signal_match:
                    signal_dbm = int(signal_match.group(1))
                    # Convert dBm to approximate percentage
                    signal_percent = max(0, min(100, int(2 * (signal_dbm + 100))))
                    current_network['signal'] = signal_percent
            
            elif 'DS Parameter set: channel' in line:
                channel_match = re.search(r'channel (\d+)', line)
                if channel_match:
                    current_network['channel'] = channel_match.group(1)
        
        # Add the last network
        if current_network.get('bssid'):
            networks.append(current_network)
        
        return networks
        
    except subprocess.TimeoutExpired:
        logger.error(f"iw scan timeout on {interface}")
        return []
    except Exception as e:
        logger.error(f"iw scan error on {interface}: {e}")
        return []

def discover_wifi():
    """Discover WiFi networks and return list."""
    try:
        # Try PyWiFi first
        networks = scan_networks()
        if networks:
            logger.info(f"Discovered {len(networks)} WiFi networks via PyWiFi")
            return networks
        
        # Fallback to iw scan using interfaces from advanced_confusion
        logger.warning("PyWiFi returned no results, trying iw scan")
        from .advanced_confusion import get_wifi_interfaces
        interfaces = get_wifi_interfaces()
        
        if not interfaces:
            logger.error("No WiFi interfaces available")
            return []
        
        # Use the first available interface for scanning
        interface = interfaces[0]
        networks = _scan_with_iw(interface)
        logger.info(f"Discovered {len(networks)} WiFi networks via iw on {interface}")
        return networks
        
    except Exception as e:
        logger.error(f"WiFi discovery failed: {e}")
        return []

def discover_bluetooth():
    """Discover Bluetooth devices and return list."""
    try:
        # Enable Bluetooth for discovery only if not already enabled
        from .bluetooth_manager import enable_bluetooth, is_bluetooth_enabled
        
        if not is_bluetooth_enabled():
            logger.info("🔓 Enabling Bluetooth for discovery...")
            enable_bluetooth()
            time.sleep(3)  # Allow time for Bluetooth to fully activate
        else:
            logger.debug("Bluetooth already enabled for discovery")
        
        devices = get_bt_devices()
        logger.info(f"Discovered {len(devices)} Bluetooth devices")
        return devices
    except Exception as e:
        logger.error(f"Bluetooth discovery failed: {e}")
        return []

def disable_wifi_autoconnect():
    """Disable WiFi auto-connect and disconnect current connections."""
    try:
        # Disconnect all WiFi connections
        import subprocess
        subprocess.run(['netsh', 'wlan', 'disconnect'], capture_output=True)
        
        # Disable auto-connect for all profiles
        result = subprocess.run(['netsh', 'wlan', 'show', 'profiles'], 
                              capture_output=True, text=True)
        
        for line in result.stdout.splitlines():
            if 'All User Profile' in line:
                profile = line.split(':')[1].strip()
                subprocess.run(['netsh', 'wlan', 'set', 'profileparameter', 
                              f'name="{profile}"', 'connectionmode=manual'], 
                              capture_output=True)
        
        logger.info("Disabled WiFi auto-connect")
        return True
    except Exception as e:
        logger.error(f"Failed to disable WiFi auto-connect: {e}")
        return False

def aggressive_bluetooth_block():
    """Aggressively block all Bluetooth activity."""
    try:
        bluetooth_stop.stop_bluetooth()
        logger.info("Aggressively blocked Bluetooth")
        return True
    except Exception as e:
        logger.error(f"Failed to block Bluetooth: {e}")
        return False

def discovery_phase(wifi_enabled, bt_enabled, discovery_time, interval, advanced_mode=False):
    """Run discovery phase with user interaction."""
    # Check which advanced features are available
    advanced_discovery_available = advanced_mode and is_feature_enabled('advanced_discovery')
    llm_available_flag = advanced_mode and is_feature_enabled('llm_intelligence')
    
    mode_text = "ADVANCED" if advanced_discovery_available or llm_available_flag else "STANDARD"
    print(f"\n=== {mode_text} DISCOVERY PHASE ({discovery_time}s) ===")
    print("Scanning for RF networks. Everything is MALICIOUS unless whitelisted!")
    print("🕵️ Changeling detection ACTIVE - tracking network changes")
    
    # Show available advanced features
    if advanced_mode:
        if advanced_discovery_available:
            print("🔍 Deep packet inspection ENABLED")
        elif not is_feature_enabled('advanced_discovery'):
            print("⚠️  Deep packet inspection DISABLED - missing scapy dependency")
            
        if llm_available_flag:
            print("🧠 AI-powered threat analysis ACTIVE")
            # Initialize LLM
            llm_available = initialize_llm("llama3.1:8b")
            if llm_available:
                print("🧠 Local LLM intelligence ONLINE")
            else:
                print("⚠️  LLM connection failed - check Ollama server")
        elif not is_feature_enabled('llm_intelligence'):
            print("⚠️  LLM Intelligence DISABLED - missing dependencies")
    
    json_store.init()
    _migrate_legacy_lists_once()
    wifi_whitelist = set(json_store.list_whitelist('wifi').keys()) if wifi_enabled else set()
    bt_whitelist = set(json_store.list_whitelist('bluetooth').keys()) if bt_enabled else set()
    
    # Initialize changeling tracker
    tracker = ChangelingTracker()
    
    # Initialize advanced discovery if available
    advanced_discovery = None
    if advanced_discovery_available and wifi_enabled and AdvancedDiscovery:
        try:
            advanced_discovery = AdvancedDiscovery()  # type: ignore
            # Start packet capture on first available interface
            from .advanced_confusion import get_wifi_interfaces
            interfaces = get_wifi_interfaces()
            if interfaces:
                logger.info(f"🔍 Starting packet capture on {interfaces[0]}")
                advanced_discovery.start_packet_capture(interfaces[0], discovery_time)
            else:
                logger.warning("⚠️  No WiFi interfaces available for packet capture")
        except Exception as e:
            logger.error(f"Failed to initialize advanced discovery: {e}")
            advanced_discovery = None
    
    start_time = time.time()
    
    while time.time() - start_time < discovery_time:
        print(f"\n--- Discovery scan (remaining: {int(discovery_time - (time.time() - start_time))}s) ---")
        
        # WiFi Discovery
        if wifi_enabled:
            disable_wifi_autoconnect()  # Prevent auto-connections
            networks = discover_wifi()
            
            for net in networks:
                ssid = net.get('ssid', '')
                bssid = net.get('bssid', '')
                
                # Track for changeling behavior
                is_changeling = tracker.track_wifi_network(net)
                
                # LLM Analysis if available
                llm_analysis = None
                if llm_available_flag and llm_intelligence and getattr(llm_intelligence, 'available', False):
                    try:
                        llm_analysis = get_llm_analysis(net)
                        threat_level = llm_analysis.get('threat_level', 'unknown')
                        confidence = llm_analysis.get('confidence', 0.0)
                        
                        if threat_level in ['high', 'critical'] and float(confidence) > 0.7:
                            logger.error(f"LLM HIGH THREAT: {ssid} ({bssid}) - {threat_level.upper()}")
                            logger.error(f"   Analysis: {llm_analysis.get('analysis', '')[:100]}...")
                            is_changeling = True
                    except Exception as e:
                        logger.debug(f"LLM analysis failed for {ssid}: {e}")
                
                if bssid.lower() not in wifi_whitelist and ssid.lower() not in wifi_whitelist:
                    # Auto-classify changelings and LLM high threats as malicious
                    if is_changeling or tracker.is_known_changeling(bssid):
                        reason = "Changeling" if not llm_analysis else f"LLM-{llm_analysis.get('threat_level', 'unknown').upper()}"
                        logger.error(f"🚨 AUTO-MALICIOUS ({reason}): {ssid} ({bssid})")
                        json_store.add_malicious('wifi', bssid, ssid, reason)
                    else:
                        # Show LLM analysis in prompt if available
                        prompt_text = f"MALICIOUS WiFi detected: {ssid} ({bssid})"
                        if llm_analysis:
                            threat_level = llm_analysis.get('threat_level', 'unknown')
                            prompt_text += f" [LLM: {threat_level.upper()}]"
                        prompt_text += ". Whitelist? [y/N]"
                        
                        response = prompt_with_timeout(prompt_text, timeout=10, default="n")
                        
                        if response.startswith('y'):
                            json_store.add_whitelist('wifi', bssid, ssid)
                            wifi_whitelist.add(bssid.lower())
                        else:
                            json_store.add_malicious('wifi', bssid, ssid, 'user-deny')
                            
                            # Add to LLM threat context
                            if llm_intelligence and getattr(llm_intelligence, 'available', False):
                                llm_intelligence.add_threat_context({
                                    'source': bssid,
                                    'threat_type': 'malicious_wifi',
                                    'ssid': ssid,
                                    'llm_analysis': llm_analysis
                                })
        
        # Bluetooth Discovery
        if bt_enabled:
            aggressive_bluetooth_block()  # Block pairing attempts
            devices = discover_bluetooth()
            
            for inst, name in devices:
                # Track for changeling behavior
                is_changeling = tracker.track_bluetooth_device(inst, name)
                
                if inst.lower() not in bt_whitelist:
                    # Auto-classify changelings as malicious
                    if is_changeling or tracker.is_known_changeling(inst):
                        logger.error(f"🚨 AUTO-MALICIOUS: Changeling {name} ({inst})")
                        json_store.add_malicious('bluetooth', inst, name, 'changeling')
                    else:
                        response = prompt_with_timeout(
                            f"MALICIOUS Bluetooth detected: {name} ({inst}). Whitelist? [y/N]",
                            timeout=10, default="n"
                        )
                        
                        if response.startswith('y'):
                            json_store.add_whitelist('bluetooth', inst, name)
                            bt_whitelist.add(inst.lower())
                        else:
                            json_store.add_malicious('bluetooth', inst, name, 'user-deny')
            
            # Re-disable Bluetooth after scan (only if currently enabled)
            from .bluetooth_manager import is_bluetooth_enabled
            if is_bluetooth_enabled():
                bluetooth_stop.stop_bluetooth()
        
        # Check for disappeared networks (possible adaptation)
        if wifi_enabled and 'networks' in locals():  # type: ignore[name-defined]
            tracker.detect_network_disappearance(locals().get('networks', []), 'wifi')
        if bt_enabled and 'devices' in locals():  # type: ignore[name-defined]
            tracker.detect_network_disappearance(locals().get('devices', []), 'bluetooth')
        
        time.sleep(interval)
    
    # Advanced analysis results
    if advanced_discovery:  # type: ignore[truthy-function]
        advanced_discovery.stop_capture()
        packet_changelings = advanced_discovery.get_changeling_candidates()
        if packet_changelings:
            print(f"\n🔍 PACKET ANALYSIS RESULTS:")
            for changeling in packet_changelings:
                print(f"   🔄 Confirmed changeling: {changeling['mac']}")
                print(f"      SSIDs: {changeling['ssids']}")
                print(f"      Threat Score: {changeling['threat_score']:.2f}")
                
                # Auto-add packet-confirmed changelings to malicious list
                json_store.add_malicious('wifi', changeling['mac'], f"PACKET_CHANGELING_{changeling['mac']}", 'packet-changeling')
    
    # Print changeling statistics
    stats = tracker.get_changeling_stats()
    print(f"\n=== DISCOVERY PHASE COMPLETE ===")
    print(f"🕵️ Changelings detected: {stats['total_changelings']} total")
    print(f"   WiFi changelings: {stats['wifi_changelings']}")
    print(f"   Bluetooth changelings: {stats['bluetooth_changelings']}")
    
    if advanced_mode:
        if advanced_discovery:
            pkt_count = len(locals().get('packet_changelings', []))
            print(f"🔍 Packet-confirmed changelings: {pkt_count}")
        
        # Start continuous LLM threat monitoring if available
        if llm_available_flag and llm_intelligence and getattr(llm_intelligence, 'available', False):
            try:
                monitor_thread = threading.Thread(target=llm_intelligence.continuous_threat_monitoring, args=(300,))
                monitor_thread.daemon = True
                monitor_thread.start()
                print("🧠 LLM continuous threat monitoring STARTED")
            except Exception as e:
                logger.warning(f"Failed to start LLM monitoring: {e}")

def block_phase(wifi_enabled, bt_enabled):
    """Run blocking phase - ensure no connections."""
    print("\n=== BLOCK PHASE ACTIVE ===")
    print("Blocking all RF connections...")
    
    if wifi_enabled:
        disable_wifi_autoconnect()
        print("WiFi auto-connect disabled")
    
    if bt_enabled:
        aggressive_bluetooth_block()
        print("Bluetooth completely blocked")

def attack_phase(wifi_enabled, bt_enabled, attack_time, confuse_enabled, aggressive_mode=False, psychological_mode=False):
    """Run attack phase - active denial of service."""
    mode_text = "AGGRESSIVE" if aggressive_mode else "STANDARD"
    if psychological_mode:
        mode_text += " + PSYCHOLOGICAL"
    
    print(f"\n=== {mode_text} ATTACK PHASE ({attack_time}s) ===")
    print(f"{'🔥 MAXIMUM AGGRESSION' if aggressive_mode else 'Active'} RF denial of service...")
    
    if psychological_mode:
        print("🧠 PSYCHOLOGICAL WARFARE ENABLED - Mind games active")
    
    # Load malicious lists
    json_store.init()
    malicious_wifi = set(json_store.list_malicious('wifi').keys()) if wifi_enabled else set()
    malicious_bt = set(json_store.list_malicious('bluetooth').keys()) if bt_enabled else set()
    
    # Show what targets we're attacking
    print(f"\n🎯 Attack Targets:")
    if wifi_enabled:
        print(f"   📡 WiFi targets: {len(malicious_wifi)} networks")
        for target in list(malicious_wifi)[:3]:  # Show first 3
            print(f"      • {target}")
        if len(malicious_wifi) > 3:
            print(f"      • ... and {len(malicious_wifi) - 3} more")
    
    if bt_enabled:
        print(f"   📱 Bluetooth targets: {len(malicious_bt)} devices")
        for target in list(malicious_bt)[:3]:  # Show first 3
            print(f"      • {target[:20]}...")
        if len(malicious_bt) > 3:
            print(f"      • ... and {len(malicious_bt) - 3} more")
    
    if not malicious_wifi and not malicious_bt:
        print(f"   ⚠️  No malicious targets found - discovery phase may need more time")
        print(f"   ℹ️  Run 'python -m rfkilla malicious add wifi <bssid>' to add test targets")
    
    start_time = time.time()
    attack_threads = []
    bluetooth_blocked = False  # Track Bluetooth state
    
    try:
        # Start confusion attacks if enabled
        if confuse_enabled and wifi_enabled:
            # Advanced confusion techniques
            confuse_thread = threading.Thread(
                target=advanced_confusion.run_advanced_confusion,
                args=(wifi_enabled, bt_enabled, attack_time if attack_time != -1 else 300)
            )
            confuse_thread.daemon = True
            confuse_thread.start()
            attack_threads.append(confuse_thread)
        
        # Main attack loop
        loop_count = 0
        while attack_time == -1 or time.time() - start_time < attack_time:
            loop_count += 1
            print(f"\n🔄 Attack Loop #{loop_count} (elapsed: {int(time.time() - start_time)}s)")
            
            # Bluetooth attacks
            if bt_enabled:
                # Attack malicious Bluetooth devices if we have any
                if malicious_bt:
                    print(f"   ⚔️  Attacking {len(malicious_bt)} Bluetooth targets...")
                    
                    # Enable Bluetooth temporarily for attack operations
                    from .bluetooth_manager import enable_bluetooth, is_bluetooth_enabled
                    if not is_bluetooth_enabled():
                        print("   🔓 Enabling Bluetooth for attack operations...")
                        enable_bluetooth()
                        time.sleep(2)  # Brief activation delay
                    
                    if aggressive_mode:
                        # Use aggressive Bluetooth denial attacks
                        bt_aggressive_thread = threading.Thread(
                            target=aggressive_deny.run_aggressive_denial,
                            args=(None, True, 60)
                        )
                        bt_aggressive_thread.daemon = True
                        bt_aggressive_thread.start()
                        attack_threads.append(bt_aggressive_thread)
                        print("     🔥 Aggressive Bluetooth attacks launched")
                    else:
                        # Standard flood attacks on specific devices
                        for device_id in list(malicious_bt)[:5]:  # Limit to avoid overload
                            flood_thread = threading.Thread(
                                target=advanced_confusion.bluetooth_file_flood,
                                args=(device_id, 10)
                            )
                            flood_thread.daemon = True
                            flood_thread.start()
                            attack_threads.append(flood_thread)
                        print(f"     📡 Bluetooth flood attacks on {min(len(malicious_bt), 5)} targets")
                    
                    # After attacks are launched, block defensively
                    time.sleep(5)  # Allow attacks to start
                    if not bluetooth_blocked:
                        print("   🔒 Blocking Bluetooth defensively after attacks launched")
                        aggressive_bluetooth_block()
                        bluetooth_blocked = True
                        
                else:
                    # No Bluetooth targets, just block defensively
                    if not bluetooth_blocked:
                        print("   🔒 Blocking Bluetooth communications (defensive mode)")
                        aggressive_bluetooth_block()
                        bluetooth_blocked = True
                        print("   ✅ Bluetooth blocked defensively")
                    print("   ℹ️  No Bluetooth targets to attack")
            
            # WiFi attacks  
            if wifi_enabled:
                disable_wifi_autoconnect()
                
                # Deauth malicious WiFi networks
                networks = discover_wifi()
                malicious_networks = [net for net in networks 
                                    if net.get('bssid', '').lower() in malicious_wifi]
                
                if malicious_networks:
                    # Check if intelligent attacks are available for aggressive mode
                    intelligent_attacks_available = aggressive_mode and is_feature_enabled('intelligent_attacks')
                    
                    if intelligent_attacks_available and IntelligentAttacker:
                        # Use intelligent attacks with optional LLM guidance
                        from .advanced_confusion import get_wifi_interfaces
                        interfaces = get_wifi_interfaces()
                        if interfaces:
                            for network in malicious_networks[:3]:  # Limit to top 3 targets
                                try:
                                    # Get LLM attack recommendations if available
                                    if llm_intelligence and getattr(llm_intelligence, 'available', False):
                                        attack_history = []  # Would load from attack log
                                        llm_attack_analysis = llm_intelligence.analyze_attack_effectiveness(
                                            attack_history, network
                                        )
                                        logger.info(f"🧠 LLM Attack Strategy: {llm_attack_analysis.get('analysis', '')[:100]}...")
                                    
                                    # Launch intelligent attack
                                    attacker = IntelligentAttacker()
                                    intel_threads = attacker.adaptive_attack(network, interfaces[0], 60)
                                    attack_threads.extend(intel_threads)
                                except Exception as e:
                                    logger.warning(f"Failed to launch intelligent attack on {network.get('ssid', 'unknown')}: {e}")
                                    # Fallback to standard deauth
                                    deauth_thread = threading.Thread(
                                        target=advanced_confusion.deauth_storm,
                                        args=([network], 30)
                                    )
                                    deauth_thread.daemon = True
                                    deauth_thread.start()
                                    attack_threads.append(deauth_thread)
                    elif aggressive_mode:
                        # Use aggressive denial system
                        aggressive_thread = threading.Thread(
                            target=aggressive_deny.run_aggressive_denial,
                            args=(malicious_networks, False, 60)
                        )
                        aggressive_thread.daemon = True
                        aggressive_thread.start()
                        attack_threads.append(aggressive_thread)
                    else:
                        # Standard coordinated deauth storm
                        deauth_thread = threading.Thread(
                            target=advanced_confusion.deauth_storm,
                            args=(malicious_networks, 30)
                        )
                        deauth_thread.daemon = True
                        deauth_thread.start()
                        attack_threads.append(deauth_thread)
            
            time.sleep(5)  # Attack interval
            
        # Add psychological warfare if enabled
        if psychological_mode and PsychologicalRFWarfare:
            try:
                print("\n🧠 DEPLOYING PSYCHOLOGICAL WARFARE...")
                psych_warfare = PsychologicalRFWarfare()
                
                # Launch fear campaign in parallel
                fear_thread = threading.Thread(
                    target=psych_warfare.deploy_fear_campaign,
                    args=(attack_time if attack_time != -1 else 300,)
                )
                fear_thread.daemon = True
                fear_thread.start()
                attack_threads.append(fear_thread)
                
                # Launch confusion matrix after 30 seconds
                time.sleep(30)
                confusion_thread = threading.Thread(
                    target=psych_warfare.deploy_confusion_matrix,
                    args=("general", attack_time if attack_time != -1 else 300)
                )
                confusion_thread.daemon = True
                confusion_thread.start()
                attack_threads.append(confusion_thread)
                
                print("✅ Psychological warfare campaigns launched!")
            except Exception as e:
                logger.warning(f"Psychological warfare failed: {e}")
            
    except KeyboardInterrupt:
        print("\nAttack phase interrupted by user")
    
    print("\n=== ATTACK PHASE COMPLETE ===")

def main_rf_loop(wifi_enabled, bt_enabled, discovery_time, attack_time, 
                 interval, block_only, attack_enabled, confuse_enabled, 
                 aggressive_mode=False, advanced_mode=False):
    """Main RF control loop."""
    logger.info("Starting RFKilla main loop")
    
    try:
        # Discovery Phase
        discovery_phase(wifi_enabled, bt_enabled, discovery_time, interval, advanced_mode)
        
        if block_only:
            # Block Phase Only
            print("\nEntering continuous block mode...")
            while True:
                block_phase(wifi_enabled, bt_enabled)
                time.sleep(interval)
        else:
            # Attack/Confuse Phase
            attack_phase(wifi_enabled, bt_enabled, attack_time, confuse_enabled, aggressive_mode)
            
    except KeyboardInterrupt:
        print("\nRFKilla loop interrupted by user")
    finally:
        # Cleanup
        if bt_enabled:
            bluetooth_stop.stop_bluetooth()
        if wifi_enabled:
            disable_wifi_autoconnect()
        logger.info("RFKilla loop ended")

# Enhanced Attack Modes using the powerful integrated modules
def enhanced_tooling_attack_phase(wifi_enabled, bt_enabled, attack_duration=600):
    """Enhanced attack phase using professional tooling integration"""
    if not EnhancedRogueHunter:
        print("⚠️  Enhanced tooling not available")
        return
    
    print(f"\n🔧 === ENHANCED TOOLING ATTACK PHASE ({attack_duration}s) ===")
    print("🎆 Professional-grade RF security tools engaged")
    print("📊 Comprehensive threat assessment → coordinated attack")
    
    try:
        # Initialize enhanced rogue hunter
        enhanced_hunter = EnhancedRogueHunter()
        
        # Phase 1: Comprehensive RF Assessment
        print("\n🔍 Phase 1: Multi-spectrum threat assessment")
        assessment_results = enhanced_hunter.comprehensive_rf_assessment(
            wifi_interface="wlan0", 
            bt_interfaces=["hci0"], 
            duration=attack_duration // 3
        )
        
        threats = assessment_results.get('potential_threats', [])
        print(f"🎯 Threat assessment complete: {len(threats)} threats identified")
        
        if threats:
            # Phase 2: Coordinated Professional Attack
            print("\n⚔️  Phase 2: Coordinated professional assault")
            attack_results = enhanced_hunter.launch_coordinated_attack(
                threats, 
                wifi_interface="wlan0",
                attack_duration=attack_duration * 2 // 3
            )
            
            print(f"✅ Enhanced attack complete:")
            print(f"   • Successful attacks: {attack_results['successful_attacks']}")
            print(f"   • Failed attacks: {attack_results['failed_attacks']}")
        else:
            print("ℹ️  No threats found - environment appears secure")
            
    except Exception as e:
        logger.error(f"Enhanced tooling attack failed: {e}")

def ultra_aggressive_bluetooth_mode(duration=1200):
    """Ultra-aggressive Bluetooth auto-annihilation mode"""
    if not BluetoothAutoAnnihilator:
        print("⚠️  Ultra-aggressive Bluetooth system not available")
        return
    
    print(f"\n📱 === ULTRA-AGGRESSIVE BLUETOOTH MODE ({duration}s) ===")
    print("🔥 MAXIMUM Bluetooth threat annihilation")
    print("🚀 Production-ready zero-trust security system")
    
    try:
        # Configure for maximum aggression
        config = {
            'scan_interval': 1.0,           # Very fast scanning
            'unattended_timeout': 3.0,      # Quick auto-classification
            'threat_threshold': 60.0,       # Lower threshold = more sensitive
            'auto_attack_threshold': 80.0,  # Auto-attack above this score
            'attack_methods': ['flood', 'disrupt', 'chaos'],
            'log_file': '/tmp/ultra_aggressive_bt.log',
            'max_devices_per_cycle': 15
        }
        
        # Initialize and start the annihilation system
        annihilator = BluetoothAutoAnnihilator(config)
        
        # Run for specified duration
        print(f"🚀 Ultra-aggressive Bluetooth annihilation ACTIVE")
        
        # Start in a separate thread to allow for timeout
        annihilator_thread = threading.Thread(target=annihilator.start)
        annihilator_thread.daemon = True
        annihilator_thread.start()
        
        # Monitor for the specified duration
        time.sleep(duration)
        annihilator.running = False
        
        print("✅ Ultra-aggressive Bluetooth mode complete")
        
    except Exception as e:
        logger.error(f"Ultra-aggressive Bluetooth mode failed: {e}")

def interface_monitoring_mode(duration=600):
    """Continuous interface health monitoring mode"""
    if not InterfaceSanityMonitor:
        print("⚠️  Interface sanity monitor not available")
        return
    
    print(f"\n🔍 === INTERFACE MONITORING MODE ({duration}s) ===")
    print("🚪 Continuous RF interface health monitoring")
    print("🔧 Auto-recovery and sanity verification active")
    
    try:
        monitor = InterfaceSanityMonitor()
        
        # Configure for comprehensive monitoring
        monitor.config['check_interval'] = 10
        monitor.config['auto_recovery'] = True
        monitor.config['comprehensive_check_interval'] = 120
        
        # Start monitoring in thread with timeout
        monitor_thread = threading.Thread(target=monitor.start_continuous_monitoring)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Monitor for specified duration
        time.sleep(duration)
        monitor.running = False
        
        print("✅ Interface monitoring mode complete")
        
    except Exception as e:
        logger.error(f"Interface monitoring mode failed: {e}")

def nuclear_option_mode(duration=1800):
    """🚀 NUCLEAR OPTION: Full spectrum RF warfare"""
    if not UltimateRFSecuritySystem:
        print("⚠️  Ultimate RF Security System not available")
        return
    
    print(f"\n💥 === NUCLEAR OPTION MODE ({duration}s) ===")
    print("🚀 MAXIMUM RF WARFARE - All attack vectors deployed")
    print("☢️  WARNING: Full spectrum annihilation active")
    print("🧠 Psychological + Technical + Chaos attacks")
    
    try:
        # Initialize ultimate RF security system
        ultimate_system = UltimateRFSecuritySystem()
        
        # Run comprehensive threat assessment first
        print("\n🔍 Phase 1: Ultimate threat assessment")
        assessment = ultimate_system.comprehensive_threat_assessment(duration // 4)
        
        threats = assessment.get('consolidated_threats', [])
        print(f"🎯 Ultimate assessment complete: {len(threats)} threats")
        
        if threats:
            # Launch nuclear option attack
            print("\n💥 Phase 2: NUCLEAR OPTION DEPLOYMENT")
            nuclear_results = ultimate_system.nuclear_option_mode(
                target_threats=threats,
                duration=duration * 3 // 4
            )
            
            print(f"✅ Nuclear option complete:")
            print(f"   • Psychological campaigns: {nuclear_results.get('psychological_campaigns', 0)}")
            print(f"   • Technical attacks: {nuclear_results.get('technical_attacks', 0)}")
            print(f"   • Confusion deployments: {nuclear_results.get('confusion_deployments', 0)}")
            print(f"   • Devastation level: {nuclear_results.get('total_devastation_level', 'UNKNOWN')}")
        else:
            print("ℹ️  No threats found for nuclear option")
            
    except Exception as e:
        logger.error(f"Nuclear option mode failed: {e}")

def continuous_guardian_mode(assessment_interval=300):
    """Continuous guardian mode with periodic threat assessment"""
    if not UltimateRFSecuritySystem:
        print("⚠️  Ultimate RF Security System not available")
        return
    
    print(f"\n🛡️ === CONTINUOUS GUARDIAN MODE ===")
    print(f"🚪 Automated RF threat detection and response")
    print(f"⏰ Assessment interval: {assessment_interval}s")
    print("🎆 Auto-engage critical threats, prompt for others")
    
    try:
        ultimate_system = UltimateRFSecuritySystem()
        ultimate_system.continuous_guardian_mode(assessment_interval)
        
    except Exception as e:
        logger.error(f"Continuous guardian mode failed: {e}")
