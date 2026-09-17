# Лог запуска: что означают строки

Разбор лога `comfy-main` на 17.09.2026 (ядро v0.35.1, модпак `main`). Что приглушено, что исправлено,
что остаётся как есть и почему. Проверять после каждого `update`/`promote`: `bash tools/comfy log main | grep -i warn`.

## Приглушено нашим паком (`custom_nodes/comfyui-rocm-halo/log_quiet.py`)

Фильтр стоит на обработчиках корневого логгера и ставится при импорте пака. Правило = регулярное
выражение + причина; убрать правило — предупреждение вернётся. При старте пак пишет одну строку
`[ROCm Halo] в логе приглушены известные предупреждения: N правил`.

| Строка | Кто | Почему безвредна |
|---|---|---|
| `[Impact Pack] The SAM2 functionality is unavailable because the facebook/sam2 dependency is not installed` (дважды) | Impact Pack при импорте `modules/impact/core.py` | `sam2` исключён в `modpack.yaml pip.exclude`: это git-сборка CUDA-расширения, под ROCm не собирается. Ноды SAM2 не используем; если понадобятся — при вызове будет та же понятная ошибка |
| `[DEPRECATION WARNING] Detected import of deprecated legacy API: /scripts/ui.js`, `/extensions/core/clipspace.js`, `/extensions/core/widgetInputs.js`, `/scripts/ui/components/buttonGroup.js`, `/scripts/ui/components/button.js` | ядро (`server.py`) при первом запросе этих файлов браузером | их импортируют JS-расширения Easy-Use (10 файлов), Impact-Pack (3), Lora Manager (1). В upstream всех трёх на 17.09 то же самое — обновлять нечего, работе не мешает. Проверка: `git grep -l 'scripts/ui.js' origin/main` в каталоге пакета |

Порядок загрузки нод в ядре — порядок `os.listdir`, не отсортирован. Сейчас наш пак грузится раньше
Impact Pack (видно по логу), поэтому его предупреждение при импорте попадает под фильтр. Если после
добавления пакетов порядок изменится, строка SAM2 вернётся — это не поломка.

## Исправлено

| Строка | Было | Стало |
|---|---|---|
| `dzNodes: LayerStyle -> Cannot import name 'guidedFilter' from 'cv2.ximgproc' … REINSTALL package 'opencv-contrib-python'` | в образ шёл `opencv-python-headless` (его просят Easy-Use, Impact-Pack, KJNodes), а `cv2.ximgproc` есть только в contrib-сборке; ставить contrib поверх — два cv2 в одном venv | `modpack.yaml`: `opencv-python-headless` в `pip.exclude`, `opencv-contrib-python-headless` в `pip.extra`. Ядро OpenCV не содержит, так что в образе один cv2 — contrib-headless (надмножество обычного, та же версия 5.0.0.93). guidedFilter нужен ультра-нодам масок LayerStyle (`MaskEdgeUltraDetail`, `RmBgUltra V2`, `SegformerUltra`, `SharpSoft`); в наших воркфлоу пока только `ImageScaleByAspectRatio V2` |

## Остаётся как есть

| Строка | Почему |
|---|---|
| `[ComfyUI-Manager] The matrix sharing feature has been disabled because the matrix-nio dependency is not installed` | шаринг воркфлоу в Matrix; не нужен |
| `torch/jit/_script.py: FutureWarning: torch.jit.script is deprecated` | какой-то из пакетов зовёт `torch.jit.script` при импорте; предупреждение самого torch, к работе отношения не имеет |
| `[rgthree-comfy] ComfyUI's new Node 2.0 rendering may be incompatible…` | справка автора rgthree про Nodes 2.0; наш пак на V3 API, rgthree используем для Fast Bypasser и закладок |
| `Asset seeder already running, skipping start` | с `--enable-assets` скан запускает `main.py`, потом его же просит фронтенд — второй вызов пропускается |

## Вкладка «Медиафайлы → Сгенерированные» пуста после перезапуска

Это не ошибка и не настройка. Вкладка читает `/api/jobs` — историю очереди, а она в ядре живёт в памяти
процесса (`execution.py`, `PromptQueue.history`, словарь с ограничением по размеру) и ключа для сохранения
на диск нет. После любого перезапуска история пуста, пока не пройдут новые задания. Сами файлы никуда не
деваются: `~/ComfyUI/main/output/`.

Ключ `--enable-assets` (включён 17.09) — про другое: база `user/comfyui.db` индексирует файлы
models/input/output (`/api/assets`, 101 выходной файл после первого скана), регистрирует загрузки.
Фронтенд 1.51 на неё вкладку «Сгенерированные» не переводит. Ключ оставлен: ядро движется к обязательной
базе, скан при старте без хеширования быстрый (276 файлов), стоимости нет.
