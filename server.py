```python
import http.server
import json
import os
import time
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8000

SCORES_FILE = "scores.json"


# =========================================================
# Работа с рекордами
# =========================================================

def load_scores():
    """Загрузить рекорды из файла."""

    if not os.path.exists(SCORES_FILE):
        return []

    try:
        with open(
            SCORES_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except (json.JSONDecodeError, OSError):
        return []


def save_scores(scores):
    """Сохранить рекорды в файл."""

    temporary_file = SCORES_FILE + ".tmp"

    with open(
        temporary_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            scores,
            file,
            ensure_ascii=False,
            indent=4
        )

    os.replace(
        temporary_file,
        SCORES_FILE
    )


def sort_scores(scores):
    """Отсортировать рекорды от большего к меньшему."""

    return sorted(
        scores,
        key=lambda item: (
            int(item.get("score", 0)),
            int(item.get("level", 1))
        ),
        reverse=True
    )


# =========================================================
# HTTP SERVER
# =========================================================

class SkyDodgeServer(
    http.server.SimpleHTTPRequestHandler
):

    server_version = "SkyDodge/1.0"

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def do_GET(self):

        path = urlparse(self.path).path

        # Главная страница
        if path == "/":

            self.serve_file("index.html")
            return

        # -------------------------------------------------
        # Получить все рекорды
        # -------------------------------------------------

        if path == "/api/scores":

            scores = load_scores()

            scores = sort_scores(scores)

            self.send_json(
                {
                    "success": True,
                    "scores": scores[:50]
                }
            )

            return

        # -------------------------------------------------
        # Получить лучший результат
        # -------------------------------------------------

        if path == "/api/best":

            scores = load_scores()

            if not scores:

                self.send_json(
                    {
                        "success": True,
                        "best": None
                    }
                )

                return

            scores = sort_scores(scores)

            self.send_json(
                {
                    "success": True,
                    "best": scores[0]
                }
            )

            return

        # -------------------------------------------------
        # Статистика игры
        # -------------------------------------------------

        if path == "/api/stats":

            scores = load_scores()

            if not scores:

                self.send_json(
                    {
                        "success": True,
                        "players": 0,
                        "best_score": 0,
                        "best_level": 0
                    }
                )

                return

            scores = sort_scores(scores)

            best_score = int(
                scores[0].get("score", 0)
            )

            best_level = max(
                int(item.get("level", 1))
                for item in scores
            )

            self.send_json(
                {
                    "success": True,
                    "players": len(scores),
                    "best_score": best_score,
                    "best_level": best_level
                }
            )

            return

        # -------------------------------------------------
        # Неизвестный адрес
        # -------------------------------------------------

        self.send_error(
            404,
            "Страница не найдена"
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    def do_POST(self):

        path = urlparse(self.path).path

        # -------------------------------------------------
        # Добавить результат игрока
        # -------------------------------------------------

        if path == "/api/scores":

            try:
                content_length = int(
                    self.headers.get(
                        "Content-Length",
                        0
                    )
                )

                raw_data = self.rfile.read(
                    content_length
                )

                data = json.loads(
                    raw_data.decode("utf-8")
                )

            except (
                ValueError,
                json.JSONDecodeError
            ):

                self.send_json(
                    {
                        "success": False,
                        "error": "Некорректные данные"
                    },
                    status=400
                )

                return

            # Имя
            name = str(
                data.get(
                    "name",
                    "Player"
                )
            ).strip()

            if not name:
                name = "Player"

            # Максимум 20 символов
            name = name[:20]

            # Счёт
            try:

                score = int(
                    data.get(
                        "score",
                        0
                    )
                )

            except (TypeError, ValueError):

                self.send_json(
                    {
                        "success": False,
                        "error": "Некорректный score"
                    },
                    status=400
                )

                return

            # Уровень
            try:

                level = int(
                    data.get(
                        "level",
                        1
                    )
                )

            except (TypeError, ValueError):

                self.send_json(
                    {
                        "success": False,
                        "error": "Некорректный level"
                    },
                    status=400
                )

                return

            # Защита от отрицательных значений
            score = max(0, score)
            level = max(1, level)

            # -------------------------------------------------
            # Создаём запись
            # -------------------------------------------------

            record = {
                "name": name,
                "score": score,
                "level": level,
                "timestamp": int(time.time())
            }

            # Загружаем существующие
            scores = load_scores()

            # Добавляем новую запись
            scores.append(record)

            # Сортируем
            scores = sort_scores(scores)

            # Оставляем 100 лучших
            scores = scores[:100]

            # Сохраняем
            save_scores(scores)

            # Позиция игрока
            position = None

            for index, item in enumerate(scores):

                if item is record:
                    position = index + 1
                    break

            # Если запись не вошла в топ
            if position is None:

                position = len(scores)

            # Проверяем, стал ли игрок первым
            is_best = (
                scores[0] is record
            )

            self.send_json(
                {
                    "success": True,
                    "position": position,
                    "is_best": is_best,
                    "record": record
                }
            )

            return

        # -------------------------------------------------
        # Очистить рекорды
        # -------------------------------------------------
        #
        # Этот endpoint можно использовать
        # только с локального сервера.
        #
        # Например:
        #
        # POST /api/reset
        #
        # -------------------------------------------------

        if path == "/api/reset":

            save_scores([])

            self.send_json(
                {
                    "success": True,
                    "message": "Рекорды очищены"
                }
            )

            return

        # -------------------------------------------------
        # Неизвестный POST
        # -------------------------------------------------

        self.send_json(
            {
                "success": False,
                "error": "Неизвестный API адрес"
            },
            status=404
        )

    # -----------------------------------------------------
    # Отправка JSON
    # -----------------------------------------------------

    def send_json(
        self,
        data,
        status=200
    ):

        response = json.dumps(
            data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(response))
        )

        self.send_header(
            "Cache-Control",
            "no-store"
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        self.end_headers()

        self.wfile.write(response)

    # -----------------------------------------------------
    # OPTIONS
    # -----------------------------------------------------

    def do_OPTIONS(self):

        self.send_response(204)

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        self.end_headers()

    # -----------------------------------------------------
    # Отдать файл
    # -----------------------------------------------------

    def serve_file(self, filename):

        if not os.path.exists(filename):

            self.send_error(
                404,
                f"Файл {filename} не найден"
            )

            return

        try:

            with open(
                filename,
                "rb"
            ) as file:

                content = file.read()

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )

            self.send_header(
                "Content-Length",
                str(len(content))
            )

            self.end_headers()

            self.wfile.write(content)

        except OSError:

            self.send_error(
                500,
                "Не удалось открыть файл"
            )


# =========================================================
# ЗАПУСК
# =========================================================

def main():

    print()
    print("=" * 45)
    print("            SKY DODGE SERVER")
    print("=" * 45)
    print()

    print(
        f"Игра: http://localhost:{PORT}"
    )

    print(
        f"Рекорды: http://localhost:{PORT}/api/scores"
    )

    print(
        f"Статистика: http://localhost:{PORT}/api/stats"
    )

    print(
        f"Лучший результат: http://localhost:{PORT}/api/best"
    )

    print()

    print(
        "Для остановки нажми CTRL+C"
    )

    print()


    server = http.server.ThreadingHTTPServer(
        (
            HOST,
            PORT
        ),
        SkyDodgeServer
    )


    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print("Сервер остановлен.")

    finally:

        server.server_close()


if __name__ == "__main__":
    main()
```
