# Черновики сообщений авторам (upstream)

Не отправлено. Отправка — только по слову пользователя (какой аккаунт, какой текст). Тексты на английском,
потому что адресаты англоязычные. Проверка фактов — наши прогоны 19–20.09.2026, см. `docs/roadmap.md`
(строка «Падение сервера по памяти (OOM)») и `memory_tools.py` пака ROCm Halo.

---

## 1. ComfyUI-Lora-Manager: MetadataRegistry keeps the DynamicPrompt (and every object in it) alive for 3 prompts

Куда: https://github.com/willmiao/ComfyUI-Lora-Manager/issues

**Title:** MetadataRegistry stores the live `DynamicPrompt` object for the last 3 prompts — models referenced from
expanded-node inputs can never be freed

**Body:**

`py/metadata_collector/metadata_registry.py` stores the prompt object itself:

```python
def set_current_prompt(self, prompt):
    self.current_prompt = prompt
    ...
    self.prompt_metadata[self.current_prompt_id]["current_prompt"] = prompt
```

and keeps `max_prompt_history = 3` entries. `prompt` here is ComfyUI's `DynamicPrompt`. For workflows whose nodes
use node expansion and pass *objects* as literal inputs of the expanded nodes (e.g. ComfyUI-MiniMax-H3-LongMedia
puts a plan object holding both VAEs and a guider holding the diffusion model there), those objects live in
`DynamicPrompt.ephemeral_prompt`. As long as the registry holds the `DynamicPrompt`, the model weights stay
allocated — for up to 3 subsequent prompts, and "Unload models" / "Free model and node cache" (`POST /free`) cannot
release them because ComfyUI no longer tracks them.

Measured on ComfyUI 0.36.0, MiniMax H3 + LongMedia, after `POST /free {"unload_models": true, "free_memory": true}`:
`torch.cuda.memory_allocated()` stays at 22.5 GiB. After evicting the registry entries (running 3 trivial prompts)
and the same `/free`: 0.08 GiB. On a unified-memory machine this ends in the kernel OOM-killing the server when the
next model is loaded on top.

As far as I can see, the metadata processor only ever reads `prompt.original_prompt` (plain JSON). Suggested fix:
store just that, e.g.

```python
self.prompt_metadata[pid]["current_prompt"] = types.SimpleNamespace(original_prompt=prompt.original_prompt)
```

(we currently apply exactly this substitution from our own node pack as a workaround, and recipe/metadata
features keep working).

---

## 2. ComfyUI core: `global_progress_registry` keeps the last `DynamicPrompt` alive after execution; `/free` does not reset it

Куда: https://github.com/Comfy-Org/ComfyUI/issues

**Title:** `comfy_execution.progress.global_progress_registry` retains the last DynamicPrompt (and objects in
expanded-node inputs) after the prompt finishes; `POST /free` does not clear it

**Body:**

`reset_progress_state(prompt_id, dynprompt)` creates `ProgressRegistry(prompt_id, dynprompt)` at the start of each
execution and the module-level `global_progress_registry` keeps it until the *next* prompt starts. The registry
holds the `DynamicPrompt`, whose `ephemeral_prompt` can contain live objects when custom nodes expand into
subgraphs and pass objects as literal inputs (models, VAEs, guiders).

Consequence: after the prompt finishes, `POST /free {"unload_models": true, "free_memory": true}` runs
`unload_all_models()` and `PromptExecutor.reset()`, but the objects referenced from the last `DynamicPrompt` are
still reachable through `global_progress_registry`, so their memory is not released until another prompt is queued.

Reference chain observed with `gc.get_referrers` (ComfyUI 0.36.0):

```
MiniMaxH3VideoVAE ← comfy.sd.VAE ← dict['video_vae'] ← LongMediaPlan ← dict['long_media_plan'] ← dict['inputs']
  ← dict['9646.0.0.3'] ← comfy_execution.graph.DynamicPrompt ← comfy_execution.progress.ProgressRegistry
  ← module comfy_execution.progress ['global_progress_registry']
```

Suggested fix: when `free_memory` is processed in `prompt_worker` (or in `PromptExecutor.reset()`), also drop the
registry's prompt reference, e.g. `comfy_execution.progress.global_progress_registry = None`
(`get_progress_state()` already recreates an empty one lazily), or have the registry hold only what the progress
handlers need (node ids / display node ids) rather than the whole `DynamicPrompt`.

Note: in our case a second holder existed as well (a custom node pack storing the same `DynamicPrompt`), so this
alone did not account for all retained memory; but the core registry was the first root found for both VAEs.
