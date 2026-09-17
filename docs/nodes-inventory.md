# Справочник нод старого toolbox

Снимок `~/comfy/custom_nodes` (42 каталога, 6.1 ГБ) на 15.09.2026 — источник для `tools/comfy node add main URL`
([ADR-0006](decisions/0006-modpack-main-starts-empty.md): в `main` ноды добавляются по потребности).
«Без git» — каталог ставился Manager'ом из реестра, версия из `pyproject.toml`, репозиторий оттуда же;
для остальных указан коммит. Правки — см. [patches-registry.md](patches-registry.md).

```
bash tools/comfy node add main https://github.com/kijai/ComfyUI-KJNodes   # клон в ~/ComfyUI/main/custom_nodes + nodes.lock
bash tools/comfy build main && bash tools/comfyctl restart               # зависимости в образ
```

| Каталог | Репозиторий | Версия / коммит | Заметки |
|---|---|---|---|
| `audio-batch` | https://github.com/set-soft/ComfyUI-AudioBatch | 3930594 |  |
| `basic_data_handling` | https://github.com/StableLlama/ComfyUI-basic_data_handling | 1.8.1 | без git |
| `comfyui-agent-panel` | https://github.com/artokun/comfyui-mcp-panel | 0.15.182 | без git |
| `ComfyUI_Comfyroll_CustomNodes` | https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes | d78b780 | правки: 2 файла (P1 шрифты — закрыто в runtime) |
| `comfyui-custom-scripts` | https://github.com/pythongosssss/ComfyUI-Custom-Scripts | 1.2.5 | без git |
| `comfyui-easy-use` | https://github.com/yolain/ComfyUI-Easy-Use | 1.3.6 | без git |
| `ComfyUI-Flux2Klein-Enhancer` | https://github.com/capitan01R/ComfyUI-Flux2Klein-Enhancer | 3.4.4 | без git |
| `comfyui-fl-yue2` | https://github.com/filliptm/ComfyUI-FL-YuE2 | b5af3e6 | в `main` с 17.09 на 8042212 (воркфлоу YuE2); импортирует `soundfile` при загрузке — добавлен в `pip.extra` |
| `comfyui-googletrans` | https://github.com/sweetndata/ComfyUI-googletrans | 0.1.1 | без git |
| `ComfyUI-H3-Motion-Context-MultiRef` | https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef | 361624f |  |
| `ComfyUI-H3-VisionPromptor` | https://github.com/benjiyaya/ComfyUI-H3-VisionPromptor | 24a3671 |  |
| `comfyui-impact-pack` | https://github.com/ltdrdata/ComfyUI-Impact-Pack | 8.28.3 | без git; есть `install.py` |
| `comfyui-inpaint-cropandstitch` | https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch | 3.0.15 | без git |
| `comfyui-inspyrenet-rembg` | https://github.com/john-mnz/ComfyUI-Inspyrenet-Rembg | 1.1.1 | без git |
| `comfyui-kjnodes` | https://github.com/kijai/ComfyUI-KJNodes | 1.5.0 | без git; P5 (libx264 в предпросмотре), P6 (Sage Attention — bypass) |
| `comfyui-krea2edit` | https://github.com/lbouaraba/comfyui-krea2edit | 86f886d |  |
| `comfyui_layerstyle` | https://github.com/chflame163/ComfyUI_LayerStyle | 2.0.40 | без git |
| `ComfyUI-LLM-text-processor` | https://github.com/KingManiya/ComfyUI-LLM-text-processor | 65983de | правки: 1 файл — P3 (Linux + локальный `llama-cli`); P7 конфликт ID с `_mtp_ND` |
| `ComfyUI-LLM-text-processor_mtp_ND.disabled` | https://github.com/Kvento/ComfyUI-LLM-text-processor_mtp_ND | 9976aed | отключён (P7); если нужен — под своим ID класса |
| `comfyui-lora-manager` | https://github.com/willmiao/ComfyUI-Lora-Manager | 1.2.1 | без git; 3.9 ГБ кэша Civitai в каталоге |
| `comfyui-mickmumpitz-nodes` | https://github.com/mickmumpitz/ComfyUI-Mickmumpitz-Nodes | 4d5ff7c |  |
| `Comfyui_Minimax_h3_latent_Upscaler_ND` | https://github.com/Kvento/Comfyui_Minimax_h3_latent_Upscaler_ND | d7c01b9 | правки: 4 файла — P4 (латент на CPU) |
| `comfyui-minimax-h3-studio` | https://github.com/thaakeno/ComfyUI-MiniMax-H3-Studio | 8e106b3 |  |
| `ComfyUI-MiniMax-M3-SongPlanner` | https://github.com/benjiyaya/ComfyUI-MiniMax-M3-SongPlanner | e46b13b |  |
| `comfyui-mxtoolkit` | https://github.com/Smirnov75/ComfyUI-mxToolkit | 0.9.92 | без git |
| `comfyui_nvidia_rtx_nodes` | https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI | 892515e | NVIDIA-only, в `main` не нужен |
| `ComfyUI-Pixaroma` | https://github.com/pixaroma/ComfyUI-Pixaroma | 1.4.126 | без git |
| `comfyui-spectrum-minimax-h3` | https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3 | be95ade |  |
| `ComfyUI-TRELLIS2` | https://github.com/visualbruno/ComfyUI-Trellis2 | 1459741 | нужны нативные сборки — этап 4 (модпак `trellis2`) |
| `ComfyUI-UtilsCollection` | https://github.com/silveroxides/ComfyUI-UtilsCollection | d6a9600 |  |
| `comfyui-videohelpersuite` | https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite | 1.7.9 | без git |
| `comfyui-vrgamedevgirl` | https://github.com/vrgamegirl19/comfyui-vrgamedevgirl | c85fda6 |  |
| `crt-nodes` | https://github.com/PGCRT/CRT-Nodes | 2.17.0 | без git; P2 — `pedalboard` в `pip.exclude` |
| `fantastic-minimax-h3-prompt-builder` | https://github.com/Adudeguyman/ComfyUI-Fantastic-MiniMaxH3-PromptBuilder | 06fef6c |  |
| `maskvidexperiments` | https://github.com/drozbay/MaskVidExperiments | e5c4450 |  |
| `mikey_nodes` | https://github.com/bash-j/mikey_nodes | 1.0.5 | без git |
| `minimax-h3-image-studio` | https://github.com/astropuzzo/ComfyUI-MiniMax-H3-Image-Studio | b4a2339 |  |
| `one-node-gemma-4` | https://github.com/yanokusnir-ai/one-node-gemma-4 | 369dcbf |  |
| `one-node-minimax-h3` | https://github.com/LeonQ8/ComfyUI-ALLinONE-MinimaxH3 | 327adb6 |  |
| `plaguekind-nodes` | https://github.com/PlagueKind/ComfyUI-PlagueKind-Nodes | 59f54d3 | правки: 11 файлов — разобрать перед добавлением |
| `rgthree-comfy` | https://github.com/rgthree/rgthree-comfy | 1.0.2608210019 | без git |
| `seedvr2_videoupscaler` | https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler | 4490bd1 |  |

Ноды с правками при добавлении оформляются форком (`origin` — форк, `upstream` — оригинал) или патчем
в `modpacks/main/patches/`; нода с изменённым поведением получает свой ID класса (ADR-0002).
