"""
Real-time viewer for REBOUND simulations - full Solar System.
Toolbar at the top, full-frame simulation, live Python console on the right.

External dependencies (not installed via pip):
    - Notepad++ (external script editing), auto-detected if installed.

Run with (from the project root):
    venv\\Scripts\\python.exe notebooks\\01_live_viewer.py
"""
import csv
import io
import json
import math
import os
import sys
import subprocess
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext, filedialog, simpledialog, messagebox
from contextlib import redirect_stdout

import numpy as np
import rebound
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

NOTEBOOKS_DIR = Path(__file__).resolve().parent
BASE_DIR = NOTEBOOKS_DIR.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
BLACK_HOLES_PATH = DATA_DIR / "black_holes.json"


def find_notepadpp():
    candidates = [
        r"C:\Program Files\Notepad++\notepad++.exe",
        r"C:\Program Files (x86)\Notepad++\notepad++.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Notepad++", "notepad++.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


NOTEPADPP_PATH = find_notepadpp()


def load_black_hole_catalog():
    try:
        with open(BLACK_HOLES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)["black_holes"]
    except (OSError, json.JSONDecodeError, KeyError):
        return []


BLACK_HOLE_CATALOG = load_black_hole_catalog()

# name, displayed letter, color, marker size, mass (Msun), semi-major axis (AU), eccentricity
SUN = ("Sun", "S", "#FFA500", 16)
PLANETS = [
    ("Mercury", "Me", "#9C9C9C", 4, 1.660e-7, 0.387, 0.2056),
    ("Venus",   "V",  "#E6C27A", 5, 2.447e-6, 0.723, 0.0068),
    ("Earth",   "E",  "#3B78D8", 5, 3.003e-6, 1.000, 0.0167),
    ("Mars",    "Ma", "#C1440E", 4, 3.213e-7, 1.524, 0.0934),
    ("Jupiter", "J",  "#D8A46B", 10, 9.545e-4, 5.203, 0.0484),
    ("Saturn",  "Sa", "#E3C88A", 9, 2.858e-4, 9.537, 0.0542),
    ("Uranus",  "U",  "#9FD9D9", 7, 4.366e-5, 19.191, 0.0472),
    ("Neptune", "N",  "#4B70DD", 7, 5.151e-5, 30.069, 0.0086),
]


def build_sim():
    """Solar System: Sun + 8 planets (real orbital elements)."""
    sim = rebound.Simulation()
    sim.units = ('yr', 'AU', 'Msun')
    sim.add(m=1.0)  # Sun
    for _, _, _, _, mass, a, e in PLANETS:
        sim.add(m=mass, a=a, e=e)
    sim.integrator = "whfast"
    sim.dt = 0.005
    return sim


class SolarSystemApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Solar System - Real-Time Simulation")
        self.root.geometry("1500x900")
        self.root.configure(bg="#1e1e1e")

        self.sim = build_sim()
        self.n = len(self.sim.particles)
        self.trails = [[] for _ in range(self.n)]
        self.trail_len = 600
        self.body_names = [SUN[0]] + [p[0] for p in PLANETS]
        self.body_letters = [SUN[1]] + [p[1] for p in PLANETS]
        self.position_log = []  # (t, body, letter, x, y) - full history, not truncated
        self.speed = tk.DoubleVar(value=0.05)
        self.paused = False
        self.editor_path = None
        self.loaded_scripts = []  # paths of loaded scripts, shown in the right-click menu

        self._build_toolbar()
        self._build_body()
        self._build_figure()

        self.console_namespace = {
            "sim": self.sim, "app": self, "run": self.run_script_file,
            "BLACK_HOLES_PATH": BLACK_HOLES_PATH,
        }
        self._console_print("Interactive console - variables: sim, app, run(path)")
        self._console_print("Examples: sim.particles[1].m | app.speed.set(0.3) | app.reset()")

        self._tick()

    # ---------- UI ----------

    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg="#2d2d2d", height=42)
        bar.pack(side=tk.TOP, fill=tk.X)

        self.btn_pause = tk.Button(bar, text="Pause", width=10, command=self.toggle_pause,
                                    bg="#3c3c3c", fg="white", activebackground="#555")
        self.btn_pause.pack(side=tk.LEFT, padx=6, pady=6)

        btn_reset = tk.Button(bar, text="Reset", width=10, command=self.reset,
                               bg="#3c3c3c", fg="white", activebackground="#555")
        btn_reset.pack(side=tk.LEFT, padx=6, pady=6)

        btn_record_log = tk.Button(bar, text="Record Log", command=self.save_position_log,
                                    bg="#3c3c3c", fg="white", activebackground="#555")
        btn_record_log.pack(side=tk.LEFT, padx=6, pady=6)

        btn_load = tk.Button(bar, text="Load script...", command=self.load_script_dialog,
                              bg="#3c3c3c", fg="white", activebackground="#555")
        btn_load.pack(side=tk.LEFT, padx=6, pady=6)

        btn_idle = tk.Button(bar, text="Open in IDLE", command=self.open_in_idle,
                              bg="#3c3c3c", fg="white", activebackground="#555")
        btn_idle.pack(side=tk.LEFT, padx=6, pady=6)

        btn_npp = tk.Button(bar, text="Create/Edit script (Notepad++)", command=self.open_in_notepadpp,
                             bg="#3c3c3c", fg="white", activebackground="#555")
        btn_npp.pack(side=tk.LEFT, padx=6, pady=6)

        tk.Label(bar, text="Speed", bg="#2d2d2d", fg="white").pack(side=tk.LEFT, padx=(20, 5))
        scale = tk.Scale(bar, from_=0.005, to=1.0, resolution=0.005, orient=tk.HORIZONTAL,
                          variable=self.speed, length=220, bg="#2d2d2d", fg="white",
                          troughcolor="#444", highlightthickness=0)
        scale.pack(side=tk.LEFT, padx=6, pady=6)

        self.time_label = tk.Label(bar, text="t = 0.00 yr", bg="#2d2d2d", fg="#00ff88",
                                    font=("Consolas", 11, "bold"))
        self.time_label.pack(side=tk.RIGHT, padx=15)

    def _build_body(self):
        body = tk.Frame(self.root, bg="black")
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.plot_frame = tk.Frame(body, bg="black")
        self.plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.console_frame = tk.Frame(body, bg="#111111", width=460)
        self.console_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.console_frame.pack_propagate(False)

        tabs_bar = tk.Frame(self.console_frame, bg="#111111")
        tabs_bar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 0))
        self.btn_tab_console = tk.Button(tabs_bar, text="Console", command=lambda: self.show_panel("console"),
                                          bg="#00552a", fg="white", font=("Consolas", 10, "bold"),
                                          relief=tk.FLAT)
        self.btn_tab_console.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self.btn_tab_editor = tk.Button(tabs_bar, text="Editor", command=lambda: self.show_panel("editor"),
                                         bg="#3c3c3c", fg="white", font=("Consolas", 10, "bold"),
                                         relief=tk.FLAT)
        self.btn_tab_editor.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        container = tk.Frame(self.console_frame, bg="#111111")
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # ---- editor (IDLE-style): write a script incrementally ----
        editor_pane = tk.Frame(container, bg="#111111")
        editor_pane.grid(row=0, column=0, sticky="nsew")
        tk.Label(editor_pane, text="EDITOR", bg="#111111", fg="#00ff88",
                 font=("Consolas", 11, "bold")).pack(side=tk.TOP, anchor="w")

        editor_toolbar = tk.Frame(editor_pane, bg="#111111")
        editor_toolbar.pack(side=tk.TOP, fill=tk.X, pady=(4, 4))
        tk.Button(editor_toolbar, text="New", command=self.editor_new,
                  bg="#3c3c3c", fg="white", font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(editor_toolbar, text="Open", command=self.editor_open,
                  bg="#3c3c3c", fg="white", font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(editor_toolbar, text="Save", command=self.editor_save,
                  bg="#3c3c3c", fg="white", font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)
        tk.Button(editor_toolbar, text="Run (Ctrl+Enter)", command=self.editor_run,
                  bg="#1f5c1f", fg="white", font=("Consolas", 8)).pack(side=tk.LEFT, padx=2)

        self.editor_text = scrolledtext.ScrolledText(
            editor_pane, bg="#1a1a1a", fg="#dcdcdc", insertbackground="white",
            font=("Consolas", 10), wrap=tk.NONE, undo=True)
        self.editor_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.editor_text.insert("1.0", "# write your script here, then Ctrl+Enter to run it\n")
        self.editor_text.bind("<Control-Return>", lambda e: (self.editor_run(), "break"))
        self._attach_clipboard_support(self.editor_text, editable=True)

        self.editor_pane = editor_pane

        # ---- interactive shell ----
        shell_pane = tk.Frame(container, bg="#111111")
        shell_pane.grid(row=0, column=0, sticky="nsew")
        tk.Label(shell_pane, text="CONSOLE", bg="#111111", fg="#00ff88",
                 font=("Consolas", 11, "bold")).pack(side=tk.TOP, anchor="w")

        self.console_output = scrolledtext.ScrolledText(
            shell_pane, bg="black", fg="#00ff88", insertbackground="white",
            font=("Consolas", 10), wrap=tk.WORD, state=tk.DISABLED)
        self.console_output.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(4, 4))
        self._attach_clipboard_support(self.console_output, editable=False)

        entry_frame = tk.Frame(shell_pane, bg="#111111")
        entry_frame.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(entry_frame, text=">>>", bg="#111111", fg="#00ff88",
                 font=("Consolas", 10, "bold")).pack(side=tk.LEFT)
        self.console_entry = tk.Entry(entry_frame, bg="black", fg="white",
                                       insertbackground="white", font=("Consolas", 10))
        self.console_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.console_entry.bind("<Return>", self.run_console_command)
        self.console_entry.bind("<Up>", self._history_up)
        self.console_entry.bind("<Down>", self._history_down)
        self._attach_clipboard_support(self.console_entry, editable=True)
        self.console_entry.focus_set()

        self.shell_pane = shell_pane

        self.history = []
        self.history_index = -1

        self.show_panel("console")

    def _build_figure(self):
        self.fig = Figure(figsize=(8, 8), dpi=100, facecolor="black")
        self.ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=0.02, right=0.99, top=0.97, bottom=0.03)
        self.ax.set_aspect("equal")
        self.ax.set_facecolor("black")
        self.ax.tick_params(colors="#666666")

        names = [SUN] + PLANETS
        colors = [b[2] for b in names]
        letters = [b[1] for b in names]
        sizes = [b[3] for b in names]

        self.points = [self.ax.plot([], [], "o", color=colors[i], markersize=sizes[i])[0]
                       for i in range(self.n)]
        self.lines = [self.ax.plot([], [], "-", color=colors[i], alpha=0.35, linewidth=1)[0]
                      for i in range(self.n)]
        self.letter_labels = [self.ax.text(0, 0, letters[i], color="white", fontsize=9,
                                            fontweight="bold", ha="center", va="bottom")
                               for i in range(self.n)]

        lim = 32
        self.ax.set_xlim(-lim, lim)
        self.ax.set_ylim(-lim, lim)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self._pan_start = None
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("resize_event", lambda evt: self._redraw_full())

        self.background = None
        self._redraw_full()

    # ---------- rendering (blitting: only redraw what moves, not the whole figure) ----------

    def _dynamic_artists(self):
        return self.points + self.lines + self.letter_labels

    def _redraw_full(self):
        """Redraw everything (axes, ticks) and recapture the static
        background. Call this only when limits/axes change or an
        artist is added/removed - not on every simulation frame."""
        artists = self._dynamic_artists()
        for a in artists:
            a.set_visible(False)
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.ax.bbox)
        for a in artists:
            a.set_visible(True)
        self._blit()

    def _blit(self):
        """Only redraw the bodies/trails/labels over the already-captured
        background - much faster than a full draw()."""
        if self.background is None:
            self._redraw_full()
            return
        self.canvas.restore_region(self.background)
        for a in self._dynamic_artists():
            self.ax.draw_artist(a)
        self.canvas.blit(self.ax.bbox)

    # ---------- mouse navigation (pan / zoom) ----------

    def _on_scroll(self, event):
        if event.xdata is None or event.ydata is None:
            return
        base_scale = 1.15
        scale_factor = 1 / base_scale if event.button == "up" else base_scale
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        self.ax.set_xlim(event.xdata - (event.xdata - xlim[0]) * scale_factor,
                          event.xdata + (xlim[1] - event.xdata) * scale_factor)
        self.ax.set_ylim(event.ydata - (event.ydata - ylim[0]) * scale_factor,
                          event.ydata + (ylim[1] - event.ydata) * scale_factor)
        self._redraw_full()

    def _on_press(self, event):
        if event.button == 1 and event.xdata is not None and event.ydata is not None:
            self._pan_start = (event.xdata, event.ydata)
        elif event.button == 3:
            self._show_sim_context_menu(event)

    def _on_release(self, event):
        self._pan_start = None

    def _on_motion(self, event):
        if self._pan_start is None or event.xdata is None or event.ydata is None:
            return
        dx = event.xdata - self._pan_start[0]
        dy = event.ydata - self._pan_start[1]
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
        self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
        self._redraw_full()

    # ---------- right-click on the simulation ----------

    def _find_nearest_body(self, x, y):
        best = None
        for i, p in enumerate(self.sim.particles):
            d = ((p.x - x) ** 2 + (p.y - y) ** 2) ** 0.5
            if best is None or d < best[4]:
                best = (self.body_names[i], self.body_letters[i], p.x, p.y, d)
        return best

    def _copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._console_print(f"-- copied to clipboard: {text} --")

    def _copy_all_positions(self):
        lines = [f"t = {self.sim.t:.4f} yr"]
        for i, p in enumerate(self.sim.particles):
            lines.append(f"{self.body_names[i]} ({self.body_letters[i]}): X={p.x:.6f}, Y={p.y:.6f}")
        self._copy_to_clipboard("\n".join(lines))

    def _center_view(self, x, y):
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        w = (xlim[1] - xlim[0]) / 2
        h = (ylim[1] - ylim[0]) / 2
        self.ax.set_xlim(x - w, x + w)
        self.ax.set_ylim(y - h, y + h)
        self._redraw_full()

    def _reset_view(self):
        lim = 32
        self.ax.set_xlim(-lim, lim)
        self.ax.set_ylim(-lim, lim)
        self._redraw_full()

    def _show_sim_context_menu(self, event):
        x, y = event.xdata, event.ydata

        menu = tk.Menu(self.canvas.get_tk_widget(), tearoff=0, bg="#2d2d2d", fg="white",
                        activebackground="#555", activeforeground="white")

        if x is not None and y is not None:
            menu.add_command(
                label=f"Copy position (X={x:.4f}, Y={y:.4f} AU)",
                command=lambda: self._copy_to_clipboard(f"{x:.6f}, {y:.6f}"))

            nearest = self._find_nearest_body(x, y)
            name, letter, nx, ny, _ = nearest
            menu.add_command(
                label=f"Copy position of {name} ({letter})",
                command=lambda: self._copy_to_clipboard(f"{name}: {nx:.6f}, {ny:.6f}"))

        menu.add_command(label="Copy simulation time (t)",
                          command=lambda: self._copy_to_clipboard(f"t = {self.sim.t:.6f} yr"))
        menu.add_command(label="Copy all positions", command=self._copy_all_positions)
        menu.add_separator()
        if x is not None and y is not None:
            menu.add_command(label="Launch a comet here", command=lambda: self.prompt_launch_comet(x, y))
            menu.add_command(label="Place a black hole here...", command=lambda: self.prompt_spawn_black_hole(x, y))

        scripts_menu = tk.Menu(menu, tearoff=0, bg="#2d2d2d", fg="white",
                                activebackground="#555", activeforeground="white")
        if self.loaded_scripts:
            for path in self.loaded_scripts:
                scripts_menu.add_command(
                    label=os.path.basename(path),
                    command=lambda p=path: self.run_script_file(p))
        else:
            scripts_menu.add_command(label="(no scripts loaded)", state=tk.DISABLED)
        menu.add_cascade(label="Loaded scripts", menu=scripts_menu)

        menu.add_separator()
        if x is not None and y is not None:
            menu.add_command(label="Center view here", command=lambda: self._center_view(x, y))
        menu.add_command(label="Reset zoom", command=self._reset_view)

        x_root = self.canvas.get_tk_widget().winfo_pointerx()
        y_root = self.canvas.get_tk_widget().winfo_pointery()
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    # ---------- copy / paste (keyboard + mouse) ----------

    def _select_all(self, widget):
        if isinstance(widget, tk.Entry):
            widget.select_range(0, tk.END)
            widget.icursor(tk.END)
        else:
            widget.tag_add(tk.SEL, "1.0", tk.END)
            widget.mark_set(tk.INSERT, tk.END)
            widget.see(tk.INSERT)
        return "break"

    def _attach_clipboard_support(self, widget, editable):
        menu = tk.Menu(widget, tearoff=0, bg="#2d2d2d", fg="white",
                        activebackground="#555", activeforeground="white")
        if editable:
            menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
        if editable:
            menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select all", command=lambda: self._select_all(widget))

        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", show_menu)
        # Ctrl+A by default moves the cursor to the start of the line (Tk's emacs-style
        # binding) - we replace it with a real "select all".
        widget.bind("<Control-a>", lambda e: self._select_all(widget))
        widget.bind("<Control-A>", lambda e: self._select_all(widget))

    def show_panel(self, name):
        if name == "editor":
            self.editor_pane.tkraise()
            self.btn_tab_editor.config(bg="#00552a")
            self.btn_tab_console.config(bg="#3c3c3c")
        else:
            self.shell_pane.tkraise()
            self.btn_tab_console.config(bg="#00552a")
            self.btn_tab_editor.config(bg="#3c3c3c")

    # ---------- console ----------

    def _console_print(self, text):
        self.console_output.configure(state=tk.NORMAL)
        self.console_output.insert(tk.END, text + "\n")
        self.console_output.configure(state=tk.DISABLED)
        self.console_output.see(tk.END)

    def run_console_command(self, event=None):
        code = self.console_entry.get()
        if not code.strip():
            return
        self.console_entry.delete(0, tk.END)
        self.history.append(code)
        self.history_index = len(self.history)
        self._console_print(f">>> {code}")
        self._exec_code(code)

    def _exec_code(self, code):
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                try:
                    result = eval(code, self.console_namespace)
                    if result is not None:
                        print(repr(result))
                except SyntaxError:
                    exec(code, self.console_namespace)
        except Exception as e:
            print(f"Error: {e}", file=buf)
        output = buf.getvalue()
        if output:
            self._console_print(output.rstrip("\n"))

    def run_script_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        self._console_print(f"--- running {path} ---")
        self._exec_code(code)
        self._console_print("--- done ---")
        self._register_loaded_script(path)

    def _register_loaded_script(self, path):
        if path in self.loaded_scripts:
            self.loaded_scripts.remove(path)
        self.loaded_scripts.insert(0, path)
        self.loaded_scripts = self.loaded_scripts[:10]

    def load_script_dialog(self):
        path = filedialog.askopenfilename(
            initialdir=str(NOTEBOOKS_DIR),
            filetypes=[("Python scripts", "*.py"), ("All files", "*.*")])
        if path:
            self.run_script_file(path)

    # ---------- editor (IDLE-style) ----------

    def editor_new(self):
        self.editor_text.delete("1.0", tk.END)
        self.editor_path = None

    def editor_open(self):
        path = filedialog.askopenfilename(
            initialdir=str(NOTEBOOKS_DIR),
            filetypes=[("Python scripts", "*.py"), ("All files", "*.*")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.editor_text.delete("1.0", tk.END)
        self.editor_text.insert("1.0", content)
        self.editor_path = path

    def editor_save(self):
        path = self.editor_path
        if not path:
            path = filedialog.asksaveasfilename(
                initialdir=str(NOTEBOOKS_DIR), defaultextension=".py",
                filetypes=[("Python scripts", "*.py")])
            if not path:
                return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.editor_text.get("1.0", tk.END))
        self.editor_path = path
        self._console_print(f"-- script saved: {path} --")

    def editor_run(self):
        code = self.editor_text.get("1.0", tk.END)
        self._console_print("--- running editor ---")
        self._exec_code(code)
        self._console_print("--- done ---")
        if self.editor_path:
            self._register_loaded_script(self.editor_path)

    def open_in_idle(self):
        if self.editor_path is None:
            self.editor_save()
            if self.editor_path is None:
                return
        else:
            self.editor_save()
        subprocess.Popen([sys.executable, "-m", "idlelib", self.editor_path])

    def open_in_notepadpp(self):
        if NOTEPADPP_PATH is None:
            self._console_print("Error: Notepad++ not found. Install it to use this button.")
            return
        # confirmoverwrite=False: lets you pick an existing script (edit)
        # OR type a new name (create), in the same dialog.
        path = filedialog.asksaveasfilename(
            initialdir=str(NOTEBOOKS_DIR), defaultextension=".py",
            filetypes=[("Python scripts", "*.py"), ("All files", "*.*")],
            confirmoverwrite=False, title="Create or edit a script (Notepad++)")
        if not path:
            return
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("# new script\n")
        subprocess.Popen([NOTEPADPP_PATH, path])
        self._console_print(f"-- opened in Notepad++: {path} --")

    def _history_up(self, event):
        if self.history and self.history_index > 0:
            self.history_index -= 1
            self.console_entry.delete(0, tk.END)
            self.console_entry.insert(0, self.history[self.history_index])

    def _history_down(self, event):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.console_entry.delete(0, tk.END)
            self.console_entry.insert(0, self.history[self.history_index])
        else:
            self.history_index = len(self.history)
            self.console_entry.delete(0, tk.END)

    # ---------- simulation ----------

    def toggle_pause(self):
        self.paused = not self.paused
        self.btn_pause.config(text="Resume" if self.paused else "Pause")

    def reset(self):
        self.sim = build_sim()
        base_n = 1 + len(PLANETS)
        # remove dynamically added bodies (comet, etc.) to start clean
        for artist_list in (self.points, self.lines, self.letter_labels):
            while len(artist_list) > base_n:
                artist_list.pop().remove()
        self.body_names = self.body_names[:base_n]
        self.body_letters = self.body_letters[:base_n]
        self.n = base_n
        self.trails = [[] for _ in range(self.n)]
        self.console_namespace["sim"] = self.sim
        self._redraw_full()
        self._console_print("-- simulation reset --")

    def save_position_log(self):
        """Save the full position history (t, body, x, y) accumulated
        since the last reset, into data/logs/."""
        if not self.position_log:
            self._console_print("-- nothing to save (log empty) --")
            return None
        os.makedirs(LOGS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(LOGS_DIR, f"logs_{timestamp}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["t_years", "body", "letter", "x_AU", "y_AU"])
            writer.writerows(self.position_log)
        self._console_print(f"-- log saved: {path} ({len(self.position_log)} rows) --")
        return path

    def add_body(self, name, letter, color="#7FFFD4", size=5, m=0.0,
                 x=0.0, y=0.0, vx=0.0, vy=0.0):
        """Add a body to the running simulation (e.g. comet) while keeping
        the display (trails/points/labels) in sync."""
        self.sim.add(m=m, x=x, y=y, z=0.0, vx=vx, vy=vy, vz=0.0)
        self.n = self.sim.N
        self.trails.append([])
        self.body_names.append(name)
        self.body_letters.append(letter)
        point, = self.ax.plot([], [], "o", color=color, markersize=size)
        line, = self.ax.plot([], [], "-", color=color, alpha=0.35, linewidth=1)
        label = self.ax.text(0, 0, letter, color="white", fontsize=9,
                              fontweight="bold", ha="center", va="bottom")
        self.points.append(point)
        self.lines.append(line)
        self.letter_labels.append(label)
        self._redraw_full()
        self._console_print(f"-- body added: {name} ({letter}) --")
        return self.n - 1

    def launch_comet(self, x, y, r_p=2.0, e=1.3):
        """Launch a comet from (x, y) with a chosen perihelion and
        eccentricity (real orbital mechanics: vis-viva + angular
        momentum), instead of aiming at a random direction that
        could plunge straight into the Sun."""
        GM = 4 * np.pi ** 2
        A = np.array([x, y])
        r0 = np.linalg.norm(A)
        if r0 < 1e-6:
            self._console_print("-- comet: position too close to the Sun, cancelled --")
            return

        eps = GM * (e - 1) / (2 * r_p)
        L = np.sqrt(GM * r_p * (1 + e))
        v0 = np.sqrt(2 * (eps + GM / r0))
        v_t = L / r0
        v_r = -np.sqrt(max(v0 ** 2 - v_t ** 2, 0))

        r_hat = A / r0
        t_hat = np.array([-r_hat[1], r_hat[0]])
        vx, vy = v_r * r_hat + v_t * t_hat

        self.add_body(name="Comet", letter="C", color="#7FFFD4", size=5,
                       m=0.0, x=float(x), y=float(y), vx=float(vx), vy=float(vy))
        self._console_print(f"-- comet: r0={r0:.3f} AU, perihelion={r_p} AU, e={e}, "
                             f"speed={v0:.3f} AU/yr --")

    def prompt_launch_comet(self, x, y):
        r_p = simpledialog.askfloat("Comet", "Minimum distance to the Sun (perihelion, AU):",
                                     initialvalue=2.0, minvalue=0.05, parent=self.root)
        if r_p is None:
            return
        e = simpledialog.askfloat("Comet", "Eccentricity (>1 = hyperbolic, leaves for good):",
                                   initialvalue=1.3, minvalue=1.001, parent=self.root)
        if e is None:
            return
        self.launch_comet(x, y, r_p=r_p, e=e)

    def spawn_black_hole(self, name, x, y, vx=0.0, vy=0.0):
        """Place a real black hole from the catalog (measured mass) at (x, y)."""
        match = next((tn for tn in BLACK_HOLE_CATALOG if tn["name"] == name), None)
        if match is None:
            self._console_print(f"-- black hole not found in catalog: {name} --")
            return

        m = match["mass_msun"]
        if m > 1000:
            if not messagebox.askyesno(
                "Extreme mass",
                f"{name} is {m:,.0f} solar masses.\n\n"
                "At this scale, the simulation blows up within a few years "
                "(planets get ejected to millions of AU) - "
                "the integrator isn't built for such an extreme mass ratio.\n\n"
                "Place it anyway?",
                parent=self.root):
                self._console_print(f"-- placement of {name} cancelled --")
                return

        size = min(6 + 2 * max(0, math.log10(max(m, 1))), 40)
        self.add_body(name=match["name"], letter="BH", color="#000000", size=size,
                      m=m, x=float(x), y=float(y), vx=float(vx), vy=float(vy))
        self._console_print(f"-- black hole placed: {match['name']} - {m:,.3f} Msun --")

    def prompt_spawn_black_hole(self, x, y):
        if not BLACK_HOLE_CATALOG:
            self._console_print("-- catalog not found: data/black_holes.json --")
            return

        win = tk.Toplevel(self.root)
        win.title("Choose a black hole")
        win.configure(bg="#2d2d2d")

        tk.Label(win, text="Choose a real black hole to place here:",
                 bg="#2d2d2d", fg="white").pack(padx=10, pady=(10, 4))
        listbox = tk.Listbox(win, width=55, height=min(len(BLACK_HOLE_CATALOG), 12),
                              bg="black", fg="#00ff88", font=("Consolas", 10))
        for tn in BLACK_HOLE_CATALOG:
            listbox.insert(tk.END, f"{tn['name']}  -  {tn['mass_msun']:,.3f} Msun")
        listbox.selection_set(0)
        listbox.pack(padx=10, pady=4)

        def confirm():
            sel = listbox.curselection()
            if not sel:
                return
            name = BLACK_HOLE_CATALOG[sel[0]]["name"]
            win.destroy()
            self.spawn_black_hole(name, x, y)

        btns = tk.Frame(win, bg="#2d2d2d")
        btns.pack(pady=(4, 10))
        tk.Button(btns, text="Place here", command=confirm,
                  bg="#1f5c1f", fg="white").pack(side=tk.LEFT, padx=4)
        tk.Button(btns, text="Cancel", command=win.destroy,
                  bg="#3c3c3c", fg="white").pack(side=tk.LEFT, padx=4)

    def _tick(self):
        if not self.paused:
            self.sim.integrate(self.sim.t + self.speed.get())

        for i, p in enumerate(self.sim.particles):
            self.trails[i].append((p.x, p.y))
            if len(self.trails[i]) > self.trail_len:
                self.trails[i].pop(0)
            xs, ys = zip(*self.trails[i])
            self.points[i].set_data([p.x], [p.y])
            self.lines[i].set_data(xs, ys)
            self.letter_labels[i].set_position((p.x, p.y + 0.6))
            if not self.paused:
                self.position_log.append((self.sim.t, self.body_names[i],
                                           self.body_letters[i], p.x, p.y))

        self.time_label.config(text=f"t = {self.sim.t:.2f} yr")
        self._blit()
        self.root.after(30, self._tick)


if __name__ == "__main__":
    root = tk.Tk()
    app = SolarSystemApp(root)
    root.mainloop()
