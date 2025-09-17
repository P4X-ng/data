# UX Contract: Just Commands

- just → help and summary
- just doctor → Environment checks (KVM/HVF, tools, disk space)
- just setup [INSTALL=1] → Install Quickemu and deps for your platform
- just quickget OS VERSION [FLAVOR] → Download image and generate .conf; moves .conf to vms/
- just new NAME [TEMPLATE=linux|windows] → Scaffold a new config from templates/
- just list → List configs in vms/
- just up NAME [HEADLESS=0] → Boot a VM
- just stop NAME → Graceful shutdown
- just ssh NAME [PORT=2222 USER=ubuntu] → SSH helper to forwarded port
- just delete NAME [CONFIRM=1] → Remove vms/NAME.conf and vms/NAME.*
- just clean [CONFIRM=1] → Clear downloads/

Defaults are safe and predictable. All destructive actions require explicit confirmation flags.
