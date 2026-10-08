# -*- coding: utf-8 -*-
"""👥 Ադմինի կոնսոլ առանձին պատուհանում / Консоль администратора отдельно от сервера.

    python app/admin.py                 — интерактивно (команды: help, users, allow <логин> ...)
    python app/admin.py allow ivan      — одна команда (удобно на сервере Render: Shell)

Работает с теми же файлами data/users.json и data/sessions.json, что и сервер —
сервер сразу видит изменения, перезапуск не нужен."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import users  # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa
        pass
    users.NOTIFY[0] = False
    if len(sys.argv) > 1:
        print(users.run_command(" ".join(f'"{a}"' if " " in a else a for a in sys.argv[1:])))
        return
    print("\n  Mix Media — консоль администратора")
    print(users.HELP)
    print(users.run_command("requests"))
    while True:
        try:
            line = input("\n  admin> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip().lower() in ("exit", "quit", "q", "выход"):
            break
        out = users.run_command(line)
        if out:
            print(out)


if __name__ == "__main__":
    main()
