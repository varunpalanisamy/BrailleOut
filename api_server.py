"""
Lightweight Flask API server for the Braille web frontend.
Run with: python api_server.py
Runs on port 5001 so it doesn't conflict with anything else.
"""

import os
import re
import base64
import html as html_lib
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


@app.route("/api/transcript")
def get_transcript():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Could not extract video ID — paste the full YouTube URL"}), 400

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        raw = " ".join(item["text"] for item in transcript_list)
        text = html_lib.unescape(raw)
        return jsonify({"text": text, "video_id": video_id})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/process-image", methods=["POST"])
def process_image():
    try:
        data = request.get_json(force=True)
        image_b64: str = data.get("image", "")
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        from google import genai

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {
                    "parts": [
                        {
                            "text": (
                                "Extract ONLY the text visible in this image. "
                                "Return just the raw text with no explanation. "
                                "If no text is visible, return an empty string."
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_b64,
                            }
                        },
                    ]
                }
            ],
        )
        return jsonify({"text": (response.text or "").strip()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    print("Starting Braille API server on http://localhost:5001")
    app.run(port=5001, debug=True)
