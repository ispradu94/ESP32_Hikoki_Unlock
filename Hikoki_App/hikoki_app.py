"""Hikoki Battery Tool - small desktop front-end for the HIKOKI ESP32 firmware.

Talks to the board over a serial port using the firmware's single-key console
protocol (0-5 = screens, 6 = unlock, p = sleep) and interprets the text replies.
"""
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import serial
from serial.tools import list_ports

DEFAULT_BAUD = 115200
BAUD_RATES = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]

# (button label, key sent to the board)
SCREENS = [
    ("Battery info", "0"),
    ("Voltage / Temp", "1"),
    ("Error log", "2"),
    ("Tools used", "3"),
    ("Detected errors", "4"),
    ("Overload stats", "5"),
]

ERROR_MARKER = "Cannot read battery"
HARD_TIMEOUT_S = 90.0
IDLE_DONE_S = 0.7


class BoardLink:
    """Serial connection to the board; one command at a time."""

    def __init__(self):
        self.ser = None
        self.lock = threading.Lock()

    @property
    def connected(self):
        return self.ser is not None and self.ser.is_open

    def open(self, port, baud):
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = baud
        ser.timeout = 0.1
        # Keep DTR/RTS low so opening the port does not reset the ESP32.
        ser.dtr = False
        ser.rts = False
        ser.open()
        self.ser = ser

    def close(self):
        if self.ser is not None:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def run(self, key, on_text=None):
        """Send one key and collect the reply text until it looks complete."""
        with self.lock:
            ser = self.ser
            ser.reset_input_buffer()
            ser.write(key.encode("ascii"))
            buf = ""
            start = last_rx = time.monotonic()
            while True:
                chunk = ser.read(256)
                now = time.monotonic()
                if chunk:
                    text = chunk.decode("utf-8", errors="replace")
                    buf += text
                    last_rx = now
                    if on_text:
                        on_text(text)
                idle = now - last_rx
                if ERROR_MARKER in buf and idle > 0.3:
                    break
                if key == "6" and "Done" in buf and idle > 0.3:
                    break
                if key.lower() == "p" and buf and idle > 1.0:
                    break
                if key in "012345" and "===" in buf and idle > IDLE_DONE_S:
                    break
                if now - start > HARD_TIMEOUT_S:
                    break
            return buf


# ---------- interpretation of the replies ----------

KV_RE = re.compile(r"^\s*([^:|=]+?)\s*:\s*(.+?)\s*$")


def parse_reply(text):
    """Return (title, rows, error) where rows is a list of (item, value)."""
    title = ""
    rows = []
    error = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("--- Working"):
            continue
        if ERROR_MARKER in line:
            error = "Cannot read the battery. Check the connection and try again."
            continue
        if line.startswith("==="):
            title = line.strip("= ").strip()
            continue
        if " | " in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3:
                fatal, charge_no, msg = parts
                rows.append((msg, f"Fatal: {'Yes' if fatal == 'Y' else 'No'}   Charge #: {charge_no}"))
                continue
        # The firmware prints some pairs on one line, separated by two spaces.
        for part in re.split(r"\s{2,}", line):
            m = KV_RE.match(part)
            if m:
                rows.append((m.group(1), m.group(2)))
            else:
                rows.append((part, ""))
    return title, rows, error


def analyse_voltage(text):
    """Cell/bank analysis from the 'Voltage / Temp' screen, same rules as the web page."""
    cells = [float(v) for v in re.findall(r"L[1-5]:\s*(-?\d+\.\d+)v", text)]
    lower = re.search(r"Lower bank:\s*(-?\d+\.\d+)v", text)
    upper = re.search(r"Upper bank:\s*(-?\d+\.\d+)v", text)
    if len(cells) != 5 or not lower or not upper:
        return []
    cell_diff = max(cells) - min(cells)
    bank_diff = abs(float(lower.group(1)) - float(upper.group(1)))
    notes = [
        f"Cell diff: {cell_diff:.3f} V   Bank diff: {bank_diff:.3f} V",
        "Rebalance all battery cells" if cell_diff > 0.05 else "Cells are in good condition",
    ]
    low = [str(i + 1) for i, v in enumerate(cells) if v < 2.5]
    if low:
        notes.append(f"Check the condition of cell(s): {', '.join(low)}")
    notes.append(
        "Check the voltage of all battery cells again"
        if bank_diff > 0.05 else "Both banks are in good condition"
    )
    return notes


# ---------- GUI ----------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hikoki Battery Tool")
        self.geometry("720x560")
        self.minsize(620, 480)
        self._set_icon()
        self.link = BoardLink()
        self.events = queue.Queue()
        self.busy = False
        self.action_buttons = []

        self._build_connection_bar()
        self._build_tabs()
        self._build_status_bar()
        self.refresh_ports()
        self._set_connected(False)
        self.after(100, self._pump_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_icon(self):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "icon.ico")
        try:
            if sys.platform.startswith("win"):
                self.iconbitmap(path)
            else:
                self.iconphoto(True, tk.PhotoImage(file=os.path.join(base, "icon.png")))
        except tk.TclError:
            pass

    def _build_connection_bar(self):
        bar = ttk.Frame(self, padding=(8, 8, 8, 0))
        bar.pack(fill="x")
        ttk.Label(bar, text="Port:").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(bar, textvariable=self.port_var, width=28, state="readonly")
        self.port_box.pack(side="left", padx=(4, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh_ports).pack(side="left")
        ttk.Label(bar, text="Baud:").pack(side="left", padx=(12, 0))
        self.baud_var = tk.StringVar(value=str(DEFAULT_BAUD))
        ttk.Combobox(bar, textvariable=self.baud_var, values=BAUD_RATES, width=9).pack(side="left", padx=4)
        self.connect_btn = ttk.Button(bar, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(side="left", padx=(12, 0))

    def _build_tabs(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        hikoki = ttk.Frame(nb, padding=8)
        nb.add(hikoki, text="HIKOKI")
        self._build_hikoki_tab(hikoki)

        for name in ("Makita LXT", "Makita XGT"):
            f = ttk.Frame(nb)
            nb.add(f, text=name)
            ttk.Label(f, text=name, font=("Segoe UI", 16, "bold")).pack(pady=(60, 6))
            ttk.Label(f, text="Coming soon", foreground="#777777").pack()

    def _build_hikoki_tab(self, parent):
        buttons = ttk.Frame(parent)
        buttons.pack(fill="x")
        for i, (label, key) in enumerate(SCREENS):
            b = ttk.Button(buttons, text=label, command=lambda k=key, l=label: self.start_command(k, l))
            b.grid(row=0, column=i, sticky="ew", padx=2, pady=2)
            buttons.columnconfigure(i, weight=1)
            self.action_buttons.append(b)

        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(2, 6))
        unlock = ttk.Button(actions, text="Unlock battery", command=self.do_unlock)
        sleep = ttk.Button(actions, text="Tool sleep", command=self.do_sleep)
        unlock.pack(side="left", padx=2)
        sleep.pack(side="left", padx=2)
        self.action_buttons += [unlock, sleep]

        self.result_title = ttk.Label(parent, text="No data yet", font=("Segoe UI", 11, "bold"))
        self.result_title.pack(anchor="w")

        paned = ttk.PanedWindow(parent, orient="vertical")
        paned.pack(fill="both", expand=True, pady=(4, 0))

        top = ttk.Frame(paned)
        self.tree = ttk.Treeview(top, columns=("item", "value"), show="headings", height=10)
        self.tree.heading("item", text="Item")
        self.tree.heading("value", text="Value")
        self.tree.column("item", width=300)
        self.tree.column("value", width=300)
        sb = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        paned.add(top, weight=3)

        self.analysis = tk.Text(parent, height=4, wrap="word", state="disabled", background="#f4f4f4")
        paned.add(self.analysis, weight=1)

        self.log = tk.Text(parent, height=6, wrap="word", state="disabled", font=("Consolas", 9))
        paned.add(self.log, weight=2)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Disconnected")
        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=(6, 2)).pack(fill="x")

    # ----- connection -----

    def refresh_ports(self):
        ports = [f"{p.device} - {p.description}" for p in list_ports.comports()]
        self.port_box["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
        elif not ports:
            self.port_var.set("")

    def toggle_connection(self):
        if self.link.connected:
            self.link.close()
            self._set_connected(False)
            self.status_var.set("Disconnected")
            return
        port = self.port_var.get().split(" - ")[0].strip()
        if not port:
            messagebox.showwarning("Port", "Select a serial port first.")
            return
        try:
            baud = int(self.baud_var.get())
        except ValueError:
            messagebox.showwarning("Baud rate", "Baud rate must be a number.")
            return
        try:
            self.link.open(port, baud)
        except (serial.SerialException, OSError) as e:
            messagebox.showerror("Connection failed", str(e))
            return
        self._set_connected(True)
        self.status_var.set(f"Connected to {port} @ {baud}")

    def _set_connected(self, connected):
        self.connect_btn.configure(text="Disconnect" if connected else "Connect")
        self._update_buttons()

    def _update_buttons(self):
        state = "normal" if self.link.connected and not self.busy else "disabled"
        for b in self.action_buttons:
            b.configure(state=state)

    # ----- commands -----

    def start_command(self, key, label):
        if not self.link.connected or self.busy:
            return
        self.busy = True
        self._update_buttons()
        self.status_var.set(f"{label}: waiting for the board...")
        self._append_log(f"\n>>> {label} (key '{key}')\n")

        def worker():
            try:
                text = self.link.run(key, on_text=lambda t: self.events.put(("log", t)))
                self.events.put(("done", key, label, text))
            except (serial.SerialException, OSError) as e:
                self.events.put(("fail", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def do_unlock(self):
        if messagebox.askyesno("Unlock", "Send the unlock command to the battery?"):
            self.start_command("6", "Unlock")

    def do_sleep(self):
        if messagebox.askyesno(
            "Tool sleep",
            "The board goes into deep sleep and must be reset (EN button) to wake up.\nContinue?",
        ):
            self.start_command("p", "Tool sleep")

    def _pump_events(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if ev[0] == "log":
                    self._append_log(ev[1])
                elif ev[0] == "done":
                    self._show_result(*ev[1:])
                elif ev[0] == "fail":
                    self.busy = False
                    self.link.close()
                    self._set_connected(False)
                    self.status_var.set("Connection lost")
                    messagebox.showerror("Serial error", ev[1])
        except queue.Empty:
            pass
        self.after(100, self._pump_events)

    def _show_result(self, key, label, text):
        self.busy = False
        self._update_buttons()
        title, rows, error = parse_reply(text)
        self.tree.delete(*self.tree.get_children())
        notes = []

        if not text.strip():
            self.result_title.configure(text=label)
            self.status_var.set(f"{label}: no response from the board (check port/baud)")
            notes.append("No response. Check the port, baud rate and that the HIKOKI firmware is running.")
        elif error:
            self.result_title.configure(text=label)
            self.status_var.set(f"{label}: failed")
            notes.append(error)
        else:
            self.result_title.configure(text=title or label)
            for item, value in rows:
                self.tree.insert("", "end", values=(item, value))
            self.status_var.set(f"{label}: done")
            if key == "1":
                notes += analyse_voltage(text)
            elif key == "6":
                notes.append("Unlock command sent.")
            elif key.lower() == "p":
                notes.append("Board is in deep sleep. Press its reset (EN) button to wake it up.")

        self.analysis.configure(state="normal")
        self.analysis.delete("1.0", "end")
        self.analysis.insert("1.0", "\n".join(notes))
        self.analysis.configure(state="disabled")

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _on_close(self):
        self.link.close()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
