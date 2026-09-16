#!/usr/bin/env python3
"""tools/workflow-deps.py — какие ноды воркфлоу отсутствуют в модпаке и из каких пакетов они приходят.

  python3 tools/workflow-deps.py ФАЙЛ.json [...] [--schema var/schema/comfy-main_stable.json] [--modpack main]

Типы нод берутся из воркфлоу (формат UI: nodes + definitions.subgraphs; формат API: id → class_type),
сверяются со снимком /object_info (tools/comfy smoke). Для недостающих пакет определяется по
properties.cnr_id / aux_id, которые фронтенд пишет в каждую ноду; репозиторий — из docs/nodes-inventory.md.
Сверка виджетов (эвристика, по сырому /object_info рядом со снимком): число widgets_values каждой ноды
против числа виджетов в схеме. Ловит вставку/удаление входов в середине (сдвиг значений, как с LLMTextProcessor).
Шум: ноды ядра, сохранённые старой версией, фронтенд мигрирует сам — смотреть на [сохранена: пакет версия].
Ноды из modpacks/<модпак>/node-policy.yaml помечаются отдельно: что на gfx1151 не работает, чем заменить,
где нужна наша нода из пака ROCm Halo. Вызов через tools/comfy workflow deps ФАЙЛ...
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
# Виртуальные ноды фронтенда: их нет в /object_info, но и пакет им не нужен.
FRONTEND_ONLY = {"Note", "MarkdownNote", "Reroute", "PrimitiveNode", "SubgraphInput", "SubgraphOutput"}


def load_inventory():
    """docs/nodes-inventory.md → {ключ: (репозиторий, заметки)}; ключи — имя каталога и хвост URL, в нижнем регистре."""
    inv = {}
    p = ROOT / "docs" / "nodes-inventory.md"
    if not p.exists():
        return inv
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*`([^`]+)`\s*\|\s*(\S+)\s*\|\s*[^|]*\|\s*([^|]*)\|", line)
        if not m:
            continue
        name, url, note = m.group(1), m.group(2), m.group(3).strip()
        inv[name.lower()] = (url, note)
        inv[url.rstrip("/").rsplit("/", 1)[-1].lower()] = (url, note)
        inv[url.lower().removeprefix("https://github.com/")] = (url, note)
    return inv


def load_policy(modpack):
    """modpacks/<модпак>/node-policy.yaml → (правила по нодам, типы только-фронтендных нод)."""
    pf = ROOT / "modpacks" / modpack / "node-policy.yaml"
    if not pf.exists():
        return {}, set()
    doc = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
    return (doc.get("nodes") or {}), set(doc.get("frontend_only") or [])


def load_lock(modpack):
    lf = ROOT / "modpacks" / modpack / "nodes.lock"
    if not lf.exists():
        return {}
    nodes = (yaml.safe_load(lf.read_text(encoding="utf-8")) or {}).get("nodes") or []
    out = {}
    for n in nodes:
        out[n["name"].lower()] = n
        if n.get("repo") and n["repo"] != "local":
            out[str(n["repo"]).rstrip("/").removesuffix(".git").rsplit("/", 1)[-1].lower()] = n
    return out


def iter_nodes(wf):
    """(тип, properties) для всех нод, включая подграфы."""
    if isinstance(wf, dict) and "nodes" in wf:
        subgraph_ids = {sg.get("id") for sg in (wf.get("definitions") or {}).get("subgraphs") or []}
        for n in wf["nodes"]:
            yield n.get("type", ""), n.get("properties") or {}
        for sg in (wf.get("definitions") or {}).get("subgraphs") or []:
            for n in sg.get("nodes") or []:
                yield n.get("type", ""), n.get("properties") or {}
        return
    if isinstance(wf, dict):  # API-формат
        for n in wf.values():
            if isinstance(n, dict) and "class_type" in n:
                yield n["class_type"], {}


WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO",
                # виджеты фронтенда без сокета (V3-ноды ядра): цвет, окно 3D-просмотра
                "COLOR", "LOAD_3D", "LOAD_3D_ANIMATION"}


class Dynamic(Exception):
    """У ноды динамические входы (COMFY_DYNAMICCOMBO_V3 и т.п.) — число виджетов зависит от выбора."""


def schema_widgets(info):
    """Имена входов-виджетов ноды по /object_info в порядке объявления и признак control_after_generate."""
    out = []
    for section in ("required", "optional"):
        for name, spec in ((info.get("input") or {}).get(section) or {}).items():
            if not isinstance(spec, list) or not spec:
                continue
            t, opts = spec[0], (spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {})
            if isinstance(t, str) and t.startswith("COMFY_") and t.endswith("_V3"):
                raise Dynamic(t)
            if isinstance(t, list) or t in WIDGET_TYPES or opts.get("socketless"):
                if opts.get("forceInput"):
                    continue
                control = bool(opts.get("control_after_generate")) or (t == "INT" and name in ("seed", "noise_seed"))
                out.append((name, control))
                # кнопка загрузки файла — отдельный виджет фронтенда со своим значением
                if any(opts.get(k) for k in ("image_upload", "video_upload", "audio_upload", "animated_image_upload")):
                    out.append((name + ":upload", False))
    return out


def widget_mismatches(wf, schema_full):
    """Ноды, у которых число значений виджетов в воркфлоу не сходится со схемой (признак сдвига входов)."""
    res, dynamic = [], set()
    graphs = [wf] + list((wf.get("definitions") or {}).get("subgraphs") or [])
    for g in graphs:
        for n in g.get("nodes") or []:
            t = n.get("type")
            vals = n.get("widgets_values")
            if t not in schema_full or not isinstance(vals, list):
                continue
            try:
                w = schema_widgets(schema_full[t])
            except Dynamic:
                dynamic.add(t)
                continue
            if not w:
                continue
            # хвостовые None — кнопки из JS-расширений нод (например, у easy seed), значений не несут
            while vals and vals[-1] is None:
                vals = vals[:-1]
            lo = len(w)
            hi = len(w) + sum(1 for _, c in w if c)
            # входы-виджеты, превращённые в сокеты, в старых воркфлоу всё равно держат значение — поэтому только диапазон
            if not (lo <= len(vals) <= hi):
                pr = n.get("properties") or {}
                src = f"{pr.get('cnr_id') or pr.get('aux_id') or '?'} {str(pr.get('ver', ''))[:9]}".strip()
                res.append((t, n.get("id"), len(vals), lo, hi, src))
    return res, dynamic


MARK = {"replace": "заменить", "bypass": "обойти (Bypass)", "ours": "наша нода", "caution": "внимание", "ok": "проверено"}
# node-policy.yaml, поле verified: чем подтверждена запись
VERIFIED = {"run": "подтверждено прогоном", "bench": "только синтетика, прогоном не проверено",
            "docs": "только по документации", "no": "не проверено"}


def report_policy(used, missing_types, policy):
    """Пометки политики для нод, реально встречающихся в воркфлоу."""
    hits = [(t, policy[t]) for t in sorted(used | missing_types) if t in policy and policy[t].get("status") != "ok"]
    if not hits:
        return
    print("   железо и замены (node-policy.yaml):")
    for t, rule in hits:
        st = str(rule.get("status", "?"))
        head = f"      {MARK.get(st, st)}: {t}"
        if rule.get("with"):
            head += f" → {rule['with']}"
        head += f"   [{VERIFIED.get(str(rule.get('verified', 'no')), 'не проверено')}]"
        if t in missing_types and st in ("replace", "bypass"):
            head += "   [ноды нет в модпаке — пакет можно не ставить]"
        print(head)
        why = " ".join(str(rule.get("why", "")).split())
        if why:
            print(f"         {why}")


def analyze(path, schema, inventory, lock, schema_full=None, policy=None, frontend_only=frozenset()):
    wf = json.loads(Path(path).read_text(encoding="utf-8"))
    subgraph_ids = {sg.get("id") for sg in (wf.get("definitions") or {}).get("subgraphs") or []} if isinstance(wf, dict) else set()
    total = 0
    present = set()
    missing = defaultdict(lambda: defaultdict(set))   # пакет → тип → версии
    pkg_ver = {}
    for t, props in iter_nodes(wf):
        if not t or t in subgraph_ids or t in FRONTEND_ONLY or t in frontend_only:
            continue
        total += 1
        if t in schema:
            present.add(t)
            continue
        pkg = props.get("cnr_id") or props.get("aux_id") or "?"
        missing[pkg][t].add(str(props.get("ver", ""))[:7])
        if props.get("ver"):
            pkg_ver[pkg] = str(props["ver"])[:7]

    used = set(present)
    missing_types = {t for pkg in missing for t in missing[pkg]}
    print(f"\n{path}")
    print(f"   нод: {total}, типов есть в схеме: {len(present)}, не хватает типов: {sum(len(v) for v in missing.values())} из {len(missing)} пакетов")
    for pkg in sorted(missing, key=lambda p: (p == "?", p.lower())):
        key = pkg.lower()
        tail = key.rsplit("/", 1)[-1]
        lk = lock.get(key) or lock.get(tail)
        inv = inventory.get(key) or inventory.get(tail)
        status = "в nodes.lock (пересобрать/перезапустить?)" if lk else ("→ " + inv[0] if inv else "репозиторий неизвестен (cnr: https://registry.comfy.org/nodes/" + pkg + ")")
        ver = f" (в воркфлоу ver {pkg_ver[pkg]})" if pkg in pkg_ver else ""
        print(f"   [{pkg}]{ver} {status}")
        if inv and inv[1]:
            print(f"      ! {inv[1]}")
        for t in sorted(missing[pkg]):
            print(f"      - {t}")
    if policy:
        report_policy(used, missing_types, policy)
    if schema_full is not None and isinstance(wf, dict) and "nodes" in wf:
        mm, dynamic = widget_mismatches(wf, schema_full)
        if dynamic:
            print(f"   виджеты не сверялись (динамические входы V3): {', '.join(sorted(dynamic))}")
        if mm:
            print(f"   ! виджеты не сходятся со схемой ({len(mm)}) — возможен сдвиг значений, проверить ноду в UI:")
            for t, nid, got, lo, hi, src in sorted(mm, key=lambda x: (x[5], x[0], str(x[1]))):
                exp = str(lo) if lo == hi else f"{lo}–{hi}"
                print(f"      #{nid} {t} [сохранена: {src}]: в воркфлоу {got}, в схеме {exp}")
        else:
            print("   виджеты: число значений у всех найденных нод сходится со схемой")
    return missing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--schema", default=str(ROOT / "var" / "schema" / "comfy-main_stable.json"))
    ap.add_argument("--modpack", default="main")
    a = ap.parse_args()
    sp = Path(a.schema)
    sp.exists() or sys.exit(f"нет снимка схемы {sp} — сними: bash tools/comfy smoke {a.modpack}")
    schema = set(json.loads(sp.read_text(encoding="utf-8")).keys())
    raw = sp.with_name(sp.name[:-5] + ".object_info.json")
    schema_full = json.loads(raw.read_text(encoding="utf-8")) if raw.exists() else None
    if schema_full is None:
        print(f"(нет {raw.name} — сверка виджетов пропущена; сними заново: bash tools/comfy smoke {a.modpack})")
    inventory, lock = load_inventory(), load_lock(a.modpack)
    policy, frontend_only = load_policy(a.modpack)
    print(f"схема: {sp.name} ({len(schema)} типов), справочник: {len(inventory)//3} пакетов, nodes.lock {a.modpack}: {len(set(id(v) for v in lock.values()))}, политика: {len(policy)} нод")
    all_pkgs = set()
    for f in a.files:
        all_pkgs |= set(analyze(f, schema, inventory, lock, schema_full, policy, frontend_only))
    if len(a.files) > 1:
        print(f"\nвсего пакетов на все файлы: {len(all_pkgs)}: {', '.join(sorted(all_pkgs, key=str.lower))}")


if __name__ == "__main__":
    main()
