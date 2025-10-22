#!/usr/bin/env python3
"""Скрипт для проверки качества документации модуля.

Этот скрипт запускает pydocstyle и interrogate для проверки
соответствия документации стандартам Google Style и измерения покрытия.

Usage:
    python scripts/check_docs.py <module_path>
    python scripts/check_docs.py database/
    python scripts/check_docs.py services/lesson_service.py
"""

import sys
import subprocess
from pathlib import Path


def run_command(cmd: list[str], description: str) -> tuple[int, str]:
    """Выполняет команду и возвращает результат.
    
    Args:
        cmd: Список аргументов команды
        description: Описание проверки для вывода
        
    Returns:
        Tuple из (код возврата, вывод команды)
    """
    print(f"\n{'='*60}")
    print(f"🔍 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        output = result.stdout + result.stderr
        print(output)
        
        return result.returncode, output
    except FileNotFoundError:
        error_msg = f"❌ Команда не найдена: {cmd[0]}\nУстановите зависимости: pip install -r requirements.txt"
        print(error_msg)
        return 1, error_msg


def check_module_docs(module_path: str) -> int:
    """Проверяет документацию модуля.
    
    Запускает pydocstyle для проверки формата и interrogate
    для измерения покрытия документацией.
    
    Args:
        module_path: Путь к модулю или файлу для проверки
        
    Returns:
        0 если все проверки прошли успешно, иначе 1
    """
    path = Path(module_path)
    
    if not path.exists():
        print(f"❌ Путь не существует: {module_path}")
        return 1
    
    print(f"\n📚 Проверка документации: {module_path}")
    
    # Проверка формата с pydocstyle
    pydocstyle_code, _ = run_command(
        ["pydocstyle", module_path],
        "Проверка соответствия Google Style (pydocstyle)"
    )
    
    # Проверка покрытия с interrogate
    interrogate_code, _ = run_command(
        ["interrogate", "-v", "--fail-under=90", module_path],
        "Проверка покрытия документацией (interrogate)"
    )
    
    # Итоговый результат
    print(f"\n{'='*60}")
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ")
    print(f"{'='*60}")
    
    if pydocstyle_code == 0 and interrogate_code == 0:
        print("✅ Все проверки пройдены успешно!")
        print(f"✅ Формат: Google Style соблюден")
        print(f"✅ Покрытие: >= 90%")
        return 0
    else:
        print("❌ Обнаружены проблемы:")
        if pydocstyle_code != 0:
            print("  - Несоответствие Google Style формату")
        if interrogate_code != 0:
            print("  - Покрытие документацией < 90%")
        return 1


def main():
    """Главная функция скрипта."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_docs.py <module_path>")
        print("\nПримеры:")
        print("  python scripts/check_docs.py database/")
        print("  python scripts/check_docs.py services/lesson_service.py")
        sys.exit(1)
    
    module_path = sys.argv[1]
    exit_code = check_module_docs(module_path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
