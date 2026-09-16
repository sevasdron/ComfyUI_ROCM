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
- `MiniMaxH3MemoryEfficientSageAttentionPatch` — кандидат на замену `Model Attention Backend` с backend
  `comfy kitchen attention` (INT8-аттеншен, на синтетике cos 0.99988 к fp32). Если на прогоне не пойдёт — прежний
  Bypass остаётся рабочим вариантом.
- Из `Mickmumpitz` нужны только `AudioExists` / `ImageExists`; `ultralytics` (YOLO-детектор) исключён из pip — импорт там
  ленивый. В `LayerStyle` нужна одна `ImageScaleByAspectRatio V2`; `opencv-contrib-python` исключён, `guidedFilter`
  у пакета под try/except.
