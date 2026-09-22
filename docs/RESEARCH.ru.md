# Почему выбран ArtifactSpan

Дата исследования: 21 сентября 2026. Допущения: один разработчик, небольшой бюджет, без собственной подтверждённой аудитории. Это продолжение исследования из предыдущих проектов; условия программ поддержки и публичный профиль разобраны в общем отчёте. Новый репозиторий сам по себе не доказывает соответствие программам.

**Вывод:** реализован небольшой офлайн-анализатор имён и порядка передачи артефактов в GitHub Actions. Публичные примеры подтверждают класс ошибок. Спрос именно на отдельный CLI ещё требует проверки. Утверждение «такого нигде нет» не доказано: найден конкретный пробел в проверенных инструментах, а не абсолютная уникальность.

## Что отсеяно до реализации

| Направление | Что уже существует | Решение |
|---|---|---|
| Проверка потерянных optional dependencies в npm lockfile | [optional-deps-validate](https://www.npmjs.com/package/@starcart.com/optional-deps-validate), [npm-check](https://www.npmjs.com/package/@dependably/npm-check) | Прямой сценарий уже занят |
| Происхождение переменных окружения Compose/CI | [envorigin](https://docs.rs/envorigin/latest/envorigin/index.html) описывает аудит и граф происхождения | Не делать ещё один общий env-аудитор |
| Покрытие Docker volumes резервным копированием | [arkeep](https://github.com/arkeep-io/arkeep), [kopi-docka](https://github.com/TZERO78/kopi-docka) | Активная категория; часть coverage-функций — roadmap, это не доказательство готовности, но отдельный пробел не подтверждён |
| Битые ссылки Obsidian, включая canvas | [obsidian_phantom_files](https://github.com/vorkampfer/obsidian_phantom_files) | Уже есть прямой инструмент |
| Ссылки в Jupyter notebooks | [markdown-checker](https://github.com/john0isaac/markdown-checker) поддерживает md/ipynb | Польза отдельного дубликата не доказана |
| Проверка min/max статистики Parquet | [CheckParquet251Command](https://github.com/apache/parquet-java/blob/master/parquet-cli/src/main/java/org/apache/parquet/cli/commands/CheckParquet251Command.java) проверяет известный класс повреждений | Предпочесть развитие существующих валидаторов |
| Сравнение OCI images | [diffoci](https://github.com/reproducible-containers/diffoci), [tare](https://github.com/DataDog/tare) | Не удалось обосновать достаточно отдельный сценарий |
| Структурное сравнение ICS | [ICS Compare](https://filediffs.com/ics-compare), [ics-tools](https://github.com/martinp26/ics-tools) | Общая идея уже реализована |
| Покрытие манифестов Dependabot | [dependabot-auto-configure](https://pkg.go.dev/github.com/larsartmann/dependabot-auto-configure) | Автоматическое обнаружение и настройка уже существуют |
| Batch-тесты routing + inhibition в Alertmanager | [Запрос #5167](https://github.com/prometheus/alertmanager/issues/5167) открыт, но автор уже описал отдельный [alertmanager-routing-tests](https://dev.to/frosnerd/unit-testing-alertmanager-routing-and-inhibition-rules-1hj4); также есть [am-route-test](https://github.com/jjneely/am-route-test) | Открытый issue не означает свободную нишу; идею отклонить |

Это перечень изученных альтернатив, не каталог всех проектов. Общий поиск репозиториев через интеграцию местами возвращал ошибки или нерелевантные результаты; они не интерпретировались как отсутствие конкурентов.

## Три наиболее серьёзных кандидата

Оценки ниже — инженерное суждение, не вероятность одобрения программой.

| Кандидат | Пользователь и повторяемая проблема | Отдельный продукт / вклад upstream | Стоимость, доступ к первым пользователям |
|---|---|---|---|
| ArtifactSpan | Maintainer matrix CI: одинаковые имена upload, неверный needs, запрещённый символ после подстановки | Узкий пробел подтверждён примером; upstream-правила actionlint могут быть лучше отдельного CLI в долгосрочной перспективе | Локальный Python, без серверов; добровольные прогоны на workflow проектов, обсуждавших artifact migrations |
| Alertmanager inhibition tests | SRE: изменение маршрутов/подавления ломает уведомления | Проблема реальная, но отдельное решение уже опубликовано; разумнее помочь существующему проекту или #5167 | Требуется сопровождение семантики Alertmanager; пользователи в соответствующем upstream discussion |
| Compose env provenance | Разработчик: сложно объяснить итоговое значение env | envorigin уже охватывает идею; отличие нашего нового проекта не доказано | Много правил нескольких CI; первые пользователи уже доступны существующему проекту |

## Подтверждённая проблема и статус issues

* [upload-artifact #478](https://github.com/actions/upload-artifact/issues/478), **закрыт**: переход к immutable artifacts v4 ломал схемы с одинаковым именем в matrix. Это свидетельство ошибки конфигурации, не незакрытого дефекта GitHub.
* [#493](https://github.com/actions/upload-artifact/issues/493), **закрыт**: тот же класс миграции, в том числе сборки ONNX. Уже есть обходные схемы с отдельными именами и последующим объединением. В timeline есть исправления downstream, включая merged PR; нельзя продавать это как отсутствие решения.
* [#692](https://github.com/actions/upload-artifact/issues/692), **открыт на дату проверки**: значение shard вида `1/5` попадает в имя, `/` запрещён. Ограничение предусмотрено реализацией, а не ожидает нашего исправления в GitHub. В timeline присутствуют downstream merged PR: [ByronWilliamsCPA/.github #234](https://github.com/ByronWilliamsCPA/.github/pull/234) и [levelup #8](https://github.com/anurag008w/levelup/pull/8).
* [#678](https://github.com/actions/upload-artifact/issues/678), открыт: соседняя проблема merge/delete-merged. **В первую версию не входит.** Анализ имени не проверяет содержимое объединяемых архивов.

Официальные способы исправления уже описаны в [upload-artifact](https://github.com/actions/upload-artifact), [migration guide](https://github.com/actions/upload-artifact/blob/main/docs/MIGRATION.md) и [передаче данных между jobs](https://docs.github.com/en/actions/tutorials/store-and-share-data). Продуктовая гипотеза — находить эти ошибки до дорогого запуска CI.

## Сравнение с существующими линтерами

Прочитаны [checks actionlint](https://github.com/rhysd/actionlint/blob/main/docs/checks.md), [правила ghalint](https://github.com/suzuki-shunsuke/ghalint), [sisakulint](https://github.com/sisaku-security/sisakulint). Их проверяемые области включают синтаксис, выражения, action inputs, политики и безопасность, включая artifact poisoning у sisakulint. Это не тот же анализ совпадений конкретных имён после разворачивания matrix и порядка producer/consumer.

Для actionlint выполнено сравнение на одинаковых собственных входах:

| Вход | actionlint 1.7.12 | ArtifactSpan 0.1.0 |
|---|---|---|
| examples/collision.yml | exit 0, без диагностики | exit 1: duplicate_upload, producer_not_ordered |
| examples/fixed.yml | exit 0, без диагностики | exit 0, две связи producer → consumer |

Команда сравнения: `actionlint -shellcheck= -pyflakes= examples/collision.yml`. Отключены только внешние анализаторы shell/Python; собственные проверки workflow включены. Использован [официальный release 1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12), Windows amd64 ZIP SHA-256 `6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9`. Это проверка одного конкретного пробела, не оценка общего качества actionlint. Другие линтеры сравнивались по документации, не запускались.

Дополнительно неизменённый YAML code block из #692 разобран как данные: обнаружено **пять invalid_artifact_name** для shard 1/5…5/5. Команды из workflow не исполнялись. Полный чужой workflow и бинарник actionlint не включены в дистрибутив; в examples/reports сохранены результат, URL и хеш входа.

## Почему собственный прототип пока оправдан

Первая версия проверяет небольшую семантическую гипотезу без форка чужого продукта, серверов и платных API. Она полезна для оценки правила на реальных workflow и сбора ложных срабатываний. Перед расширением разумно обсудить те же правила с upstream actionlint: если там появляется эквивалент, переносить полезные тесты и правила, а не поддерживать дубликат ради владения репозиторием.

Риск спроса остаётся: maintainer может предпочесть один линтер, а динамические matrix и reusable workflows потребуют более сложного анализа. Наличие issues доказывает класс ошибки, но не наличие пользователей ArtifactSpan. На момент выпуска нет заявленных внешних установок, отзывов или интеграций. Контакты, публикация и заявки не выполнялись.
