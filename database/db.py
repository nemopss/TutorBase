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

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()

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