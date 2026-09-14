# Целевая архитектура

Статус: **черновик**, решения фиксируются в [decisions/](decisions/).

## Главная идея: три слоя, которые обновляются независимо

Сейчас ROCm, torch, ComfyUI и ноды зашиты в один образ и меняются только вместе.
Разделяем их по скорости изменений:

```
┌───────────────────────────────────────────────────────────┐
│ 3. МОДПАК   modpack-<имя>:<версия>                        │  меняется, когда меняется
│    pip-зависимости нод, собранные колёса                  │  состав нод или их зависимости
│    (код нод — в ~/ComfyUI/<модпак>/custom_nodes)          │
├───────────────────────────────────────────────────────────┤
│ 2. ЯДРО     comfy-core:<тег ComfyUI>-<runtime>            │  каждые несколько дней
│    ComfyUI по тегу/коммиту, requirements.txt,             │  (релизы ComfyUI)
│    frontend, Manager, патчи ядра                          │
├───────────────────────────────────────────────────────────┤
│ 1. RUNTIME  strix-runtime:<rocm>-<torch>                  │  раз в недели/месяцы
│    ОС, Python 3.13, venv, torch/vision/audio/triton       │  (осознанно)
│    под gfx1151, переменные ROCm                           │
└───────────────────────────────────────────────────────────┘
  НЕ в образах: модели, код нод, user, input, output, кэши — всё в ~/ComfyUI/<модпак> и /mnt/data
```

Каждый слой — `Containerfile` с `FROM` предыдущего. Podman хранит общие слои один раз,
поэтому держать рядом несколько ядер и модпаков почти ничего не стоит.

### Слой 1 — runtime

- Собираем сами по рецепту kyuz0 (см. [current-state.md](current-state.md)): там около
  десятка шагов, и нам не нужны его ComfyUI, ноды и скрипты моделей.
- Версии torch/ROCm закреплены явно (`torch==2.14.0a0+rocm7.15.0a20260721`).
  Из них генерируется `constraints.txt`, который получают все верхние слои:
  никакой `pip install` выше не может подменить torch.
- Колёса torch/ROCm складываем в локальный `wheelhouse/`: nightly-индекс AMD не обязан
  хранить старые сборки вечно, а пересобрать runtime нужно уметь и через полгода.
- Сюда же — системные пакеты, нужные нодам: ffmpeg, шрифты (вместо симлинка на
  `/usr/share/fonts/truetype`), при необходимости `mesa-vulkan-drivers`.
- Отдельный вариант `strix-runtime-devel` с `rocm-sdk-devel` и `ninja` — для сборки
  нативных расширений (TRELLIS.2 и т.п.). Результат — колёса, а не установленные файлы.

### Слой 2 — ядро ComfyUI

- `ARG COMFYUI_REF` — тег (`v0.35.1`) или коммит master. Клон, `pip install -r requirements.txt`
  и `manager_requirements.txt` с `constraints.txt` из runtime.
- Патчи ядра накладываются серией из `core/patches/` через `git apply --check`.
  Если патч больше не применяется — сборка останавливается и сообщает, какой именно:
  это сигнал, что upstream изменил или исправил место.
- Сборка слоя занимает минуты: torch уже в runtime, качаются только frontend-пакеты и мелочь.
- ComfyUI **не** монтируется с хоста как основной путь: его Python-зависимости меняются
  почти каждый релиз (`comfyui-frontend-package`, `comfy-kitchen`, `comfy-aimdo`, `av`),
  и код должен приезжать вместе с подходящими пакетами. Для отладки есть режим
  «dev»: поверх образа монтируется локальный checkout (например, для bisect).

### Слой 3 — модпак

- `FROM comfy-core:<ref>`: базовый тег ядра — параметр, модпак пересобирается на новое
  ядро без правки своих файлов.
- Ноды — из `nodes.lock`: URL, коммит (или версия реестра Comfy для нод без git),
  список патчей. Форки держим в своём GitHub: `origin` — форк, `upstream` — оригинал.
  Сам код нод в образ не входит — он в папке модпака на хосте (раздел «Данные»),
  в образе только их зависимости.
- Ноды, у которых мы меняем поведение или входы, получают свой идентификатор класса
  (префикс `ND_`), чтобы не перекрывать оригинал. Собственные ноды под эту машину — в паке
  `comfyui-rocm-halo` («ROCm Halo», префикс `RH_`), Node API V3, без JavaScript ([ADR-0005](decisions/0005-frontend-nodes2-and-node-api-v3.md)).
- pip-зависимости нод ставятся с `constraints.txt`. Исключения (`pedalboard`, `opencv-python`
  поверх headless) описываются явно в `modpack.yaml`.
- Manager в модпаке выключен: состав меняется только через репозиторий.

## Данные и запуск контейнера

Всё рабочее у модпака — **одна папка на хосте**. Внутри ровно те подпапки, которые
ComfyUI ожидает от `--base-directory`, поэтому она монтируется одним томом:

```
~/ComfyUI/
  main/                   ← модпак (одна папка = всё его рабочее)
    custom_nodes/         ← ноды: git-клоны/форки, правятся прямо здесь
    user/                 ← настройки, воркфлоу, comfyui.db
    input/
    output/
    temp/
  trellis2/
    custom_nodes/ user/ input/ output/ temp/
```

Бэкапы `user/` перед promote — в `var/backups/` репозитория.

Монтирований у контейнера всего три:

| В контейнере | С хоста | Режим | Ключ ComfyUI |
|---|---|---|---|
| `/data` | `~/ComfyUI/<модпак>` | запись | `--base-directory /data` |
| `/models` | `/mnt/data/AI_Models/ComfyUI` | только чтение, общее для всех модпаков | `--models-directory /models` |
| `/cache/hf` | `/mnt/data/huggingface` | запись, общий | `HF_HOME` |

Плюс устройства `/dev/kfd`, `/dev/dri` (`--group-add video,render`). Весь `/home`, `/mnt`
и корень хоста в контейнер **не** пробрасываются.

Ноды лежат в папке модпака, а не внутри образа: их удобно править, и данные нод
(например, 3.9 ГБ кэша Civitai у lora-manager) не раздувают образ. В образ модпака
попадают только их pip-зависимости, собранные по `requirements.txt` из `custom_nodes/`
и `nodes.lock`. `tools/comfy sync` приводит `custom_nodes/` к состоянию `nodes.lock`
и показывает расхождения (локальные правки, лишние каталоги).

Кандидат обновления ядра использует те же `custom_nodes/`, `input/`, `output/`,
но **копию** `user/`: новая версия при старте мигрирует `comfyui.db`, и старая может её не открыть.

Порт у каждого модпака свой (8000 — основной, 8100+ — кандидаты обновлений).
Ключи запуска ComfyUI хранятся в `modpack.yaml`, а не в скрипте на хосте.

## Раскладка репозитория (план)

Репозиторий: `/mnt/code/ComfyUI_ROCM` — NTFS-раздел `Code`, общий с Windows,
монтируется через `/etc/fstab` (ntfs-3g). Особенности:
- `core.fileMode=false` (NTFS не хранит флаг исполняемости), `.gitattributes` с `eol=lf`;
- образы podman сюда не кладутся — слои не хранятся на NTFS, они остаются в `~/.local/share/containers` (btrfs);
- тяжёлое пересоздаваемое — в `var/` (вне git и вне контекста сборки, в сборку подключается через `RUN --mount`).

```
ComfyUI_ROCM/
  docs/                       ← эта документация
  runtime/
    Containerfile             ← слой 1
    versions.env              ← база, Python, версии torch/ROCm, индекс колёс, имя образа
    constraints.txt           ← снимок закреплённого стека (пишет tools/runtime-build)
  core/
    Containerfile             ← слой 2, ARG COMFYUI_REF
    versions.env              ← runtime-образ, репозиторий и ref ComfyUI по умолчанию
    apply-patches.sh          ← наложение patches/ при сборке (applied / in upstream / conflict)
    check-torch-stack.py      ← контроль: pip не сдвинул стек из /opt/constraints.txt
    check-core-import.py      ← импорт ядра при сборке (без GPU)
    patches/                  ← патчи ядра ComfyUI (0001-growmask-cpu.patch, …)
  modpacks/
    main/
      modpack.yaml            ← базовое ядро, ключи запуска, порт, исключения pip
      nodes.lock              ← ноды: репозиторий, коммит, патчи
      patches/                ← патчи нод
      workflows/              ← эталонные воркфлоу для тестов (рабочие — в ~/ComfyUI/main/user)
      Containerfile           ← слой 3 (генерируемый или общий шаблон)
    trellis2/
  var/                        ← вне git
    wheelhouse/               ← кэш колёс torch/ROCm
    wheels/                   ← собранные нативные пакеты (o_voxel, cumesh, …)
    backups/                  ← копии user/ перед promote
  tests/
    smoke/gpu_check.py        ← torch видит GPU, matmul/SDPA/conv (для runtime)
    schema/dump.py, diff.py   ← снимок /object_info и сравнение: удалённые ноды, ломающие изменения входов
    workflows/                ← прогон эталонных воркфлоу через API (этап 3)
  tools/
    wheelhouse-sync           ← скачать колёса стека по versions.env в var/wheelhouse
    runtime-build             ← собрать слой 1 из wheelhouse
    runtime-test              ← GPU-смоук образа (tests/smoke/gpu_check.py)
    comfy                     ← build core / run / stop / log / status / smoke / schema diff
                                (update / promote / rollback — этап 3)
```

Запуск контейнера (`tools/comfy run`): `--device /dev/kfd --device /dev/dri --group-add keep-groups
--userns=keep-id`, порт только на `127.0.0.1`, `HOME=/data` (иначе `uv` у Manager не может писать кэш),
`main.py` абсолютным путём. Снимки схем и логи smoke — в `var/schema`, `var/logs`.

Скрипты запускаются как `bash tools/<имя>`: NTFS не хранит бит исполняемости.

## Что переносим из текущей установки

| Сейчас | В новой схеме |
|---|---|
| `start_comfy_manager` | ключи в `modpack.yaml`, запуск через `tools/comfy run` |
| `comfy_pin_torch` + `PIP_CONSTRAINT` | `constraints.txt` из runtime, применяется при сборке |
| `comfy_snapshot` / `comfy_rollback` | теги образов + бэкап `user/` перед promote |
| `comfy_check` | `tests/smoke` |
| ручные правки в `/opt` | `core/patches`, пакеты runtime |
| `~/comfy/custom_nodes`, `~/comfy/user`, `~/comfy/input`, `~/comfy-outputs` | `~/ComfyUI/main/{custom_nodes,user,input,output}` + `modpacks/main/nodes.lock` |
| `~/comfy-models` (симлинк) | монтирование `/mnt/data/AI_Models/ComfyUI` → `/models` |
| `~/comfy/fonts` + симлинк в `/usr/share/fonts` | шрифты в образе runtime |

Текущий контейнер `strix-halo-comfyui` работает, пока модпак `main` не пройдёт
все проверки на тех же воркфлоу.
