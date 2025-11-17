from flask import Flask, render_template, request, send_file, send_from_directory
import requests
from bs4 import BeautifulSoup
import sqlite3
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

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
        # Fake browser headers (avoid blocking)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.SSLError:
            if url.startswith("https://"):
                url = url.replace("https://", "http://")
                response = requests.get(url, headers=headers, timeout=10)
            else:
                raise
        except requests.exceptions.ConnectionError:
            raise Exception("Failed to connect to the website. It may be offline or blocking requests.")

        soup = BeautifulSoup(response.text, "html.parser")

        # --- Extract key elements ---
        title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"
        meta = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta["content"].strip() if meta and meta.get("content") else "No meta description found"

        h1_tags = soup.find_all("h1")
        images = soup.find_all("img")
        links = soup.find_all("a", href=True)
        missing_alt = sum(1 for img in images if not img.get("alt"))

        # --- SEO scoring ---
        score = 100
        issues, fixes = [], []

        if title == "No title found":
            score -= 10
            issues.append("Missing title tag")
            fixes.append("Add a descriptive <title> tag with keywords.")
        if meta_desc == "No meta description found":
            score -= 10
            issues.append("Missing meta description")
            fixes.append("Include a <meta name='description'> tag.")
        if len(h1_tags) == 0:
            score -= 10
            issues.append("No H1 tag found")
            fixes.append("Add a main <h1> heading.")
        if missing_alt > 5:
            score -= 10
            issues.append("Many images missing alt attributes")
            fixes.append("Add descriptive alt text for all images.")
        if len(links) < 5:
            score -= 10
            issues.append("Not enough internal/external links")
            fixes.append("Add more internal/external links to enhance navigation.")
        if len(response.text) < 500:
            score -= 10
            issues.append("Page content too short")
            fixes.append("Add more keyword-rich and valuable content.")

        # --- Mobile-friendly check ---
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if not viewport:
            score -= 10
            issues.append("Not mobile-friendly")
            fixes.append("Add a responsive viewport meta tag for mobile support.")

        # --- Schema markup check ---
        if not soup.find("script", attrs={"type": "application/ld+json"}):
            score -= 10
            issues.append("No structured data found")
            fixes.append("Add JSON-LD structured data from schema.org.")

        # --- Platform detection ---
        html = response.text.lower()
        if "wordpress" in html:
            platform = "WordPress"
        elif "shopify" in html:
            platform = "Shopify"
        elif "wix" in html:
            platform = "Wix"
        elif "squarespace" in html:
            platform = "Squarespace"
        else:
            platform = "Custom/Static site"

        score = max(0, min(100, score))

        return {
            "url": url,
            "title": title,
            "meta_desc": meta_desc,
            "h1_count": len(h1_tags),
            "missing_alt": missing_alt,
            "link_count": len(links),
            "load_time": round(response.elapsed.total_seconds(), 2),
            "seo_score": score,
            "report": issues,
            "fixes": fixes,
            "platform": platform
        }

    except Exception as e:
        return {"error": str(e)}

# ---------- Generate Fixed HTML ----------
def generate_fixed_page(url, html_content):
    os.makedirs("fixed_sites", exist_ok=True)
    soup = BeautifulSoup(html_content, "html.parser")

    # Auto-fix common SEO issues
    if not soup.title:
        new_title = soup.new_tag("title")
        new_title.string = "AI Optimized Page"
        soup.head.insert(0, new_title)

    if not soup.find("meta", attrs={"name": "description"}):
        meta = soup.new_tag("meta", attrs={"name": "description", "content": "AI optimized meta description."})
        soup.head.append(meta)

    if not soup.find("meta", attrs={"name": "viewport"}):
        viewport = soup.new_tag("meta", attrs={"name": "viewport", "content": "width=device-width, initial-scale=1.0"})
        soup.head.append(viewport)

    if not soup.find("script", attrs={"type": "application/ld+json"}):
        schema = soup.new_tag("script", attrs={"type": "application/ld+json"})
        schema.string = """{
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Smart SEO Auditor",
            "url": "%s"
        }""" % url
        soup.head.append(schema)

    for img in soup.find_all("img"):
        if not img.get("alt"):
            img["alt"] = "AI added image description"

    if not soup.find("h1"):
        h1 = soup.new_tag("h1")
        h1.string = "AI Generated Heading for SEO Improvement"
        soup.body.insert(0, h1)

    file_path = os.path.join("fixed_sites", "corrected_page.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(str(soup))
    return file_path

# ---------- Routes ----------
@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    if request.method == "POST":
        url = request.form.get("website_url", "").strip()
        ownership = request.form.get("ownership", "no")

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

                if ownership.lower() == "yes":
                    headers = {"User-Agent": "Mozilla/5.0"}
                    response = requests.get(url, headers=headers, timeout=10)
                    path = generate_fixed_page(url, response.text)
                    result["fixed_path"] = path
                    result["ownership_message"] = "✅ You own this site. AI auto-fix applied."
                else:
                    result["ownership_message"] = "⚠️ You don’t own this site. Only suggestions shown."

    return render_template("index.html", result=result)

@app.route("/fixed_sites/<path:filename>")
def serve_fixed_files(filename):
    return send_from_directory("fixed_sites", filename)

@app.route("/download", methods=["POST"])
def download_pdf():
    data = request.form
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("Smart SEO Report")

    pdf.drawString(220, 750, "Smart SEO Auditor Report")
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
