# Воркфлоу модпака `main`

Порядок подключения ([ADR-0006](../decisions/0006-modpack-main-starts-empty.md)): воркфлоу → `tools/comfy workflow deps` →
`node add` недостающих пакетов (+ `node patch`, если нужна правка) → `build main` → `promote` → прогон.

`workflow deps` заодно печатает замены из [node-policy.yaml](../../modpacks/main/node-policy.yaml): что на gfx1151 не работает,
чем это заменить нодой ядра и где нужна наша нода из пака ROCm Halo. Правило: если функцию можно получить нодой ядра или
обойти — ставим замену и лишний пакет не тащим ([rocm-accelerators.md](../rocm-accelerators.md)).
У каждой записи политики есть поле `verified`: `run` — подтверждено настоящим прогоном, `bench` — только синтетикой,
`docs` — только по документации. Всё, что не `run`, проверяем на первом же прогоне и обновляем.

Раскладка в `~/ComfyUI/main/user/default/workflows/`: категория автора, внутри — папка автора
(`Image/ND/`, `Video/ND/`, `Audio/ND/`…), свои воркфлоу — в корне категории.
Исходники воркфлоу ND (не правленные) — `/run/media/ai/ComfyUI/ComfyUI_Influencer_Build_v4.7/ComfyUI/user/default/workflows/`.

| Воркфлоу | Источник | Пакеты нод | Статус |
|---|---|---|---|
| `3d_pixal3d_trellis2_image_to_model` | шаблон ComfyUI | ядро + ROCm Halo (`#94` RH Trellis2 Upsample Stage, `#324` RH Cast to float32) | работает (res 32/64) |
| `Image/ND/ND_Krea2_Ultimate_TI2I_v1.4` | ND, Influencer Build v4.7 | basic_data_handling, Easy-Use, Impact-Pack, Inpaint-CropAndStitch, KJNodes, krea2edit, LLM-text-processor (P3), mxToolkit, Comfyroll, rgthree | 15.09: образ `v0.35.1-66685a5` в stable, все 58 типов нод есть; прогон — ждёт выбора CLIP |
| `Video/ND/ND_MiniMax_H3_Ultimate_2-Stages_v3.0_WIP_1` | ND, Influencer Build v4.7 | + AudioBatch, Mickmumpitz, Spectrum-MiniMax-H3, LayerStyle, Fantastic-MiniMaxH3-PromptBuilder, SolAttn_triton, Minimax_h3_latent_Upscaler (P4) | 16.09: ноды добавлены, файл воркфлоу — с внешнего диска, когда примонтирован |
| `ND_YuE2_T2M_…` | ND | — | очередь |
| `Video/ND/ND_MiniMax_H3_Ultimate_2-Stages_v2.0` | ND | + `ComfyUI-MiniMax-H3-LongMedia` | 16.09: готовый воркфлоу автора на LongMedia, всё остальное уже есть; ждёт перезапуска и прогона |
| `Video/ND/ND_MiniMax_H3_Ultimate_VVJ_v2.1_RH` | ND, правленый | + LongMedia | 16.09: Sage-патч заменён нодой ядра, `Sigmas Split` → `SplitSigmas`; недостающих нод нет, ждёт прогона (оригинал рядом, удалить после тестов) |

Заметки:
- Krea2 v1.4 из Influencer Build цел: LoRA-нода `#170 Krea 2 Loras` подключена. Обрыв связей из CHANGES.md §10 был
  только в копии `~/comfy/user/default/workflows/ND/Image/`.
- Impact-Pack нужен ради одной `ImpactStringSelector`; `sam2` исключён из pip (`modpack.yaml`).
- Krea2 v1.4 собран автором на Windows: пути моделей через `\` (`Krea2\krea2_turbo_mxfp8.safetensors`) — на Linux
  фронтенд их не сопоставит, в `Model Selector` #164 и #8662 выбрать тот же файл заново. CLIP #162
  `qwen3vl_4b_fp8_scaled.safetensors` в `/models` нет; из Krea2 есть `Krea2/qwen3VLInstruct4bHeretic_v10.safetensors`.
- `workflow deps` на Krea2: сдвигов виджетов у добавленных пакетов нет; предупреждения только у нод ядра,
  сохранённых старыми версиями (`ImageCropV2` 0.18.1, `ResolutionSelector` 0.25.0) — фронтенд мигрирует их сам.

## MiniMax H3 2-Stages v3.0 WIP

- Пути моделей снова в виде Windows (`MiniMax\\minimax_h3_video_vae_fp16.safetensors`): перевыбрать в `MiniMax H3 Model Loader`
  (#138 CLIP, #139/#140 VAE, #9121 diffusion) и в `Turbo Lora` (#9348, #9551). Все пять файлов в `/models` есть.
- `SolAttnPatch` — кандидат на замену нодой ядра `Block Sparse Attention` (method `sol-attn`): на синтетике она идёт
  через HIP-ядра comfy-kitchen и даёт 2.0x на 8k токенов и 4.1x на 32k против SDPA. Проверить на прогоне (качество при
  `tau` 1.0–1.5). Пакет `ComfyUI-SolAttn_triton` убирать только после удачного прогона:
  `bash tools/comfy node rm main ComfyUI-SolAttn_triton`.
- В подграфе `MiniMax H3 Model Loader` (нода `#9425`) бэкенд выбирается виджетом `choice`:
  `comfy_kitchen_attention` / `sage_attention` / `none`. Внутри уже стоит нода ядра `Model Attention Backend`
  с выбранным `comfy kitchen attention`, на неё ведёт ветка `comfy_kitchen_attention`. Соседний `switch`
  включает ветку с `SolAttnPatch` — держим `False`.
- `MiniMaxH3MemoryEfficientSageAttentionPatch` `#9825` стоит **вне** этого выбора (после переключателя, перед
  `MiniMaxChunkFeedForward`) и срабатывает при любом значении `choice`: на прогоне 16.09 она уронила воркфлоу
  (`sageattention is not new enough version…`). Ставить ей Bypass.
- Обе развилки ленивые, невыбранная ветка не исполняется: `If/Else Switch` ядра (`#9752`) объявляет `on_true`/`on_false`
  lazy и реализует `check_lazy_status`, `SwitchCase` из basic_data_handling — так же по `select`. Отсюда два следствия:
  `SolAttnPatch` `#9751` при `switch = False` не вызывается, а при `choice = none` не вызывается и сама
  `Model Attention Backend`, то есть INT8-бэкенд остаётся выключенным.
- `MiniMaxH3MemoryEfficientSageAttentionPatch` — кандидат на замену `Model Attention Backend` с backend
  `comfy kitchen attention` (INT8-аттеншен, на синтетике cos 0.99988 к fp32). Если на прогоне не пойдёт — прежний
  Bypass остаётся рабочим вариантом.
- Из `Mickmumpitz` нужны только `AudioExists` / `ImageExists`; `ultralytics` (YOLO-детектор) исключён из pip — импорт там
  ленивый. В `LayerStyle` нужна одна `ImageScaleByAspectRatio V2`; `opencv-contrib-python` исключён, `guidedFilter`
  у пакета под try/except.

## Длинные видео: MiniMax H3 LongMedia

У автора ND уже есть два готовых воркфлоу на этом пакете, оба на MiniMax H3 (на LTX 2.5 таких нет):
`ND_MiniMax_H3_Ultimate_2-Stages_v2.0` (10 нод LongMedia: Setup, два Sampler, Decode, PackAV/SplitAV, VRAMCacheCleanup)
и `ND_MiniMax_H3_Ultimate_VVJ_v2.1` (7 нод). Первому, кроме самого LongMedia, ничего не нужно — остальные пакеты
у нас стоят. Второму нужна ещё `Sigmas Split` из RES4LYF, вместо которой берём `SplitSigmas` ядра
(тащить пакет сэмплеров ради одной ноды не будем). `Fast Bypasser (rgthree)` — фронтендовая нода, она в схеме
не появляется и пакета не требует; такие типы перечислены в `frontend_only` политики.


Пакет `vizart-vj/ComfyUI-MiniMax-H3-LongMedia` (реестр: `minimax-h3-longmedia`) добавлен 16.09 как кандидат под
задачу «длинный ролик из цепочки коротких»: планирование клипов, непрерывность между сегментами, липсинк,
режимы под нехватку памяти. Конфликтов имён классов с установленными пакетами нет, своих pip-зависимостей нет.

Что учесть на ROCm: собственные ядра пакета (`sol_kernel/sm120.py`, `fusions_sm120.py`) включаются только при
compute capability `(12, 0)` — это NVIDIA Blackwell, у нас условие не выполняется и пакет идёт обычным путём.
Ускорение на нашей машине даёт не он, а `Model Attention Backend` = `comfy kitchen attention` (см.
[rocm-accelerators.md](../rocm-accelerators.md)).

Родственное, что уже установлено и решает ту же задачу другими средствами: набор Mickmumpitz (`FrameContextFit`,
`AnchorFrameExtractor`, `EndFrameInjector`, `IterationSwitch`, `ControlCrossfadeIterationFix`, `VideoConcatenate`),
циклы Easy-Use (`For Loop Start/End`, `While Loop Start/End`), `TensorLoopOpen/Close` и `ImageBatchExtendWithOverlap`
из KJNodes, контекстные окна ядра (`Context Windows (Manual)`, `Wan Context Windows`, `LTXV Context Windows`)
и `Add Guide for MiniMax H3` для якорей персонажей.

## Правка воркфлоу файлом: грабли с идентификаторами

Ноды, добавленные скриптом в JSON, исчезли после того, как воркфлоу открыли и сохранили в интерфейсе.
Причина — неуникальные `id`: у подграфов и корня общее пространство идентификаторов, а взятый «свободным»
номер уже занимала нода корня. Правило: новый id берём как `max(все id корня и всех подграфов,
last_node_id) + 1`, новые связи — так же от `last_link_id`, и в конце обновляем `last_node_id`/`last_link_id`.

Проверять правку нужно не только `workflow deps`, но и загрузкой в самом ComfyUI: открыть страницу,
`app.loadGraphData(...)`, затем `app.graph.serialize()` и убедиться, что добавленные ноды и входы подграфа
на месте (это и есть эмуляция «открыл и сохранил»).

## Пустой промпт при reasoning=on

`LLMTextProcessor` при `reasoning = on` ждёт от модели закрытый блок размышлений. Если модель его не закрыла
(упёрлась в `max_tokens` или `timeout_seconds`), нода отдаёт **пустой** `RESPONSE`, а весь текст уходит в
неподключённый выход `REASONING` (`llama_cli.py`: `if END_THINKING not in thinking_text: return "", ...`).
Внешне это выглядит как пустой предпросмотр промпта `#9429` и «видео не по теме»: дальше по цепочке уходит
пустая строка.

Что сделано в копии `_RH`: на ноду `#9430` выведены `ctx_size` (шаг 512) и `max_tokens`, чтобы лимиты
крутились на месте. Нода пака `RH Text Fallback` (ошибка с подсказкой или подстановка исходного текста)
написана, но в подграф пока не встроена: вставленная файлом, она теряет часть входов при загрузке в интерфейс —
вставлять её нужно средствами самого редактора.

Быстрый обход, пока страховки нет: `reasoning = off`, либо `max_tokens` с запасом (8192+) и `ctx_size` больше.

## h3_mode выбирается автоматически

Ошибка `h3_mode='hybrid' requires image_1 as the opening keyframe` возникает, когда в медиа-загрузчике `#173`
пусто, а на ноде `#184` стоит режим, которому нужен первый кадр. В копии `_RH` режим больше не задаётся руками:
`RH H3 Mode` (`#9667`, наш пак) получает `picture_1`, `picture_2` и `video_1` со сплиттера `#174` и отдаёт имя
режима, `CR String To Combo` (`#9668`) превращает строку в значение списка, оно уходит во вход `h3_mode` ноды `#184`.

Правило ноды: видео → `video_ref_edit`, одна картинка → `fl2va`, две и больше → `ref2va`, пусто → `t2va`.
`hybrid` автоматически не выбирается никогда (он требует первый кадр) — только через `override` на самой ноде.
Виджет `h3_mode` у Setup остаётся как запасной на случай, если связь снимут.

## Ночные прогоны 16–17.09: LongMedia подтверждена

Пять прогонов воркфлоу `VVJ_v2.1_RH`, все без ошибок. Времена восстановлены из `~/ComfyUI/main/user/comfyui_8100.log`
(файловый лог переживает выключение питания, логи контейнера — нет).

Нумерация: «прогон N» — как их считает автор; «задание» — номер в очереди ComfyUI (они шли как 3…7).

| Прогон | Задание | Память | Refiner | Референс | Размышления | Время | Качество (оценка автора) |
|---|---|---|---|---|---|---|---|
| 1 | 3 | normal | нет | нет | выкл | 31:22 | норм |
| 2 | 4 | auto | нет | нет | выкл | 31:31 | норм |
| 3 | 5 | normal | **да** | нет | выкл | **45:53** | чуть рябит, немного дёрганый |
| 4 | 6 | normal | нет | **да** (`fl2va` в логе) | выкл | 32:16 | немного дёрганый |
| 5 | 7 | normal | нет | нет (`t2va` в логе) | вкл по описанию | 31:21 | сильно рябит при движении |

**Вывод по LongMedia: работает.** Ролики выходят заданной длины (15 с), склеек между сегментами не видно,
цвет ровный, вспышек и скачков яркости нет — то есть `timeline_mode = segmented` с переходом в 22 кадра
держит непрерывность. Это ответ на вопрос «что даёт LongMedia, если длина и так доступна»: она даёт
длину БЕЗ швов, а не просто длину.

Цена Refiner Pass: +14.5 минуты к прогону (45:53 против 31:22 у той же конфигурации без него).

Память за ночь (`bash tools/runstat var/logs/memsample-night-5runs.log`): пик GTT 65.5 ГиБ, пик ОЗУ 77 ГиБ,
carve-out VRAM снова не используется. GPU занят в среднем 36% за всё окно наблюдения — простои между прогонами
и внутри них (LLM-усилитель идёт на CPU).

**Открыто: рябь при движении.** Склейки и цвет ни при чём, подбираем параметры генерации — план в разделе ниже.

## Длительность и сегменты в LongMedia

На ноде `#184` (свёрнута и закреплена) за длину отвечают три параметра, и до правки они были связаны так,
что длинного ролика не получалось:

| Параметр | Что значит | Было | Стало |
|---|---|---|---|
| `timeline_mode` | `single` — один проход H3; `segmented` — цепочка клипов; `multiclip` — по плану клипов | `single` | `segmented` |
| `manual_duration` | общая длина таймлайна (учитывается при `duration_source = manual`) | ползунок `#9438`, потолок 15 с | тот же ползунок, потолок 120 с |
| `segment_seconds` | длина одного сегмента; `transition_frames` добавляется как контекст и её не уменьшает | тот же ползунок `#9438` | отдельный ползунок `#9666` «Segment | Seconds», 1–60 с |

То есть один ползунок «Duration | Seconds» раньше задавал разом и общую длину, и длину сегмента, а режим
`single` всё равно делал один проход — отсюда ощущение, что LongMedia ничего не добавляет.

Полезное рядом: `duration_source` (`auto`, `manual`, `audio`, `video`, `longest_input`) умеет брать длину
из звуковой дорожки или самого длинного входа — это ответ на «не хочу задавать длительность руками».

## VVJ v2.1: что поправлено в копии `_RH`

- В подграфе `MiniMax H3 Model Loader` Sage-патч `#9433` стоял жёстко между загрузчиком и списком моделей,
  без переключателя. Заменён на ноду ядра `Model Attention Backend` (`#9434`) с backend `comfy kitchen attention`.
- `Sigmas Split` из RES4LYF `#9638` заменена на `SplitSigmas` ядра: то же расписание на входе, тот же INT на `step`,
  выход `low_sigmas` уходит в `MiniMaxH3LatentLabLongMediaSampler`. Пакет RES4LYF не нужен.
- Режимы памяти в подграфе `VRAM Mode` (`#9648`): `auto`, `normal`, `low_vram`, `ultra_low_vram` — это `memory_mode`
  сэмплеров LongMedia, чистая политика резидентности весов, от NVIDIA не зависит и работает целиком. На нашей машине
  `auto` смотрит на отношение размера модели к «видеопамяти», а ComfyUI видит 126 ГиБ единой памяти, поэтому выберет
  `normal`; `low_vram` и `ultra_low_vram` проверять отдельно (в прогоне 16.09 пик ОЗУ был 91 ГиБ из 96).
- Выпадающий список `sage_attention` у `DiffusionModelLoaderKJ` (вход `#9425`) пробовать нельзя ни в одном варианте,
  включая `..._triton`: все они требуют пакет `sageattention`, которого в образе нет (`ModuleNotFoundError`).
  Оставлять `disabled`.
- Бэкенд аттеншена выведен наружу тумблером: на ноде `#9425` вход `comfy_kitchen_attention` (BOOLEAN, по умолчанию
  включён), внутри подграфа ленивый `If/Else Switch` выбирает между `Model Attention Backend` и моделью как есть.
  Прежний список `sage_attention` с лицевой стороны убран (он ведёт в загрузчик KJNodes и на ROCm бесполезен).
- В VVJ у автора более ранняя ревизия подграфа `ND Advanced Prompt`: наружу не выведены ни `reasoning`, ни
  `memory_mode`, хотя у самой `LLMTextProcessor` эти входы есть (`reasoning`: auto / on / off). Режим размышления
  выведен на ноду `#9430` отдельным входом; `memory_mode` при необходимости выводится так же.
- `MiniMaxH3LatentLabLongMediaSetup` в режиме `h3_mode = hybrid` требует `image_1` (опорный первый кадр).
  Режимы: `t2va` (только текст), `fl2va` (первый и необязательный последний кадр), `ref2va` (референсы),
  `hybrid`, `video_ref_edit`.
- Авторская висящая связь в подграфе `ND Advanced Prompt` (link 15206 на несуществующую ноду 5750) есть и в оригинале,
  правкой не тронута.

## План борьбы с рябью (по одному параметру за прогон)

Порядок от самого вероятного к дорогому; база — конфигурация прогона 1 (normal, без Refiner, без референса, 31:22).

| Шаг | Что меняем | Где | Ожидаемая цена |
|---|---|---|---|
| 1 | шагов сэмплинга 10 → 16 | ползунок `Main | Steps` `#9526` (6–25) | +60% времени, ~50 мин |
| 2 | планировщик `sgm_uniform` → другой, либо сэмплер `er_sde` → детерминированный | подграф `Sampler Selector` `#9522` | нейтрально |
| 3 | сдвиг сигм | `MiniMaxH3SigmaShift` `#47` | нейтрально |
| 4 | INT8-аттеншен выключить (тумблер `comfy_kitchen_attention` на `#9425`) | проверяет, не наша ли оптимизация даёт шум | дорого: без INT8 шаг был в 5.25 раза медленнее |

Шаг 4 делаем последним: он проверяет наше собственное изменение, но стоит нескольких часов прогона.
