# AI-Powered Braille Display

An assistive device that reads real-world text through a camera and converts it to Grade 1 Braille — displayed visually on screen and physically raised by 6 servo motors. Powered by **Gemma 4**, Google's latest multimodal model, running locally via Ollama with no internet or API keys required.

> **No external webcam needed.** The current version defaults to your laptop's built-in camera. Any MacBook or laptop with an internal camera works out of the box.

---

## Images

<p align="center">
  <img src="https://github.com/user-attachments/assets/3e99b283-588e-4927-b53b-b73a82a5d44b" width="300" />
  <img src="https://github.com/user-attachments/assets/96bac622-504a-4019-b788-d26084b8f8d5" width="500" />
</p>

| ![Underneath the Braille table](https://github.com/user-attachments/assets/630b9906-6fc6-4bc3-983f-a83d06162c6b) | ![Top view of Braille Table](https://github.com/user-attachments/assets/c158f615-d1e1-42b4-b6a4-e974968ffeb9) | ![Arduino and Base Studio](https://github.com/user-attachments/assets/ddee993b-5c24-40fa-bb29-e56fe5d9a45e) |
| :---: | :---: | :---: |
| Underneath the Braille table with 6 servo motors | Top view of Braille Table | Arduino and Base Studio with jumper wires |

---

## How It Works

The project has two AI pipelines — a fully offline one powered by **Gemma 4**, and a cloud-based one using Gemini + Claude.

### Primary Pipeline — Gemma 4 (Offline, No API Keys)

```
Webcam + Microphone → Whisper STT → Gemma 4 via Ollama → Braille Converter → UI + Arduino + TTS
```

**Gemma 4** (`gemma4:e4b`) is a multimodal model from Google that runs entirely on your local machine via [Ollama](https://ollama.com). It handles both vision (reading text from camera frames) and language (understanding voice input) in a single model — no cloud calls, no API keys, no internet after the initial model pull.

1. **Webcam** captures live frames of text (books, signs, screens, etc.)
2. **Microphone** records voice input — **Whisper** (running locally) transcribes it to text
3. **Gemma 4** receives the camera frame and/or transcript and extracts the target text
4. **Braille converter** maps each character to its Grade 1 Braille dot pattern
5. **Tkinter UI** renders the Braille cell — 6 dots in a 2×3 grid — updating letter by letter
6. **Arduino** receives a 6-bit binary string (e.g. `"101010"`) over serial and physically raises/lowers 6 servo-driven pins *(optional — the UI works without hardware)*
7. **TTS** speaks each letter aloud

### Cloud Pipeline — Gemini + Claude

```
Webcam → Gemini 2.5 Flash OCR → Claude Sonnet Cleanup → Braille Converter → UI + Arduino + TTS
```

An alternative pipeline using cloud APIs: **Google Gemini 2.5 Flash** handles vision OCR and **Anthropic Claude Sonnet** cleans up the extracted text. Requires API keys.

---

## No Hardware? No Problem

**You don't need an Arduino or servo motors to run this.** All pipelines show Braille output in the on-screen UI regardless of whether hardware is connected — the serial step is simply skipped if no Arduino is found.

| Mode | Requirements | What you get |
|------|-------------|--------------|
| `braille_display.py` | Nothing — zero setup | Press any key to see its Braille dot pattern |
| `gemma_pipeline.py` | Ollama + Gemma 4 (free, offline) | Full AI pipeline with live Braille cell UI |
| `braille_pipeline.py` | Gemini + Anthropic API keys | Cloud AI pipeline with live Braille cell UI |

The Braille cell lights up on screen for every letter in every mode — hardware just adds the physical pin movement on top.

---

## Files

| File | Description |
|------|-------------|
| `gemma_pipeline.py` | **Primary app** — offline pipeline using Gemma 4 via Ollama; webcam vision + voice input via Whisper |
| `braille_pipeline.py` | Cloud pipeline — Gemini 2.5 Flash OCR + Claude Sonnet text cleanup |
| `api_server.py` | Flask backend for the web UI — streams Gemma 4 vision analysis via Server-Sent Events |
| `braille_servo_test.py` | Servo tester — press a–z to test the Braille cell UI and servo movement without AI |
| `braille_display.py` | Minimal viewer — press a–z to see dot patterns; no hardware or API keys needed |
| `requirements.txt` | All Python dependencies |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/varunpalanisamy/Braille.git
cd Braille
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt
```

### 3. Install Ollama and pull Gemma 4

Ollama lets you run large language models locally. Gemma 4 is the model that powers the primary pipeline.

```bash
# Install Ollama
brew install ollama           # macOS
# Windows / Linux: https://ollama.com/download

# Start the Ollama daemon (keep this running in a terminal)
ollama serve

# Pull Gemma 4 — one-time ~3 GB download, fully offline after
ollama pull gemma4:e4b
```

Once pulled, Gemma 4 is cached locally and the pipeline works without any internet connection or API keys.

### 4. Add API keys *(cloud pipeline only — skip if using Gemma)*

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
ELEVENLABS_API_KEY=...   # optional — falls back to pyttsx3 / macOS say
```

Get keys from:
- **Anthropic**: [console.anthropic.com](https://console.anthropic.com)
- **Google Gemini**: [aistudio.google.com](https://aistudio.google.com)
- **ElevenLabs**: [elevenlabs.io](https://elevenlabs.io) *(optional)*

### 5. Set up the Arduino *(optional — skip for software-only prototype)*

1. Install [Arduino IDE](https://www.arduino.cc/en/software)
2. Wire 6 servos to digital pins 2–7
3. Upload the sketch below (one-time — IDE can close after)
4. Find your serial port:
   ```bash
   ls /dev/cu.*
   ```
5. Update `SERIAL_PORT` in `braille_pipeline.py` and `braille_servo_test.py` to match

#### Arduino Sketch

```cpp
#include <Servo.h>

Servo s[6];
const int PINS[6]  = {2, 3, 4, 5, 6, 7};
const int UP_DEG   = 130;   // pin raised  — adjust to your servo travel
const int DOWN_DEG = 50;    // pin lowered — adjust to your servo travel

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < 6; i++) {
    s[i].attach(PINS[i]);
    s[i].write(DOWN_DEG);
  }
  delay(500);
}

void loop() {
  if (Serial.available() >= 6) {
    char buf[7];
    Serial.readBytes(buf, 6);
    buf[6] = '\0';
    while (Serial.available() && Serial.peek() == '\n') Serial.read();

    for (int i = 0; i < 6; i++) s[i].write(DOWN_DEG);
    delay(350);

    for (int i = 0; i < 6; i++) {
      if (buf[i] == '1') s[i].write(UP_DEG);
    }
  }
}
```

**Servo wiring:**

| Servo | Arduino Pin | Braille Dot | Position |
|-------|------------|-------------|----------|
| 1 | Pin 2 | Dot 1 | Top-left |
| 2 | Pin 3 | Dot 2 | Mid-left |
| 3 | Pin 4 | Dot 3 | Bot-left |
| 4 | Pin 5 | Dot 4 | Top-right |
| 5 | Pin 6 | Dot 5 | Mid-right |
| 6 | Pin 7 | Dot 6 | Bot-right |

---

## Running

### Gemma 4 pipeline — offline, no API keys

> Make sure `ollama serve` is running and `gemma4:e4b` is pulled before starting.

```bash
python3 gemma_pipeline.py
```

1. A window opens with a live webcam feed and Braille cell display
2. Point the camera at any text, or speak — Whisper transcribes your voice locally
3. Gemma 4 reads the image and/or transcript entirely on your machine
4. The Braille cell updates letter by letter on screen; servos move if Arduino is connected
5. TTS speaks each letter aloud

### Cloud pipeline — Gemini + Claude

```bash
python3 braille_pipeline.py
```

1. A window opens showing your live webcam feed
2. Point the camera at any printed or on-screen text
3. Click **CAPTURE TEXT** — Gemini OCR and Claude run in the background
4. Use **NEXT →** / **← PREV** (or SPACE / arrow keys) to step through each letter
5. The Braille cell lights up on screen and each letter is spoken aloud

### Servo tester *(no AI needed)*

```bash
python3 braille_servo_test.py
```

Press any letter key (a–z) to see the Braille cell update and the servos move. Useful for verifying wiring and servo angles.

### Braille viewer *(zero setup)*

```bash
python3 braille_display.py
```

Press any letter to see its Braille dot pattern. No API keys, no Ollama, no Arduino.

---

## Braille Dot Layout

```
[ Dot 1 ]  [ Dot 4 ]
[ Dot 2 ]  [ Dot 5 ]
[ Dot 3 ]  [ Dot 6 ]
```

The 6-character binary string maps left-to-right across dots 1–6.  
Example: letter **K** (dots 1, 3) → `"101000"` → servo 1 and servo 3 raise up.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Vision + language (offline) | **Gemma 4** via Ollama (`gemma4:e4b`) |
| Speech-to-text (offline) | OpenAI Whisper (runs locally) |
| OCR (cloud) | Google Gemini 2.5 Flash |
| Text cleanup (cloud) | Anthropic Claude Sonnet 4.6 |
| UI | Python tkinter + Pillow |
| Camera | OpenCV |
| Hardware control | pyserial → Arduino Uno |
| Servos | 6× standard hobby servos on pins 2–7 |
| TTS | ElevenLabs API → pyttsx3 → macOS `say` |

---

## Hackathon Tracks

- **Best Use of Gemini API** — Gemini 2.5 Flash powers the vision OCR step in the cloud pipeline
- **Best Assistive Technology / Accessibility Hack**
