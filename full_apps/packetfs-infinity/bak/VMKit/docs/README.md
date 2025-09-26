# VMKit Quickemu UX

This layer adds a simple, cross-distro developer experience on top of Quickemu so a new user can:

1) just doctor
2) just setup (optional; with INSTALL=1)
3) just quickget ubuntu 24.04
4) just up ubuntu-24.04-desktop (or the generated name)

Directory layout:
- vms/: VM configs (.conf) and local disks created by templates (safe to delete)
- downloads/: ISO and base image cache from quickget
- templates/: Safe, commented Quickemu config templates
- scripts/: Helper scripts used by the Justfile

We do not run demos by default. Any demo materials must live under demo/ and be explicitly invoked.
