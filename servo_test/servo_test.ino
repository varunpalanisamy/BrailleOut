#include <Servo.h>

Servo s1, s2, s3, s4, s5, s6;

void setup() {
  s1.attach(2);
  s2.attach(3);
  s3.attach(4);
  s4.attach(5);
  s5.attach(6);
  s6.attach(7);

  // Start all at center (90 degrees)
  s1.write(90);
  s2.write(90);
  s3.write(90);
  s4.write(90);
  s5.write(90);
  s6.write(90);
  delay(1000);
}

void moveAll(int deg) {
  s1.write(deg);
  s2.write(deg);
  s3.write(deg);
  s4.write(deg);
  s5.write(deg);
  s6.write(deg);
}

void loop() {
  moveAll(95);
  delay(2000);
  
  moveAll(85);
  delay(2000);
}