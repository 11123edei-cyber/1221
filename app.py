from datetime import datetime
from io import BytesIO
from pathlib import Path
import sqlite3
from threading import Lock

import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request, send_file
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from ultralytics import YOLO
from werkzeug.exceptions import RequestEntityTooLarge


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "history.db"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 МБ

model = YOLO(str(BASE_DIR / "yolov8n.pt"))
process_lock = Lock()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                count INTEGER
            )
        """)


def get_history():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT id, timestamp, count FROM requests ORDER BY id"
        ).fetchall()


init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.errorhandler(RequestEntityTooLarge)
def image_too_large(error):
    return jsonify(error="Размер файла не должен превышать 10 МБ."), 413


@app.route("/process", methods=["POST"])
def process_image():
    file = request.files.get("image")
    if file is None or not file.filename:
        return jsonify(error="Выберите изображение."), 400

    raw = file.read()
    if not raw:
        return jsonify(error="Файл пуст."), 400

    try:
        img = cv2.imdecode(
            np.frombuffer(raw, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
    except cv2.error:
        img = None

    if img is None:
        return jsonify(error="Не удалось прочитать изображение."), 400

    try:
        # Модель и общий файл результата используются последовательно.
        with process_lock:
            # COCO: класс 58 — potted plant (растение в горшке).
            result = model.predict(
                img, classes=[58], conf=0.25, verbose=False
            )[0]
            count = len(result.boxes)

            saved = cv2.imwrite(
                str(STATIC_DIR / "result.jpg"),
                result.plot(),
            )
            if not saved:
                raise RuntimeError("Не удалось сохранить изображение")

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO requests (timestamp, count) VALUES (?, ?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), count),
                )
    except Exception:
        app.logger.exception("Ошибка обработки изображения")
        return jsonify(error="Не удалось обработать изображение."), 500

    return jsonify(count=count)


@app.route("/export/excel")
def export_excel():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "История"
    sheet.append(["ID", "Дата и время", "Количество растений"])

    for row in get_history():
        sheet.append(row)

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, width in (("A", 10), ("B", 24), ("C", 26)):
        sheet.column_dimensions[column].width = width

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="plant_history.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/export/pdf")
def export_pdf():
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    rows = [["ID", "Date and time", "Plant count"]]
    rows.extend([list(row) for row in get_history()])

    table = Table(rows, colWidths=[55, 270, 125], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4CAF50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    document.build([
        Paragraph("Plant counting history", styles["Title"]),
        Spacer(1, 12),
        table,
    ])
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="plant_history.pdf",
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)