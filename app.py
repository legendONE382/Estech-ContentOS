import os
import sqlite3
from datetime import datetime
from typing import Optional

import requests
from flask import Flask, g, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("CONTENTOS_DB", "contentos.db")

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "open-mistral-7b")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_: Optional[BaseException]) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS brand_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            industry TEXT NOT NULL,
            target_audience TEXT NOT NULL,
            brand_tone TEXT NOT NULL,
            products_services TEXT NOT NULL,
            website_link TEXT,
            competitors TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS generated_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER NOT NULL,
            content_type TEXT NOT NULL,
            topic TEXT NOT NULL,
            product TEXT NOT NULL,
            goal TEXT NOT NULL,
            prompt TEXT NOT NULL,
            output_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (brand_id) REFERENCES brand_profiles(id)
        );
        """
    )
    db.commit()


def get_latest_brand() -> Optional[sqlite3.Row]:
    db = get_db()
    return db.execute(
        "SELECT * FROM brand_profiles ORDER BY id DESC LIMIT 1"
    ).fetchone()


def build_prompt(brand: sqlite3.Row, content_type: str, topic: str, product: str, goal: str) -> str:
    return f"""You are a senior content strategist for {brand['business_name']}.
Industry: {brand['industry']}
Target audience: {brand['target_audience']}
Brand tone: {brand['brand_tone']}
Products/Services: {brand['products_services']}
Website: {brand['website_link'] or 'N/A'}
Competitors: {brand['competitors'] or 'N/A'}

Create {content_type} content about: {topic}
Highlight product/service: {product}
Primary goal: {goal}

Requirements:
- Keep language on-brand and persuasive.
- Include a clear call-to-action.
- Provide a polished, publication-ready output.
- Add 3 optional hashtags when the format is social.
"""


def generate_with_mistral(prompt: str) -> str:
    if not MISTRAL_API_KEY:
        return (
            "MISTRAL_API_KEY is not configured. Add your API key in environment variables "
            "to generate live AI content.\n\n"
            "Preview prompt used:\n"
            f"{prompt}"
        )

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": "You create premium marketing content for businesses."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    resp = requests.post(MISTRAL_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


@app.route("/")
def index():
    brand = get_latest_brand()
    library = get_db().execute(
        """
        SELECT gc.*, bp.business_name
        FROM generated_content gc
        JOIN brand_profiles bp ON bp.id = gc.brand_id
        ORDER BY gc.id DESC LIMIT 20
        """
    ).fetchall()
    return render_template("index.html", brand=brand, library=library)


@app.route("/brand", methods=["POST"])
def save_brand():
    db = get_db()
    db.execute(
        """
        INSERT INTO brand_profiles
        (business_name, industry, target_audience, brand_tone, products_services, website_link, competitors, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.form["business_name"],
            request.form["industry"],
            request.form["target_audience"],
            request.form["brand_tone"],
            request.form["products_services"],
            request.form.get("website_link", ""),
            request.form.get("competitors", ""),
            datetime.utcnow().isoformat(),
        ),
    )
    db.commit()
    return redirect(url_for("index"))


@app.route("/generate", methods=["POST"])
def generate():
    brand = get_latest_brand()
    if not brand:
        return jsonify({"error": "Please complete Brand Setup first."}), 400

    content_type = request.form["content_type"]
    topic = request.form["topic"]
    product = request.form["product"]
    goal = request.form["goal"]

    prompt = build_prompt(brand, content_type, topic, product, goal)

    try:
        output_text = generate_with_mistral(prompt)
    except requests.RequestException as exc:
        return jsonify({"error": f"AI generation failed: {exc}"}), 502

    db = get_db()
    db.execute(
        """
        INSERT INTO generated_content
        (brand_id, content_type, topic, product, goal, prompt, output_text, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            brand["id"],
            content_type,
            topic,
            product,
            goal,
            prompt,
            output_text,
            datetime.utcnow().isoformat(),
        ),
    )
    db.commit()

    return jsonify({"output": output_text, "prompt": prompt})


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
