#ifndef HikokiSerial_h
#define HikokiSerial_h

#include <Arduino.h>

class HikokiSerial {
  public:
    HikokiSerial(uint8_t outpin, uint8_t inv_outpin, uint8_t inpin) {
      _outpin = outpin;
      _inv_outpin = inv_outpin;
      _inpin = inpin;
      
      pinMode(_inpin, INPUT);
      pinMode(_outpin, OUTPUT);
      pinMode(_inv_outpin, OUTPUT);

      digitalWrite(_outpin, LOW);
      digitalWrite(_inv_outpin, HIGH);

      _tx_delay = 104; // 1000000 / 9600
    }

  void write(uint8_t * buff, int len) {
    for (int i = 0; i < len; i++) write(buff[i]);
  }

  void read(uint8_t * buff, int len) {
    for (int i = 0; i < len; i++) {
        // Read everything without aborting on errors
        buff[i] = (uint8_t)recv();
    }
  }

  int recv() {
    int data = 0;
    uint32_t waitIter = 3000; 
    
    // 1. Wait for the start bit (the battery must pull the line LOW)
    // This avoids reading "air" and a wall of garbage
    while (digitalRead(_inpin) == HIGH) {
        esp_rom_delay_us(10);
        if (--waitIter == 0) return 0; 
    }

    noInterrupts(); 

    // 2. Aim for the middle of the first data bit (1.5 bits = 156us)
    esp_rom_delay_us(156); 

    // 3. Read 8 bits
    for (uint8_t i = 1; i > 0; i <<= 1) {
      // Working polarity: HIGH on the line is bit 1
      if (digitalRead(_inpin) == HIGH) data |= i; 
      esp_rom_delay_us(104);
    }
    
    interrupts();
    return data;
  }

  void write(uint8_t b) {
    noInterrupts(); 
    // Bit startu
    digitalWrite(_outpin, HIGH);
    digitalWrite(_inv_outpin, LOW);
    esp_rom_delay_us(104);

    for (uint8_t i = 1; i > 0; i <<= 1) {
      if (b & i){
        digitalWrite(_outpin, LOW);
        digitalWrite(_inv_outpin, HIGH);
      } else {
        digitalWrite(_outpin, HIGH);
        digitalWrite(_inv_outpin, LOW);    
      }
      esp_rom_delay_us(104);
    }

    digitalWrite(_outpin, LOW);
    digitalWrite(_inv_outpin, HIGH);
    esp_rom_delay_us(104);
    interrupts();
  }

  private: 
    uint8_t _outpin, _inv_outpin, _inpin;
    uint16_t _tx_delay;
};

#endif