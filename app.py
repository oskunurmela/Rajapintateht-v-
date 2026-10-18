"""My Festival REST API — M10 starter (CSC Rahti).

FI: Tämä on M10-tehtävän lähtöpohja. GET /api/artists on valmiina mallina;
    toteuta loput TODO-kohdat. Aja paikallisesti:  python app.py
    ja testaa:  python test_endpoints.py http://localhost:8080
EN: This is the M10 starter. GET /api/artists is done as an example;
    implement the remaining TODOs. Run locally:  python app.py
    and test:  python test_endpoints.py http://localhost:8080
"""
import os
import sqlite3
from datetime import datetime  

from flask import Flask, jsonify, request

app = Flask(__name__)

# FI: Kanta kulkee kontin mukana. Polun voi vaihtaa ympäristömuuttujalla.
# EN: The database ships inside the container. Override the path with an env var.
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "myfestival.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # M8: sqlite3 ei valvo FK:ita oletuksena / FKs are off by default
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def health():
    """FI: Rahti ja selain näkevät, että sovellus on pystyssä.
    EN: Lets Rahti and your browser see the app is up."""
    return jsonify(status="ok", endpoints=["/api/artists", "/api/days", "/api/stages",
                                           "/api/artists/<id>/events", "/api/timetable?day=YYYY-MM-DD",
                                           "POST /api/events", "DELETE /api/events/<id>"])


@app.get("/api/artists")
def get_artists():
    conn = get_db()
    rows = conn.execute("SELECT artist_id, name, country FROM Artist ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/days")
def get_days():
    """FI: Apuendpoint: festivaalipäivät (tarkistin hakee tästä day_id:n).
    EN: Helper endpoint: festival days (the checker reads day_id from here)."""
    conn = get_db()
    rows = conn.execute("SELECT day_id, date FROM Day ORDER BY date").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/stages")
def get_stages():
    """FI: Apuendpoint: lavat. EN: Helper endpoint: stages."""
    conn = get_db()
    rows = conn.execute("SELECT stage_id, name FROM Stage ORDER BY stage_id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/artists/<int:artist_id>/events")
def get_artist_events(artist_id):
    conn = get_db()
    
    query = """
        SELECT e.event_id, d.date AS day, s.name AS stage, e.start_time AS starts
        FROM Event e
        JOIN Day d ON e.day_id = d.day_id
        JOIN Stage s ON e.stage_id = s.stage_id
        WHERE e.artist_id = ?
    """
    rows = conn.execute(query, (artist_id,)).fetchall()
    conn.close()
    
    if not rows:
        return jsonify({"error": "Artistia tai keikkoja ei löytynyt"}), 404
        
    return jsonify([dict(r) for r in rows])




@app.get("/api/timetable")
def get_timetable():
    day = request.args.get("day")
    
    if day:
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            return jsonify(error="Virheellinen päivämäärämuoto"), 400
            
    conn = get_db()
    
    query = """
        SELECT 
            d.date, 
            s.name AS stage, 
            a.name AS artist, 
            e.start_time AS starts,
            substr(time(e.start_time, '+' || e.duration_min || ' minutes'), 1, 5) AS ends
        FROM Event e
        JOIN Day d ON e.day_id = d.day_id
        JOIN Stage s ON e.stage_id = s.stage_id
        JOIN Artist a ON e.artist_id = a.artist_id
    """
    
    params = []
    if day:
        query += " WHERE d.date = ?"
        params.append(day)
        
    query += " ORDER BY d.date ASC, e.start_time ASC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    return jsonify([dict(r) for r in rows])


@app.post("/api/events")
def create_event():
    body = request.get_json(silent=True) or {}
    
    required_fields = ["artist_id", "stage_id", "day_id", "start_dt"]
    for field in required_fields:
        if field not in body:
            return jsonify(error=f"Puuttuva kenttä: {field}"), 400

    try:
        datetime.strptime(body["start_dt"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify(error="Virheellinen aika"), 400

    conn = get_db()
    try:
        type_row = conn.execute("SELECT event_type_id FROM EventType LIMIT 1").fetchone()
        event_type_id = type_row["event_type_id"] if type_row else 1

        cursor = conn.execute(
            """
            INSERT INTO Event (day_id, stage_id, artist_id, event_type_id, start_time, duration_min)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (body["day_id"], body["stage_id"], body["artist_id"], event_type_id, body["start_dt"], 45)
        )
        event_id = cursor.lastrowid
        conn.commit()
        
        new_row = conn.execute("SELECT * FROM Event WHERE event_id = ?", (event_id,)).fetchone()
        conn.close()
        
        return jsonify(dict(new_row)), 201
        
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify(error="Viiteavainvirhe tai id ei ole olemassa"), 400


@app.delete("/api/events/<int:event_id>")
def delete_event(event_id):
    conn = get_db()
    cursor = conn.execute("DELETE FROM Event WHERE event_id = ?", (event_id,))
    conn.commit()
    conn.close()
    
    if cursor.rowcount == 0:
        return jsonify(error="Esiintymistä ei löytynyt"), 404
        
    return "", 204


if __name__ == "__main__":
    # FI: Paikallinen kehityspalvelin. Rahdissa sovellusta ajaa gunicorn (ks. Dockerfile).
    # EN: Local dev server. On Rahti the app is run by gunicorn (see Dockerfile).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
