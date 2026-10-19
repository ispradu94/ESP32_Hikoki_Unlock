# ESP32 Hikoki Unlock

Read and unlock Hikoki / HiKOKI 18V/36V (MultiVolt) lithium batteries with an ESP32.

The ESP32 talks to the battery over its single-wire serial line (9600 baud, bit-banged) and exposes the data in two ways:

- **Wi-Fi web interface** — the board creates its own access point; open a page from your phone or PC.
- **Desktop app** — a small Python/Tkinter program (Windows and Linux) that talks to the board over USB serial.

Features: battery model, serial number, manufacture date, charge count, cell and bank voltages, temperatures, error log, tools used, safety flags, overload statistics, **lockout reset (unlock)** and tool sleep.

> Makita LXT / XGT are placeholders ("Coming soon") in both the web page and the desktop app.

> **Warning:** unlocking a battery that was locked by a safety error (overcharge, damaged cells, blown fuse) can be dangerous. Use at your own risk.

## Repository layout

| Folder | Content |
|---|---|
| [`HIKOKI/`](HIKOKI) | Arduino sketch (`HIKOKI.ino`) + `HikokiSerial.h` (local bit-bang serial driver) |
| [`HikokiSerial/`](HikokiSerial) | Same driver as a standalone library (optional, see below) |
| [`Hikoki_App/`](Hikoki_App) | Desktop app (Python, Tkinter + pyserial) |

## 1. Flashing the ESP32 (Arduino IDE)

Tested target: **LOLIN32 V1.0.0** (any ESP32 board should work).

1. Install **Arduino IDE 2.x** from <https://www.arduino.cc/en/software>.
2. Install the USB driver if Windows does not show a COM port (LOLIN32 usually uses **CH340**).
3. Add the ESP32 board package: **File → Preferences → Additional boards manager URLs**, add
   ```
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```
4. **Tools → Board → Boards Manager**, search `esp32` (by Espressif Systems) and install it.
5. Select the board: **Tools → Board → esp32 → WEMOS LOLIN32** (or *ESP32 Dev Module*).
6. Select the port in **Tools → Port**. Upload speed 115200 is the safest; partition scheme *Default*.
7. Open [`HIKOKI/HIKOKI.ino`](HIKOKI/HIKOKI.ino) and press **Upload**. If it stays on `Connecting...`, hold the **BOOT** button.

No extra libraries are needed: `WiFi` and `WebServer` come with the ESP32 core, and `HikokiSerial.h` already sits next to the sketch (included with `#include "HikokiSerial.h"`).

The standalone [`HikokiSerial/`](HikokiSerial) folder is only needed if you prefer a shared library: copy it to `Documents/Arduino/libraries/` and use `#include <HikokiSerial.h>`.

### Wiring

Default pins (edit the `HikokiSerial serial1(...)` line in the sketch to change them):

| Signal | GPIO |
|---|---|
| OUT (to battery data line) | 18 |
| Inverted OUT | 17 |
| IN (from battery data line) | 16 |

Without a battery connected the board still boots and serves the pages, but data reads fail with *"Cannot read battery"*.

### Web interface

1. Connect to the Wi-Fi network **`HikokiUnlock`** (password `12345678`). Change `WIFI_SSID` / `WIFI_PASS` in the sketch if you want.
2. Open <http://192.168.4.1> in a browser, then choose **HIKOKI**.

### Serial console (115200 baud)

| Key | Action |
|---|---|
| `0` | Battery information |
| `1` | Voltage and temperature |
| `2` | Error log |
| `3` | Tools used |
| `4` | Detected errors |
| `5` | Overload statistics |
| `6` | Unlock (reset lockout) |
| `p` | Deep sleep (reset the board to wake it) |

## 2. Desktop app

The app is a front-end for the serial console above: pick the USB port and baud rate (default **115200**), press **Connect**, then use the buttons. Replies are parsed into a table, with a short analysis for cell and bank voltages.

### Run from source

Requirements: **Python 3.9+** with Tkinter, and `pyserial`.

**Windows**
```powershell
cd Hikoki_App
python -m pip install -r requirements.txt
python hikoki_app.py
```

**Linux (Debian/Ubuntu)**
```bash
sudo apt install python3 python3-pip python3-tk
cd Hikoki_App
python3 -m pip install -r requirements.txt
python3 hikoki_app.py
```
On Linux your user must be allowed to open the serial port:
```bash
sudo usermod -aG dialout $USER   # then log out and back in
```

### Build a standalone executable

[PyInstaller](https://pyinstaller.org) builds for the OS it runs on, so build on Windows for a Windows `.exe` and on Linux for a Linux binary.

**Windows** (output: `Hikoki_App/dist/Hikoki_App.exe`)
```powershell
cd Hikoki_App
python -m pip install -r requirements.txt
python -m PyInstaller --onefile --noconsole --name Hikoki_App --icon icon.ico --add-data "icon.ico;." --add-data "icon.png;." hikoki_app.py
```

**Linux** (output: `Hikoki_App/dist/Hikoki_App`)
```bash
cd Hikoki_App
python3 -m pip install -r requirements.txt
python3 -m PyInstaller --onefile --noconsole --name Hikoki_App --add-data "icon.png:." hikoki_app.py
```

### Regenerating the icon (optional)

```bash
python -m pip install pillow
python make_icon.py
```

## Troubleshooting

- **No COM port / port not listed** — install the CH340 (or CP210x) driver, try another USB cable (some are charge-only), press *Refresh*.
- **Upload stuck on `Connecting...`** — hold the BOOT button while uploading.
- **"Cannot read battery"** — check wiring, pin numbers and that the battery is attached.
- **Windows shows an old icon for the `.exe`** — it is the Windows icon cache; rename the file or restart Explorer.
