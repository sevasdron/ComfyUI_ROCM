"""Снимок схемы нод: /object_info запущенного ComfyUI -> нормализованный JSON.

    python tests/schema/dump.py http://127.0.0.1:8100 var/schema/v0.35.1.json

Для каждой ноды сохраняем то, что ломает сохранённые воркфлоу при изменении:
порядок и имена входов (ComfyUI сопоставляет значения виджетов по порядку),
их типы, выходы и их имена. Значения по умолчанию и подсказки не сравниваем.
"""
import json
import sys
import urllib.request


def normalize(info: dict) -> dict:
    out = {}
    for name, node in info.items():
        inputs = []
        for section in ("required", "optional"):
            for in_name, spec in (node.get("input") or {}).get(section, {}).items():
                typ = spec[0] if isinstance(spec, (list, tuple)) and spec else spec
                if isinstance(typ, list):  # список вариантов (combo) — только факт списка
                    typ = "COMBO"
                inputs.append([section, in_name, str(typ)])
        out[name] = {
            "inputs": inputs,
            "outputs": [str(t) if not isinstance(t, list) else "COMBO" for t in node.get("output", [])],
            "output_names": node.get("output_name", []),
            "category": node.get("category", ""),
        }
    return out


def main():
    base, dst = sys.argv[1].rstrip("/"), sys.argv[2]
    with urllib.request.urlopen(f"{base}/object_info", timeout=60) as r:
        info = json.load(r)
    schema = normalize(info)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"{len(schema)} nodes -> {dst}")


if __name__ == "__main__":
    main()
