# ppl — Perplexity CLI (chat/cmd/script)

[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-blue)](./)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Made with Python](https://img.shields.io/badge/python-3.10%2B-informational)](./)

**ppl** — консольный инструмент “как утилита”, который подключается к Perplexity API и помогает:  
- общаться в режиме чата (`chat`),  
- генерировать одну команду под задачу (`cmd`),  
- генерировать скрипты (`script`) и предлагать установку зависимостей перед запуском.

Проект написан на Typer (CLI) и Rich (красивый вывод), общение с моделью идёт через Perplexity Chat Completions API.

---

## Содержание
- [Фичи](#фичи)
- [Установка](#установка)
- [API ключ](#api-ключ)
- [Использование](#использование)
- [Как устроено](#как-устроено)
- [Сборка релизов (onefile)](#сборка-релизов-onefile)
- [Безопасность](#безопасность)
- [Траблшутинг](#траблшутинг)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Лицензия](#лицензия)
- [Ссылки](#ссылки)

---

## Фичи
- **chat**: разговорный режим, подмешивает историю диалога (контекст) и выводит ответ Markdown’ом.
- **cmd**: возвращает одну bash-команду в JSON-формате + заметки; умеет предложить выполнить команду после подтверждения.
- **script**:
  - `script python`: модель возвращает код + список pip-зависимостей (`pip: ["..."]`), `ppl` предлагает установить зависимости *глобально для пользователя* (`pip install --user ...`), затем показывает код и предлагает запуск.
  - `script bash`: генерирует bash-скрипт, показывает и предлагает запуск.
- **key**: сохранить/очистить Perplexity API key локально.
- **clear**: очистить историю.

---

## Установка

### Вариант A — скачать релиз-бинарник (рекомендуется)
1. Перейди в **GitHub Releases** этого репозитория и скачай файл под свою ОС:
   - Linux/macOS: `ppl`
   - Windows: `ppl.exe`
2. Сделай файл исполняемым (Linux/macOS):
   ```bash
   chmod +x ppl
   ```
3. Проверь:
   ```bash
   ./ppl --help
   ```

### Вариант B — запуск из исходников (для разработки)
```bash
python -m pip install -r requirements.txt
python main.py --help
```

---

## API ключ

`ppl` ищет ключ в таком порядке:

1) `PERPLEXITY_API_KEY` (переменная окружения)  
2) `~/.config/ppl/config.json` (локальный конфиг)

### Установить ключ через команду
```bash
ppl key
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

### Удалить сохранённый ключ
```bash
ppl key --clear
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

Опции:
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

Что важно:
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
   Формат `python -m pip install ...` — стандартный способ вызывать pip через выбранный интерпретатор. [page:0]
3) Сохраняет скрипт во временную папку и показывает код.
4) Спрашивает подтверждение на запуск.

---

## Как устроено

- История: `~/.config/ppl/history.json`
- Конфиг: `~/.config/ppl/config.json`
- Контекст: в `chat/cmd/script` подмешиваются последние `--context N` сообщений.
- Вывод:
  - ответы чата печатаются через `Rich Markdown`,
  - команды/скрипты — через `Rich Syntax`,
  - заметки — через `Rich Panel`.

---

## Сборка релизов (onefile)

Сборка делается PyInstaller’ом в режиме **onefile** (один исполняемый файл).  
Важно: мы используем `.spec`, чтобы корректно упаковывались внутренние данные Rich (unicode-таблицы). PyInstaller подробно описывает роль spec-файлов и хуков. [page:2][page:3]

### 1) Установи зависимости сборки
```bash
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

### 2) Собери
```bash
rm -rf build dist
pyinstaller --clean --noconfirm ppl.spec
```

Результат:
- Linux/macOS: `dist/ppl`
- Windows: `dist/ppl.exe`

### 3) Проверь бинарник
```bash
./dist/ppl --help
./dist/ppl chat "Привет"
```

---

## Безопасность

- **Не вшивай API ключ** в код и не коммить его в репозиторий.
- Любая команда/скрипт, сгенерированные моделью, потенциально могут быть небезопасны.
- `ppl` всегда спрашивает подтверждение перед выполнением (`cmd --run` и запуск в `script`).
- `script python` ставит зависимости глобально “для пользователя” (`--user`) — это удобно, но может засорять окружение. Если хочешь изоляцию, лучше перейти на отдельный venv для рантайма (см. Roadmap).

---

## Траблшутинг

### “Нет API ключа”
Сделай одно из двух:
- `ppl key`
- или установи `PERPLEXITY_API_KEY`

### “Не найден системный Python”
`script python` ищет:
- Windows: `py -3`
- Linux/macOS: `python3` или `python`

Поставь Python и убедись, что он в `PATH`.

### Модель вернула невалидный JSON
Запусти с `--debug` и повтори запрос (или переформулируй задачу, попроси “верни только JSON”).

---

## Roadmap
Идеи, которые можно доделать:
- Изоляция зависимостей для `script python` в отдельный venv (а не `--user`).
- Автосборка релизов через GitHub Actions под Linux/Windows/macOS.
- Поддержка `cmd` под PowerShell/Windows native.
- Команда `ppl doctor` (проверка ключа, Python, pip, прав, путей).
- Команда `ppl export-history` (в Markdown/JSONL).

---

## Contributing
Это пет‑проект, но PR и идеи приветствуются:
1) форк  
2) ветка `feature/...`  
3) PR с описанием изменений и тест-кейсами (команды запуска)

---

## Лицензия
MIT (добавь файл `LICENSE`).

---

## Ссылки
- Perplexity API — Chat Completions: https://docs.perplexity.ai/api-reference/chat-completions-post [page:5]
- Typer (CLI framework): https://typer.tiangolo.com/ [page:4]
- README шаблон/структура (для вдохновения): Best README Template: https://github.com/othneildrew/Best-README-Template [web:330]
```

Если хочешь, я подгоню README под твой GitHub: добавлю бейдж “Release”, бейдж CI, секцию “Download” с конкретными именами ассетов (Linux/macOS/Windows), и красивый блок “Demo” с реальными примерами вывода (как выглядит `chat`, `cmd`, `script`).
