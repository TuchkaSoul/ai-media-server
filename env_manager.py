#!/usr/bin/env python3
"""
env_manager.py — универсальный менеджер окружений (venv + conda)
для проекта MediaStorage Server
---------------------------------------------------------------
Позволяет:
- Создавать / обновлять / удалять окружения
- Активировать venv или conda окружение
- Проверять статус и управлять через консольное меню
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
from InquirerPy import inquirer

# ───────────────────────────────
# Конфигурация путей
# ───────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
ENVS_DIR = PROJECT_ROOT / "envs"
VENV_PATH = ENVS_DIR / "backend_env"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
CONDA_ENV_NAME = "ml_env"
CONDA_ENV_FILE = PROJECT_ROOT / "environment.yml"


# ───────────────────────────────
# Вспомогательные функции
# ───────────────────────────────

def run(cmd, check=True):
    """Упрощённый вызов команд"""
    print(f"\n🔧 Выполняю: {' '.join(cmd)}\n")
    subprocess.run(cmd, check=check)


def is_tool_installed(tool):
    """Проверяет наличие утилиты"""
    return subprocess.call([ tool,'--version',], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def is_venv_active():
    return os.environ.get("VIRTUAL_ENV") is not None


def is_conda_active():
    return os.environ.get("CONDA_DEFAULT_ENV") == CONDA_ENV_NAME


def run_in_shell(command):
    """Запускает новую оболочку"""
    if platform.system() == "Windows":
        subprocess.run(["cmd", "/k", command])
    else:
        subprocess.run(["bash", "-c", f"{command}; exec bash"])


# ───────────────────────────────
# Управление VENV
# ───────────────────────────────

def create_venv():
    if VENV_PATH.exists():
        print("⚠️  Venv уже существует.")
        return
    ENVS_DIR.mkdir(exist_ok=True)
    run([sys.executable, "-m", "venv", str(VENV_PATH)])
    print("✅ Venv успешно создан.")
    if REQUIREMENTS_FILE.exists():
        run([str(VENV_PATH / "bin" / "pip"), "install", "-r", str(REQUIREMENTS_FILE)])


def update_venv():
    if not VENV_PATH.exists():
        print("❌ Venv не найден. Сначала создайте его.")
        return
    if REQUIREMENTS_FILE.exists():
        run([str(VENV_PATH / "bin" / "pip"), "install", "--upgrade", "-r", str(REQUIREMENTS_FILE)])
        print("✅ Venv обновлён.")


def delete_venv():
    if not VENV_PATH.exists():
        print("ℹ️  Venv не существует.")
        return
    import shutil
    shutil.rmtree(VENV_PATH)
    print("🗑️  Venv удалён.")


def activate_venv():
    if not VENV_PATH.exists():
        print("❌ Venv не найден.")
        return
    activate_cmd = (
        f"{VENV_PATH}\\Scripts\\activate" if platform.system() == "Windows"
        else f"source {VENV_PATH}/bin/activate"
    )
    run_in_shell(activate_cmd)


# ───────────────────────────────
# Управление CONDA
# ───────────────────────────────

def create_conda_env():
    if not is_tool_installed("conda"):
        print("❌ Conda не установлена.")
        return
    run(["conda", "env", "create", "-f", str(CONDA_ENV_FILE)])
    print("✅ Conda окружение создано.")


def update_conda_env():
    if not is_tool_installed("conda"):
        print("❌ Conda не установлена.")
        return
    run(["conda", "env", "update", "-f", str(CONDA_ENV_FILE), "--prune"])
    print("✅ Conda окружение обновлено.")


def delete_conda_env():
    if not is_tool_installed("conda"):
        print("❌ Conda не установлена.")
        return
    run(["conda", "env", "remove", "-n", CONDA_ENV_NAME])
    print("🗑️  Conda окружение удалено.")


def activate_conda():
    if not is_tool_installed("conda"):
        print("❌ Conda не установлена.")
        return
    run_in_shell(f"conda activate {CONDA_ENV_NAME}")


# ───────────────────────────────
# Прочее
# ───────────────────────────────

def deactivate_env():
    if is_conda_active():
        print("Чтобы отключить conda окружение, выполните: conda deactivate")
        run_in_shell("conda deactivate")
        print("Успешно")
    elif is_venv_active():
        print("Чтобы отключить venv, выполните: deactivate")
        run_in_shell("deactivate")
        print("Успешно")
    else:
        print("ℹ️  Нет активного окружения.")


def check_status():
    print("\n📦 Статус окружений:")
    if is_venv_active():
        print(f"✅ Активировано venv: {os.environ['VIRTUAL_ENV']}")
    elif is_conda_active():
        print(f"✅ Активировано conda: {os.environ['CONDA_DEFAULT_ENV']}")
    else:
        print("⚪ Окружение не активно.")
    print("──────────────────────────────\n")


# ───────────────────────────────
# Главное меню
# ───────────────────────────────

def interactive_menu():
    while True:
        choice = inquirer.select(
            message="Выберите действие:",
            choices=[
                "🆕 Создать окружение",
                "🔄 Обновить окружение",
                "🗑️  Удалить окружение",
                "▶ Активировать окружение",
                "🔻 Отключить окружение",
                "ℹ️  Проверить статус",
                "❌ Выход"
            ],
        ).execute()

        if choice == "🆕 Создать окружение":
            env_type = inquirer.select(
                message="Тип окружения:",
                choices=["venv (backend_env)", "conda (ml_env)"]
            ).execute()
            if "venv" in env_type:
                create_venv()
            else:
                create_conda_env()

        elif choice == "🔄 Обновить окружение":
            env_type = inquirer.select(
                message="Какое обновить:",
                choices=["venv (backend_env)", "conda (ml_env)"]
            ).execute()
            if "venv" in env_type:
                update_venv()
            else:
                update_conda_env()

        elif choice == "🗑️  Удалить окружение":
            env_type = inquirer.select(
                message="Какое удалить:",
                choices=["venv (backend_env)", "conda (ml_env)"]
            ).execute()
            if "venv" in env_type:
                delete_venv()
            else:
                delete_conda_env()

        elif choice == "▶ Активировать окружение":
            env_type = inquirer.select(
                message="Какое активировать:",
                choices=["venv (backend_env)", "conda (ml_env)"]
            ).execute()
            if "venv" in env_type:
                activate_venv()
            else:
                activate_conda()

        elif choice == "🔻 Отключить окружение":
            deactivate_env()

        elif choice == "ℹ️  Проверить статус":
            check_status()

        elif choice == "❌ Выход":
            print("👋 Завершение работы менеджера окружений.")
            break


# ───────────────────────────────
# Точка входа
# ───────────────────────────────

if __name__ == "__main__":
    print([sys.executable, "-m", "venv", str(VENV_PATH)])
    interactive_menu()
