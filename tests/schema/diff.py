"""Сравнение двух снимков схемы нод (tests/schema/dump.py).

    python tests/schema/diff.py var/schema/old.json var/schema/new.json [--fail-on-breaking]

Ломающие изменения (сдвигают значения виджетов или рвут связи в сохранённых воркфлоу):
нода исчезла, вход удалён/переименован/переставлен/сменил тип, выход удалён/переставлен.
Новые ноды и входы, добавленные в конец, — не ломающие, но показываются.
"""
import json
import sys


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fail_on_breaking = "--fail-on-breaking" in sys.argv
    old, new = load(args[0]), load(args[1])

    removed = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    breaking, benign = [], []

    for name in sorted(set(old) & set(new)):
        o, n = old[name], new[name]
        oi, ni = o["inputs"], n["inputs"]
        if oi != ni:
            o_names = [i[1] for i in oi]
            n_names = [i[1] for i in ni]
            common = [x for x in o_names if x in n_names]
            if any(x not in n_names for x in o_names):
                breaking.append((name, "input removed: " + ", ".join(x for x in o_names if x not in n_names)))
            elif [x for x in n_names if x in common] != common:
                breaking.append((name, "input order changed"))
            elif n_names[: len(o_names)] != o_names:
                breaking.append((name, "input inserted in the middle: " + ", ".join(x for x in n_names if x not in o_names)))
            else:
                types_changed = [
                    (a[1], a[2], b[2]) for a, b in zip(oi, ni) if a[1] == b[1] and a[2] != b[2]
                ]
                if types_changed:
                    breaking.append((name, "input type changed: " + "; ".join(f"{i} {a}->{b}" for i, a, b in types_changed)))
                else:
                    benign.append((name, "inputs appended: " + ", ".join(n_names[len(o_names):])))
        if o["outputs"] != n["outputs"] or o["output_names"] != n["output_names"]:
            if len(n["outputs"]) >= len(o["outputs"]) and n["outputs"][: len(o["outputs"])] == o["outputs"]:
                benign.append((name, "outputs appended"))
            else:
                breaking.append((name, f"outputs changed: {o['outputs']} -> {n['outputs']}"))

    print(f"nodes: {len(old)} -> {len(new)}; removed {len(removed)}, added {len(added)}, "
          f"breaking changes {len(breaking)}, benign changes {len(benign)}")
    for title, items in (("REMOVED NODES", removed), ("ADDED NODES", added)):
        if items:
            print(f"\n{title} ({len(items)}):")
            for x in items:
                print("  ", x)
    for title, items in (("BREAKING", breaking), ("BENIGN", benign)):
        if items:
            print(f"\n{title} ({len(items)}):")
            for name, what in items:
                print(f"   {name}: {what}")

    if fail_on_breaking and (removed or breaking):
        sys.exit(1)


if __name__ == "__main__":
    main()
