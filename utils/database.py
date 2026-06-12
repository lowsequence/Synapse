import sqlite3
from typing import Dict, Any, Optional, List
import json

def init_db():
    conn = sqlite3.connect('database/antinuke.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS antinuke_status 
                 (guild_id TEXT PRIMARY KEY, status TEXT)''')

    conn.commit()
    conn.close()

    conn = sqlite3.connect('database/premium_codes.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS premium_users 
                 (user_id INTEGER, guild_id INTEGER, expires_at TEXT,
                  PRIMARY KEY (user_id, guild_id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS premium_codes
                 (code TEXT PRIMARY KEY, duration TEXT, used INTEGER DEFAULT 0)''')

    conn.commit()
    conn.close()

    conn = sqlite3.connect('database/np.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS np 
                 (id INTEGER PRIMARY KEY, expiry_time TEXT)''')

    conn.commit()
    conn.close()

    conn = sqlite3.connect('database/antinuke.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS guild_config
                 (guild_id TEXT PRIMARY KEY,
                  prefix TEXT DEFAULT '.',
                  owners TEXT DEFAULT '[]',
                  whitelisted TEXT DEFAULT '[]',
                  punishment TEXT DEFAULT 'Ban')''')

    c.execute('''CREATE TABLE IF NOT EXISTS antinuke_modules
                 (guild_id TEXT PRIMARY KEY,
                  antiban TEXT DEFAULT 'on',
                  antibot TEXT DEFAULT 'on',
                  antichannel TEXT DEFAULT 'on',
                  antiemoji TEXT DEFAULT 'on',
                  antiguild TEXT DEFAULT 'on',
                  antikick TEXT DEFAULT 'on',
                  antiping TEXT DEFAULT 'on',
                  antiprune TEXT DEFAULT 'on',
                  antirole TEXT DEFAULT 'on',
                  antiweb TEXT DEFAULT 'on',
                  antimember TEXT DEFAULT 'on')''')

    c.execute('''CREATE TABLE IF NOT EXISTS antinuke_logs
                 (guild_id TEXT PRIMARY KEY,
                  channel_logs INTEGER DEFAULT NULL,
                  mod_logs INTEGER DEFAULT NULL,
                  guild_logs INTEGER DEFAULT NULL,
                  role_logs INTEGER DEFAULT NULL)''')

    c.execute('''CREATE TABLE IF NOT EXISTS antinuke_thresholds
                 (guild_id TEXT PRIMARY KEY,
                  channel_threshold INTEGER DEFAULT 1,
                  ban_threshold INTEGER DEFAULT 1,
                  kick_threshold INTEGER DEFAULT 1,
                  role_threshold INTEGER DEFAULT 1,
                  webhook_threshold INTEGER DEFAULT 1)''')

    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect('database/antinuke.db')

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_config(guild_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    conn.row_factory = dict_factory
    c = conn.cursor()

    c.execute('SELECT * FROM guild_config WHERE guild_id = ?', (guild_id,))
    result = c.fetchone()

    if not result:
        default_config = {
            'guild_id': guild_id,
            'prefix': '?',
            'owners': '[]',
            'whitelisted': '[]',
            'punishment': 'Ban'
        }
        c.execute('''INSERT INTO guild_config 
                     (guild_id, prefix, owners, whitelisted, punishment)
                     VALUES (?, ?, ?, ?, ?)''',
                  (guild_id, '?', '[]', '[]', 'Ban'))
        conn.commit()
        result = default_config

    for key in ['owners', 'whitelisted']:
        if isinstance(result[key], str):
            result[key] = json.loads(result[key])

    conn.close()
    return result

def update_config(guild_id: str, data: Dict[str, Any]):
    conn = get_db_connection()
    c = conn.cursor()

    data_copy = data.copy()
    for key in ['owners', 'whitelisted']:
        if key in data_copy and isinstance(data_copy[key], list):
            data_copy[key] = json.dumps(data_copy[key])

    c.execute('''INSERT OR REPLACE INTO guild_config 
                 (guild_id, prefix, owners, whitelisted, punishment)
                 VALUES (?, ?, ?, ?, ?)''',
              (guild_id, data_copy.get('prefix', '?'),
               data_copy.get('owners', '[]'),
               data_copy.get('whitelisted', '[]'),
               data_copy.get('punishment', 'Ban')))

    conn.commit()
    conn.close()

def get_antinuke_status(guild_id: str) -> str:
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('SELECT status FROM antinuke_status WHERE guild_id = ?', (guild_id,))
    result = c.fetchone()

    if not result:
        c.execute('INSERT INTO antinuke_status (guild_id, status) VALUES (?, ?)',
                 (guild_id, 'off'))
        conn.commit()
        status = 'off'
    else:
        status = result[0]

    conn.close()
    return status

def update_antinuke_status(guild_id: str, status: str):
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('INSERT OR REPLACE INTO antinuke_status (guild_id, status) VALUES (?, ?)',
              (guild_id, status))

    conn.commit()
    conn.close()

def get_module_status(guild_id: str, module: str) -> str:
    conn = get_db_connection()
    c = conn.cursor()

    c.execute(f'SELECT {module} FROM antinuke_modules WHERE guild_id = ?', (guild_id,))
    result = c.fetchone()

    if not result:
        c.execute(f'INSERT INTO antinuke_modules (guild_id, {module}) VALUES (?, ?)',
                 (guild_id, 'on'))
        conn.commit()
        status = 'on'
    else:
        status = result[0]

    conn.close()
    return status

def update_module_status(guild_id: str, module: str, status: str):
    conn = get_db_connection()
    c = conn.cursor()

    c.execute(f'INSERT OR REPLACE INTO antinuke_modules (guild_id, {module}) VALUES (?, ?)',
              (guild_id, status))

    conn.commit()
    conn.close()

def get_logs_channel(guild_id: str, log_type: str) -> Optional[int]:
    conn = get_db_connection()
    c = conn.cursor()

    c.execute(f'SELECT {log_type}_logs FROM antinuke_logs WHERE guild_id = ?', (guild_id,))
    result = c.fetchone()

    if not result:
        c.execute('INSERT INTO antinuke_logs (guild_id) VALUES (?)', (guild_id,))
        conn.commit()
        channel_id = None
    else:
        channel_id = result[0]

    conn.close()
    return channel_id

def update_logs_channel(guild_id: str, log_type: str, channel_id: Optional[int]):
    conn = get_db_connection()
    c = conn.cursor()

    c.execute(f'INSERT OR REPLACE INTO antinuke_logs (guild_id, {log_type}_logs) VALUES (?, ?)',
              (guild_id, channel_id))

    conn.commit()
    conn.close()

def get_threshold(guild_id: str, threshold_type: str) -> int:
    conn = get_db_connection()
    c = conn.cursor()

    c.execute(f'SELECT {threshold_type}_threshold FROM antinuke_thresholds WHERE guild_id = ?',
              (guild_id,))
    result = c.fetchone()

    if not result:
        c.execute('INSERT INTO antinuke_thresholds (guild_id) VALUES (?)', (guild_id,))
        conn.commit()
        threshold = 1
    else:
        threshold = result[0]

    conn.close()
    return threshold

def update_threshold(guild_id: str, threshold_type: str, value: int):
    conn = get_db_connection()
    c = conn.cursor()

    c.execute(f'''INSERT OR REPLACE INTO antinuke_thresholds 
                 (guild_id, {threshold_type}_threshold) VALUES (?, ?)''',
              (guild_id, value))

    conn.commit()
    conn.close()