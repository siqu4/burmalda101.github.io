from flask import Flask, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import time

app = Flask(__name__)

# ==========================================
# НАСТРОЙКИ
# ==========================================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

DATABASE = "sky_dodge.db"

# Максимальный допустимый счёт,
# который можно отправить за один запрос.
MAX_SCORE = 10_000_000

# Максимальный уровень.
MAX_LEVEL = 1000


# ==========================================
# DATABASE
# ==========================================

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():

    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
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


init_db()


# ==========================================
# HELPERS
# ==========================================

def get_current_user():

    user_id = session.get("user_id")

    if not user_id:
        return None

    db = get_db()

    user = db.execute(
        """
        SELECT id, username, created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    db.close()

    return user


def clean_username(username):

    if not isinstance(username, str):
        return None

    username = username.strip()

    if len(username) < 3:
        return None

    if len(username) > 20:
        return None

    # Разрешаем буквы, цифры, _, -
    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "_-"
    )

    if not all(
        char in allowed
        for char in username
    ):
        return None

    return username


# ==========================================
# REGISTER
# ==========================================

@app.route(
    "/api/register",
    methods=["POST"]
)
def register():

    data = request.get_json(
        silent=True
    ) or {}

    username = clean_username(
        data.get("username")
    )

    password = data.get(
        "password"
    )


    if not username:

        return jsonify({
            "success": False,
            "error":
                "Ник должен содержать 3–20 символов. "
                "Разрешены буквы, цифры, _ и -."
        }), 400


    if not isinstance(
        password,
        str
    ) or len(password) < 6:

        return jsonify({
            "success": False,
            "error":
                "Пароль должен содержать минимум 6 символов."
        }), 400


    if len(password) > 128:

        return jsonify({
            "success": False,
            "error":
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
            "error":
                "Этот ник уже занят."
        }), 409


    password_hash =
        generate_password_hash(
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
        "message":
            "Аккаунт успешно создан.",
        "user": {
            "id": user_id,
            "username": username
        }
    })


# ==========================================
# LOGIN
# ==========================================

@app.route(
    "/api/login",
    methods=["POST"]
)
def login():

    data = request.get_json(
        silent=True
    ) or {}


    username = clean_username(
        data.get("username")
    )

    password = data.get(
        "password"
    )


    if not username or not password:

        return jsonify({
            "success": False,
            "error":
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
            "error":
                "Неверный ник или пароль."
        }), 401


    if not check_password_hash(
        user["password_hash"],
        password
    ):

        return jsonify({
            "success": False,
            "error":
                "Неверный ник или пароль."
        }), 401


    session.clear()
    session["user_id"] =
        user["id"]


    return jsonify({
        "success": True,
        "message":
            "Вы успешно вошли.",
        "user": {
            "id":
                user["id"],
            "username":
                user["username"]
        }
    })


# ==========================================
# LOGOUT
# ==========================================

@app.route(
    "/api/logout",
    methods=["POST"]
)
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message":
            "Вы вышли из аккаунта."
    })


# ==========================================
# CURRENT USER
# ==========================================

@app.route(
    "/api/me",
    methods=["GET"]
)
def me():

    user =
        get_current_user()


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
            "id":
                user["id"],

            "username":
                user["username"]
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


# ==========================================
# SAVE SCORE
# ==========================================

@app.route(
    "/api/score",
    methods=["POST"]
)
def save_score():

    user =
        get_current_user()


    if not user:

        return jsonify({
            "success": False,
            "error":
                "Нужно войти в аккаунт."
        }), 401


    data = request.get_json(
        silent=True
    ) or {}


    try:

        score = int(
            data.get(
                "score",
                0
            )
        )

        level = int(
            data.get(
                "level",
                1
            )
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "success": False,
            "error":
                "Некорректный результат."
        }), 400


    # Защита от отрицательных значений.

    score =
        max(
            0,
            score
        )

    level =
        max(
            1,
            level
        )


    # Защита от совсем нереальных значений.

    if score > MAX_SCORE:

        return jsonify({
            "success": False,
            "error":
                "Слишком большой счёт."
        }), 400


    if level > MAX_LEVEL:

        return jsonify({
            "success": False,
            "error":
                "Некорректный уровень."
        }), 400


    # Дополнительная проверка:
    # каждые 50 очков соответствует уровню.

    expected_level =
        min(
            MAX_LEVEL,
            (score // 50) + 1
        )


    if level > expected_level:

        level =
            expected_level


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


    old_score =
        old["best_score"]
        if old else 0


    old_level =
        old["best_level"]
        if old else 1


    new_record = (
        score >
        old_score
    )


    if score > old_score:

        best_score =
            score

    else:

        best_score =
            old_score


    best_level =
        max(
            old_level,
            level
        )


    now =
        int(time.time())


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


# ==========================================
# LEADERBOARD
# ==========================================

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
        ON users.id =
           scores.user_id

        WHERE scores.best_score >= 0

        ORDER BY
            scores.best_score DESC,
            scores.best_level DESC,
            scores.updated_at ASC

        LIMIT 100
        """
    ).fetchall()


    db.close()


    result = []


    for index, row in enumerate(
        rows,
        start=1
    ):

        result.append({

            "position":
                index,

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
            result
    })


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route(
    "/api/health",
    methods=["GET"]
)
def health():

    return jsonify({
        "success": True,
        "status": "online"
    })


# ==========================================
# MAIN
# ==========================================

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
