# AI-Powered Braille Display

A physical assistive device that reads real-world text through a webcam, processes it with AI, and outputs it in Grade 1 Braille — both on screen and physically via 6 servo motors that raise and lower pins.

---

## Images

<p align="center">
  <img src="https://github.com/user-attachments/assets/3e99b283-588e-4927-b53b-b73a82a5d44b" width="300" />
  <img src="https://github.com/user-attachments/assets/96bac622-504a-4019-b788-d26084b8f8d5" width="500" />
</p>



| ![Underneath the Braille table](https://github.com/user-attachments/assets/630b9906-6fc6-4bc3-983f-a83d06162c6b) | ![Top view of Braille Table](https://github.com/user-attachments/assets/c158f615-d1e1-42b4-b6a4-e974968ffeb9) | ![Arduino and Base Studio](https://github.com/user-attachments/assets/ddee993b-5c24-40fa-bb29-e56fe5d9a45e) |
| :---: | :---: | :---: |
| Underneath the Braille table with 6 servo motors | Top view of Braille Table | Arduino and Base Studio with jumper wires |


## How It Works

**Cloud pipeline (Gemini + Claude):**
```
Webcam → Gemini Vision OCR → Claude AI Cleanup → Braille Cell UI → Arduino → 6 Servo Motors → TTS Voice
```

**Local pipeline (Gemma via Ollama — no API keys needed):**
```
Webcam + Microphone → Whisper STT → Gemma 4 (Ollama, offline) → Braille Cell UI → Arduino → TTS Voice
```

1. **Webcam** captures a live image of text (a book, sign, screen, etc.)
2. **Google Gemini 2.5 Flash** (or **Gemma 4 locally via Ollama**) performs OCR — extracting raw text from the image
3. **Anthropic Claude** cleans up OCR errors in the cloud pipeline; Gemma handles everything locally in the offline pipeline
4. **Braille converter** maps each letter to its Grade 1 Braille dot pattern
5. **tkinter UI** displays the Braille cell visually — 6 dots in a 2×3 grid
6. **Arduino** receives a 6-character binary string (e.g. `"101010"`) over serial and moves 6 servo motors to physically raise or lower Braille pins *(optional — see below)*
7. **Text-to-speech** announces each letter aloud (ElevenLabs → pyttsx3 → macOS `say` fallback)

---

## Files

| File | Description |
|------|-------------|
| `braille_pipeline.py` | Main app — full end-to-end pipeline with live camera, OCR, Claude, Braille display, Arduino, and TTS |
| `gemma_pipeline.py` | Offline pipeline — uses local Gemma 4 via Ollama (no API keys); supports voice input via Whisper + webcam vision |
| `api_server.py` | Flask backend for the web frontend — streams Gemma vision analysis via Server-Sent Events |
| `braille_servo_test.py` | Standalone servo tester — press a letter key to instantly test the Braille cell UI and servo movement without needing the AI pipeline |
| `braille_display.py` | Minimal Braille cell viewer — press a–z to see the dot pattern, **no hardware or API keys required** |
| `requirements.txt` | All Python dependencies |

---

## No Hardware? No Problem

**You do not need an Arduino or servo motors to run this project.** The hardware is what makes it a physical assistive device, but every pipeline still displays Braille on-screen in a visual UI — so you can fully explore and demo the project as a software prototype with zero physical components.

| Mode | What you need | What you see |
|------|--------------|--------------|
| `braille_display.py` | Nothing — no keys, no hardware | Braille dot patterns for any letter you press |
| `gemma_pipeline.py` | Ollama + Gemma model (offline, free) | Live Braille cell UI driven by your webcam and voice |
| `braille_pipeline.py` | API keys (Gemini + Anthropic) | Full pipeline UI — Braille cell updates after each capture |

If no Arduino is connected, the serial output step is simply skipped — everything else (OCR, AI, Braille cell display, TTS) runs exactly the same. **The Braille cell will still light up on screen for every letter.**

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

### 3. Add your API keys *(cloud pipeline only — skip if using Gemma)*

Create a `.env` file in the project root (never commit this):

```
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
ELEVENLABS_API_KEY=...   # optional — falls back to macOS say
```

Get keys from:
- **Anthropic**: [console.anthropic.com](https://console.anthropic.com)
- **Google Gemini**: [aistudio.google.com](https://aistudio.google.com)
- **ElevenLabs**: [elevenlabs.io](https://elevenlabs.io) *(optional)*

### 4. Set up Ollama + Gemma *(offline pipeline only — skip if using cloud APIs)*

The `gemma_pipeline.py` runs entirely offline using a local model. No API keys are needed.

```bash
# Install Ollama
brew install ollama          # macOS
# Windows / Linux: download from https://ollama.com

# Start the Ollama daemon (keep this running in the background)
ollama serve

# Pull the Gemma 4 model — one-time ~3 GB download, runs offline after
ollama pull gemma4:e4b
```

Once pulled, the model is cached locally and works without an internet connection.

### 5. Set up the Arduino *(optional — skip if running as a software prototype)*

1. Install [Arduino IDE](https://www.arduino.cc/en/software)
2. Wire 6 servos to digital pins 2–7
3. Upload the sketch below (one-time step — IDE can close after)
4. Find your serial port:
   ```bash
   ls /dev/cu.*
   ```
5. Update `SERIAL_PORT` in both `braille_pipeline.py` and `braille_servo_test.py` to match

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

    // All pins down first (visible reset)
    for (int i = 0; i < 6; i++) s[i].write(DOWN_DEG);
    delay(350);

    // Raise only the active dots
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

### Full pipeline (webcam + AI + servos + TTS)

```bash
python3 braille_pipeline.py
```

1. A window opens showing your live webcam feed
2. Point the camera at any printed or on-screen text
3. Click **CAPTURE TEXT** — Gemini OCR and Claude run in the background
4. Use **NEXT →** / **← PREV** (or SPACE / arrow keys) to step through each letter
5. The Braille cell lights up on screen, the servos move physically, and the letter is spoken aloud

### Offline pipeline — Gemma via Ollama (no API keys, no internet)

> **Requires**: Ollama running (`ollama serve`) with `gemma4:e4b` pulled — see Setup step 4.

```bash
python3 gemma_pipeline.py
```

1. A Tkinter window opens with a live webcam feed and Braille cell display
2. Speak a word or point the camera at text — Whisper transcribes audio locally
3. Gemma 4 processes the image and/or transcript entirely on your machine
4. The Braille cell updates on screen for each letter; servos move if an Arduino is connected
5. No API keys or internet connection needed after the one-time model pull

### Servo tester (no AI needed)

```bash
python3 braille_servo_test.py
```

Press any letter key (a–z) to immediately see the Braille cell update and the servos move. Use this to verify wiring and servo angles before running the full pipeline.

### Braille viewer only (no hardware needed)

```bash
python3 braille_display.py
```

Simple demo — press a letter key to see its Braille dot pattern. No API keys or Arduino required.

---

## Braille Dot Layout

```
[ Dot 1 ]  [ Dot 4 ]
[ Dot 2 ]  [ Dot 5 ]
[ Dot 3 ]  [ Dot 6 ]
```

The 6-character binary pattern sent to Arduino maps left-to-right across dots 1–6.
Example: letter **K** (dots 1, 3) → `"101000"` → servo 1 and servo 3 raise up.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| OCR (cloud) | Google Gemini 2.5 Flash (Vision) |
| OCR (offline) | Gemma 4 via Ollama (`gemma4:e4b`) |
| Speech-to-text (offline) | OpenAI Whisper (local) |
| Text cleanup | Anthropic Claude Sonnet 4.6 |
| UI | Python tkinter + Pillow |
| Camera | OpenCV |
| Hardware control | pyserial → Arduino Uno |
| Servos | 6× standard hobby servos on pins 2–7 |
| TTS | ElevenLabs API → pyttsx3 → macOS `say` |

---

## Hackathon Tracks

- **Best Use of Gemini API** — Gemini 2.5 Flash powers the vision OCR step
- **Best Assistive Technology / Accessibility Hack**
