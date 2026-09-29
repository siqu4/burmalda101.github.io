import os
import sqlite3
import time
import secrets

from flask import Flask, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Секретный ключ для сессий
app.secret_key = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "sky_dodge.db")


# =========================================================
# БАЗА ДАННЫХ
# =========================================================

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_database():
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            best_score INTEGER NOT NULL DEFAULT 0,
            best_level INTEGER NOT NULL DEFAULT 1,
            updated_at INTEGER NOT NULL,

            FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
        )
    """)

    db.commit()
    db.close()


init_database()


# =========================================================
# ПОЛУЧЕНИЕ ПОЛЬЗОВАТЕЛЯ
# =========================================================

def get_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    db = get_db()

    user = db.execute(
        """
        SELECT id, username
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    db.close()

    return user


# =========================================================
# ПРОВЕРКА НИКА
# =========================================================

def validate_username(username):

    if not isinstance(username, str):
        return None

    username = username.strip()

    if len(username) < 3:
        return None

    if len(username) > 20:
        return None

    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_-"
    )

    for char in username:

        if char not in allowed:
            return None

    return username


# =========================================================
# ГЛАВНАЯ СТРАНИЦА
# =========================================================

@app.route("/")
def index():

    index_file = os.path.join(
        BASE_DIR,
        "index.html"
    )

    if not os.path.exists(index_file):

        return """
        <h1>SKY DODGE</h1>
        <p>Файл index.html не найден.</p>
        """, 404

    with open(
        index_file,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


# =========================================================
# РЕГИСТРАЦИЯ
# =========================================================

@app.route(
    "/api/register",
    methods=["POST"]
)
def register():

    data = request.get_json(
        silent=True
    ) or {}

    username = validate_username(
        data.get("username")
    )

    password = data.get("password")


    if not username:

        return jsonify({
            "success": False,
            "message":
                "Ник должен содержать от 3 до 20 символов."
        }), 400


    if not isinstance(password, str):

        return jsonify({
            "success": False,
            "message": "Введите пароль."
        }), 400


    if len(password) < 6:

        return jsonify({
            "success": False,
            "message":
                "Пароль должен содержать минимум 6 символов."
        }), 400


    if len(password) > 128:

        return jsonify({
            "success": False,
            "message":
                "Пароль слишком длинный."
        }), 400


    db = get_db()

    existing = db.execute(
        """
        SELECT id
        FROM users
        WHERE username = ?
        """,
        (username,)
    ).fetchone()


    if existing:

        db.close()

        return jsonify({
            "success": False,
            "message":
                "Такой ник уже существует."
        }), 409


    password_hash = generate_password_hash(
        password
    )

    now = int(time.time())


    cursor = db.execute(
        """
        INSERT INTO users
        (
            username,
            password_hash,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            username,
            password_hash,
            now
        )
    )


    user_id = cursor.lastrowid


    db.execute(
        """
        INSERT INTO scores
        (
            user_id,
            best_score,
            best_level,
            updated_at
        )
        VALUES (?, 0, 1, ?)
        """,
        (
            user_id,
            now
        )
    )


    db.commit()
    db.close()


    session.clear()
    session["user_id"] = user_id


    return jsonify({
        "success": True,
        "message": "Аккаунт создан.",
        "user": {
            "id": user_id,
            "username": username
        }
    })


# =========================================================
# ВХОД
# =========================================================

@app.route(
    "/api/login",
    methods=["POST"]
)
def login():

    data = request.get_json(
        silent=True
    ) or {}


    username = validate_username(
        data.get("username")
    )

    password = data.get("password")


    if not username or not password:

        return jsonify({
            "success": False,
            "message":
                "Введите ник и пароль."
        }), 400


    db = get_db()

    user = db.execute(
        """
        SELECT
            id,
            username,
            password_hash
        FROM users
        WHERE username = ?
        """,
        (username,)
    ).fetchone()

    db.close()


    if not user:

        return jsonify({
            "success": False,
            "message":
                "Неверный ник или пароль."
        }), 401


    if not check_password_hash(
        user["password_hash"],
        password
    ):

        return jsonify({
            "success": False,
            "message":
                "Неверный ник или пароль."
        }), 401


    session.clear()
    session["user_id"] = user["id"]


    return jsonify({
        "success": True,
        "message": "Вход выполнен.",
        "user": {
            "id": user["id"],
            "username": user["username"]
        }
    })


# =========================================================
# ВЫХОД
# =========================================================

@app.route(
    "/api/logout",
    methods=["POST"]
)
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Вы вышли из аккаунта."
    })


# =========================================================
# ТЕКУЩИЙ ПОЛЬЗОВАТЕЛЬ
# =========================================================

@app.route(
    "/api/me",
    methods=["GET"]
)
def me():

    user = get_user()


    if not user:

        return jsonify({
            "success": True,
            "logged_in": False
        })


    db = get_db()

    score = db.execute(
        """
        SELECT
            best_score,
            best_level
        FROM scores
        WHERE user_id = ?
        """,
        (user["id"],)
    ).fetchone()

    db.close()


    return jsonify({
        "success": True,
        "logged_in": True,

        "user": {
            "id": user["id"],
            "username": user["username"]
        },

        "score": {
            "best_score":
                score["best_score"]
                if score else 0,

            "best_level":
                score["best_level"]
                if score else 1
        }
    })


# =========================================================
# СОХРАНЕНИЕ РЕКОРДА
# =========================================================

@app.route(
    "/api/score",
    methods=["POST"]
)
def save_score():

    user = get_user()


    if not user:

        return jsonify({
            "success": False,
            "logged_in": False,
            "message":
                "Войдите в аккаунт."
        }), 401


    data = request.get_json(
        silent=True
    ) or {}


    try:

        score = int(
            data.get("score", 0)
        )

        level = int(
            data.get("level", 1)
        )

    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "message":
                "Некорректный счёт."
        }), 400


    if score < 0:

        return jsonify({
            "success": False,
            "message":
                "Счёт не может быть отрицательным."
        }), 400


    # Защита от совсем нереальных значений
    if score > 10_000_000:

        return jsonify({
            "success": False,
            "message":
                "Слишком большой счёт."
        }), 400


    if level < 1:
        level = 1


    # В твоей игре:
    # каждые 50 очков = новый уровень

    expected_level = (
        score // 50
    ) + 1


    if level > expected_level:

        level = expected_level


    db = get_db()


    old = db.execute(
        """
        SELECT
            best_score,
            best_level
        FROM scores
        WHERE user_id = ?
        """,
        (user["id"],)
    ).fetchone()


    old_score = (
        old["best_score"]
        if old else 0
    )

    old_level = (
        old["best_level"]
        if old else 1
    )


    new_record = score > old_score


    if new_record:

        best_score = score
        best_level = level

    else:

        best_score = old_score
        best_level = old_level


    now = int(time.time())


    db.execute(
        """
        INSERT INTO scores
        (
            user_id,
            best_score,
            best_level,
            updated_at
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET

            best_score =
                excluded.best_score,

            best_level =
                excluded.best_level,

            updated_at =
                excluded.updated_at
        """,
        (
            user["id"],
            best_score,
            best_level,
            now
        )
    )


    db.commit()
    db.close()


    return jsonify({

        "success": True,

        "new_record":
            new_record,

        "best_score":
            best_score,

        "best_level":
            best_level
    })


# =========================================================
# ТАБЛИЦА ЛИДЕРОВ
# =========================================================

@app.route(
    "/api/leaderboard",
    methods=["GET"]
)
def leaderboard():

    db = get_db()


    rows = db.execute(
        """
        SELECT
            users.username,
            scores.best_score,
            scores.best_level

        FROM scores

        JOIN users
        ON users.id = scores.user_id

        ORDER BY
            scores.best_score DESC,
            scores.best_level DESC,
            scores.updated_at ASC

        LIMIT 100
        """
    ).fetchall()


    db.close()


    leaderboard_data = []


    for position, row in enumerate(
        rows,
        start=1
    ):

        leaderboard_data.append({

            "position":
                position,

            "username":
                row["username"],

            "score":
                row["best_score"],

            "level":
                row["best_level"]
        })


    return jsonify({
        "success": True,
        "leaderboard":
            leaderboard_data
    })


# =========================================================
# ПРОВЕРКА СЕРВЕРА
# =========================================================

@app.route(
    "/api/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "success": True,

        "status": "online",

        "game": "SKY DODGE"
    })


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
