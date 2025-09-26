#!/usr/bin/env python3
"""
pf.py — tiny symbol‑free pyinfra runner for PacketFS

Features
- One file: this script is both the CLI and the DSL executor
- Symbol‑free DSL loaded from Pfyfile.pf (with includes)
- Tasks: task <name> ... end; describe; shell; packages install/remove; service; directory; copy
- Hosts/env: env=prod, hosts=user@ip:22,..., repeatable host=...; default @local
- Sudo: sudo=true to run operations with sudo
- Streams pyinfra output (runs /home/punk/.venv/bin/python -m pyinfra ...)

Usage
  ./pf.py list                   # show tasks (grouped by category prefix before '-')
  ./pf.py dev-setup              # run a task locally (@local)
  ./pf.py env=prod dev-test      # use env alias (see ENV_MAP)
  ./pf.py host=punk@10.0.0.5:22 dev-setup
  ./pf.py host=ubuntu@1.2.3.4 host=punk@4.3.2.1 sudo=true service-restart

DSL (in Pfyfile.pf or included files)
  include base.pf

  task dev-setup
    describe Setup central venv tools
    shell /home/punk/.venv/bin/python -m pip -q -U pip setuptools wheel
  end

  task dev-test
    describe Run unit tests
    shell /home/punk/.venv/bin/python -m pytest -q tests
  end

Supported verbs inside task
- describe <text>
- shell <command...>
- packages install <name...>
- packages remove <name...>
- service start|stop|enable|disable|restart <name>
- directory <path> [mode=0755]
- copy <local> <remote> [mode=0644] [user=...] [group=...]

Top‑level (outside task)
- include path.pf    # quoted or unquoted; resolved relative to Pfyfile.pf

Notes
- Package ops use apt under the hood (Ubuntu/Debian). Other distros fall back to shell detection.
- Services use systemctl via shell.
- Copy uses pyinfra files.put; directory uses files.directory for idempotence.
- Central venv enforced when launching pyinfra: /home/punk/.venv/bin/python -m pyinfra
"""
from __future__ import annotations

import os
import re
import shlex
import sys
import tempfile
import textwrap
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

# ---- User-configurable env aliases ----
ENV_MAP: Dict[str, List[str]] = {
    "local": ["@local"],
    # Add your own groups here; merged if env= is repeated
    # "prod": ["ubuntu@10.0.0.5:22", "punk@10.4.4.4:24"],
}

VENV_PY = "/home/punk/.venv/bin/python"
PYINFRA_MOD = "pyinfra"
PFYFILE_DEFAULT = "Pfyfile.pf"

# ---- DSL model ----
@dataclass
class Step:
    kind: str
    args: Dict[str, str] = field(default_factory=dict)
    argv: List[str] = field(default_factory=list)
    text: str = ""  # for 'describe' and raw lines

@dataclass
class Task:
    name: str
    describe: str = ""
    steps: List[Step] = field(default_factory=list)

@dataclass
class Program:
    tasks: Dict[str, Task] = field(default_factory=dict)

# ---- Parser ----
INCLUDE_RE = re.compile(r"^include\s+(?P<path>\S.*)$", re.I)
TASK_START_RE = re.compile(r"^task\s+(?P<name>[A-Za-z0-9_.:+\-]+)\s*$", re.I)
TASK_END_RE = re.compile(r"^end\s*$", re.I)


def _unquote_path(token: str) -> str:
    s = token.strip()
    if (s.startswith("\"") and s.endswith("\"")) or (s.startswith("\'") and s.endswith("\'")):
        return s[1:-1]
    return s


def parse_pfyfile(root_path: Path) -> Program:
    seen: Set[Path] = set()
    program = Program()

    def load_file(p: Path):
        p = p.resolve()
        if p in seen:
            return
        seen.add(p)
        if not p.exists():
            raise FileNotFoundError(f"pf: include not found: {p}")
        cur_task: Optional[Task] = None
        for raw in p.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # Task block handling
            if cur_task is None:
                m_inc = INCLUDE_RE.match(line)
                if m_inc:
                    inc_token = m_inc.group("path").strip()
                    inc_path = _unquote_path(inc_token)
                    inc_file = (p.parent / inc_path).resolve()
                    load_file(inc_file)
                    continue
                m_task = TASK_START_RE.match(line)
                if m_task:
                    tname = m_task.group("name").strip()
                    if tname in program.tasks:
                        # allow redefining to append? prefer last definition wins
                        pass
                    cur_task = Task(name=tname)
                    program.tasks[tname] = cur_task
                    continue
                # ignore stray lines at top-level
                continue
            else:
                # inside task
                if TASK_END_RE.match(line):
                    cur_task = None
                    continue
                # parse task content via shlex
                try:
                    parts = shlex.split(line)
                except Exception:
                    # treat unparsable as describe text
                    cur_task.steps.append(Step(kind="describe", text=line))
                    continue
                if not parts:
                    continue
                verb = parts[0].lower()
                if verb == "describe":
                    cur_task.describe = line[len("describe"):].strip()
                    cur_task.steps.append(Step(kind="describe", text=cur_task.describe))
                elif verb == "shell":
                    cmd = line[len("shell"):].strip()
                    cur_task.steps.append(Step(kind="shell", text=cmd))
                elif verb == "packages" and len(parts) >= 2:
                    action = parts[1].lower()
                    pkgs = parts[2:]
                    cur_task.steps.append(Step(kind=f"packages_{action}", argv=pkgs))
                elif verb == "service" and len(parts) >= 3:
                    action = parts[1].lower()
                    svc = parts[2]
                    cur_task.steps.append(Step(kind=f"service_{action}", argv=[svc]))
                elif verb == "directory" and len(parts) >= 2:
                    path = parts[1]
                    opts = _kv(parts[2:])
                    cur_task.steps.append(Step(kind="directory", args={"path": path, **opts}))
                elif verb == "copy" and len(parts) >= 3:
                    local, remote = parts[1], parts[2]
                    opts = _kv(parts[3:])
                    cur_task.steps.append(Step(kind="copy", args={"local": local, "remote": remote, **opts}))
                else:
                    # unknown: emit as raw shell to be safe
                    cur_task.steps.append(Step(kind="shell", text=line))

    load_file(root_path)
    return program


def _kv(tokens: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for t in tokens:
        if "=" in t:
            k, v = t.split("=", 1)
            out[k.strip()] = v.strip()
    return out

# ---- Deploy code generation ----

def render_deploy(task: Task, sudo: bool) -> str:
    """Return a Python deploy module string for pyinfra."""
    lines: List[str] = []
    lines.append("from pyinfra.operations import server, files")
    lines.append("")
    title = task.describe or f"Run task {task.name}"
    lines.append(f"# Task: {task.name}")
    lines.append(f"# {title}")

    sflag = "True" if sudo else "False"

    for i, st in enumerate(task.steps, 1):
        if st.kind == "describe":
            lines.append(f"# {st.text}")
            continue
        if st.kind == "shell":
            safe = _py_str(st.text)
            lines.append(
                f"server.shell({safe}, _sudo={sflag}, name={_py_str(f'shell[{i}] {st.text[:60]}')})"
            )
        elif st.kind == "directory":
            path = st.args.get("path", "")
            mode = st.args.get("mode") or "0755"
            lines.append(
                f"files.directory(path={_py_str(path)}, mode={_py_str(mode)}, _sudo={sflag}, name={_py_str(f'directory[{i}] {path} {mode}')})"
            )
        elif st.kind == "copy":
            local = st.args.get("local", "")
            remote = st.args.get("remote", "")
            mode = st.args.get("mode")
            user = st.args.get("user")
            group = st.args.get("group")
            opts = []
            if mode:
                opts.append(f"mode={_py_str(mode)}")
            if user:
                opts.append(f"user={_py_str(user)}")
            if group:
                opts.append(f"group={_py_str(group)}")
            opt_s = (
                ", " + ", ".join(opts)
            ) if opts else ""
            lines.append(
                f"files.put(src={_py_str(local)}, dest={_py_str(remote)}{opt_s}, _sudo={sflag}, name={_py_str(f'copy[{i}] {local} -> {remote}')})"
            )
        elif st.kind in ("packages_install", "packages_remove"):
            pkgs = st.argv
            present = st.kind.endswith("install")
            # Prefer apt if available; fallback to generic shell detection
            if pkgs:
                pkg_str = " ".join(shlex.quote(p) for p in pkgs)
                if present:
                    cmd = (
                        "(command -v apt-get >/dev/null && sudo apt-get update -y && sudo apt-get install -y "
                        + pkg_str
                        + ") || (command -v dnf >/dev/null && sudo dnf install -y "
                        + pkg_str
                        + ") || (command -v pacman >/dev/null && sudo pacman -S --noconfirm "
                        + pkg_str
                        + ")"
                    )
                else:
                    cmd = (
                        "(command -v apt-get >/dev/null && sudo apt-get remove -y "
                        + pkg_str
                        + ") || (command -v dnf >/dev/null && sudo dnf remove -y "
                        + pkg_str
                        + ") || (command -v pacman >/dev/null && sudo pacman -R --noconfirm "
                        + pkg_str
                        + ")"
                    )
                lines.append(
                    f"server.shell({_py_str(cmd)}, _sudo={sflag}, name={_py_str(f'packages[{i}] {"install" if present else "remove"} ' + ' '.join(pkgs))})"
                )
        elif st.kind.startswith("service_"):
            action = st.kind.split("_", 1)[1]
            name = st.argv[0] if st.argv else ""
            cmd = f"systemctl {action} {shlex.quote(name)}"
            lines.append(
                f"server.shell({_py_str(cmd)}, _sudo=True, name={_py_str(f'service[{i}] {action} {name}')})"
            )
        else:
            safe = _py_str(st.text or "")
            lines.append(f"server.shell({safe}, _sudo={sflag}, name={_py_str(f'raw[{i}]')})")

    return "\n".join(lines) + "\n"


def _py_str(s: str) -> str:
    return repr(s)

# ---- CLI & executor ----

def parse_cli(argv: List[str]) -> Tuple[Dict[str, str], List[str]]:
    opts: Dict[str, str] = {}
    tasks: List[str] = []
    for tok in argv:
        if "=" in tok:
            k, v = tok.split("=", 1)
            opts[k] = v
        else:
            tasks.append(tok)
    return opts, tasks


def resolve_hosts(opts: Dict[str, str]) -> List[str]:
    hosts: List[str] = []
    # env can be repeated; merge lists
    env_vals = [v for k, v in opts.items() if k == "env"]
    for ev in env_vals:
        for alias in ev.split(","):
            alias = alias.strip()
            if not alias:
                continue
            hosts.extend(ENV_MAP.get(alias, []))
    # hosts= comma list
    if "hosts" in opts:
        hosts.extend([h.strip() for h in opts["hosts"].split(",") if h.strip()])
    # repeatable host=
    for k, v in opts.items():
        if k == "host":
            hosts.append(v)
    if not hosts:
        hosts = ["@local"]
    # dedupe preserving order
    seen: Set[str] = set()
    out: List[str] = []
    for h in hosts:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def run_task(task: Task, hosts: List[str], sudo: bool) -> int:
    code = render_deploy(task, sudo)
    with tempfile.TemporaryDirectory(prefix="pfy_") as td:
        dfile = Path(td) / f"deploy_{task.name}.py"
        dfile.write_text(code)
        inv = ",".join(hosts)
        cmd = [VENV_PY, "-m", PYINFRA_MOD, inv, str(dfile)]
        print(f"[pf] hosts={inv} sudo={'true' if sudo else 'false'} task={task.name}")
        return subprocess.call(cmd)


def group_by_category(names: List[str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for n in sorted(names):
        cat = n.split("-", 1)[0] if "-" in n else "misc"
        groups.setdefault(cat, []).append(n)
    return groups


def main(argv: List[str]) -> int:
    if not Path(VENV_PY).exists():
        print(f"[pf] WARNING: central venv python not found at {VENV_PY}; pyinfra may not run", file=sys.stderr)
    opts, args = parse_cli(argv)
    sudo = opts.get("sudo", "false").lower() in {"1", "true", "yes"}

    pfyfile = Path(os.getenv("PFYFILE", PFYFILE_DEFAULT))
    if not pfyfile.exists():
        print(f"[pf] No {pfyfile} found. Create one with tasks (`task name ... end`) or set PFYFILE.", file=sys.stderr)
        return 2

    program = parse_pfyfile(pfyfile)

    if not args or args[0] in {"help", "--help", "-h"}:
        print(__doc__)
        print("\nTasks (pf list):\n  ./pf.py list")
        return 0

    if args[0] == "list":
        groups = group_by_category(list(program.tasks.keys()))
        print("Available tasks (grouped by category):")
        for cat in sorted(groups):
            print(f"\n[{cat}]")
            for name in groups[cat]:
                desc = program.tasks[name].describe or ""
                print(f"  {name:32} {desc}")
        return 0

    hosts = resolve_hosts(opts)

    # support multiple tasks in one invocation (sequential)
    rc_total = 0
    for tname in args:
        if tname not in program.tasks:
            print(f"[pf] task not found: {tname}", file=sys.stderr)
            return 2
        rc = run_task(program.tasks[tname], hosts, sudo)
        if rc != 0:
            rc_total = rc
            break
    return rc_total


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
