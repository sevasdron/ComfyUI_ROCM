# ADR-0004. Runtime: стабильная Fedora 44, герметичная установка из wheelhouse, без `chmod -R /opt`

Статус: **принято** · 14.09.2026

## Контекст

Образ kyuz0 собран на `fedora:45` в статусе «Container Image Prerelease» (системный Python 3.15.0rc1,
gcc 16). Нам нужен свой runtime по его рецепту, но воспроизводимый: тот же `Containerfile` через
полгода должен давать тот же результат.

Проверено 14.09.2026:

- Fedora 45 ещё не выпущена, её репозитории меняются ежедневно. Fedora 44 — стабильная,
  поддерживается до ~мая 2027, совпадает с хостом.
- Нужные пакеты одинаковы в обеих: `python3.13` (3.13.15 в F44 / 3.13.14 в F45), `ffmpeg-free` 8.1.2.
- Колёса torch/ROCm — manylinux, от версии Fedora не зависят.
- Линейка `rocm7.15` на индексе `rocm.nightlies.amd.com/whl-multi-arch` **закончилась 28.07.2026**,
  дальше публикуются только `rocm10.0`/`rocm10.1`. Наши версии (torch `2.14.0a0+rocm7.15.0a20260721`
  и т.д.) пока лежат, но гарантий нет.
- Из 16.2 ГБ образа kyuz0 7.34 ГБ — слой `chmod -R a+rwX /opt`, полный дубликат venv (6.9 ГБ).
- `TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1` и `TORCH_BLAS_PREFER_HIPBLASLT=1` у kyuz0 заданы только
  в `/etc/profile.d` — вне login-shell (обычный `podman run`) они не действуют.

## Решение

1. **База — `registry.fedoraproject.org/fedora:44`**, Python из пакета `python3.13`.
   Задаётся `BASE_IMAGE` в `runtime/versions.env`.
2. **Колёса ставятся только из `var/wheelhouse`** (`pip install --no-index --find-links`).
   `tools/wheelhouse-sync` скачивает стек по `versions.env` (с зависимостями, sdist собираются
   в колёса), `tools/runtime-build` монтирует папку в сборку через `podman build -v`.
   Сборка образа не ходит в сеть за Python-пакетами.
3. **`chmod -R` нет.** venv принадлежит root, всем — чтение. Верхние слои ставят пакеты при сборке;
   в рантайме venv не пишется (ноды и их зависимости — через модпак, ADR-0002).
4. **`/opt/constraints.txt` + `ENV PIP_CONSTRAINT`/`UV_CONSTRAINT`** генерируются в образе из
   установленного стека. Любой `pip install` в верхних слоях и внутри контейнера не может подменить
   torch/ROCm (P11). Копия — `runtime/constraints.txt` в репозитории, для чтения без запуска образа.
5. Переменные ROCm — `ENV` образа, а не `profile.d`.
6. Шрифты — пакеты Fedora (Noto, DejaVu, Liberation, Adwaita — те же семейства, что в
   `~/comfy/fonts`), плюс `/usr/share/fonts/truetype/` как папка ссылок на все `.ttf` (P1:
   Comfyroll читает её плоско через `os.listdir`).

## Рассмотренные варианты

| Вариант | Почему нет |
|---|---|
| `fedora:45` как у kyuz0 | prerelease: пересборка через месяц даёт другой набор пакетов; выигрыша нет |
| Python 3.14 (системный в F44, колёса cp314 на индексе есть) | экосистема колёс нод отстаёт; задача — повторить проверенный стек 3.13 |
| Установка torch прямо с индекса AMD при сборке (как kyuz0) | линейка 7.15 уже снята с публикации новых сборок; старые могут исчезнуть — сборка станет невозможной |
| `fedora-minimal` | экономия ~100 МБ, но `microdnf` и отсутствие части утилит усложняют отладку; не стоит того при venv 6.9 ГБ |

## Последствия

- Ожидаемый размер runtime ~8 ГБ против 16.2 ГБ у kyuz0.
- Обновление стека torch/ROCm = правка `versions.env` → `wheelhouse-sync` → `runtime-build`;
  следующий шаг — переход на `rocm10.x`, это отдельный этап с полной проверкой воркфлоу.
- `var/wheelhouse` (~6 ГБ на версию) надо хранить: без него runtime не пересобрать.
- Контейнеры запускаются без `privileged`: `--device /dev/kfd --device /dev/dri --group-add keep-groups`.
