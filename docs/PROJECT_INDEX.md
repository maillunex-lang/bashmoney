# Мед и Нефть · индекс проекта

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
| gdd.economy | `docs/gdd/07_economy.md` | расчёт, спрос, производство и деньги |
| gdd.world | `docs/gdd/08_world.md` | города и изометрическая карта |

## Модули

| Модуль | Каталоги | Документы | Контракты | Тесты | Зависит от |
|---|---|---|---|---|---|
| design | `docs/**` | gdd.vision, gdd.features, gdd.architecture | `docs/contracts/design.md` | — | — |
| catalog | `server/catalog/**`, `tests/catalog/**` | gdd.features, gdd.architecture | `docs/contracts/catalog.md` | `tests/catalog/**` | — |
| economy | `server/economy/**`, `tests/economy/**` | gdd.features, gdd.architecture | `docs/contracts/economy.md` | `tests/economy/**` | catalog |
| market | `server/market/**`, `tests/market/**` | gdd.features | `docs/contracts/market.md` | `tests/market/**` | catalog |
| companies | `server/companies/**`, `tests/companies/**` | gdd.features, gdd.architecture | `docs/contracts/companies.md` | `tests/companies/**` | — |
| server | `server/api/**`, `tests/api/**` | gdd.architecture | `docs/contracts/server.md` | `tests/api/**` | economy, market, companies |
| logistics | `server/logistics/**`, `tests/logistics/**` | gdd.features | `docs/contracts/logistics.md` | `tests/logistics/**` | catalog, companies |
| world | `server/world/**`, `tests/world/**` | gdd.features | `docs/contracts/world.md` | `tests/world/**` | — |
| client_core | `client/project.godot`, `client/core/**`, `tests/client_core/**` | gdd.ui | `docs/contracts/client_core.md` | `tests/client_core/**` | — |
| client_map | `client/map/**`, `tests/client_map/**` | gdd.ui | `docs/contracts/client_map.md` | `tests/client_map/**` | client_core, world |
| client_ui | `client/ui/**`, `tests/client_ui/**` | gdd.ui | `docs/contracts/client_ui.md` | `tests/client_ui/**` | client_core, server |
| integration | `tests/integration/**`, `tools/scenarios/**` | gdd.features | `docs/contracts/integration.md` | `tests/integration/**` | server, logistics, world, client_map, client_ui |
| release | `release/**`, `tests/release/**`, `client/export_presets.cfg` | gdd.release, gdd.quality | `docs/contracts/release.md` | `tests/release/**` | integration |
| research | `server/research/**`, `tests/research/**` | gdd.features | `docs/contracts/research.md` | `tests/research/**` | economy, companies |
| social | `server/social/**`, `tests/social/**` | gdd.features | `docs/contracts/social.md` | `tests/social/**` | server, companies |

## Критические правила
- Общие файлы GDD, docs/work_plan.json и индекс изменяет только директор.
- Выполнено только после зелёного CI и слияния PR.
- Никаких изменений чужих VPS-сервисов, деплой только по разрешению владельца.

## Устаревшие ссылки
- Модуль design: contracts docs/contracts/design.md не существует
- Модуль catalog: paths server/catalog/** не существует
- Модуль catalog: paths tests/catalog/** не существует
- Модуль catalog: contracts docs/contracts/catalog.md не существует
- Модуль catalog: tests tests/catalog/** не существует
- Модуль economy: paths server/economy/** не существует
- Модуль economy: paths tests/economy/** не существует
- Модуль economy: contracts docs/contracts/economy.md не существует
- Модуль economy: tests tests/economy/** не существует
- Модуль market: paths server/market/** не существует
- Модуль market: paths tests/market/** не существует
- Модуль market: contracts docs/contracts/market.md не существует
- Модуль market: tests tests/market/** не существует
- Модуль companies: paths server/companies/** не существует
- Модуль companies: paths tests/companies/** не существует
- Модуль companies: contracts docs/contracts/companies.md не существует
- Модуль companies: tests tests/companies/** не существует
- Модуль server: paths server/api/** не существует
- Модуль server: paths tests/api/** не существует
- Модуль server: contracts docs/contracts/server.md не существует
- Модуль server: tests tests/api/** не существует
- Модуль logistics: paths server/logistics/** не существует
- Модуль logistics: paths tests/logistics/** не существует
- Модуль logistics: contracts docs/contracts/logistics.md не существует
- Модуль logistics: tests tests/logistics/** не существует
- Модуль world: paths server/world/** не существует
- Модуль world: paths tests/world/** не существует
- Модуль world: contracts docs/contracts/world.md не существует
- Модуль world: tests tests/world/** не существует
- Модуль client_core: paths client/project.godot не существует
- Модуль client_core: paths client/core/** не существует
- Модуль client_core: paths tests/client_core/** не существует
- Модуль client_core: contracts docs/contracts/client_core.md не существует
- Модуль client_core: tests tests/client_core/** не существует
- Модуль client_map: paths client/map/** не существует
- Модуль client_map: paths tests/client_map/** не существует
- Модуль client_map: contracts docs/contracts/client_map.md не существует
- Модуль client_map: tests tests/client_map/** не существует
- Модуль client_ui: paths client/ui/** не существует
- Модуль client_ui: paths tests/client_ui/** не существует
- Модуль client_ui: contracts docs/contracts/client_ui.md не существует
- Модуль client_ui: tests tests/client_ui/** не существует
- Модуль integration: paths tests/integration/** не существует
- Модуль integration: paths tools/scenarios/** не существует
- Модуль integration: contracts docs/contracts/integration.md не существует
- Модуль integration: tests tests/integration/** не существует
- Модуль release: paths release/** не существует
- Модуль release: paths tests/release/** не существует
- Модуль release: paths client/export_presets.cfg не существует
- Модуль release: contracts docs/contracts/release.md не существует
- Модуль release: tests tests/release/** не существует
- Модуль research: paths server/research/** не существует
- Модуль research: paths tests/research/** не существует
- Модуль research: contracts docs/contracts/research.md не существует
- Модуль research: tests tests/research/** не существует
- Модуль social: paths server/social/** не существует
- Модуль social: paths tests/social/** не существует
- Модуль social: contracts docs/contracts/social.md не существует
- Модуль social: tests tests/social/** не существует
