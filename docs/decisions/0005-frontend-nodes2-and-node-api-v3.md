# ADR-0005. Nodes 2.0 (Vue-рендер) — выключен в stable; свои ноды — на Node API V3

Статус: **принято** · 14.09.2026

## Контекст

В ComfyUI идут два независимых перехода:

1. **Frontend «Nodes 2.0»** — ноды рисуются Vue-компонентами вместо LiteGraph-canvas.
   В нашем ядре (frontend 1.51.10) выключен по умолчанию: `Comfy.VueNodes.Enabled=false`,
   тумблер в меню логотипа. Comfy-Org: «некоторые кастом-ноды потребуют обновления».
   По коду frontend: стандартные виджеты и `addDOMWidget` работают; чужие canvas-виджеты
   заворачиваются в `WidgetLegacy` (мини-canvas, ограниченная интерактивность);
   `onDrawForeground`/`onDrawBackground` **ноды** не вызываются; патчи `LGraphCanvas.prototype`
   работают частично (связи и группы остаются на canvas, меню переведены на хуки).
2. **Node API V3** (Python): `io.ComfyNode` со схемой вместо `INPUT_TYPES`. В ядре 0.35.1 —
   502 ноды V3 против 73 V1; V1 продолжает работать, принудительной миграции нет.

Скан 42 пакетов старой сборки (435 тыс. строк их JS): 17 без JS, 4 LOW, 7 MEDIUM (DOM-виджеты),
**14 HIGH** — canvas-хуки и патчи прототипов: rgthree, custom-scripts (pysssss), easy-use,
kjnodes, impact-pack, videohelpersuite, crt-nodes, mxtoolkit, Pixaroma, vrgamedevgirl,
minimax-h3-studio, mickmumpitz, layerstyle, agent-panel. Форк-кандидаты пользователя:
Comfyroll, LLM-text-processor, Minimax-апскейлер — без JS; plaguekind — MEDIUM; kjnodes — HIGH.

## Решение

- **Nodes 2.0 в stable-модпаке выключен явно** (настройка в `user/`), пока rgthree, pysssss,
  easy-use, kjnodes и impact-pack не объявят поддержку. Пробуем на candidate, руками,
  на эталонных воркфлоу.
- **При каждом обновлении ядра** проверяем умолчание `Comfy.VueNodes.Enabled` в приехавшем
  frontend (grep по бандлу) — попадёт в `tools/comfy smoke`.
- **HIGH-пакеты не адаптируем сами**: это чужой UI на десятки тысяч строк, авторы сделают
  раньше и лучше. kjnodes берём из git upstream + патч P5, а не копию папки.
- **Свои новые ноды (`ND_*`) — только V3** (`io.ComfyNode`, `ComfyExtension`, `comfy_entrypoint`)
  и без canvas-JS: только стандартные типы виджетов или `addDOMWidget`. Тогда они совместимы
  с Nodes 2.0 по построению.
- **Форки чужих нод на V3 не переписываем**: патч остаётся в 1–2 файла, иначе rebase на
  upstream невозможен. Нужно другое поведение/входы — не форк, а своя `ND_`-нода на V3 рядом.

## Последствия

- Nodes 2.0 включится у нас позже, чем у Comfy-Org, — осознанно.
- В `modpack.yaml` появляется блок настроек frontend (этап 3).
- В `tests/smoke` — проверка умолчания Vue-режима после обновления ядра (этап 3).
