# Бизнес Башкортостан · индекс проекта

Компактная карта репозитория. Сгенерировано `python3 tools/context_pack.py index --write`.
Исполнитель читает этот файл первым, затем только документы и файлы своей задачи.

## Документы

| Ключ | Файл | О чём |
|---|---|---|
| gdd.vision | `docs/gdd/01_vision.md` | зачем проект, для кого, платформы |
| gdd.features | `docs/gdd/02_features.md` | функции и приоритеты |
| gdd.architecture | `docs/gdd/03_architecture.md` | модули, зоны файлов, данные |
| gdd.ui | `docs/gdd/04_ui.md` | экраны, адаптивность, доступность |
| gdd.quality | `docs/gdd/05_quality.md` | нефункциональные требования, тесты, безопасность |
| gdd.release | `docs/gdd/06_release.md` | сборка, публикация, откат |
| gdd.decisions | `docs/gdd/DECISIONS_APPROVED.md` | решения владельца |

## Модули

| Модуль | Каталоги | Документы | Контракты | Тесты | Зависит от |
|---|---|---|---|---|---|
| core | `project.godot`, `scenes/**`, `.github/workflows/**` | gdd.architecture | `docs/contracts/core.md` | `tests/core/**` | — |
| gameplay | `scripts/gameplay/**`, `scenes/gameplay/**` | gdd.features | `docs/contracts/gameplay.md` | `tests/gameplay/**` | core |
| ui | `scenes/ui/**`, `scripts/ui/**` | gdd.ui | `docs/contracts/ui.md` | `tests/ui/**` | core |
| release | `.github/workflows/release.yml`, `export_presets.cfg` | gdd.release | `docs/contracts/release.md` | `tests/release/**` | core |

## Критические правила
- Релиз публикуется только из релизного workflow (канал release, подпись, SHA256SUMS).
