# Текущее состояние (до начала проекта)

Снимок на 14.09.2026. Это то, от чего уходим, и то, что нельзя сломать по дороге.

> **20.09.2026: описанный здесь toolbox удалён** (контейнер `strix-halo-comfyui`, образ kyuz0, снимки `my-comfy`). Документ остаётся
> как справка: откуда взяты версии ROCm/torch, ключи запуска и состав нод. Уникальные файлы контейнера (воркфлоу
> `minimax_h3_t2v_turbo.json`, `comfy.settings.json`) — в `var/backups/toolbox-strix-halo-comfyui/`. Образ при нужде
> возвращается `podman pull docker.io/kyuz0/amd-strix-halo-comfyui:latest` (16 ГБ).

## Контейнер

| | |
|---|---|
| Имя | `strix-halo-comfyui` (toolbox, privileged, сеть хоста) |
| Образ | `docker.io/kyuz0/amd-strix-halo-comfyui:latest`, digest `sha256:384aa1fe…`, собран 11.08.2026 |
| ОС образа | Fedora 45 (Container Image Prerelease) |
| Python | 3.13.14, venv `/opt/venv` |
| torch | `2.14.0a0+rocm7.15.0a20260721` (torchvision 0.29.0a0, torchaudio 2.11.0.2, triton 3.8.0) |
| ROCm | `rocm-sdk-*` 7.15.0a20260721 в виде pip-колёс, `rocm-sdk-device-gfx1151` |
| ComfyUI | 0.31.0, коммит `62b3c94` от 11.08.2026, лежит в `/opt/ComfyUI` |
| Manager | `comfyui_manager` 4.2.2 (встроенный, флаги `--enable-manager --enable-manager-legacy-ui`) |
| Монтирования | весь `/home/ai`, весь `/mnt`, корень хоста |
| Снимки | `localhost/my-comfy:baseline`, `localhost/my-comfy:before-update` |

Переменные окружения образа: `TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1`, `TORCH_BLAS_PREFER_HIPBLASLT=1`.

## Как kyuz0 собирает образ

По `podman history`:

1. `dnf install` — python3.13, gcc, git, ffmpeg-free, libdrm-devel;
2. venv в `/opt/venv`;
3. `pip install --index-url https://rocm.nightlies.amd.com/whl-multi-arch/ --pre "torch[device-gfx1151]" "torchvision[device-gfx1151]" torchaudio`;
4. `git clone --depth=1` ComfyUI — **ветка master на момент сборки, без закрепления версии**;
5. `pip install -r requirements.txt` + opencv-headless, hf_transfer и т.п.;
6. четыре ноды: ComfyUI-GGUF (форк kyuz0), ComfyUI_essentials, ComfyUI-AMDGPUMonitor, ComfyUI-MiniMax-H3-Turbo;
7. скрипты загрузки моделей, баннер, alias `start_comfy_ui`.

**Главный вывод для проекта:** версия ComfyUI зашита в образ автора. Свежий ComfyUI мы
получаем только тогда, когда kyuz0 пересоберёт `latest`, и вместе с ним непредсказуемо
меняются torch и ROCm. На 14.09 образу 4 недели: за это время ComfyUI ушёл с 0.31.0
на 0.35.1 — это 14 релизов и 195 коммитов.

## Запуск и обслуживание (на хосте, `~/bin`)

| Скрипт | Назначение |
|---|---|
| `comfyctl start/stop/restart/status/log` | управление контейнером и сервером |
| `start_comfy_manager` | строка запуска: `--port 8000`, пути в `~/comfy`, `--disable-mmap --gpu-only --bf16-vae`, `PIP_CONSTRAINT` |
| `comfy_pin_torch` | генерирует `~/comfy/pip-constraints.txt` с текущими версиями torch |
| `comfy_snapshot` / `comfy_rollback` | `podman commit` + манифест / пересоздание из снимка |
| `comfy_check` | смоук-тест: torch видит GPU, сервер стартует, нет `IMPORT FAILED` |
| `comfy_setup` | возврат Manager и зависимостей нод после обновления образа |

Шпаргалка пользователя: `/home/ai/Desktop/ToolBoxCommand.md`.

## Данные

| Путь | Что |
|---|---|
| `~/comfy` | base-directory: `custom_nodes`, `user`, `input`, база `user/comfyui.db` |
| `~/comfy/user/default/workflows` | 116 воркфлоу (папки `ND`, `MY`, `IG`, `EXAMPLE`) |
| `~/comfy-models` → `/mnt/data/AI_Models/ComfyUI` | модели (NTFS) |
| `~/comfy-outputs` | результаты |
| `~/comfy/bin/llama.cpp` | llama.cpp b10472 (CPU) для LLMTextProcessor; в `main` — `~/ComfyUI/main/bin/llama.cpp/`, Vulkan-сборка через `tools/llama-fetch` |
| `~/comfy/bin/patches` | патчи и журнал `CHANGES.md` |

## Кастом-ноды

42 каталога в `~/comfy/custom_nodes` (один отключён) плюс 4 ноды в образе.

- **24 под git** — можно форкать и закреплять по коммиту.
- **18 без git** (поставлены Manager из реестра архивом): basic_data_handling, comfyui-agent-panel,
  comfyui-custom-scripts, comfyui-easy-use, ComfyUI-Flux2Klein-Enhancer, comfyui-googletrans,
  comfyui-impact-pack, comfyui-inpaint-cropandstitch, comfyui-inspyrenet-rembg, comfyui-kjnodes,
  comfyui_layerstyle, comfyui-lora-manager, comfyui-mxtoolkit, ComfyUI-Pixaroma,
  comfyui-videohelpersuite, crt-nodes, mikey_nodes, rgthree-comfy.
  Для модпака их надо сопоставить с git-репозиториями и версиями реестра.
- **С локальными правками:** Comfyroll (2 файла), LLM-text-processor (1),
  Minimax_h3_latent_Upscaler_ND (4), plaguekind-nodes (11), kjnodes (без git, есть `.orig`).
- **Отключены:** `ComfyUI-LLM-text-processor_mtp_ND.disabled` — перекрывал исходную ноду.
- `comfyui_nvidia_rtx_nodes` на AMD бесполезен — кандидат на исключение.
- `ComfyUI-TRELLIS2` (visualbruno) склонирован, нативные зависимости не собраны.

## Проблемы, которые решает проект

1. Правки в `/opt` (GrowMask, удалённый pedalboard, симлинк шрифтов) живут в слое контейнера
   и пропадают при пересоздании.
2. Одна папка нод и один venv на всё: нода с тем же идентификатором молча перекрывает другую
   (так сломались 25 воркфлоу).
3. Manager ставит что угодно прямо в рабочее окружение.
4. Версии ComfyUI, torch и ROCm меняются только вместе и только по воле автора образа.
5. Контейнер без изоляции: privileged, весь `/home` и `/mnt` на запись.
