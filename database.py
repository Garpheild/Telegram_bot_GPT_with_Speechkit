import logging
import sqlite3
from config import DB_FILE_NAME
import os


def create_table():
    try:
        with sqlite3.connect(DB_FILE_NAME) as con:
            cur = con.cursor()
            cur.execute('''
            CREATE TABLE IF NOT EXISTS user_data(
            id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            used_gpt_tokens INTEGER DEFAULT 0,
            used_stt_blocks INTEGER DEFAULT 0,
            used_tts_tokens INTEGER DEFAULT 0);
                ''')
            con.commit()
    except Exception as e:
        logging.error(e)


def get_data_from_db(chat_id, columns="chat_id"):
    try:
        with sqlite3.connect(DB_FILE_NAME) as con:
            cur = con.cursor()
            data = cur.execute(f'''
            SELECT {columns}
            FROM user_data 
            WHERE chat_id = {chat_id};
                ''')
            return [_ for _ in data]
    except Exception as e:
        logging.error(e)


def insert_user_to_db(chat_id):
    try:
        with sqlite3.connect(DB_FILE_NAME) as con:
            cur = con.cursor()
            if not get_data_from_db(chat_id):
                cur.execute(f'''
                INSERT INTO user_data(chat_id)
                VALUES ({chat_id});
                ''')
                con.commit()
    except Exception as e:
        logging.error(e)


def update_db(chat_id, columns: tuple, values: tuple, replace=True):
    try:
        with sqlite3.connect(DB_FILE_NAME) as con:
            cur = con.cursor()
            for column, value in zip(columns, values):
                if replace:
                    cur.execute(f'UPDATE user_data SET {column} = ? WHERE chat_id = {chat_id};', (value,))
                else:
                    cur.execute(f'UPDATE user_data SET {column} = {column} || ? WHERE chat_id = {chat_id};', (value,))
        con.commit()
    except Exception as e:
        logging.error(e)


if os.path.exists(DB_FILE_NAME):
    create_table()
