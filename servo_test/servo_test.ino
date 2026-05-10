#include <Servo.h>

Servo s[6];
const int PINS[6]  = {2, 3, 4, 5, 6, 7};
const int UP_DEG   = 95;
const int DOWN_DEG = 85;

// Servos 2 and 5 (index 1 and 4) use half the angle range
const int UP_DEG_SMALL   = 94;
const int DOWN_DEG_SMALL = 86;


void writeServo(int i, bool up) {
  bool isSmall = (i == 1 || i == 4);
  bool isFlipped = (i == 4);  // servo 5 is upside down

  bool actualUp = isFlipped ? !up : up;

  if (actualUp) {
    s[i].write(isSmall ? UP_DEG_SMALL : UP_DEG);
  } else {
    s[i].write(isSmall ? DOWN_DEG_SMALL : DOWN_DEG);
  }
}

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < 6; i++) {
    s[i].attach(PINS[i]);
    writeServo(i, false);
  }
  delay(300);

  for (int i = 0; i < 6; i++) writeServo(i, true);
  Serial.println("ALL_UP");
  delay(1000);

  for (int i = 0; i < 6; i++) writeServo(i, false);
  Serial.println("ALL_DOWN");
  delay(500);

  for (int i = 0; i < 6; i++) {
    writeServo(i, true);
    Serial.print("SERVO_");
    Serial.println(i + 1);
    delay(500);
    writeServo(i, false);
    delay(300);
  }

  Serial.println("READY");
}

void loop() {
  if (Serial.available() > 0) {
    char buf[16];
    int len = Serial.readBytesUntil('\n', buf, 15);
    buf[len] = '\0';
    while (Serial.available()) Serial.read();
    if (len == 6) {
      for (int i = 0; i < 6; i++) {
        writeServo(i, buf[i] == '1');
      }
    }
  }
}
