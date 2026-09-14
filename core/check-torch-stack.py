#!/usr/bin/env python3
"""Проверка после `pip install`: пакеты torch/ROCm из /opt/constraints.txt
не подменились и не изменили версию при установке requirements.txt ядра.

Сравниваем по точному имени пакета (часть до "=="), а не по префиксу:
у ComfyUI в requirements.txt есть torchsde — имя начинается с "torch",
но это самостоятельный пакет, не часть закреплённого стека, и его не
должно быть в этом сравнении.
"""
import subprocess
import sys


def parse(lines):
    out = {}
    for line in lines:
        line = line.strip()
        if not line or "==" not in line:
            continue
        name, version = line.split("==", 1)
        out[name] = version
    return out


def main():
    want = parse(open("/opt/constraints.txt", encoding="utf-8"))
    freeze = subprocess.run(
        ["pip", "freeze"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    got = {n: v for n, v in parse(freeze).items() if n in want}

    if got == want:
        print("torch stack unchanged")
        return

    print("torch stack changed:", file=sys.stderr)
    for name in sorted(set(want) | set(got)):
        w, g = want.get(name), got.get(name)
        if w != g:
            print(f"  {name}: constraints={w!r} pip={g!r}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
