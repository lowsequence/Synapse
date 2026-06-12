import sqlite3
import os
from typing import Optional, Union

class ColorDatabase:
    def __init__(self, db_path: str = "userDB/colors.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_colors (
                    user_id TEXT PRIMARY KEY,
                    color_value TEXT NOT NULL
                )
            """)
            conn.commit()

    def get_color(self, user_id: str) -> Optional[Union[int, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT color_value FROM user_colors WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return None
                
            color_value = result[0]
            return color_value if color_value in ["top", "random"] else int(color_value)

    def set_color(self, user_id: str, color_value: Union[int, str]):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_colors (user_id, color_value)
                VALUES (?, ?)
            """, (user_id, str(color_value)))
            conn.commit()