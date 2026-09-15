# План работ

Текущий контейнер `strix-halo-comfyui` не трогаем, пока модпак `main` не пройдёт проверки.

## Этап 0 — документация ✅ (14.09.2026)

Эта папка: железо, текущее состояние, архитектура, стратегия обновлений, реестр правок.

## Этап 1 — runtime ✅ (14.09.2026)

- `runtime/Containerfile` + `runtime/versions.env`: Fedora 44, Python 3.13, torch `2.14.0a0+rocm7.15.0a20260721`
  ([ADR-0004](decisions/0004-runtime-fedora-stable-wheelhouse.md)).
- `tools/wheelhouse-sync` → `var/wheelhouse` (26 колёс, 1.6 ГБ); `tools/runtime-build` ставит только из него
  (`--no-index`) и пишет `runtime/constraints.txt`; в образе — `PIP_CONSTRAINT`/`UV_CONSTRAINT`.
- Образ `localhost/strix-runtime:rocm7.15.0a20260721-torch2.14` — **7.29 ГБ** (kyuz0: 16.2 ГБ).
- `tools/runtime-test` (`tests/smoke/gpu_check.py`) на нашем образе и kyuz0: gfx1151 виден, matmul bf16
  36.9 vs 37.2 TFLOPS, SDPA 0.73 vs 0.73 мс, flash/efficient доступны, точность одинаковая.
  Без `privileged`: только `/dev/kfd`, `/dev/dri`, `--group-add keep-groups`.
- Сравнение скорости на эталонном воркфлоу перенесено на этап 2 (нужен ComfyUI).

## Этап 2 — ядро ✅ (14.09.2026)

- `core/Containerfile` (`ARG COMFYUI_REF`: тег/ветка/SHA, shallow-clone с `.git`), `core/versions.env`,
  патчи через `core/apply-patches.sh` (applied / in upstream / conflict), `core/patches/0001-growmask-cpu.patch` (P9).
  Проверки при сборке: стек torch не сдвинулся (`check-torch-stack.py`), ядро импортируется (`check-core-import.py`).
- Образ `localhost/comfy-core:v0.35.1` — 8.9 ГБ (runtime 7.29 + 1.6 ГБ зависимостей ядра); сборка ~5 мин.
- `tools/comfy build core | run | stop | log | status | smoke | schema diff`; запуск по ADR-0003
  (`/data`, `/models` RO, `/cache/hf`, без privileged, `--userns=keep-id`), ключи запуска прежние.
- Smoke на чистом 0.35.1 с Manager, порт 8100: GPU `AMD Radeon 8060S`, `/` 200, 927 нод, без трейсбеков.
- `tests/schema`: первый боевой diff 0.31.0 → 0.35.1: 9 нод удалено (облачные API), 103 добавлено,
  9 ломающих изменений (типы/порядок входов у `CreateVideo`, `SaveVideo`, `MiniMaxH3ReferenceToVideo`, Meshy/Tripo).
- Найдено по дороге: под `--userns=keep-id` нужны `git config --system safe.directory` (иначе Manager не видит
  ревизию) и `HOME=/data` (иначе `uv` у Manager падает на втором старте).
- Перенесено в этап 3: `update / promote / rollback` — они работают с тегами модпака и бэкапом `user/`,
  без модпака `main` их не на чем проверить.

## Этап 3 — модпак `main`

- **Начат 14.09**: собственный пак `comfyui-rocm-halo` («ROCm Halo», Node API V3, без JS), первая нода
  `RH Cast to float32` вместо патчей ядра P12/P13. Пока локальный git в `~/ComfyUI/core/custom_nodes/`, хостинг — позже.
- 15.09: в паке 4 ноды — `RH Cast to float32`, `RH VAE Precision`, `RH Mesh Info`, `RH Trellis2 Upsample Stage` (P14:
  structure resolution=64 в upstream не работает). Воркфлоу TRELLIS.2/pixal3d проходит на res 32 и 64.
  Уроки V3: `lock_class` пересобирает класс ноды — никаких `super()` и атрибутов класса в `execute`; хук подсказки
  оборачивает `execution.get_output_data`.
- 15.09 ✅ **модпак как код**: `modpacks/main/{modpack.yaml,nodes.lock}`, общий `modpacks/Containerfile`,
  `tools/modpack.py`; `tools/comfy build main | run main [--channel candidate] | sync | node add|bump | update | promote | rollback`.
  Образ `comfy-main:v0.35.1-<lock7>` (8.89 ГБ — у пака ROCm Halo нет зависимостей), теги каналов `stable / candidate / prev`.
  Smoke stable: 931 нода (927 ядра + 4 RH), без ошибок импорта. [ADR-0006](decisions/0006-modpack-main-starts-empty.md):
  `main` стартует пустым (вариант B), старые 42 каталога — справочник [nodes-inventory.md](nodes-inventory.md).
  Остановка контейнера — `--stop-signal SIGINT` (на SIGTERM ComfyUI не реагирует, podman ждал 15 с и слал SIGKILL).
- 15.09 ✅ переезд данных `~/ComfyUI/core` → `~/ComfyUI/main`; `main` — рабочий (ярлыки). Первый воркфлоу ND Krea2 v1.4:
  10 пакетов нод через `node add`, P3 через `node patch`, `workflow deps` (типы нод + сверка виджетов). См. [workflows/main.md](workflows/main.md).
- ~~Переезд данных: `~/ComfyUI/core` → `~/ComfyUI/main` (`mv`, ярлыки и `comfyctl` уже смотрят на `main`) — после остановки
  текущего прогона. Старые `~/comfy/user` (116 воркфлоу) и `~/comfy/input` — копировать по запросу: воркфлоу с чужими
  нодами откроются с «missing nodes», пока ноды не добавлены.~~
- 15.09 ✅ живой `update main --to v0.35.2` (на временной папке данных): ядро 0.35.2 собрано (патч GrowMask лёг),
  `comfy-main:v0.35.2-170bea7` → `candidate`, smoke на 8101 чистый, схема 931 → 942 (+11: Bria*, FluxVideoEditNode,
  GeminiNodeV3; ломающих 0). `promote` (бэкап user/, теги, `core:` в modpack.yaml) и `rollback --user latest` проверены;
  stable оставлен на v0.35.1 — promote в работу после переезда данных и ручной проверки кандидата.
- Ноды по потребности через `node add`; форки P3/P4/P5 — когда соответствующая нода понадобится в `main`.
- Эталонные воркфлоу `modpacks/main/workflows/`, `tests/workflows` — после первых нод.
- Переход на `main` как основной, `strix-halo-comfyui` остаётся резервом.

## Этап 4 — модпак `trellis2` (пилот нативных сборок)

- `strix-runtime-devel`, сборка колёс o-voxel → FlexGEMM → CuMesh → nvdiffrast под gfx1151.
- Нода visualbruno/ComfyUI-Trellis2, `ATTN_BACKEND=sdpa`, `SPARSE_CONV_BACKEND=flex_gemm`.
- Точка решения — nvdiffrast: без него только геометрия без текстур.

## Место на диске (оценка, 14.09.2026)

Хранилище образов — на btrfs `/` (свободно ~79 ГБ).

| Что | Объём |
|---|---|
| runtime (без дубликата `chmod -R /opt`, который есть у kyuz0: 7.3 ГБ из 16.2) | 7.3 ГБ (факт) |
| ядро ComfyUI × 2–3 версии | 3–4 ГБ |
| модпак `main` × 3 (stable / candidate / prev) | 6–12 ГБ |
| кэш колёс torch/ROCm (`var/wheelhouse`, на NTFS) | 1.6 ГБ на версию (факт) |
| **рабочий режим** | **~25–35 ГБ** |
| пик: сборки + devel для TRELLIS.2 | ~45 ГБ |
| пик на время переезда (старый toolbox как резерв, +21 ГБ) | 55–65 ГБ |

Данные модпака (`~/ComfyUI/main`) — ещё ~6.5 ГБ, из них 3.9 ГБ кэш Civitai у lora-manager.

## Открытые вопросы

| Вопрос | Когда решать |
|---|---|
| ~~ОС runtime: Fedora 45 prerelease как у kyuz0 или стабильная версия с Python 3.13~~ — Fedora 44 stable, [ADR-0004](decisions/0004-runtime-fedora-stable-wheelhouse.md) | решено 14.09 |
| Хранить форки нод на GitHub (какой аккаунт) или в локальных bare-репозиториях | этап 3 |
| ~~Remote для репозитория~~ — public github.com/sevasdron/ComfyUI_ROCM | решено 14.09 |
| Эталонные воркфлоу: какие именно и какой бюджет времени на прогон | этап 2–3 |
| VRAM в BIOS 32 ГБ или минимум + большой GTT — замер 14.09: carve-out не используется (1.4 ГБ), всё в GTT, см. [hardware.md](hardware.md) | проверить минимум в BIOS на том же прогоне |
| ~~Nodes 2.0 (Vue-рендер) и Node API V3: что делать с нодами~~ — [ADR-0005](decisions/0005-frontend-nodes2-and-node-api-v3.md): в stable выключен, свои ноды на V3 | решено 14.09 |
| Отказ от `privileged` и монтирования всего `/home` — не сломает ли ноды, пишущие вне своих папок | по мере добавления нод в `main` |
| Manager в `main`: включён на время набора нод (ADR-0006); выключить, когда состав устоится | этап 3 |
| Кэш HuggingFace: какой путь сейчас реально используется (`/mnt/data/huggingface` или `~/.cache`) и работают ли его симлинки на NTFS. `tools/comfy` пока монтирует `/mnt/data/huggingface` (переопределяется `HF_CACHE`) | этап 3, при первом воркфлоу с HF-моделью |
