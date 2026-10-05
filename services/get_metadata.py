import json
from PIL import Image
from bs4 import BeautifulSoup

def summarize_csv(path):
    import pandas as pd
    df = pd.read_csv(path, nrows=1000)
    summary = {
        "type": "csv",
        "columns": list(df.columns),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "sample_rows": df.head(10).to_dict(orient="records"),
        "num_rows": len(df),
    }
    return json.dumps(summary, indent=2)


def summarize_json(path):
    import json
    with open(path) as f:
        data = json.load(f)

    summary ={
        "type": "json",
        "keys": list(data.keys()) if isinstance(data, dict) else None,
        "sample": data[:3] if isinstance(data, list) else None,
        "structure": str(type(data)),
    }

    return json.dumps(summary, indent=2)

def summarize_text(path):
    encodings_to_try = ["utf-8", "cp1252"]
    content = None
    used_encoding = None

    for enc in encodings_to_try:
        try:
            with open(path, encoding=enc) as f:
                content = f.read()
                used_encoding = enc
                break
        except UnicodeDecodeError:
            continue

    if content is None:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read()
            used_encoding = "utf-8 (errors replaced)"

    summary = {
        "type": "text",
        "encoding_used": used_encoding,
        "length": len(content),
        "preview": content[:100]
    }

    return json.dumps(summary, indent=2)

def summarize_html(path):
    try:
        with open(path, encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.string if soup.title else None
        links = len(soup.find_all("a"))
        images = len(soup.find_all("img"))
        text = soup.get_text(separator=" ", strip=True)

        summary = {
            "type": "html",
            "title": title,
            "num_links": links,
            "num_images": images,
            "text_preview": text[:100],
        }
        return json.dumps(summary, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)