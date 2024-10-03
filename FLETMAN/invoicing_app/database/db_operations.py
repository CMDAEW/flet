import sqlite3
import os
import sys

def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.text_factory = str
    return conn

def get_db_path():
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(app_dir, 'invoicing.db')

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'assets', 'LV_FILES', relative_path)