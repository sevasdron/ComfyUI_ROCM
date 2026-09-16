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
| `Video/ND/ND_MiniMax_H3_Ultimate_VVJ_v2.1` | ND | + LongMedia, `Sigmas Split` заменить на `SplitSigmas` ядра | 16.09: скопирован, требует одной замены ноды |

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
