# Реестр правок и обходов

Всё, что отличает нашу сборку от чистого upstream. Подробности и история —
`/home/ai/comfy/bin/patches/CHANGES.md` (раздел указан в колонке «§»).

**Слой:** runtime / core / node / workflow / launch — куда правка уйдёт в новой архитектуре.
**Статус upstream:** проверяется при каждом обновлении.

| # | Что | Где | Слой | § | Статус upstream | Как переносим |
|---|---|---|---|---|---|---|
| P1 | Шрифты: нода читает Debian-путь `/usr/share/fonts/truetype` | Comfyroll `CR Select Font` | runtime / node | 1 | не исправлено | шрифты в образ runtime по этому пути; позже — патч поиска шрифтов в форке |
| P2 | `pedalboard` 0.9.25 даёт SIGILL при импорте, роняет весь ComfyUI | crt-nodes | node | 2 | колесо не исправлено | исключить `pedalboard` из зависимостей модпака; без него отключается только AudioCompressor |
| P3 | Блокировка Linux в `_platform_spec()` + поиск локального `llama-cli` | ComfyUI-LLM-text-processor | node | 3 | не исправлено | форк; `llama.cpp` — в образ модпака или runtime |
| P4 | Апскейлер возвращает латент на CPU, `torch.cat` падает в конце прогона | Comfyui_Minimax_h3_latent_Upscaler_ND | node | 4 | не исправлено | форк, 2 файла |
| P5 | Предпросмотр: NVENC → добавлен libx264 перед WebP | comfyui-kjnodes (без git) | node | 5 | не исправлено | форк KJNodes; обновляется часто — патч держать минимальным |
| P6 | Sage Attention на AMD не работает, у ноды нет выключателя | KJNodes `MiniMaxH3MemoryEfficientSageAttentionPatch` | workflow | 7 | — | Bypass в воркфлоу; опционально — вход-выключатель в форке KJNodes |
| P7 | Два пакета регистрируют `LLMTextProcessor`, форк сдвигает входы | `_mtp_ND` | node | 9 | — | в модпаке только один из пакетов; форк с MTP — под своим ID класса |
| P8 | Обрыв связей LoRA-ноды в Krea2/Flux2 | воркфлоу `ND_Krea2_Ultimate_TI2I_v1.4` и производные | workflow | 10 | авторский воркфлоу | исправленные копии в `workflows/` модпака |
| P9 | GrowMask: `m.numpy()` на GPU-тензоре при `--gpu-only` | ComfyUI `comfy_extras/nodes_mask.py:376` | core | 11 | **не исправлено в v0.35.1** | `core/patches/0001-growmask-cpu.patch`; кандидат в PR upstream |
| P10 | `--disable-smart-memory`, `--cache-none` сняты | строка запуска | launch | 11 | — | ключи в `modpack.yaml`; для тяжёлых видео — опциональный профиль |
| P11 | torch защищён от подмены при установке нод | `PIP_CONSTRAINT` / `UV_CONSTRAINT` | runtime | — | — | `constraints.txt` из runtime на всех слоях |

## Как добавлять

1. Правка — в форк ноды или в `core/patches/NNNN-<суть>.patch`.
2. Строка в таблице: слой, ссылка на коммит/патч, статус upstream.
3. Если правка чинит ошибку upstream — ссылка на issue/PR, когда он будет.
4. Если при обновлении патч оказался в upstream — строку не удалять, а пометить «принято в vX.Y.Z» и убрать файл патча.
