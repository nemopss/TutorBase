#!/usr/bin/env python
"""Quick test script for notification text updates."""

import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Test 1: Import texts module
print("Test 1: Importing texts module...")
try:
    from utils import texts
    print("✅ Texts module imported successfully")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Check new text constants exist
print("\nTest 2: Checking new text constants...")
required_constants = [
    'PAYMENT_CONFIRM_BUTTON',
    'PAYMENT_DECLINE_BUTTON',
    'PAYMENT_CONFIRM_REPLY',
    'PAYMENT_DECLINE_REPLY',
    'PAYMENT_CONFIRM_LOG',
    'PAYMENT_DECLINE_LOG',
    'PAYMENT_REMINDER_WEEK_BEFORE',
    'PAYMENT_REMINDER_DAY_BEFORE',
]

for const in required_constants:
    if hasattr(texts, const):
        value = getattr(texts, const)
        print(f"✅ {const}: {value[:50]}...")
    else:
        print(f"❌ Missing constant: {const}")
        sys.exit(1)

# Test 3: Check updated text constants
print("\nTest 3: Checking updated text constants...")
updated_checks = [
    ('START_MESSAGE', 'Привет! Выбери'),
    ('HOMEWORK_REMINDER_MESSAGE', 'как минимум за час'),
    ('REMINDER_DAY_BEFORE_MESSAGE', 'Всё в силе'),
    ('PACKAGE_RENEWAL_REMINDER_MESSAGE', 'Скажи, пожалуйста'),
    ('GET_PRICES_TEXT', 'диагностика'),
    ('PROMPT_FOR_LEVEL', 'Новичок'),
]

for const_name, expected_substring in updated_checks:
    value = getattr(texts, const_name)
    if expected_substring in value:
        print(f"✅ {const_name} contains '{expected_substring}'")
    else:
        print(f"❌ {const_name} missing '{expected_substring}'")
        print(f"   Value: {value[:100]}")
        sys.exit(1)

# Test 4: Check placeholder format
print("\nTest 4: Checking placeholder formats...")
week_before = texts.PAYMENT_REMINDER_WEEK_BEFORE
day_before = texts.PAYMENT_REMINDER_DAY_BEFORE

if '{name}' in week_before and '{last_lesson_date}' in week_before:
    print(f"✅ PAYMENT_REMINDER_WEEK_BEFORE has correct placeholders")
else:
    print(f"❌ PAYMENT_REMINDER_WEEK_BEFORE missing placeholders")
    sys.exit(1)

if '{name}' in day_before:
    print(f"✅ PAYMENT_REMINDER_DAY_BEFORE has correct placeholders")
else:
    print(f"❌ PAYMENT_REMINDER_DAY_BEFORE missing placeholders")
    sys.exit(1)

# Test 5: Check syntax of modified files
print("\nTest 5: Checking Python syntax...")
import py_compile
files_to_check = [
    'utils/texts.py',
    'handlers/reminders.py',
    'services/reminders.py',
    'services/package_scheduler.py',
]

for filepath in files_to_check:
    try:
        py_compile.compile(filepath, doraise=True)
        print(f"✅ {filepath} - syntax OK")
    except py_compile.PyCompileError as e:
        print(f"❌ {filepath} - syntax error: {e}")
        sys.exit(1)

print("\n" + "="*50)
print("✅ All tests passed!")
print("="*50)
