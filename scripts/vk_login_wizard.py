#!/usr/bin/env python3
"""Простой мастер получения VK токена — на русском."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "54693054"


def main() -> int:
    print("=" * 60)
    print("  Получение VK токена для автоприёма заявок")
    print("=" * 60)
    print()
    print("Сейчас в Secrets, скорее всего, ключ СООБЩЕСТВА.")
    print("Нужен личный токен с правом groups (через VK ID).")
    print()
    print("── Шаг 1 из 2: откройте ссылку в браузере ──")
    print()

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "get_vk_token.py"),
            "start",
            "--client-id",
            APP_ID,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    print()
    print("── Шаг 2 из 2: вставьте redirect URL ──")
    print()
    print("После «Разрешить» скопируйте адрес из строки браузера")
    print("(начинается с http://localhost?code=...)")
    print()
    try:
        redirect_url = input("Вставьте URL сюда и нажмите Enter: ").strip()
    except EOFError:
        print()
        print("Нет ввода. Отправьте этот URL агенту в чат — он обменяет код сам.")
        return 0

    if not redirect_url:
        print("URL не введён. Запустите снова или отправьте URL агенту.")
        return 1

    print()
    print("Обмен кода на токен...")
    exchange = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "get_vk_token.py"),
            "exchange",
            "--redirect-url",
            redirect_url,
            "--client-id",
            APP_ID,
        ],
        cwd=ROOT,
        check=False,
    )
    if exchange.returncode != 0:
        print()
        print("Не вышло. Проверьте, что в Secrets есть VK_SERVICE_TOKEN")
        print("(сервисный ключ из кабинета приложения 54693054).")
        return exchange.returncode

    print()
    print("Готово! Скопируйте access_token в Cursor Secret VK_ACCESS_TOKEN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
