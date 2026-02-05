# perplexity-cli (`ppl`) — Perplexity CLI (chat/cmd/script)

[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macos-blue)](./)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

**ppl** — консольная утилита “как системный инструмент”, которая подключается к Perplexity API и помогает:
- общаться в режиме чата (`chat`),
- генерировать одну bash-команду под задачу (`cmd`),
- генерировать скрипты (`script`) и предлагать установку зависимостей перед запуском.

---

## Содержание
- [Фичи](#фичи)
- [Требования](#требования)
- [Установка](#установка)
- [Настройка API ключа](#настройка-api-ключа)
- [Использование](#использование)
- [Файлы и хранение данных](#файлы-и-хранение-данных)
- [Сборка релизов (onefile)](#сборка-релизов-onefile)
- [Безопасность](#безопасность)
- [Траблшутинг](#траблшутинг)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Лицензия](#лицензия)
- [Ссылки](#ссылки)

---

## Фичи
- **chat** — разговорный режим, подмешивает историю диалога (контекст) и выводит ответ Markdown’ом (Rich).
- **cmd** — возвращает одну bash-команду в JSON-формате + заметки; умеет предложить выполнить команду после подтверждения.
- **script**
  - `script python` — модель возвращает код + список pip-зависимостей; `ppl` предлагает установить зависимости, затем показывает код и предлагает запуск.
  - `script bash` — генерирует bash-скрипт, показывает и предлагает запуск.
- **key** — сохранить/очистить Perplexity API key локально.
- **clear** — очистить историю.

---

## Требования

### Для запуска бинарника
Ничего, кроме вашей ОС и доступа в интернет.

### Для `ppl script python`
Нужен установленный **системный Python** и `pip`, потому что зависимости ставятся командой вида:
```bash
python -m pip install --user <packages...>
```

Как `ppl` ищет Python:
- Windows: `py -3`
- Linux/macOS: `python3` или `python`

---

## Установка

### Скачать готовый бинарник (Releases)

Актуальные ассеты в релизах:
- **Windows**: `ppl-win-x86.exe`
- **Linux**: `ppl-linux`
- **macOS**: пока нет (у автора нет MacBook для сборки и тестирования)

Открой Releases:  
https://github.com/Fristivan/perplexity-cli/releases

---

### Установка на Linux (`ppl-linux`)
1) Скачай `ppl-linux`
2) Сделай исполняемым:
```bash
chmod +x ppl-linux
```
3) (Опционально) Переименуй в `ppl`:
```bash
mv ppl-linux ppl
```
4) Положи в PATH:
```bash
mkdir -p ~/.local/bin
mv ./ppl ~/.local/bin/ppl
chmod +x ~/.local/bin/ppl
```
5) Если `~/.local/bin` ещё не в PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```
6) Проверка:
```bash
ppl --help
ppl chat "Привет"
```

---

### Установка на Windows (`ppl-win-x86.exe`)
1) Скачай `ppl-win-x86.exe`
2) Переименуй в `ppl.exe` (так удобнее):
- через Проводник, или командой:
```powershell
Rename-Item .\ppl-win-x86.exe ppl.exe
```
3) Создай папку, например:
- `C:\Tools\ppl\`
4) Перемести туда `ppl.exe`
5) Добавь `C:\Tools\ppl\` в переменную среды **Path**
6) Перезапусти терминал и проверь:
```powershell
ppl --help
ppl chat "Привет"
```

---

### Запуск из исходников (для разработки)
```bash
python -m pip install -r requirements.txt
python main.py --help
```

---

## Настройка API ключа

`ppl` ищет ключ в таком порядке:
1) `PERPLEXITY_API_KEY` (переменная окружения)
2) `~/.config/ppl/config.json` (локальный конфиг)

### Установить ключ через команду
```bash
ppl key
```

Удалить ключ:
```bash
ppl key --clear
```

### Установить ключ через переменную окружения
Linux/macOS:
```bash
export PERPLEXITY_API_KEY="..."
```

Windows (PowerShell):
```powershell
setx PERPLEXITY_API_KEY "..."
```

---

## Использование

### chat — обычный чат
```bash
ppl chat "Привет"
ppl chat "объясни venv"
ppl chat --short "объясни venv"
ppl chat --context 10 "что мы обсуждали?"
```

Полезные опции:
- `--short` — короче и без прелюдий
- `--context N` — сколько последних сообщений подмешивать
- `--model`, `--temperature`, `--max-tokens` — параметры генерации
- `--debug` — печатает сырой ответ модели

### cmd — сгенерировать bash-команду под задачу
```bash
ppl cmd "как установить telegram на ubuntu"
ppl cmd --short "как посмотреть занятое место на диске"
ppl cmd --run "проверить версию python"
```

Важно:
- `cmd` просит модель вернуть **строгий JSON**: команду + заметки.
- `--run` всегда спрашивает подтверждение перед выполнением.

### script — сгенерировать скрипт
Python:
```bash
ppl script python "выведи текущее время в Нью-Йорке, Минске и Чикаго"
```

Bash:
```bash
ppl script bash "покажи топ-10 самых больших файлов в текущей папке"
```

Поведение `script python`:
1) `ppl` показывает предложенные зависимости (pip-пакеты).
2) Предлагает установить их через:
   ```bash
   python -m pip install --user <packages...>
   ```
3) Сохраняет скрипт во временную папку и показывает код.
4) Спрашивает подтверждение на запуск.

---

## Файлы и хранение данных
- История: `~/.config/ppl/history.json`
- Конфиг: `~/.config/ppl/config.json`

> Примечание: на Windows этот путь тоже работает, но это “упрощённый” вариант. В будущем можно перейти на нативные пути `%APPDATA%` / `~/Library/Application Support`.

---

## Сборка релизов (onefile)

Сборка делается PyInstaller’ом в режиме **onefile** (один исполняемый файл).

### Почему в репозитории есть `ppl.spec`
Мы собираем релиз **из `ppl.spec`**, потому что Rich использует внутренние unicode-таблицы и “скрытые импорты”, которые PyInstaller не всегда подхватывает автоматически.  
Без этого бинарник может падать на `ModuleNotFoundError` внутри `rich._unicode_data.*`.

Spec-файл — это исполняемый Python-код, а PyInstaller строит приложение, выполняя этот файл. Документация PyInstaller: https://pyinstaller.org/en/stable/spec-files.html

### 1) Установи зависимости сборки
```bash
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

### 2) Собери (правильный способ)
Собирать нужно **из `ppl.spec`**:

```bash
rm -rf build dist
pyinstaller --clean --noconfirm ppl.spec
```

Результат:
- Linux/macOS: `dist/ppl` (можешь переименовать в `ppl-linux` для релиза)
- Windows: `dist/ppl.exe` (можешь переименовать в `ppl-win-x86.exe` для релиза)

### 3) Проверь бинарник
```bash
./dist/ppl --help
./dist/ppl chat "Привет"
```

### Важно про кроссплатформенность
Релизы нужно собирать отдельно на каждой ОС:
- Linux → на Linux
- Windows → на Windows
- macOS → на macOS

---

## Безопасность
- **Не коммить API ключ** в репозиторий и не вшивай его в бинарник.
- Любая команда/скрипт, сгенерированные моделью, потенциально могут быть небезопасны.
- `ppl` спрашивает подтверждение перед выполнением (`cmd --run` и запуск в `script`).
- `script python` ставит зависимости через `--user`. Это удобно, но может “засорять” пользовательское окружение Python.

---

## Траблшутинг

### “Нет API ключа”
Сделай одно из двух:
- `ppl key`
- или установи `PERPLEXITY_API_KEY`

### “Не найден системный Python”
`script python` не сможет поставить зависимости и запустить скрипт. Установи Python и убедись, что он доступен как `python3/python` (Linux/macOS) или `py -3` (Windows).

### Модель вернула невалидный JSON
Запусти с `--debug`, чтобы увидеть сырой ответ, затем повтори запрос или уточни формулировку (“верни только JSON строго по схеме”).

---

## Roadmap
- Изоляция зависимостей для `script python` в отдельный venv (вместо `pip --user`).
- Автосборка релизов через GitHub Actions под Linux/Windows/macOS.
- PowerShell-режим для `cmd` на Windows.
- `ppl doctor` (проверка ключа, Python, pip, путей).
- Экспорт истории (`ppl export-history`) в Markdown/JSONL.

---

## Contributing
Это пет‑проект, но PR и идеи приветствуются:
1) Fork
2) Ветка `feature/...`
3) PR с описанием изменений и простыми тест-кейсами (команды запуска)

---

## Лицензия
MIT (добавь файл `LICENSE`).

---

## Ссылки
- Perplexity API — Chat Completions: https://docs.perplexity.ai/api-reference/chat-completions-post
- Typer (CLI framework): https://typer.tiangolo.com/
- PyInstaller — Spec files: https://pyinstaller.org/en/stable/spec-files.html
