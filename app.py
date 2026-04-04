from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from database import get_db, init_db
from hasher import generate_hash
from reddit_scanner import scan_reddit
import os
import uuid

load_dotenv()

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

init_db()


# ── REGISTER OFFICIAL CONTENT ──────────────────────────────────────
@app.route("/api/register", methods=["POST"])
def register_content():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    name = request.form.get("name", file.filename)

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = f"{uuid.uuid4()}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    phash = generate_hash(filepath)
    if not phash:
        return jsonify({"error": "Could not generate hash for this image"}), 500

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO registered_content (name, filename, phash) VALUES (?, ?, ?)",
        (name, filename, phash)
    )
    registered_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Content registered successfully",
        "id": registered_id,
        "name": name,
        "phash": phash
    }), 201


# ── SCAN REDDIT FOR MATCHES ────────────────────────────────────────
@app.route("/api/scan/<int:registered_id>", methods=["POST"])
def scan_content(registered_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registered_content WHERE id = ?", (registered_id,))
    content = cursor.fetchone()
    conn.close()

    if not content:
        return jsonify({"error": "Registered content not found"}), 404

    matches = scan_reddit(content["phash"], content["name"])

    conn = get_db()
    cursor = conn.cursor()
    for match in matches:
        cursor.execute("""
            INSERT INTO flagged_content 
            (registered_id, content_name, platform, source_url, post_title, match_score, detection_method, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            registered_id,
            content["name"],
            "Reddit",
            match["source_url"],
            match["post_title"],
            match["match_score"],
            match["detection_method"],
            "Pending"
        ))
    conn.commit()
    conn.close()

    return jsonify({
        "message": f"{len(matches)} matches found",
        "matches": matches
    }), 200


# ── GET ALL REGISTERED CONTENT ─────────────────────────────────────
@app.route("/api/registered", methods=["GET"])
def get_registered():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registered_content ORDER BY uploaded_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200


# ── GET ALL FLAGGED CONTENT ────────────────────────────────────────
@app.route("/api/flagged", methods=["GET"])
def get_flagged():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM flagged_content ORDER BY flagged_at DESC")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        for key, val in d.items():
            if isinstance(val, bytes):
                d[key] = val.decode("utf-8", errors="ignore")
        result.append(d)
    return jsonify(result), 200


# ── UPDATE FLAG STATUS ─────────────────────────────────────────────
@app.route("/api/flagged/<int:flag_id>/status", methods=["PATCH"])
def update_status(flag_id):
    data = request.get_json()
    new_status = data.get("status")

    allowed_statuses = ["Allowed", "Flagged", "Ignored"]
    if new_status not in allowed_statuses:
        return jsonify({"error": "Invalid status. Use Allowed, Flagged, or Ignored"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE flagged_content SET status = ? WHERE id = ?", (new_status, flag_id))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Status updated to {new_status}"}), 200


# ── GET ANOMALIES ──────────────────────────────────────────────────
@app.route("/api/anomaly", methods=["GET"])
def get_anomalies():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM anomalies ORDER BY total_flags DESC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200


# ── SEED ANOMALY DATA FOR DEMO ─────────────────────────────────────
@app.route("/api/anomaly/seed", methods=["POST"])
def seed_anomaly():
    demo_anomalies = [
        {
            "content_name": "Virat Kohli Century Celebration",
            "total_flags": 47,
            "first_seen": "2025-04-04 08:12:00",
            "last_seen": "2025-04-04 09:10:00"
        },
        {
            "content_name": "IPL 2025 Official Poster",
            "total_flags": 31,
            "first_seen": "2025-04-04 10:00:00",
            "last_seen": "2025-04-04 10:45:00"
        },
        {
            "content_name": "Champions Trophy Final Highlight",
            "total_flags": 22,
            "first_seen": "2025-04-04 06:30:00",
            "last_seen": "2025-04-04 07:20:00"
        }
    ]

    conn = get_db()
    cursor = conn.cursor()
    for anomaly in demo_anomalies:
        cursor.execute("""
            INSERT INTO anomalies (content_name, total_flags, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
        """, (anomaly["content_name"], anomaly["total_flags"], anomaly["first_seen"], anomaly["last_seen"]))
    conn.commit()
    conn.close()

    return jsonify({"message": "Anomaly demo data seeded successfully"}), 201


# ── DASHBOARD STATS ────────────────────────────────────────────────
@app.route("/api/stats", methods=["GET"])
def get_stats():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM registered_content")
    registered = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM flagged_content")
    flagged = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM flagged_content WHERE status = 'Pending'")
    pending = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM flagged_content WHERE status = 'Allowed'")
    allowed = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM anomalies")
    anomalies = cursor.fetchone()["total"]

    conn.close()

    return jsonify({
        "registered_content": registered,
        "total_flags": flagged,
        "pending_review": pending,
        "marked_allowed": allowed,
        "active_anomalies": anomalies
    }), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)