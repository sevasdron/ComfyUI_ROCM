#!/usr/bin/env python3
"""Импорт ядра ComfyUI при сборке — без GPU и без сервера, ловит сломанные
зависимости ещё в build, до `podman run`.

GPU при сборке недоступен (у `podman build`, в отличие от `podman run`, нет
устройств из --device), а comfy.model_management на уровне модуля обращается
к torch.cuda, если не попросить CPU явно. main.py делает это через
comfy.options.enable_args_parsing() + разбор --cpu/--gpu-only из sys.argv;
здесь реального запуска main.py нет, так что повторяем то же самое вручную.
"""
import sys

import comfy.options

comfy.options.enable_args_parsing()
sys.argv = ["main.py", "--cpu"]

import comfy.model_management  # noqa: E402
import comfyui_manager  # noqa: E402
import nodes  # noqa: E402

print("core import ok")
