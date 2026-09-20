> Справка собрана 20.09.2026 субагентом по первоисточникам в сети (verified: docs). На нашей машине ничего из этого не запускалось; выводы про ROCm — из чужих issue. Решения по установке паков — за пользователем.

# Исследование: задачи ACE-Step 1.5 и разделение на стемы в ComfyUI

Контекст: локальный ComfyUI (ядро v0.36.0), AMD Strix Halo gfx1151, ROCm 7.15, torch 2.14, CUDA нет.
Дата исследования: 2026-09-20. Все источники — веб (не проверялись напрямую на установленном ядре; часть выводов — из пересказа WebFetch, не из сырого текста файлов, см. оговорки).

## ЧАСТЬ 1. ACE-Step 1.5: задачи, кроме text2music

Официальный репозиторий подтверждён: **github.com/ace-step/ACE-Step-1.5** (README: "The most powerful local music generation model... supporting Mac, AMD, Intel, and CUDA devices").

### 1.1 Список задач (Musicians Guide + README)

Источники: `docs/en/ace_step_musicians_guide.md` и корневой README.md репозитория ace-step/ACE-Step-1.5.

| Задача | Вход | Выход |
|---|---|---|
| Text2Music | caption (теги стиля/настроения/инструментов) + lyrics со структурными тегами | полный трек WAV/MP3 |
| Cover / Remix | исходное аудио + новый caption + Audio Cover Strength (0.0–1.0) | трек в новом стиле с сохранением структуры оригинала |
| Repaint | исходное аудио + окно времени (start/end, сек) + caption на этот участок | тот же трек с пересгенерированным участком |
| Lego (наслоение) | бэк-трек/частичный инструментал + caption + выбор дорожки (vocals/drums/bass/guitar/keyboard...) | полный микс с добавленными слоями инструментов, либо чистый изолированный стем нужного инструмента (описание расходится между Musicians Guide и DeepWiki — см. ниже) |
| Extract (сепарация) | полное смикшированное аудио (`src_audio`) + название дорожки | изолированный стем запрошенного инструмента/вокала |
| Complete (доген аранжировки) | вокальная дорожка отдельно (`src_audio`, частичный микс) | сгенерированная инструментальная подложка / полный микс с добавленными дорожками |

Примечание по Lego: Musicians Guide описывает его как «добавление слоёв» (вход — бэк-трек, выход — полный микс), а DeepWiki-страница «Advanced Tasks (Lego, Extract, Complete)» описывает его как генерацию **изолированной** дорожки по `global_caption` + выбору трека. Это разночтение не удалось разрешить без чтения исходного кода `inference.py`/`pipeline.py` самого ACE-Step-1.5 — файл не читался напрямую в этом исследовании.

LM-компонент («Songwriter») автоматически отключается для Cover, Repaint и Extract — задачи работают прямо с исходным аудио и не нуждаются в фазе планирования (источник: Musicians Guide).

### 1.2 Ограничения по вариантам модели — ПОДТВЕРЖДЕНО таблицей из README

Источник: raw README.md репозитория ace-step/ACE-Step-1.5 (таблица "Model Variants Capability Matrix").

| Вариант | Text2Music | Cover | Repaint | Extract | Lego | Complete |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| acestep-v15-base (2B) | + | + | + | + | + | + |
| acestep-v15-sft (2B) | + | + | + | - | - | - |
| acestep-v15-turbo (2B) | + | + | + | - | - | - |
| acestep-v15-xl-base (4B) | + | + | + | + | + | + |
| acestep-v15-xl-sft (4B) | + | + | + | - | - | - |
| **acestep-v15-xl-turbo (4B)** | + | + | + | **-** | **-** | **-** |

Вывод: **XL Turbo (используемая пользователем модель) НЕ поддерживает Extract/Lego/Complete** — только text2music, cover, repaint. Это подтверждено также моделькартой HuggingFace `ACE-Step/acestep-v15-xl-turbo`, где вместо перечня задач стоит "Standard", в отличие от `acestep-v15-xl-base`, где явно указано "All (extract, lego, complete)". Ссылки: https://github.com/ace-step/ACE-Step-1.5 , https://huggingface.co/ACE-Step/acestep-v15-xl-turbo , https://huggingface.co/ACE-Step/acestep-v15-xl-base

Для extract/lego/complete пользователю нужен отдельно скачанный `acestep-v15-xl-base` (или обычный `-base`), а не имеющийся XL Turbo.

### 1.3 Доступность в ComfyUI

**Ядро ComfyUI (comfy_extras/nodes_ace.py, Comfy-Org/ComfyUI):**
- `TextEncodeAceStepAudio` — старый ACE-Step 1.0 энкодер (tags, lyrics, lyrics_strength). Референс-аудио и task нет.
- `TextEncodeAceStepAudio15` — для 1.5: tags, lyrics, seed, bpm, duration, timesignature, language, keyscale, generate_audio_codes, cfg_scale, temperature, top_p/top_k/min_p. Параметра `task` нет.
- `EmptyAceStepLatentAudio` / `EmptyAceStep15LatentAudio` — пустой латент (seconds, batch_size). Без референс-аудио.
- `ReferenceAudio` — единственная нода с входом аудио: принимает conditioning + опциональный latent, описанный как «reference audio for ace step 1.5». Входов для масок/окна repaint не найдено.

Официальная документация docs.comfy.org (`tutorials/audio/ace-step/ace-step-v1-5`) прямо пишет, что в ComfyUI на данный момент поддерживается **только text2music**, а Cover и Repaint перечислены как «доступно в ACE-Step 1.5, но ещё не поддержано в ComfyUI». Про Extract/Lego/Complete в тексте документации вообще не упоминается (то есть не то что не поддержано отдельно — они не входят в обсуждение ядра ComfyUI). Источник: https://docs.comfy.org/tutorials/audio/ace-step/ace-step-v1-5

Итого: **ядро ComfyUI на данный момент даёт только text2music для ACE-Step 1.5**; cover/repaint/extract/lego/complete в основных нодах отсутствуют.

**Сторонние паки нод ComfyUI с задачами cover/repaint/extract/lego:**

| Репозиторий | Официальность | Последний коммит / звёзды | Что даёт |
|---|---|---|---|
| ace-step/ACE-Step-ComfyUI | официальный (организация ace-step) | 2026-03-01, 82 звезды, 12 форков, MIT | Ноды Text2music Gen Params/Settings/Server, Audio Codes, Show Text. Судя по пересказу — работает как клиент к серверу инференса ACE-Step 1.5 (локальный inference-сервер или облачный API acemusic.ai), а не чистые torch-ноды на графе ComfyUI. Заявлена поддержка cover/remix и repaint через API. Дальше не проверялось (требует отдельного инференс-сервера ACE-Step, не только ComfyUI). |
| ryanontheinside/ComfyUI_RyanOnTheInside | неофициальный, но крупный и активный пак («Everything-Reactivity») | 2026-03-20, 865 звёзд, 57 форков, MIT | Нативные ComfyUI-гайдеры под ACE-Step 1.5: "ACE-Step 1.5 Edit Guider" (extend/repaint), "ACE-Step 1.5 Cover Guider" (семантическое переиспользование структуры источника), task-aware текстовый энкодер. По его собственному README «Extract Guider» и «Lego Guider» помечены как **Coming Soon** — то есть ещё не реализованы. Это единственный найденный пак, где cover/repaint делаются прямо в графе ComfyUI (без внешнего сервера). |
| starsFriday/ComfyUI-ACEStep | неофициальный | не проверялся детально (не хватило времени в рамках задачи) | Заявлен как «серия улучшенных нод для ACEStep» — состав не проверен. |

Вывод по части 1: работоспособный набор задач в ComfyUI на сегодня — **text2music (ядро) + cover/repaint (через ryanontheinside/ComfyUI_RyanOnTheInside, нативно)**. Extract/Lego/Complete в ComfyUI **нигде не найдены реализованными** (ни в ядре, ни в проверенных сторонних паках — у RyanOnTheInside заявлены «Coming Soon»); к тому же они всё равно недоступны на модели XL Turbo, которая стоит у пользователя — потребуется XL-base.

---

## ЧАСТЬ 2. Разделение трека на стемы в ComfyUI

### 2.1 Кандидаты

| Репозиторий | Последний коммит | Звёзды/форки | Модели / стемы | Лицензия |
|---|---|---|---|---|
| **christian-byrne/audio-separation-nodes-comfyui** | 2026-08-17 | 615 / 61 | Hybrid Demucs (torchaudio) → 4 стема (bass, drums, other, vocals) + инструменты recombine/tempo-match/slice | MIT |
| **set-soft/AudioSeparation** | 2026-02-11 | 31 / 5 | MDX-Net + Demucs, всего заявлено 46 моделей (в основном из проекта UVR5); Demucs даёт 4 или 6 стемов, «UVR Demucs» — только vocals/other; есть karaoke-модели | код GPL-3.0, модели MIT |
| **ethanfel/ComfyUI-MelBandRoFormer** (форк kijai/ComfyUI-MelRoFormer) | 2026-09-16 (4 дня назад) | 0 у форка / 256 у оригинала kijai | Mel-Band RoFormer + BS-RoFormer (архитектуры вшиты, отдельный пакет bs-roformer не нужен) + Demucs; 40+ моделей: vocals/instrumental/karaoke/dereverb/denoise/aspiration/crowd; 2-стем (vocal+residual) у большинства, 4-стем у части моделей и у Demucs | не указана явно |
| ddontsov93/ComfyUI-AudioSeparator | 2025-12-22 | 2 / 1 | audio-separator (UVR5 CLI, MDX-Net + VR Architecture) | не указана |
| AIFSH/ComfyUI-UVR5 | 2024-06-20 (устарел, >2 лет) | 123 / 24 | UVR5 (vocals/фон) | Other/NOASSERTION |

### 2.2 Зависимости и риски для torch 2.14 ROCm

- **christian-byrne/audio-separation-nodes-comfyui**: requirements включают `torchaudio>=2.3.0` (без верхней границы), `librosa>=0.10.2,<1`, `numpy`, `moviepy`. Точного файла requirements.txt по прямой ссылке получить не удалось (404 при попытке raw-фетча — возможно, зависимости описаны в другом файле, например pyproject.toml); полный список не подтверждён напрямую. Открытая нижняя граница — риска пиннинга не видно.
- **set-soft/AudioSeparation**: requirements.txt = `torch`, `torchaudio`, `numpy`, `safetensors`, `tqdm`, `seconohe>=1.0.2` (обязательные, без версий) + опционально `requests`, `colorama`, `onnxruntime` (закомментированы). **Пиннинга torch/torchaudio нет вообще** — минимальный риск конфликта с ROCm-сборкой.
- **ethanfel/ComfyUI-MelBandRoFormer**: requirements.txt = `rotary-embedding-torch>=0.8.6`, `einops>=0.8`, `huggingface-hub>=0.34`, `pyloudnorm>=0.2`, `soundfile>=0.13`, `matplotlib>=3.8`, `demucs>=4.1` — тоже без верхних границ и без прямого пиннинга torch. Зависимость `demucs>=4.1` тянет свой torch/torchaudio constraint (см. 2.4).
- Библиотека **python-audio-separator (nomadkaraoke)**, на которой основан ddontsov93/ComfyUI-AudioSeparator: `pyproject.toml` задаёт `torch>=2.13,<3` (Linux/Darwin-arm64) — совместимо с torch 2.14; `onnxruntime`/`onnxruntime-gpu>=1.17` как опциональные extras (`[cpu]`, `[gpu]`, `[dml]`). Именно extra `[gpu]` тянет `onnxruntime-gpu`, который **собран под CUDA** и на ROCm не даёт ускорения (см. 2.3).

### 2.3 ROCm/AMD: что известно

- **Demucs + torch ROCm**: в issue pytorch/pytorch #111355 сообщается о **segfault** при прогоне Demucs на AMD RX 6700 XT с torch/torchaudio 2.1.0+rocm5.6 (ROCm 5.6.1) — старая связка, но показывает, что стабильность Demucs на ROCm исторически была под вопросом. Более свежих подтверждений успешного прогона на актуальном ROCm 7.x не найдено — фактическую проверку на gfx1151/ROCm 7.15 нужно делать прогоном, а не по бенчмаркам (согласно принятому в проекте правилу «verified by run»).
- **onnxruntime на ROCm/AMD, особенно gfx1151**: открытый issue ROCm/ROCm #6294 «Official Windows ONNX Runtime / ROCm support for Ryzen AI MAX+ 395 laptops (Radeon 8060S / gfx1151)» — **это именно железо пользователя**. Статус на дату issue: ONNX Runtime видит только `AzureExecutionProvider` и `CPUExecutionProvider`, `ROCMExecutionProvider` недоступен, рабочего решения нет (issue открыт, ETA не названо). Похожий issue yoyokits/Maestro-AMD #3 (16 сентября 2026, отдельный проект) сообщает segfault при попытке audio-separator 0.36.1 задействовать ROCm 7.2 + onnxruntime-gpu — код проекта неверно детектировал CUDA вместо ROCm и падал при обращении к GPU-провайдеру ONNX; проблема не решена на момент issue.
- Вывод: **готового собранного onnxruntime-gpu под ROCm/gfx1151 практически нет** — доступные onnxruntime-gpu пакеты собраны под CUDA и либо падают, либо откатываются на CPU-провайдер. Модели в формате ONNX (MDX-Net, VR Architecture из UVR5, часть моделей audio-separator) на этой машине реалистично работают **только через CPUExecutionProvider** (медленнее, но безопасно), либо не работают вовсе, если код (как в примере Maestro-AMD) плохо определяет устройство.
- Чисто **torch-модели** (Demucs, Mel-Band/BS-RoFormer в реализации ComfyUI-MelBandRoFormer — там собственная реализация roformer на PyTorch, ONNX не требуется) в принципе не зависят от onnxruntime и должны идти через обычный ROCm torch backend — но именно они и есть в упомянутом issue #111355 с историческим segfault-риском на Demucs. Проверить можно только прогоном.

### 2.4 Рекомендация

1. **Ставить первым: ethanfel/ComfyUI-MelBandRoFormer** (форк активного kijai/ComfyUI-MelRoFormer, коммит 4 дня назад). Причины: модели RoFormer — чистый torch, без ONNX-зависимости (обходит основной риск ROCm — onnxruntime-gpu); нет пиннинга torch/torchaudio в requirements; даёт лучшее качество разделения (Mel-Band/BS-RoFormer сейчас — SOTA по сравнению с htdemucs); Demucs идёт довеском через `demucs>=4.1` для тех, кому нужны его модели. Риск — Demucs-часть теоретически может упереться в тот же segfault, что в pytorch#111355 (надо проверить прогоном на месте, не по бенчмаркам).
2. Вторым кандидатом — **set-soft/AudioSeparation**: тоже без пиннинга torch, даёт больше стемов (до 6 через htdemucs_6s) и явно опционален по onnxruntime (по умолчанию не тянет его) — то есть по умолчанию не потащит CUDA-only onnxruntime-gpu, а если понадобится MDX-Net — можно доустановить `onnxruntime` (CPU-провайдер) отдельно и осознанно.
3. **christian-byrne/audio-separation-nodes-comfyui** — самый популярный (615 звёзд), но ограничен только Hybrid Demucs (4 стема), полный requirements.txt не удалось прочитать напрямую (см. 2.2) — перед установкой стоит проверить его руками.
4. Пакеты, оборачивающие MDX-Net/VR Architecture через onnxruntime-gpu (ddontsov93/ComfyUI-AudioSeparator, AIFSH/ComfyUI-UVR5, часть audio-separator) — **риск для ROCm выше всего**: onnxruntime-gpu собран под CUDA, а свежий issue в независимом проекте (Maestro-AMD) на сопоставимом стеке (ROCm 7.2 + onnxruntime GPU) даёт segfault при попытке задействовать GPU. Ставить их стоит только с осознанным ограничением на CPU-провайдер onnxruntime, либо не ставить вовсе, если нужен только Demucs/RoFormer функционал.
5. **Вариант «своя нода поверх пакета demucs (pip) на чистом torch»**: зависимости минимальны и без верхних границ — `torch>=2.1`, `torchaudio>=2.1` (для Linux, non-x86_64-Darwin), плюс `einops`, `huggingface-hub`, `julius>=0.2.3`, `lameenc>=1.2`, `pyyaml`, `safetensors`, `sphn>=0.1.12`, `tqdm` (источник: pyproject.toml github.com/adefossez/demucs). Лицензия MIT. Полностью совместимо по версии torch (2.14 > 2.1) и не тянет ONNX вообще — это самый низкорисковый по зависимостям путь, но требует написать саму ноду (загрузка модели, инференс, разбиение на чанки, склейка) самостоятельно — готовой обёртки под ROCm нет, придётся тестировать сегфолт-риск из issue #111355 на месте.

---

## Чего не удалось проверить

- Точное поведение Lego-задачи в ACE-Step 1.5 — расхождение между Musicians Guide («наслоение поверх бэк-трека») и DeepWiki («изолированная генерация по caption+track») не разрешено без чтения исходного кода pipeline.
- Реальный состав starsFriday/ComfyUI-ACEStep не проверялся.
- Работает ли ace-step/ACE-Step-ComfyUI полностью локально без внешнего inference-сервера/облака — не выяснено однозначно (похоже, нужен отдельно поднятый ACE-Step сервер).
- Точное содержимое requirements.txt/pyproject у christian-byrne/audio-separation-nodes-comfyui (прямые raw/blob запросы вернули 404 — вероятно, зависимости объявлены в другом файле или на другой ветке).
- Лицензия ComfyUI-MelBandRoFormer (форк) и её исходника kijai/ComfyUI-MelRoFormer не указана явно ни на одной странице, которую удалось получить.
- Ни один из пакетов реально не прогонялся на данной машине (gfx1151, ROCm 7.15, torch 2.14) — все выводы про ROCm/onnxruntime основаны на чужих issue (близких по железу/версиям, но не идентичных), не на собственном прогоне. Согласно правилу «verified by run» в проекте, статус этих кандидатов до прогона на месте следует считать «не проверено», а не «работает»/«не работает».
- Не проверялось, есть ли отдельно собранный `onnxruntime-rocm` пакет (например, из AMD-репозиториев или сообщества) — поиск нашёл только открытые issue о его отсутствии/нестабильности, но не исчерпывающий обзор всех существующих сборок.
