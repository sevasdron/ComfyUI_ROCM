#!/usr/bin/env bash
# Накладывает /opt/patches/*.patch на /opt/ComfyUI в порядке имён (0001-…, 0002-…).
# Исходы для каждого патча:
#   applied    — штатно;
#   IN UPSTREAM — обратный патч применяется, значит правка уже в ядре: файл патча удалить,
#                 строку в docs/patches-registry.md пометить «принято в vX.Y.Z»;
#   CONFLICT   — сборка останавливается, патч надо адаптировать под новую версию.
set -euo pipefail
cd /opt/ComfyUI
shopt -s nullglob

fail=0
for p in /opt/patches/*.patch; do
    name=$(basename "$p")
    if git apply --check "$p" 2>/dev/null; then
        git apply "$p"
        echo "patch ${name}: applied"
    elif git apply --reverse --check "$p" 2>/dev/null; then
        echo "patch ${name}: IN UPSTREAM (already present) — remove the file, update patches-registry.md"
    else
        echo "patch ${name}: CONFLICT"
        git apply --check "$p" 2>&1 | sed 's/^/    /' || true
        fail=1
    fi
done

if [ "$fail" -ne 0 ]; then
    echo "core patches failed for $(git describe --tags --always)" >&2
    exit 1
fi
git --no-pager diff --stat
