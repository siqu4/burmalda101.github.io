```python
import http.server
import json
import os
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8000

SCORES_FILE = "scores.json"


def load_scores():
    if not os.path.exists(SCORES_FILE):
        return []

    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except:
        return []


def save_scores(scores):
    with open(SCORES_FILE, "w", encoding="utf-8") as file:
        json.dump(
            scores,
            file,
            ensure_ascii=False,
            indent=4
        )


class GameServer(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):

        path = urlparse(self.path).path

        # Таблица рекордов
        if path == "/api/scores":

            scores = load_scores()

            scores.sort(
                key=lambda x: x.get("score", 0),
                reverse=True
            )

            self.send_json(scores[:50])
            return

        # Статистика
        if path == "/api/stats":

            scores = load_scores()

            best_score = 0
            best_level = 0

            if scores:
                best_score = max(
                    x.get("score", 0)
                    for x in scores
                )

                best_level = max(
                    x.get("level", 1)
                    for x in scores
                )

            self.send_json({
                "players": len(scores),
                "best_score": best_score,
                "best_level": best_level
            })

            return

        # Обычные файлы
        super().do_GET()


    def do_POST(self):

        path = urlparse(self.path).path

        if path != "/api/scores":
            self.send_error(
                404,
                "API endpoint not found"
            )
            return

        try:

            length = int(
                self.headers.get(
                    "Content-Length",
                    0
                )
            )

            raw_data = self.rfile.read(length)

            data = json.loads(
                raw_data.decode("utf-8")
            )

        except:

            self.send_json(
                {
                    "success": False,
                    "error": "Неверный JSON"
                },
                400
            )

            return


        name = str(
            data.get(
                "name",
                "Player"
            )
        ).strip()

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

        except:

            self.send_json(
                {
                    "success": False,
                    "error": "Score и level должны быть числами"
                },
                400
            )

            return


        # Защита от странных значений

        if not name:
            name = "Player"

        name = name[:20]

        score = max(
            0,
            score
        )

        level = max(
            1,
            level
        )


        scores = load_scores()

        record = {
            "name": name,
            "score": score,
            "level": level
        }

        scores.append(record)

        scores.sort(
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        # Оставляем 100 лучших
        scores = scores[:100]

        save_scores(scores)

        position = 1

        for i, item in enumerate(scores):

            if item is record:

                position = i + 1
                break


        self.send_json({
            "success": True,
            "position": position,
            "record": record
        })


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
            "Access-Control-Allow-Origin",
            "*"
        )

        self.end_headers()

        self.wfile.write(response)


print()
print("================================")
print("          SKY DODGE")
print("================================")
print()
print("Сервер запущен!")
print()
print("Открыть игру:")
print(f"http://localhost:{PORT}")
print()
print("Рекорды:")
print(f"http://localhost:{PORT}/api/scores")
print()
print("Для остановки нажми CTRL+C")
print()

server = http.server.ThreadingHTTPServer(
    (HOST, PORT),
    GameServer
)

try:
    server.serve_forever()

except KeyboardInterrupt:

    print()
    print("Сервер остановлен.")

finally:

    server.server_close()
```
