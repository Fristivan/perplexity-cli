#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Literal, Optional

import typer
from perplexity import Perplexity
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

Role = Literal["system", "user", "assistant"]
Mode = Literal["chat", "cmd", "script"]

console = Console()
app = typer.Typer(add_completion=False, help="ppl — CLI Perplexity (chat/cmd/script)")

CIT_RE = re.compile(r"\[\d+\]")


# -------------------- storage --------------------

def app_dir() -> Path:
    # кроссплатформенно, но просто: используем XDG_CONFIG_HOME / ~/.config
    # (на Windows тоже сработает, просто будет в профиле пользователя)
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ppl"
    base.mkdir(parents=True, exist_ok=True)
    return base


def history_path() -> Path:
    return app_dir() / "history.json"


def config_path() -> Path:
    return app_dir() / "config.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        # best-effort: ограничить права (работает на Unix)
        os.chmod(path, 0o600)
    except Exception:
        pass


# -------------------- text helpers --------------------

def strip_citations(text: str) -> str:
    t = CIT_RE.sub("", text)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return t.strip()


def extract_text(resp: Any) -> str:
    if resp is None:
        return ""
    choices = getattr(resp, "choices", None)
    if choices:
        c0 = choices[0]
        msg = getattr(c0, "message", None) or getattr(c0, "delta", None)
        if msg is not None:
            content = getattr(msg, "content", None)
            if content:
                return str(content)
        content = getattr(c0, "content", None)
        if content:
            return str(content)
    try:
        d = resp if isinstance(resp, dict) else resp.to_dict()
        return d["choices"][0]["message"]["content"]
    except Exception:
        return str(resp)


def parse_json_from_model(text: str) -> dict[str, Any]:
    t = text.strip()
    if not t.startswith("{"):
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            t = m.group(0)
    return json.loads(t)


def clip(text: str, limit: int = 4000) -> str:
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "\n...[truncated]"


# -------------------- history (single global) --------------------

def load_history() -> dict[str, Any]:
    data = load_json(history_path(), {"version": 1, "messages": []})
    if not isinstance(data, dict) or "messages" not in data or not isinstance(data["messages"], list):
        return {"version": 1, "messages": []}
    data.setdefault("version", 1)
    return data


def save_history(hist: dict[str, Any]) -> None:
    save_json(history_path(), hist)


def clear_history() -> None:
    p = history_path()
    if p.exists():
        p.unlink()


def push_message(hist: dict[str, Any], role: Role, content: str, mode: Mode) -> None:
    hist["messages"].append({"role": role, "content": content, "mode": mode})


def get_context(hist: dict[str, Any], max_messages: int) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = []
    for m in hist.get("messages", []):
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        msgs.append({"role": role, "content": content})

    if max_messages > 0 and len(msgs) > max_messages:
        msgs = msgs[-max_messages:]
    return msgs


# -------------------- API key --------------------

def get_api_key() -> str:
    # 1) env
    k = os.environ.get("PERPLEXITY_API_KEY", "").strip()
    if k:
        return k
    # 2) config file
    cfg = load_json(config_path(), {})
    if isinstance(cfg, dict):
        k = str(cfg.get("api_key", "")).strip()
        if k:
            return k
    return ""


@app.command("key")
def key_cmd(
    set_: Optional[str] = typer.Argument(None, help="Установить ключ (или используй interactive prompt)"),
    clear: bool = typer.Option(False, "--clear", help="Удалить сохранённый ключ"),
) -> None:
    cfg = load_json(config_path(), {})
    if not isinstance(cfg, dict):
        cfg = {}

    if clear:
        cfg.pop("api_key", None)
        save_json(config_path(), cfg)
        typer.echo(f"Ключ удалён из {config_path()}")
        raise typer.Exit(0)

    if not set_:
        set_ = typer.prompt("Введите Perplexity API key", hide_input=True)

    cfg["api_key"] = set_.strip()
    save_json(config_path(), cfg)
    typer.echo(f"Ключ сохранён в {config_path()} (локально у пользователя)")


# -------------------- prompts --------------------

def system_prompt_chat(short: bool) -> str:
    # Цель: вести себя как нормальный чат-ассистент, не как справочник.
    common = (
        "You are a helpful chat assistant.\n"
        "Write in the same language as the user.\n"
        "Be natural and conversational.\n"
        "Do not explain obvious words or give background unless the user asks.\n"
        "Do not give lists of alternatives unless requested.\n"
        "IMPORTANT: Do NOT include citation markers like [1], [2], etc.\n"
    )
    if short:
        return common + "Answer in 1-2 short sentences. No preface.\n"
    return common + "Answer directly. Keep it concise.\n"



def system_prompt_cmd(short: bool) -> str:
    extra = "Return a single short command.\n" if short else "Return one safe command.\n"
    return (
        "You are a CLI assistant for Ubuntu/macOS/Windows (when using WSL or similar).\n"
        "Return ONLY valid JSON.\n"
        'Schema: {"type":"command","language":"bash","command":"...","notes":"..."}\n'
        + extra +
        "Avoid destructive commands. Prefer read-only diagnostics. No sudo unless necessary.\n"
        "IMPORTANT: Do NOT include citation markers like [1], [2], etc.\n"
    )


def system_prompt_script_python() -> str:
    # ключевая фича: модель обязана вернуть pip deps
    return (
        "You are a CLI assistant.\n"
        "Return ONLY valid JSON.\n"
        'Schema: {"type":"script","language":"python","filename":"script.py","pip":["pkg1","pkg2"],"code":"...","notes":"..."}\n'
        "Rules:\n"
        "- Generate a complete Python 3.12+ script, self-contained.\n"
        "- If script uses third-party libs, list PyPI package names in pip.\n"
        "- If only stdlib is used, pip must be an empty list.\n"
        "- Do not include markdown fences.\n"
        "IMPORTANT: Do NOT include citation markers like [1], [2], etc.\n"
    )


def system_prompt_script_bash() -> str:
    return (
        "You are a CLI assistant.\n"
        "Return ONLY valid JSON.\n"
        'Schema: {"type":"script","language":"bash","filename":"script.sh","pip":[],"code":"...","notes":"..."}\n'
        "Rules:\n"
        "- Generate a complete Bash script, self-contained.\n"
        "- pip must be an empty list.\n"
        "- Do not include markdown fences.\n"
        "IMPORTANT: Do NOT include citation markers like [1], [2], etc.\n"
    )


# -------------------- Perplexity call --------------------

def call_ppl(
    messages: list[dict[str, str]],
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    spinner: str,
    debug: bool,
) -> str:
    api_key = get_api_key()
    if not api_key:
        typer.echo("Нет API ключа. Установи: ppl key (или env PERPLEXITY_API_KEY).", err=True)
        raise typer.Exit(1)

    client = Perplexity(api_key=api_key)
    with console.status("[bold cyan]Жду ответ Perplexity...[/]", spinner=spinner):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    text = extract_text(resp)
    if debug:
        console.print(Panel.fit(text, title="raw response"))
    return text


# -------------------- system python / pip --------------------

def find_system_python() -> list[str]:
    """
    Возвращает команду, которой можно вызвать Python + pip:
    - Windows: ["py", "-3"]
    - иначе: ["python3"] или ["python"]
    """
    if os.name == "nt" and shutil.which("py"):
        return ["py", "-3"]
    if shutil.which("python3"):
        return ["python3"]
    if shutil.which("python"):
        return ["python"]
    return []


def pip_install_user(pkgs: list[str]) -> list[str]:
    py = find_system_python()
    if not py:
        return []
    # python -m pip install --user ... (это нормальная схема вызова pip) [page:0]
    return [*py, "-m", "pip", "install", "--user", *pkgs]


def normalize_pip_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for x in value:
        if isinstance(x, str):
            s = x.strip()
            if s and s not in out:
                out.append(s)
    return out


# -------------------- commands --------------------

@app.command()
def clear() -> None:
    """Очистить историю."""
    clear_history()
    typer.echo(f"Очищено: {history_path()}")


@app.command()
def chat(
    query: str = typer.Argument(..., help="Сообщение в чат"),
    short: bool = typer.Option(False, "--short", help="Сильно укоротить ответ"),
    context: int = typer.Option(30, "--context", help="Сколько последних сообщений подмешивать"),
    model: str = typer.Option("sonar", "--model"),
    temperature: float = typer.Option(0.2, "--temperature"),
    max_tokens: int = typer.Option(900, "--max-tokens"),
    spinner: str = typer.Option("dots", "--spinner"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    hist = load_history()
    msgs = [{"role": "system", "content": system_prompt_chat(short)}]
    msgs.extend(get_context(hist, context))
    msgs.append({"role": "user", "content": query})

    if short:
        max_tokens = min(max_tokens, 220)

    text = call_ppl(msgs, model=model, temperature=temperature, max_tokens=max_tokens, spinner=spinner, debug=debug)
    answer = strip_citations(text)

    push_message(hist, "user", clip(query), "chat")
    push_message(hist, "assistant", clip(answer), "chat")
    save_history(hist)

    console.print(Markdown(answer))


@app.command()
def cmd(
    query: str = typer.Argument(..., help="Сформулируй задачу, я верну bash-команду"),
    short: bool = typer.Option(False, "--short", help="Короткая команда"),
    run: bool = typer.Option(False, "--run", help="Сразу предложить выполнить"),
    context: int = typer.Option(30, "--context"),
    model: str = typer.Option("sonar", "--model"),
    temperature: float = typer.Option(0.1, "--temperature"),
    max_tokens: int = typer.Option(400, "--max-tokens"),
    spinner: str = typer.Option("dots", "--spinner"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    hist = load_history()
    msgs = [{"role": "system", "content": system_prompt_cmd(short)}]
    msgs.extend(get_context(hist, context))
    msgs.append({"role": "user", "content": query})

    text = call_ppl(msgs, model=model, temperature=temperature, max_tokens=max_tokens, spinner=spinner, debug=debug)

    try:
        data = parse_json_from_model(text)
    except Exception as e:
        typer.echo(f"Ошибка JSON: {e}", err=True)
        console.print(Panel.fit(text, title="response text"))
        raise typer.Exit(2)

    notes = strip_citations((data.get("notes") or "").strip())
    command = strip_citations((data.get("command") or "").strip())

    if notes:
        console.print(Panel.fit(notes, title="notes"))
    if not command:
        typer.echo("Команда не возвращена (command пустая).", err=True)
        raise typer.Exit(3)

    console.print(Panel.fit(Syntax(command, "bash", line_numbers=False), title="command"))

    push_message(hist, "user", clip(f"[cmd] {query}"), "cmd")
    push_message(hist, "assistant", clip(f"[cmd]\n{command}\n\n{notes}".strip()), "cmd")
    save_history(hist)

    if run and (typer.confirm("Выполнить команду?", default=False)):
        # минимальная страховка
        if any(x in command.lower() for x in ("rm -rf", "mkfs", "dd if=")):
            typer.echo("Похоже на опасную команду, отмена.", err=True)
            raise typer.Exit(4)
        rc = subprocess.run(["bash", "-lc", command]).returncode
        raise typer.Exit(int(rc))


@app.command()
def script(
    lang: str = typer.Argument(..., help="python|bash"),
    query: str = typer.Argument(..., help="Что должен делать скрипт"),
    context: int = typer.Option(20, "--context"),
    model: str = typer.Option("sonar", "--model"),
    temperature: float = typer.Option(0.1, "--temperature"),
    max_tokens: int = typer.Option(1200, "--max-tokens"),
    spinner: str = typer.Option("dots", "--spinner"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    lang = lang.strip().lower()
    if lang not in ("python", "bash"):
        typer.echo("lang должен быть python или bash.", err=True)
        raise typer.Exit(1)

    hist = load_history()
    sys_prompt = system_prompt_script_python() if lang == "python" else system_prompt_script_bash()

    msgs = [{"role": "system", "content": sys_prompt}]
    msgs.extend(get_context(hist, context))
    msgs.append({"role": "user", "content": query})

    text = call_ppl(msgs, model=model, temperature=temperature, max_tokens=max_tokens, spinner=spinner, debug=debug)

    try:
        data = parse_json_from_model(text)
    except Exception as e:
        typer.echo(f"Ошибка JSON: {e}", err=True)
        console.print(Panel.fit(text, title="response text"))
        raise typer.Exit(2)

    notes = strip_citations((data.get("notes") or "").strip())
    filename = (data.get("filename") or ("script.py" if lang == "python" else "script.sh")).strip()
    code = strip_citations((data.get("code") or "").rstrip()) + "\n"
    pip_deps = normalize_pip_list(data.get("pip"))

    if notes:
        console.print(Panel.fit(notes, title="notes"))
    if not code.strip():
        typer.echo("Скрипт не возвращён (code пустой).", err=True)
        raise typer.Exit(3)

    # 1) сначала deps (как ты просил)
    if lang == "python" and pip_deps:
        py = find_system_python()
        if not py:
            typer.echo("Не найден системный Python (python3/python или py -3). Установи Python и повтори.", err=True)
            raise typer.Exit(4)

        install_cmd = pip_install_user(pip_deps)
        if not install_cmd:
            typer.echo("Не смог сформировать команду pip install.", err=True)
            raise typer.Exit(5)

        console.print(Panel.fit(Syntax(" ".join(install_cmd), "bash"), title="Install deps (user-global)"))
        if typer.confirm("Установить зависимости?", default=True):
            p = subprocess.run(install_cmd)
            if p.returncode != 0:
                raise typer.Exit(int(p.returncode))

    # 2) сохраняем скрипт
    tmpdir = Path(tempfile.mkdtemp(prefix="ppl-"))
    path = tmpdir / filename
    path.write_text(code, encoding="utf-8")
    if lang == "bash":
        try:
            os.chmod(path, 0o700)
        except Exception:
            pass

    console.print(Panel.fit(str(path), title="saved to"))
    console.print(Panel.fit(Syntax(code, lang, line_numbers=True), title="script"))

    push_message(hist, "user", clip(f"[script:{lang}] {query}"), "script")
    push_message(hist, "assistant", clip(f"[script:{lang}] pip={pip_deps}\n{notes}\n\n{code}"), "script")
    save_history(hist)

    # 3) запуск
    if not typer.confirm("Запустить скрипт?", default=False):
        raise typer.Exit(0)

    if lang == "python":
        py = find_system_python()
        if not py:
            typer.echo("Не найден системный Python для запуска.", err=True)
            raise typer.Exit(6)
        rc = subprocess.run([*py, str(path)]).returncode
    else:
        rc = subprocess.run(["bash", str(path)]).returncode
    raise typer.Exit(int(rc))


if __name__ == "__main__":
    app()
