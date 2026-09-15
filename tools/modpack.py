#!/usr/bin/env python3
"""tools/modpack.py — modpacks/<имя>/{modpack.yaml, nodes.lock}: чтение, контекст сборки, сверка нод.

Вызывается из tools/comfy, но работает и сам:
  python3 tools/modpack.py env NAME                         переменные модпака для shell (eval)
  python3 tools/modpack.py context NAME OUT NODES_DIR [--core REF]
                                                            контекст сборки образа в OUT
  python3 tools/modpack.py sync NAME NODES_DIR [--apply]    сверить custom_nodes с nodes.lock
  python3 tools/modpack.py add NAME NODES_DIR URL|--local DIR [--name N] [--ref REF]
                                                            добавить ноду в папку и в nodes.lock
  python3 tools/modpack.py bump NAME NODES_DIR NODE [REF]   перевести ноду на REF (по умолчанию origin/HEAD)
  python3 tools/modpack.py latest-tag REPO_URL              последний релизный тег ComfyUI (vX.Y.Z)

nodes.lock правится текстом (append / замена строки ref), а не yaml.dump: сохраняем комментарии и порядок.
"""
import argparse
import hashlib
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODPACKS = ROOT / "modpacks"
IGNORED_DIRS = {"__pycache__", ".git"}


def die(msg, code=1):
    print(f"modpack: {msg}", file=sys.stderr)
    sys.exit(code)


def git(*args, cwd=None, check=True, capture=True):
    r = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=capture)
    if check and r.returncode:
        die(f"git {' '.join(args)} в {cwd or '.'}: {(r.stderr or r.stdout).strip()}")
    return (r.stdout or "").strip()


def pack_dir(name):
    d = MODPACKS / name
    if not (d / "modpack.yaml").is_file():
        die(f"нет модпака {name}: {d / 'modpack.yaml'}")
    return d


def load_pack(name):
    d = pack_dir(name)
    cfg = yaml.safe_load((d / "modpack.yaml").read_text(encoding="utf-8")) or {}
    lock_file = d / "nodes.lock"
    lock = (yaml.safe_load(lock_file.read_text(encoding="utf-8")) or {}) if lock_file.exists() else {}
    nodes = lock.get("nodes") or []
    names = [n["name"] for n in nodes]
    if len(names) != len(set(names)):
        die("nodes.lock: повторяющиеся name")
    return d, cfg, nodes


# ---------- env ----------

def cmd_env(a):
    _, cfg, nodes = load_pack(a.name)
    args = cfg.get("args") or []
    print(f"MP_NAME={shlex.quote(cfg.get('name', a.name))}")
    print(f"MP_CORE={shlex.quote(str(cfg.get('core', '')))}")
    print(f"MP_PORT={int(cfg.get('port', 8100))}")
    print(f"MP_MANAGER={1 if cfg.get('manager') else 0}")
    print(f"MP_ARGS={shlex.quote(' '.join(str(x) for x in args))}")
    print(f"MP_NODES={len(nodes)}")


# ---------- context ----------

REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def req_lines(path, excludes):
    """Строки requirements.txt ноды; исключённые пакеты остаются комментарием (видно в контексте)."""
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = REQ_NAME.match(s)
        pkg = m.group(1).lower().replace("_", "-") if m else ""
        if pkg in excludes:
            out.append(f"# исключено modpack.yaml pip.exclude: {s}")
        else:
            out.append(s)
    return out


def cmd_context(a):
    d, cfg, nodes = load_pack(a.name)
    out = Path(a.out)
    nodes_dir = Path(a.nodes_dir)
    if out.exists():
        shutil.rmtree(out)
    (out / "wheels").mkdir(parents=True)
    (out / "wheels" / ".keep").write_text("")

    pip_cfg = cfg.get("pip") or {}
    excludes = {str(x).lower().replace("_", "-") for x in (pip_cfg.get("exclude") or [])}
    req = ["# Сгенерировано tools/modpack.py context — не править руками.", ""]
    missing = []
    for n in nodes:
        ndir = nodes_dir / n["name"]
        if not ndir.is_dir():
            missing.append(n["name"])
            continue
        if n.get("pip") is False:
            req.append(f"# {n['name']}: pip: false")
            continue
        rf = ndir / "requirements.txt"
        if rf.is_file():
            req.append(f"# --- {n['name']} ({rf.name})")
            req += req_lines(rf, excludes)
        else:
            req.append(f"# --- {n['name']}: requirements.txt нет")
    if missing:
        die(f"нет каталогов нод: {', '.join(missing)} — сначала: tools/comfy sync {a.name} --apply")
    extra = [str(x) for x in (pip_cfg.get("extra") or [])]
    if extra:
        req.append("# --- modpack.yaml pip.extra")
        req += extra
    (out / "requirements.txt").write_text("\n".join(req) + "\n", encoding="utf-8")
    (out / "dnf.txt").write_text("\n".join(str(x) for x in (cfg.get("dnf") or [])) + "\n", encoding="utf-8")

    wheels_src = ROOT / "var" / "wheels" / a.name
    nwheels = 0
    if wheels_src.is_dir():
        for w in wheels_src.glob("*.whl"):
            shutil.copy2(w, out / "wheels" / w.name)
            nwheels += 1

    lock_sha = hashlib.sha256((d / "nodes.lock").read_bytes()).hexdigest() if (d / "nodes.lock").exists() else "0" * 64
    core = a.core or str(cfg.get("core", ""))
    (out / "modpack.env").write_text(
        f"MODPACK={a.name}\nCORE_REF={core}\nLOCK_SHA={lock_sha}\nLOCK7={lock_sha[:7]}\n", encoding="utf-8")
    npkg = sum(1 for l in req if l and not l.startswith("#"))
    print(f"контекст {out}: нод {len(nodes)}, pip-строк {npkg}, dnf {len(cfg.get('dnf') or [])}, колёс {nwheels}, lock {lock_sha[:7]}")


# ---------- sync ----------

def node_state(n, ndir):
    """(состояние, подробности). Состояния: missing / notgit / ok / ref / dirty / remote."""
    if not ndir.is_dir():
        return "missing", ""
    if not (ndir / ".git").exists():
        return "notgit", "каталог без git"
    head = git("rev-parse", "HEAD", cwd=ndir)
    dirty = git("status", "--porcelain", cwd=ndir)
    problems = []
    if n.get("repo") != "local":
        origin = git("remote", "get-url", "origin", cwd=ndir, check=False)
        if origin.rstrip("/").removesuffix(".git") != str(n["repo"]).rstrip("/").removesuffix(".git"):
            problems.append(f"origin {origin or '—'} ≠ {n['repo']}")
    if head != n["ref"]:
        problems.append(f"HEAD {head[:7]} ≠ lock {str(n['ref'])[:7]}")
    if dirty:
        problems.append(f"локальные правки: {len(dirty.splitlines())} файл(ов)")
    if not problems:
        return "ok", head[:7]
    state = "remote" if any(p.startswith("origin") for p in problems) else ("dirty" if dirty else "ref")
    return state, "; ".join(problems)


def apply_patches(pack, n, ndir):
    for p in n.get("patches") or []:
        pf = pack / "patches" / p
        if not pf.is_file():
            die(f"{n['name']}: нет патча {pf}")
        r = subprocess.run(["git", "apply", "--check", str(pf)], cwd=ndir, capture_output=True, text=True)
        if r.returncode:
            die(f"{n['name']}: патч {p} не ложится: {r.stderr.strip()}")
        git("apply", str(pf), cwd=ndir)
        print(f"   {n['name']}: патч {p} наложен")


def cmd_sync(a):
    pack, cfg, nodes = load_pack(a.name)
    nodes_dir = Path(a.nodes_dir)
    nodes_dir.mkdir(parents=True, exist_ok=True)
    bad = 0
    for n in nodes:
        ndir = nodes_dir / n["name"]
        state, info = node_state(n, ndir)
        if state == "ok":
            print(f"ok       {n['name']} @ {info}")
            continue
        if not a.apply:
            print(f"{state:8} {n['name']}: {info or 'нет каталога'}")
            bad += 1
            continue
        if state == "missing":
            if n.get("repo") == "local":
                print(f"missing  {n['name']}: локальный пак без remote — восстановить нечем")
                bad += 1
                continue
            print(f"clone    {n['name']} ← {n['repo']}")
            git("clone", "-q", str(n["repo"]), str(ndir), capture=False)
            git("checkout", "-q", "--detach", str(n["ref"]), cwd=ndir)
            apply_patches(pack, n, ndir)
        elif state == "ref":
            if n.get("repo") != "local":
                git("fetch", "-q", "origin", cwd=ndir)
            print(f"checkout {n['name']} → {str(n['ref'])[:7]}")
            git("checkout", "-q", "--detach", str(n["ref"]), cwd=ndir)
            apply_patches(pack, n, ndir)
        else:
            print(f"{state:8} {n['name']}: {info} — руками (sync не трогает правки и чужой origin)")
            bad += 1
    locked = {n["name"] for n in nodes}
    for p in sorted(nodes_dir.iterdir()):
        if p.name in IGNORED_DIRS or p.name.startswith(".") or not p.is_dir():
            continue
        if p.name not in locked:
            hint = ""
            if (p / ".git").exists():
                url = git("remote", "get-url", "origin", cwd=p, check=False)
                hint = f" (git: {url or 'без remote'})"
            print(f"extra    {p.name}: нет в nodes.lock{hint} — node add или убрать")
            bad += 1
    if bad:
        print(f"расхождений: {bad}")
    else:
        print("custom_nodes совпадает с nodes.lock")
    sys.exit(1 if bad else 0)


# ---------- add / bump ----------

def lock_append(pack, name, repo, ref):
    lf = pack / "nodes.lock"
    text = lf.read_text(encoding="utf-8") if lf.exists() else "nodes:\n"
    if re.search(rf"^\s*-\s*name:\s*{re.escape(name)}\s*$", text, re.M):
        die(f"{name} уже есть в nodes.lock")
    text = re.sub(r"^nodes:\s*\[\]\s*$", "nodes:", text, flags=re.M)   # пустой список → открытый ключ
    if not re.search(r"^nodes:\s*$", text, re.M):
        text = text.rstrip("\n") + "\nnodes:\n"
    block = f"  - name: {name}\n    repo: {repo}\n    ref: {ref}\n    patches: []\n"
    lf.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")


def lock_set_ref(pack, name, ref):
    lf = pack / "nodes.lock"
    lines = lf.read_text(encoding="utf-8").splitlines(keepends=True)
    i = next((k for k, l in enumerate(lines) if re.match(rf"^\s*-\s*name:\s*{re.escape(name)}\s*$", l)), None)
    if i is None:
        die(f"{name} нет в nodes.lock")
    for k in range(i + 1, len(lines)):
        if re.match(r"^\s*-\s*name:", lines[k]):
            break
        m = re.match(r"^(\s*ref:\s*)(\S+)(.*)$", lines[k])
        if m:
            old = m.group(2)
            lines[k] = f"{m.group(1)}{ref}{m.group(3).rstrip()}\n"
            lf.write_text("".join(lines), encoding="utf-8")
            return old
    die(f"{name}: в nodes.lock нет строки ref")


def cmd_add(a):
    pack, cfg, nodes = load_pack(a.name)
    nodes_dir = Path(a.nodes_dir)
    nodes_dir.mkdir(parents=True, exist_ok=True)
    if a.local:
        ndir = Path(a.local)
        if not ndir.is_absolute():
            ndir = nodes_dir / a.local
        name = a.node_name or ndir.name
        if not (ndir / ".git").exists():
            die(f"{ndir}: локальный пак должен быть git-репозиторием (git init + commit)")
        if ndir.resolve().parent != nodes_dir.resolve():
            die(f"{ndir} лежит не в {nodes_dir}")
        ref = git("rev-parse", "HEAD", cwd=ndir)
        lock_append(pack, name, "local", ref)
        print(f"добавлено: {name} (local @ {ref[:7]})")
        return
    url = a.url
    name = a.node_name or url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]
    if not name:
        die("не могу вывести имя из URL, укажи --name")
    ndir = nodes_dir / name
    if ndir.exists():
        if not (ndir / ".git").exists():
            die(f"{ndir} уже есть и это не git — убери или переименуй")
        origin = git("remote", "get-url", "origin", cwd=ndir, check=False)
        if origin.rstrip("/").removesuffix(".git") != url.rstrip("/").removesuffix(".git"):
            die(f"{ndir}: origin {origin} ≠ {url}")
        print(f"каталог {name} уже есть, беру его")
    else:
        print(f"clone {url} → {ndir}")
        git("clone", "-q", url, str(ndir), capture=False)
    if a.ref:
        git("fetch", "-q", "origin", cwd=ndir, check=False)
        git("checkout", "-q", "--detach", a.ref, cwd=ndir)
    ref = git("rev-parse", "HEAD", cwd=ndir)
    lock_append(pack, name, url, ref)
    rf = ndir / "requirements.txt"
    print(f"добавлено: {name} @ {ref[:7]}" + ("" if rf.is_file() else " (requirements.txt нет)"))
    if rf.is_file():
        print("   зависимости → образ: bash tools/comfy build " + a.name)


def cmd_bump(a):
    pack, cfg, nodes = load_pack(a.name)
    n = next((x for x in nodes if x["name"] == a.node), None) or die(f"{a.node} нет в nodes.lock")
    ndir = Path(a.nodes_dir) / a.node
    ndir.is_dir() or die(f"нет каталога {ndir}")
    if n.get("repo") == "local":
        ref = git("rev-parse", "HEAD", cwd=ndir)
    else:
        if git("status", "--porcelain", cwd=ndir):
            die(f"{a.node}: есть локальные правки — закоммить или убери, потом bump")
        git("fetch", "-q", "origin", cwd=ndir)
        target = a.ref or git("rev-parse", "--abbrev-ref", "origin/HEAD", cwd=ndir, check=False) or "origin/HEAD"
        git("checkout", "-q", "--detach", target, cwd=ndir)
        ref = git("rev-parse", "HEAD", cwd=ndir)
        apply_patches(pack, n, ndir)
    old = lock_set_ref(pack, a.node, ref)
    print(f"{a.node}: {old[:7]} → {ref[:7]}" + ("" if old != ref else " (без изменений)"))


# ---------- latest-tag ----------

def cmd_latest_tag(a):
    out = git("ls-remote", "--tags", "--refs", a.repo, "refs/tags/v*")
    tags = []
    for line in out.splitlines():
        t = line.split("refs/tags/", 1)[-1]
        m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", t)
        if m:
            tags.append((tuple(int(x) for x in m.groups()), t))
    tags or die("релизных тегов vX.Y.Z не найдено")
    print(max(tags)[1])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("env"); s.add_argument("name"); s.set_defaults(f=cmd_env)
    s = sp.add_parser("context"); s.add_argument("name"); s.add_argument("out"); s.add_argument("nodes_dir")
    s.add_argument("--core"); s.set_defaults(f=cmd_context)
    s = sp.add_parser("sync"); s.add_argument("name"); s.add_argument("nodes_dir")
    s.add_argument("--apply", action="store_true"); s.set_defaults(f=cmd_sync)
    s = sp.add_parser("add"); s.add_argument("name"); s.add_argument("nodes_dir"); s.add_argument("url", nargs="?")
    s.add_argument("--local", help="локальный git-каталог в custom_nodes (repo: local)")
    s.add_argument("--name", dest="node_name"); s.add_argument("--ref"); s.set_defaults(f=cmd_add)
    s = sp.add_parser("bump"); s.add_argument("name"); s.add_argument("nodes_dir"); s.add_argument("node")
    s.add_argument("ref", nargs="?"); s.set_defaults(f=cmd_bump)
    s = sp.add_parser("latest-tag"); s.add_argument("repo"); s.set_defaults(f=cmd_latest_tag)
    a = p.parse_args()
    if a.cmd == "add" and not a.url and not a.local:
        die("add: нужен URL или --local DIR")
    a.f(a)


if __name__ == "__main__":
    main()
