# AI-Powered Braille Display — HackDavis 2026

A physical assistive device that reads real-world text through a webcam, processes it with AI, and outputs it in Grade 1 Braille — both on screen and physically via 6 servo motors that raise and lower pins.

---

## How It Works

```
Webcam → Gemini Vision OCR → Claude AI Cleanup → Braille Cell UI → Arduino → 6 Servo Motors → TTS Voice
```

1. **Webcam** captures a live image of text (a book, sign, screen, etc.)
2. **Google Gemini 2.5 Flash** performs OCR — extracting raw text from the image
3. **Anthropic Claude** cleans up OCR errors, fixes spelling, removes gibberish
4. **Braille converter** maps each letter to its Grade 1 Braille dot pattern
5. **tkinter UI** displays the Braille cell visually — 6 dots in a 2×3 grid
6. **Arduino** receives a 6-character binary string (e.g. `"101010"`) over serial and moves 6 servo motors to physically raise or lower Braille pins
7. **Text-to-speech** announces each letter aloud (ElevenLabs → pyttsx3 → macOS `say` fallback)

---

## Files

| File | Description |
|------|-------------|
| `braille_pipeline.py` | Main app — full end-to-end pipeline with live camera, OCR, Claude, Braille display, Arduino, and TTS |
| `braille_servo_test.py` | Standalone servo tester — press a letter key to instantly test the Braille cell UI and servo movement without needing the AI pipeline |
| `braille_display.py` | Minimal Braille cell viewer — press a–z to see the dot pattern, no hardware required |
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

### 3. Add your API keys

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

### 4. Set up the Arduino

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
| OCR | Google Gemini 2.5 Flash (Vision) |
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
