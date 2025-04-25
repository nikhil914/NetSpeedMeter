import tkinter as tk
from tkinter import ttk
import psutil
import time
import threading
import pystray
from PIL import Image, ImageDraw
import ctypes
import os
import sys
import winreg
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pickle
from datetime import datetime

class NetSpeedMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Net Speed Monitor")
        self.root.geometry("200x50+100+100")
        self.root.overrideredirect(True)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        self.is_hidden = False
        self.always_on_top = tk.BooleanVar(value=True)
        self.theme = tk.StringVar(value="green")
        self.unit = tk.StringVar(value="KB/s")
        self.running = True

        self.offset_x = 0
        self.offset_y = 0

        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)
        self.root.bind("<Button-3>", self.show_context_menu)
        self.root.bind("<FocusOut>", self.ensure_on_top)
        self.root.after(1000, self.ensure_on_top)

        self.frame = tk.Frame(root, bg="#003300")
        self.frame.pack(fill="both", expand=True)

        self.download_label = tk.Label(self.frame, text="↓ 0 KB/s", fg="lime", bg="#003300", font=("Segoe UI", 10, "bold"))
        self.download_label.pack(side="left", padx=3, pady=5)

        self.upload_label = tk.Label(self.frame, text="↑ 0 KB/s", fg="lime", bg="#003300", font=("Segoe UI", 10, "bold"))
        self.upload_label.pack(side="left", padx=3, pady=5)

        self.prev_recv = psutil.net_io_counters().bytes_recv
        self.prev_sent = psutil.net_io_counters().bytes_sent

        self.data_history = {'download': [], 'upload': [], 'time': []}
        self.usage_totals = self.load_usage_totals()
        self.update_speed()

        self.setup_context_menu()
        self.setup_tray_icon()

    def ensure_on_top(self, event=None):
        if self.always_on_top.get():
            self.root.lift()
        self.root.after(2000, self.ensure_on_top)

    def start_move(self, event):
        self.offset_x = event.x
        self.offset_y = event.y

    def do_move(self, event):
        x = event.x_root - self.offset_x
        y = event.y_root - self.offset_y
        self.root.geometry(f"+{x}+{y}")

    def show_context_menu(self, event):
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def setup_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Toggle Visibility", command=self.toggle_visibility)
        self.context_menu.add_checkbutton(label="Always on Top", variable=self.always_on_top, command=self.set_always_on_top)
        self.context_menu.add_command(label="Settings", command=self.open_settings)
        self.context_menu.add_command(label="Usage Stats", command=self.show_usage_stats)
        self.context_menu.add_command(label="Quit", command=self.quit_app)

    def convert_units(self, speed):
        unit = self.unit.get()
        if unit == "KB/s":
            return speed / 1024, "KB/s"
        elif unit == "MB/s":
            return speed / (1024 * 1024), "MB/s"
        elif unit == "Mbps":
            return (speed * 8) / (1024 * 1024), "Mbps"
        else:
            return speed / 1024, "KB/s"

    def update_speed(self):
        new_recv = psutil.net_io_counters().bytes_recv
        new_sent = psutil.net_io_counters().bytes_sent

        down_speed = new_recv - self.prev_recv
        up_speed = new_sent - self.prev_sent

        self.prev_recv = new_recv
        self.prev_sent = new_sent

        converted_down, unit = self.convert_units(down_speed)
        converted_up, _ = self.convert_units(up_speed)

        self.download_label.config(text=f"↓ {converted_down:.1f} {unit}")
        self.upload_label.config(text=f"↑ {converted_up:.1f} {unit}")

        timestamp = time.time()
        self.data_history['download'].append(converted_down)
        self.data_history['upload'].append(converted_up)
        self.data_history['time'].append(timestamp)

        if len(self.data_history['time']) > 60:
            for key in self.data_history:
                self.data_history[key].pop(0)

        self.update_usage_totals(down_speed, up_speed)
        self.root.after(1000, self.update_speed)

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.geometry("300x300")
        settings_win.resizable(False, False)

        ttk.Label(settings_win, text="Theme").pack(pady=5)
        ttk.Button(settings_win, text="Toggle Theme", command=self.toggle_theme).pack(pady=5)

        ttk.Label(settings_win, text="Speed Unit").pack(pady=5)
        unit_dropdown = ttk.Combobox(settings_win, values=["KB/s", "MB/s", "Mbps"], textvariable=self.unit)
        unit_dropdown.pack(pady=5)

        ttk.Button(settings_win, text="Show Live Graph", command=self.show_graph).pack(pady=10)

        ttk.Checkbutton(settings_win, text="Always on Top", variable=self.always_on_top, command=self.set_always_on_top).pack(pady=5)

    def show_graph(self):
        graph_win = tk.Toplevel(self.root)
        graph_win.title("Live Speed Graph")
        fig, ax = plt.subplots(figsize=(5, 3), dpi=100)
        canvas = FigureCanvasTkAgg(fig, master=graph_win)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        def update():
            ax.clear()
            ax.plot(self.data_history['time'], self.data_history['download'], label="Download", color='green')
            ax.plot(self.data_history['time'], self.data_history['upload'], label="Upload", color='blue')
            ax.legend()
            ax.set_xlabel("Time")
            ax.set_ylabel("Speed")
            canvas.draw()
            graph_win.after(1000, update)

        update()

    def show_usage_stats(self):
        stats_win = tk.Toplevel(self.root)
        stats_win.title("Usage Statistics")
        stats_win.geometry("300x200")
        text = tk.Text(stats_win)
        text.pack(expand=True, fill="both")

        stats = self.usage_totals

        text.insert("end", f"Download Today: {stats['day_download'] / (1024**2):.2f} MB\n")
        text.insert("end", f"Download This Week: {stats['week_download'] / (1024**2):.2f} MB\n")
        text.insert("end", f"Download This Month: {stats['month_download'] / (1024**2):.2f} MB\n")
        text.insert("end", f"Download This Year: {stats['year_download'] / (1024**2):.2f} MB\n")

        text.insert("end", f"Upload Today: {stats['day_upload'] / (1024**2):.2f} MB\n")
        text.insert("end", f"Upload This Week: {stats['week_upload'] / (1024**2):.2f} MB\n")
        text.insert("end", f"Upload This Month: {stats['month_upload'] / (1024**2):.2f} MB\n")
        text.insert("end", f"Upload This Year: {stats['year_upload'] / (1024**2):.2f} MB\n")

    def update_usage_totals(self, down_bytes, up_bytes):
        now = datetime.now()
        stats = self.usage_totals
        last = stats.get('last_reset', now)

        if now.date() != last.date():
            stats['day_download'] = 0
            stats['day_upload'] = 0
        if now.isocalendar()[1] != last.isocalendar()[1]:
            stats['week_download'] = 0
            stats['week_upload'] = 0
        if now.month != last.month:
            stats['month_download'] = 0
            stats['month_upload'] = 0
        if now.year != last.year:
            stats['year_download'] = 0
            stats['year_upload'] = 0

        stats['day_download'] += down_bytes
        stats['week_download'] += down_bytes
        stats['month_download'] += down_bytes
        stats['year_download'] += down_bytes

        stats['day_upload'] += up_bytes
        stats['week_upload'] += up_bytes
        stats['month_upload'] += up_bytes
        stats['year_upload'] += up_bytes

        stats['last_reset'] = now
        with open("usage_totals.pkl", "wb") as f:
            pickle.dump(stats, f)

    def load_usage_totals(self):
        try:
            with open("usage_totals.pkl", "rb") as f:
                return pickle.load(f)
        except:
            return {
                'day_download': 0, 'week_download': 0, 'month_download': 0, 'year_download': 0,
                'day_upload': 0, 'week_upload': 0, 'month_upload': 0, 'year_upload': 0,
                'last_reset': datetime.now()
            }

    def set_always_on_top(self):
        self.root.wm_attributes("-topmost", self.always_on_top.get())
        if self.always_on_top.get():
            self.ensure_on_top()

    def toggle_theme(self):
        current = self.theme.get()
        if current == "green":
            self.theme.set("dark")
            self.frame.config(bg="black")
            self.download_label.config(bg="black", fg="white")
            self.upload_label.config(bg="black", fg="white")
        else:
            self.theme.set("green")
            self.frame.config(bg="#003300")
            self.download_label.config(bg="#003300", fg="lime")
            self.upload_label.config(bg="#003300", fg="lime")

    def setup_tray_icon(self):
        image = Image.new('RGB', (64, 64), color='black')
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill='white')
        self.icon = pystray.Icon("NetSpeedMonitor", image, menu=pystray.Menu(
            pystray.MenuItem(lambda item: "Show" if self.is_hidden else "Hide", self.toggle_visibility),
            pystray.MenuItem("Settings", self.open_settings),
            pystray.MenuItem("Always on Top", self.toggle_always_on_top_menu),
            pystray.MenuItem("Quit", self.quit_app)
        ))
        threading.Thread(target=self.icon.run, daemon=True).start()

    def toggle_always_on_top_menu(self):
        self.always_on_top.set(not self.always_on_top.get())
        self.set_always_on_top()

    def toggle_visibility(self):
        if self.is_hidden:
            self.root.after(0, self.root.deiconify)
            self.is_hidden = False
        else:
            self.root.withdraw()
            self.is_hidden = True

    def quit_app(self):
        self.running = False
        self.icon.stop()
        self.root.quit()

def add_to_startup():
    exe_path = sys.executable
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, "NetSpeedMonitor", 0, winreg.REG_SZ, exe_path)
    winreg.CloseKey(key)

if __name__ == "__main__":
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    app = NetSpeedMonitor(root)
    root.mainloop()
