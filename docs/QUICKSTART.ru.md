# ArtifactSpan: первый запуск

Найдите одинаковые имена артефактов и скачивания без ожидания загрузившего их job в статическом GitHub Actions workflow.

**[Скачать визуальное руководство EN/RU](https://github.com/HexCine/artifactspan/releases/download/v0.1.2/start.html)** — сохраните HTML и откройте в браузере. Код не отправляется на сервер.

## 1. Установка

Скачайте [artifactspan-0.1.2-source.zip](https://github.com/HexCine/artifactspan/releases/download/v0.1.2/artifactspan-0.1.2-source.zip), распакуйте и откройте терминал в корне проекта.
Требуется Python 3.11+. Создайте venv: `python -m venv .venv`. Активируйте `.venv/Scripts/Activate.ps1` (PowerShell) или `source .venv/bin/activate` (macOS/Linux). Либо используйте путь к Python окружения вместо `python`.

```sh
python -m pip install .
```

## 2. Учебная проблема

```sh
python -m artifactspan examples/collision.yml
```

Конфликт возвращает 1 с местами загрузки. Исправленный workflow возвращает 0 и две связи между загрузкой и скачиванием.

## 3. Контрольный пример

```sh
python -m artifactspan examples/fixed.yml --format json
```

Ожидается код 0. При коде 2 проверьте входные данные: полного вывода нет.
Примеры синтетические. Для повторного создания demo выберите новую папку.

## Свои данные

Дайте загрузкам матрицы разные имена, добавьте needs потребителям. Проверьте строки исходника и неизвестные конструкции вместе с actionlint.

```sh
python -m artifactspan .github/workflows/ci.yml
```

Подставьте реальные пути вместо примеров. Только статическая передача артефактов. Динамические выражения могут быть неизвестны. Workflow не выполняется, наличие загружаемых файлов не доказывается.

Если файл не найден, проверьте текущую папку. Перед отправкой отчёта удалите
чувствительные имена, пути и host. В issue укажите версию, команду, ожидаемый
и фактический результат и минимальный обезличенный пример.

[Полное руководство](../README.md) · [Сообщить об ошибке](https://github.com/HexCine/artifactspan/issues)
