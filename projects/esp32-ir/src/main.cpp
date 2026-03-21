// ESP32 IR Receiver + Sender
//
// Wiring:
//   IR Receiver data pin -> GPIO14
//   IR LED anode         -> GPIO15 (via transistor / resistor)
//
// Serial monitor: 115200 baud
//
// This program listens for IR signals and prints decoded values.
// Press the built-in boot button (GPIO0) to send a test NEC signal.

#include <Arduino.h>
#include <IRrecv.h>
#include <IRsend.h>
#include <IRutils.h>

// ----- Pin assignments -----
const uint16_t kRecvPin = 14;   // IR receiver data out
const uint16_t kSendPin = 15;   // IR LED control
const uint8_t  kButtonPin = 0;  // BOOT button on most ESP32 DevKits

// ----- IR objects -----
IRrecv irrecv(kRecvPin);
IRsend irsend(kSendPin);
decode_results results;

// A known NEC test code (e.g. a common remote power button).
// Replace with a real code captured from your remote.
const uint32_t kTestNecCode = 0x00FF6897;

void setup() {
    Serial.begin(115200);
    while (!Serial) { delay(50); }

    // Start the IR receiver
    irrecv.enableIRIn();

    // Start the IR sender
    irsend.begin();

    // Boot button as input (has external pull-up on most DevKits)
    pinMode(kButtonPin, INPUT_PULLUP);

    Serial.println();
    Serial.println("=== ESP32 IR Receiver + Sender ===");
    Serial.println("Listening for IR signals on GPIO" + String(kRecvPin));
    Serial.println("Press BOOT button to send test NEC code on GPIO" + String(kSendPin));
    Serial.println();
}

void loop() {
    // --- Receive ---
    if (irrecv.decode(&results)) {
        Serial.print("[RX] Protocol: ");
        Serial.print(typeToString(results.decode_type));
        Serial.print("  Value: 0x");
        serialPrintUint64(results.value, HEX);
        Serial.print("  Bits: ");
        Serial.println(results.bits);

        // Print a reconstruction of the Arduino/C++ send call
        Serial.println(resultToSourceCode(&results));
        Serial.println();

        irrecv.resume();  // Ready for next signal
    }

    // --- Send (on button press) ---
    if (digitalRead(kButtonPin) == LOW) {
        Serial.println("[TX] Sending NEC test code: 0x" + String(kTestNecCode, HEX));
        irsend.sendNEC(kTestNecCode, 32);
        delay(500);  // Simple debounce
    }

    delay(100);
}
