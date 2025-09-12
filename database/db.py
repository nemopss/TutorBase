import aiosqlite
from pathlib import Path
from typing import List, Dict, Any
from config import config

db_path = Path(config.DB_PATH)
if not db_path.is_absolute():
    db_path = Path(__file__).parent.parent / db_path

DB_FILE = db_path
DB_FILE.parent.mkdir(parents=True, exist_ok=True)

CREATE_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name TEXT,
    language TEXT,
    level TEXT,
    preferred_time TEXT,
    contact TEXT
);
'''

CREATE_STUDENTS_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    story TEXT NOT NULL,
    photo_file_id TEXT
);
'''


async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.execute(CREATE_STUDENTS_TABLE_SQL)
        # Add photo_file_id column if it doesn't exist
        try:
            await db.execute("ALTER TABLE students ADD COLUMN photo_file_id TEXT")
            await db.commit()
        except aiosqlite.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

async def insert_application(app: Dict[str, Any]):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            '''INSERT INTO applications (created_at, name, language, level, preferred_time, contact)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (app['created_at'], app['name'], app['language'], app['level'], app['preferred_time'], app['contact'])
        )
        await db.commit()

async def fetch_last_n(n: int = 20) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute('SELECT id, created_at, name, language, level, preferred_time, contact FROM applications ORDER BY id DESC LIMIT ?', (n,))
        rows = await cur.fetchall()
        await cur.close()
    result = []
    for r in rows:
        result.append({
            'id': r[0],
            'created_at': r[1],
            'name': r[2],
            'language': r[3],
            'level': r[4],
            'preferred_time': r[5],
            'contact': r[6],
        })
    return result

async def fetch_count() -> int:
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute('SELECT COUNT(*) FROM applications')
        row = await cur.fetchone()
        await cur.close()
    return row[0] if row else 0


async def add_student(name: str, story: str, photo_file_id: str | None = None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT INTO students (name, story, photo_file_id) VALUES (?, ?, ?)", (name, story, photo_file_id))
        await db.commit()

async def get_all_students() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id, name, story, photo_file_id FROM students ORDER BY name")
        rows = await cur.fetchall()
        await cur.close()
        return [dict(row) for row in rows]

async def get_student(student_id: int) -> Dict[str, Any] | None:
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id, name, story, photo_file_id FROM students WHERE id = ?", (student_id,))
        row = await cur.fetchone()
        await cur.close()
        return dict(row) if row else None

async def delete_student(student_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM students WHERE id = ?", (student_id,))
        await db.commit()

async def fetch_all_applications() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute('SELECT id, created_at, name, language, level, preferred_time, contact FROM applications ORDER BY id ASC')
        rows = await cur.fetchall()
        await cur.close()
        return [dict(row) for row in rows]

async def delete_all_applications():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM applications")
        await db.commit()
