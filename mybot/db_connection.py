import sqlite3
from UserStatus import UserStatus
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG 
)
def create_db():
    """Создает таблицу пользователей, если она не существует."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            status TEXT,
            partner_id TEXT
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def insert_user(user_id):
    """Добавляет нового пользователя в базу данных, если он еще не существует."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if c.fetchone():
        conn.close()
        logging.debug(f"Пользователь {user_id} уже существует.")
        return
    c.execute("INSERT INTO users (user_id, status, partner_id) VALUES (?, ?, ?)", (user_id, UserStatus.IDLE, None))
    conn.commit()
    conn.close()
    logging.debug(f"Пользователь {user_id} добавлен с статусом {UserStatus.IDLE}.")

def remove_user(user_id):
    """Удаляет пользователя из базы данных и обновляет статус партнера, если он существует."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    partner_id = get_partner_id(user_id)
    if partner_id:
        c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (partner_id,))
        set_user_status(partner_id, UserStatus.PARTNER_LEFT)
    c.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_user_status(user_id):
    """Возвращает статус пользователя."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    c.execute("SELECT status FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else UserStatus.IDLE

def set_user_status(user_id, new_status):
    """Устанавливает новый статус для пользователя."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET status=? WHERE user_id=?", (new_status, user_id))
    conn.commit()
    conn.close()
    logging.debug(f"Статус пользователя {user_id} изменён на {new_status}.")

def get_partner_id(user_id):
    """Возвращает ID партнера пользователя."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    c.execute("SELECT partner_id FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def couple(current_user_id):
    """Соединяет двух пользователей в чате."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE status=? AND user_id!=?", (UserStatus.IN_SEARCH, current_user_id))
    other_user_id = c.fetchone()
    if not other_user_id:
        conn.close()
        return None
    other_user_id = other_user_id[0]
    c.execute("UPDATE users SET partner_id=? WHERE user_id=?", (other_user_id, current_user_id))
    c.execute("UPDATE users SET partner_id=? WHERE user_id=?", (current_user_id, other_user_id))
    c.execute("UPDATE users SET status=? WHERE user_id=?", (UserStatus.COUPLED, current_user_id))
    c.execute("UPDATE users SET status=? WHERE user_id=?", (UserStatus.COUPLED, other_user_id))
    conn.commit()
    conn.close()
    return other_user_id

def uncouple(user_id):
    """Разъединяет пользователя с его партнером."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    partner_id = get_partner_id(user_id)
    if not partner_id:
        conn.close()
        return
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (user_id,))
    c.execute("UPDATE users SET partner_id=NULL WHERE user_id=?", (partner_id,))
    c.execute("UPDATE users SET status=? WHERE user_id=?", (UserStatus.IDLE, user_id))
    c.execute("UPDATE users SET status=? WHERE user_id=?", (UserStatus.IDLE, partner_id))
    conn.commit()
    conn.close()

def retrieve_users_number():
    """Возвращает количество пользователей и количество пар."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users_number = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE status=?", (UserStatus.COUPLED,))
    paired_users_number = c.fetchone()[0]
    conn.close()
    return total_users_number, paired_users_number

def reset_users_status():
    """Сбрасывает статус всех пользователей на IDLE при перезапуске бота."""
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET status=?, partner_id=NULL", (UserStatus.IDLE,))
    conn.commit()
    conn.close()

def retrieve_detailed_statistics():
    conn = sqlite3.connect('chatbot_database.db')
    c = conn.cursor()

    # Пример запросов к базе данных
    total_messages = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    active_users = c.execute("SELECT COUNT(*) FROM users WHERE status = 'in_search'").fetchone()[0]
    idle_users = c.execute("SELECT COUNT(*) FROM users WHERE status = 'idle'").fetchone()[0]
    most_active_user = c.execute("""
        SELECT user_id, COUNT(*) as message_count 
        FROM messages 
        GROUP BY user_id 
        ORDER BY message_count DESC 
        LIMIT 1
    """).fetchone()

    conn.close()
    return total_messages, active_users, idle_users, most_active_user
