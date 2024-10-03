import sqlite3
import os
import sys
import appdirs
import logging

def get_db_connection():
    db_path = get_db_path()
    logging.info(f"Attempting to connect to database at: {db_path}")
    try:
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.text_factory = str
        logging.info("Database connection established successfully")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Error connecting to database: {str(e)}")
        raise

def get_db_path():
    app_dir = appdirs.user_data_dir("InvoicingApp", "KAEFER Industrie GmbH")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    return os.path.join(app_dir, 'invoicing.db')

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'assets', 'LV_FILES', relative_path)