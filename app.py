from flask import Flask, render_template, request, send_file
import requests
from bs4 import BeautifulSoup
import sqlite3
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

# ---------- Initialize Database ----------
def init_db():
    conn = sqlite3.connect("seo_data.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS seo_results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  url TEXT,
                  seo_score INTEGER,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ---------- SEO Analyzer ----------
def analyze_website(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string.strip() if soup.title else "No title found"
        meta = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta["content"].strip() if meta else "No meta description found"
        h1_tags = soup.find_all("h1")
        images = soup.find_all("img")
        links = soup.find_all("a", href=True)

        missing_alt = sum(1 for img in images if not img.get("alt"))
        link_count = len(links)

        # Unified SEO scoring
        score = 100
        issues = []

        if title == "No title found":
            score -= 10
            issues.append("Missing title tag")
        if meta_desc == "No meta description found":
            score -= 10
            issues.append("Missing meta description")
        if len(h1_tags) == 0:
            score -= 10
            issues.append("No H1 tag found")
        if missing_alt > 5:
            score -= 10
            issues.append("Many images missing alt attributes")
        if link_count < 5:
            score -= 10
            issues.append("Not enough internal/external links")
        if len(response.text) < 500:
            score -= 10
            issues.append("Page content seems too short")

        score = max(0, min(100, score))

        return {
            "url": url,
            "title": title,
            "meta_desc": meta_desc,
            "h1_count": len(h1_tags),
            "missing_alt": missing_alt,
            "link_count": link_count,
            "load_time": round(response.elapsed.total_seconds(), 2),
            "seo_score": score,
            "report": issues
        }
    except Exception as e:
        return {"error": str(e)}

# ---------- Routes ----------
@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    if request.method == "POST":
        url = request.form.get("website_url", "").strip()
        if not url.startswith(("http://", "https://")):
            result = {"error": "Please enter a valid URL starting with http or https."}
        else:
            result = analyze_website(url)
            if "error" not in result:
                conn = sqlite3.connect("seo_data.db")
                c = conn.cursor()
                c.execute("INSERT INTO seo_results (url, seo_score, timestamp) VALUES (?, ?, datetime('now'))",
                          (url, result["seo_score"]))
                conn.commit()
                conn.close()
    return render_template("index.html", result=result)

# ---------- Download Report ----------
@app.route("/download", methods=["POST"])
def download_pdf():
    data = request.form
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("Smart SEO Report")

    pdf.drawString(230, 750, "Smart SEO Auditor Report")
    pdf.line(50, 740, 550, 740)

    y = 710
    for key, value in data.items():
        if key not in ['csrf_token']:
            pdf.drawString(70, y, f"{key.capitalize()}: {value}")
            y -= 20

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="SEO_Report.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True)
