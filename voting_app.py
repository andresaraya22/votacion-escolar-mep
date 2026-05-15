import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, simpledialog
import json, os, sys, time

def _resource(filename):
    """Bundled read-only assets (logo). Works both normally and inside PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def _datafile(filename):
    """Writable data files (votes.json). Always next to the exe / script."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

VOTES_FILE = _datafile("votes.json")
LOGO_FILE  = _resource("mep_logo.png")
ADMIN_PASSWORD = "escuela123"
COOLDOWN_SECONDS = 30
SPINNER_FRAMES   = ["◐", "◓", "◑", "◒"]

PARTIES = [
    {"id": "partido_a", "name": "Partido PANDA", "tag": "Lista 1",
     "candidate": "Armonía, Dedicación y Amor",
     "color": "#2e7d32", "mascot": _resource("mascot_panda.png")},
    {"id": "partido_b", "name": "Partido LAPA",  "tag": "Lista 2",
     "candidate": "Lealtad, Amabilidad, Paz y Amistad",
     "color": "#0a5fa8", "mascot": _resource("mascot_lapa.png")},
]

MASCOT_W, MASCOT_H = 220, 120   # natural size of mascot PNGs

# ── Design tokens (matching the HTML design) ─────────────────────────────────
BG          = "#f5f3ee"
CARD        = "#ffffff"
HEADER_BG   = "#ffffff"
LINE        = "#e3e6ec"
INK         = "#111418"
INK_SOFT    = "#3a4150"
MUTED       = "#6b7280"
MEP_BLUE    = "#0a5fa8"
MEP_YELLOW  = "#f5b800"
GOOD        = "#1f7a4d"
GOOD_DARK   = "#155c3a"
BOTTOM_BG   = "#0e1a2b"
BOTTOM_TEXT = "#cfd6e2"
SELECTED_BORDER = MEP_BLUE
IDLE_BORDER     = LINE

BASE_W, BASE_H = 900, 700
MIN_SCALE = 0.6
MAX_SCALE = 3.0
FLAG_BASE = 110


class VoteButton(tk.Canvas):
    """Rounded green button with white circle-checkmark icon."""

    def __init__(self, parent, command, **kw):
        self._btn_bg = kw.pop("bg", CARD)
        w = kw.pop("width", 170)
        h = kw.pop("height", 52)
        super().__init__(parent, width=w, height=h,
                         highlightthickness=0, cursor="hand2",
                         bg=self._btn_bg, **kw)
        self._command = command
        self._enabled = True
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda _: self._draw())
        self._draw()

    def _draw(self):
        w = self.winfo_width()  or int(self["width"])
        h = self.winfo_height() or int(self["height"])
        self.delete("all")

        color = "#9ca3af" if not self._enabled else GOOD
        r = min(h // 2, 16)

        # Rounded rectangle
        self.create_arc(0,       0,       2*r, 2*r, start=90,  extent=90,  fill=color, outline=color)
        self.create_arc(w-2*r,   0,       w,   2*r, start=0,   extent=90,  fill=color, outline=color)
        self.create_arc(0,       h-2*r,   2*r, h,   start=180, extent=90,  fill=color, outline=color)
        self.create_arc(w-2*r,   h-2*r,   w,   h,   start=270, extent=90,  fill=color, outline=color)
        self.create_rectangle(r, 0,   w-r, h, fill=color, outline=color)
        self.create_rectangle(0, r,   w,  h-r, fill=color, outline=color)

        # White circle
        pad = int(h * 0.18)
        cr  = (h - 2 * pad) // 2
        cx, cy = pad + cr, h // 2
        self.create_oval(cx-cr, cy-cr, cx+cr, cy+cr, fill="white", outline="white")
        # Checkmark inside circle
        self.create_text(cx, cy, text="✓", fill=color,
                         font=("Helvetica", max(8, cr - 1), "bold"))

        # "Votar" label
        tx = cx + cr + (w - cx - cr) // 2
        fs = max(10, int(h * 0.30))
        self.create_text(tx, cy, text="Votar", fill="white",
                         font=("Helvetica", fs, "bold"))

    def _on_click(self, _event):
        if self._enabled:
            self._command()

    def configure(self, **kw):
        redraw = False
        if "state" in kw:
            self._enabled = (kw.pop("state") == "normal")
            redraw = True
        if "cursor" in kw:
            super().configure(cursor=kw.pop("cursor"))
        # discard bg/fg — colors are handled internally
        kw.pop("bg", None)
        kw.pop("fg", None)
        if kw:
            super().configure(**kw)
        if redraw:
            self._draw()

    def config(self, **kw):
        self.configure(**kw)


class VotesWindow(tk.Toplevel):
    def __init__(self, parent, votes_ref, on_clear):
        super().__init__(parent)
        self.title("Resultados de Votación")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self._votes_ref = votes_ref   # mutable dict from VotingApp
        self._on_clear  = on_clear
        self._body      = None
        self._build_header()
        self._build_body()
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width()  // 2) - (self.winfo_width()  // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _build_header(self):
        hdr = tk.Frame(self, bg=MEP_BLUE, pady=18)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📊  Resultados de Votación",
                 font=("Helvetica", 16, "bold"),
                 bg=MEP_BLUE, fg=CARD).pack()

    def _build_body(self):
        if self._body:
            self._body.destroy()

        votes = self._votes_ref
        total = sum(votes.values()) or 1

        self._body = tk.Frame(self, bg=BG, padx=44, pady=28)
        self._body.pack(fill="both")

        for party in PARTIES:
            pid   = party["id"]
            count = votes.get(pid, 0)
            pct   = count / total

            row = tk.Frame(self._body, bg=BG, pady=8)
            row.pack(fill="x")

            flag = tk.Canvas(row, width=22, height=22, bg=BG, highlightthickness=0)
            flag.pack(side="left", padx=(0, 10))
            flag.create_rectangle(0, 0, 22, 22, fill=party["color"], outline="")
            flag.create_text(11, 11, text=party["name"][0],
                             fill=CARD, font=("Helvetica", 10, "bold"))

            tk.Label(row, text=party["name"],
                     font=("Helvetica", 13, "bold"),
                     bg=BG, fg=INK, width=14, anchor="w").pack(side="left")

            tk.Label(row, text=f"{count} votos  ({int(pct * 100)}%)",
                     font=("Helvetica", 12),
                     bg=BG, fg=MUTED).pack(side="left", padx=(8, 0))

            bar_bg = tk.Frame(self._body, bg=LINE, height=12)
            bar_bg.pack(fill="x", pady=(0, 10))
            bar_bg.pack_propagate(False)
            tk.Frame(bar_bg, bg=party["color"], height=12).place(
                relx=0, rely=0, relwidth=pct, relheight=1.0)

        sep = tk.Frame(self._body, bg=LINE, height=1)
        sep.pack(fill="x", pady=(8, 10))

        total_real = sum(votes.values())
        tk.Label(self._body, text=f"Total de votos: {total_real}",
                 font=("Helvetica", 12, "bold"),
                 bg=BG, fg=INK).pack()

        btn_row = tk.Frame(self._body, bg=BG)
        btn_row.pack(pady=(22, 4))

        tk.Button(btn_row, text="🗑  Limpiar votos",
                  font=("Helvetica", 11),
                  bg="#fde8ea", fg="#b21f2d",
                  activebackground="#fcd0d3", activeforeground="#b21f2d",
                  relief="flat", padx=20, pady=8, cursor="hand2",
                  command=self._confirm_clear).pack(side="left", padx=(0, 12))

        tk.Button(btn_row, text="Cerrar",
                  font=("Helvetica", 11),
                  bg=MEP_BLUE, fg=INK,
                  activebackground="#073f74", activeforeground=INK,
                  relief="flat", padx=24, pady=8, cursor="hand2",
                  command=self._close).pack(side="left")

    def _close(self):
        self.grab_release()
        self.destroy()

    def _confirm_clear(self):
        pwd = simpledialog.askstring(
            "Confirmar limpieza",
            "Ingresá la clave para limpiar todos los votos:",
            show="*", parent=self)
        if pwd is None:
            return
        if pwd == ADMIN_PASSWORD:
            self._on_clear()
            self._build_body()   # refresh counts in place, window stays open
        else:
            messagebox.showerror("Clave incorrecta",
                                 "La clave ingresada no es correcta.",
                                 parent=self)


class VotingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Votación Escolar — MEP")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(560, 480)

        self.votes           = self._load_votes()
        self.cooldown_active = False
        self.checkbuttons    = {}
        self.card_frames     = {}
        self.flag_canvases   = {}
        self.spinner_label   = None
        self.hero_content    = None
        self.cooldown_after_id  = None
        self._scale          = 1.0
        self._resize_after_id   = None
        self._logo_img       = None
        self._mascot_imgs    = {}
        for party in PARTIES:
            try:
                self._mascot_imgs[party["id"]] = tk.PhotoImage(file=party["mascot"])
            except Exception:
                pass

        self._init_fonts()
        self._build_ui()

        self.root.bind("<Configure>", self._on_configure)
        self.root.bind("<F11>",  self._toggle_fullscreen)
        self.root.bind("<Escape>", lambda _: self.root.attributes("-fullscreen", False))
        self.root.bind("<space>",  lambda _: self._show_votes_panel())

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{BASE_W}x{BASE_H}+{(sw-BASE_W)//2}+{(sh-BASE_H)//2}")

    # ── Fonts ─────────────────────────────────────────────────────────────────

    def _init_fonts(self):
        self.fonts = {
            "eyebrow":     tkfont.Font(family="Helvetica", size=10, weight="bold"),
            "title":       tkfont.Font(family="Helvetica", size=16, weight="bold"),
            "clock":       tkfont.Font(family="Helvetica", size=11),
            "pill":        tkfont.Font(family="Helvetica", size=10, weight="bold"),
            "hero_kicker": tkfont.Font(family="Helvetica", size=10, weight="bold"),
            "hero_h1":     tkfont.Font(family="Helvetica", size=36, weight="bold"),
            "hero_lead":   tkfont.Font(family="Helvetica", size=13),
            "step_num":    tkfont.Font(family="Helvetica", size=13, weight="bold"),
            "step_text":   tkfont.Font(family="Helvetica", size=12),
            "party_name":  tkfont.Font(family="Helvetica", size=26, weight="bold"),
            "party_tag":   tkfont.Font(family="Helvetica", size=10, weight="bold"),
            "party_cand":  tkfont.Font(family="Helvetica", size=12),
            "ballot_no":   tkfont.Font(family="Helvetica", size=11, weight="bold"),
            "vote_btn":    tkfont.Font(family="Helvetica", size=16, weight="bold"),
            "footer":      tkfont.Font(family="Helvetica", size=10),
            "kbd":         tkfont.Font(family="Helvetica", size=10, weight="bold"),
            "spinner":     tkfont.Font(family="Helvetica", size=13, weight="bold"),
        }
        self._base_sizes = {k: v.cget("size") for k, v in self.fonts.items()}

    # ── Resize ────────────────────────────────────────────────────────────────

    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(
            40, self._apply_scale, event.width, event.height)

    def _apply_scale(self, w, h):
        scale = min(w / BASE_W, h / BASE_H)
        scale = max(MIN_SCALE, min(MAX_SCALE, scale))
        if abs(scale - self._scale) < 0.04:
            return
        self._scale = scale
        for key, font in self.fonts.items():
            font.configure(size=max(7, int(self._base_sizes[key] * scale)))
        flag_size = max(36, int(FLAG_BASE * scale))
        for pid, canvas in self.flag_canvases.items():
            if pid in self._mascot_imgs:
                self._draw_flag(pid, canvas, MASCOT_W)
            else:
                canvas.configure(width=flag_size, height=flag_size)
                self._draw_flag(pid, canvas, flag_size)
        if self.spinner_label:
            self.spinner_label.configure(wraplength=int(w * 0.7))

    def _toggle_fullscreen(self, event=None):
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))

    # ── Flag ──────────────────────────────────────────────────────────────────

    def _draw_flag(self, party_id, canvas, size):
        party = next(p for p in PARTIES if p["id"] == party_id)
        canvas.delete("all")
        if party_id in self._mascot_imgs:
            img = self._mascot_imgs[party_id]
            w = int(canvas["width"])
            h = int(canvas["height"])
            canvas.create_image(w // 2, h // 2, image=img, anchor="center")
        else:
            r = int(size * 0.08)
            canvas.create_rectangle(r, r, size-r, size-r,
                                     fill=party["color"], outline="", width=0)
            font_size = max(10, int(size * 0.40))
            canvas.create_text(size // 2, size // 2,
                                text=party["name"][0], fill=CARD,
                                font=("Helvetica", font_size, "bold"))

    def _draw_party_flag_strip(self, color, canvas):
        w = int(canvas["width"])
        h = int(canvas["height"])
        s = h // 3
        canvas.create_rectangle(0,     0, w,   s, fill=color,   outline="")
        canvas.create_rectangle(0,     s, w, 2*s, fill="white", outline="")
        canvas.create_rectangle(0, 2*s, w,   h,   fill=color,   outline="")

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_votes(self):
        if os.path.exists(VOTES_FILE):
            try:
                with open(VOTES_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {p["id"]: 0 for p in PARTIES}

    def _save_votes(self):
        try:
            with open(VOTES_FILE, "w") as f:
                json.dump(self.votes, f, indent=2)
        except IOError:
            pass

    # ── UI Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.grid_rowconfigure(0, weight=0)  # header
        self.root.grid_rowconfigure(1, weight=0)  # hero
        self.root.grid_rowconfigure(2, weight=1)  # cards
        self.root.grid_rowconfigure(3, weight=0)  # footer
        self.root.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_hero()
        self._build_cards()
        self._build_footer()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=HEADER_BG,
                       highlightthickness=1, highlightbackground=LINE)
        hdr.grid(row=0, column=0, sticky="ew")

        left = tk.Frame(hdr, bg=HEADER_BG, padx=24, pady=8)
        left.pack(side="left")

        # MEP logo (tk.PhotoImage supports PNG natively)
        if os.path.exists(LOGO_FILE):
            try:
                raw = tk.PhotoImage(file=LOGO_FILE)
                # subsample to fit ~120px height — larger = less pixelation
                factor = max(1, raw.height() // 120)
                self._logo_img = raw.subsample(factor, factor)
                tk.Label(left, image=self._logo_img,
                         bg=HEADER_BG).pack(side="left", padx=(0, 20))
            except Exception:
                self._build_logo_placeholder(left)
        else:
            self._build_logo_placeholder(left)

        # divider
        tk.Frame(left, bg=LINE, width=1, height=108).pack(side="left", padx=(0, 20))

        # crest
        crest = tk.Frame(left, bg=HEADER_BG)
        crest.pack(side="left")
        tk.Label(crest, text="SISTEMA DE VOTACIÓN",
                 font=self.fonts["eyebrow"],
                 bg=HEADER_BG, fg=MUTED).pack(anchor="w")
        tk.Label(crest, text="Elecciones Estudiantiles 2026",
                 font=self.fonts["title"],
                 bg=HEADER_BG, fg=INK).pack(anchor="w")
        tk.Label(crest, text="Escuela La Legua  ·  Circuito 05",
                 font=self.fonts["clock"],
                 bg=HEADER_BG, fg=MUTED).pack(anchor="w")

        # right side: pill + clock
        right = tk.Frame(hdr, bg=HEADER_BG, padx=24)
        right.pack(side="right")

        pill = tk.Frame(right, bg="#eef4fb",
                        highlightthickness=1, highlightbackground="#d9e6f4",
                        padx=12, pady=6)
        pill.pack(side="right", padx=(12, 0))
        dot_canvas = tk.Canvas(pill, width=10, height=10,
                               bg="#eef4fb", highlightthickness=0)
        dot_canvas.pack(side="left", padx=(0, 6))
        dot_canvas.create_oval(1, 1, 9, 9, fill=GOOD, outline="")
        tk.Label(pill, text="Mesa activa",
                 font=self.fonts["pill"],
                 bg="#eef4fb", fg="#073f74").pack(side="left")

    def _build_logo_placeholder(self, parent):
        box = tk.Canvas(parent, width=52, height=52,
                        bg=MEP_BLUE, highlightthickness=0)
        box.pack(side="left", padx=(0, 16))
        box.create_text(26, 26, text="MEP", fill=CARD,
                        font=("Helvetica", 12, "bold"))

    # ── Hero ──────────────────────────────────────────────────────────────────

    def _build_hero(self):
        self.hero_frame = tk.Frame(self.root, bg=BG, pady=0)
        self.hero_frame.grid(row=1, column=0, sticky="ew")

        # Normal hero content
        self.hero_content = tk.Frame(self.hero_frame, bg=BG, pady=22)
        self.hero_content.pack()

        # Kicker pill
        kicker_frame = tk.Frame(self.hero_content, bg=CARD,
                                 highlightthickness=1, highlightbackground=LINE,
                                 padx=14, pady=6)
        kicker_frame.pack()
        dot = tk.Canvas(kicker_frame, width=10, height=10,
                        bg=CARD, highlightthickness=0)
        dot.pack(side="left", padx=(0, 8))
        dot.create_rectangle(1, 1, 9, 9, fill=MEP_YELLOW, outline="")
        tk.Label(kicker_frame, text="VOTO SECRETO  ·  VOTO LIBRE",
                 font=self.fonts["hero_kicker"],
                 bg=CARD, fg=INK_SOFT).pack(side="left")

        tk.Label(self.hero_content, text="Elegí tu partido",
                 font=self.fonts["hero_h1"],
                 bg=BG, fg=INK).pack(pady=(12, 4))

       

        # Instruction
        instr_frame = tk.Frame(self.hero_content, bg=CARD,
                               highlightthickness=1, highlightbackground=LINE,
                               padx=24, pady=14)
        instr_frame.pack(pady=(14, 0))
        tk.Label(instr_frame,
                 text='Elegí el partido por el que querés votar y presioná el botón verde que dice "Votar"',
                 font=self.fonts["step_text"],
                 bg=CARD, fg=INK_SOFT,
                 wraplength=520, justify="center").pack()

        # Cooldown area — always present so layout never shifts
        self.cooldown_area = tk.Frame(self.hero_frame, bg=BG)
        self.cooldown_area.pack(pady=(6, 10))

        self.countdown_canvas = tk.Canvas(
            self.cooldown_area, width=60, height=60,
            bg=BG, highlightthickness=0)
        self.countdown_canvas.pack(side="left", padx=(0, 16))

        self.spinner_label = tk.Label(
            self.cooldown_area, text="",
            font=self.fonts["spinner"],
            bg=BG, fg=GOOD, anchor="w",
            wraplength=500, justify="left")
        self.spinner_label.pack(side="left")

    def _make_step(self, parent, num, bg_color, fg_color, text):
        circle = tk.Canvas(parent, width=28, height=28,
                            bg=CARD, highlightthickness=0)
        circle.pack(side="left", padx=(0, 8))
        circle.create_oval(0, 0, 28, 28, fill=bg_color, outline="")
        circle.create_text(14, 14, text=num, fill=fg_color,
                           font=("Helvetica", 12, "bold"))
        tk.Label(parent, text=text,
                 font=self.fonts["step_text"],
                 bg=CARD, fg=INK_SOFT).pack(side="left", padx=(0, 16))

    # ── Cards ─────────────────────────────────────────────────────────────────

    def _build_cards(self):
        outer = tk.Frame(self.root, bg=BG)
        outer.grid(row=2, column=0, sticky="nsew")
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_columnconfigure(1, weight=1)
        outer.grid_rowconfigure(0, weight=0)

        for col, party in enumerate(PARTIES):
            self._build_party_card(outer, party, col=col)

    def _build_party_card(self, parent, party, col):
        # Outer wrapper with border effect
        wrapper = tk.Frame(parent, bg=LINE, padx=2, pady=2)
        wrapper.grid(row=0, column=col, sticky="ew",
                     padx=(32 if col == 0 else 12, 12 if col == 0 else 32),
                     pady=20)
        wrapper.grid_columnconfigure(0, weight=1)
        self.card_frames[party["id"]] = wrapper

        card = tk.Frame(wrapper, bg=CARD)
        card.grid(row=0, column=0, sticky="ew")

        inner = tk.Frame(card, bg=CARD, padx=24, pady=22)
        inner.pack(fill="x")

        # Top row: crest + info
        top = tk.Frame(inner, bg=CARD)
        top.pack(fill="x")

        has_mascot = party["id"] in self._mascot_imgs
        fw = MASCOT_W if has_mascot else FLAG_BASE
        fh = MASCOT_H if has_mascot else FLAG_BASE
        flag_canvas = tk.Canvas(top, width=fw, height=fh,
                                 bg=CARD, highlightthickness=0)
        flag_canvas.pack(side="left", padx=(0, 18))
        self.flag_canvases[party["id"]] = flag_canvas
        self._draw_flag(party["id"], flag_canvas, fw)

        info = tk.Frame(top, bg=CARD)
        info.pack(side="left", fill="both", expand=True)

        tk.Label(info, text=party["name"],
                 font=self.fonts["party_name"],
                 bg=CARD, fg=INK, anchor="w").pack(fill="x")
        tk.Label(info, text=party["candidate"],
                 font=self.fonts["party_cand"],
                 bg=CARD, fg=INK_SOFT, anchor="w").pack(fill="x", pady=(6, 0))

        # Party flag strip
        flag_strip = tk.Canvas(info, width=90, height=42,
                                bg=CARD, highlightthickness=1,
                                highlightbackground=LINE)
        flag_strip.pack(anchor="w", pady=(10, 0))
        self._draw_party_flag_strip(party["color"], flag_strip)

        # Dashed separator (simulated with a dotted-style line)
        sep_canvas = tk.Canvas(inner, bg=CARD, height=2, highlightthickness=0)
        sep_canvas.pack(fill="x", pady=(18, 12))
        sep_canvas.bind("<Configure>", lambda _, c=sep_canvas: self._draw_dashes(c))

        # Footer row: ballot number + vote button
        foot = tk.Frame(inner, bg=CARD)
        foot.pack(fill="x")

        ballot_num = len([p for p in PARTIES if p["id"] <= party["id"]])
        tk.Label(foot, text=f"PAPELETA  N.º {ballot_num}",
                 font=self.fonts["ballot_no"],
                 bg=CARD, fg=INK_SOFT).pack(side="left")

        btn = VoteButton(foot, command=lambda pid=party["id"]: self._on_vote(pid),
                         bg=CARD, width=170, height=52)
        btn.pack(side="right")
        self.checkbuttons[party["id"]] = btn

    def _draw_dashes(self, canvas):
        canvas.delete("all")
        w = canvas.winfo_width()
        x = 0
        dash, gap = 6, 4
        while x < w:
            canvas.create_line(x, 1, min(x + dash, w), 1,
                               fill=LINE, width=2)
            x += dash + gap

    # ── Footer ────────────────────────────────────────────────────────────────

    def _build_footer(self):
        foot = tk.Frame(self.root, bg=BOTTOM_BG, pady=14)
        foot.grid(row=3, column=0, sticky="ew")

        # CR flag
        left = tk.Frame(foot, bg=BOTTOM_BG)
        left.pack(side="left", padx=(28, 0))

        flag = tk.Canvas(left, width=56, height=8,
                         bg=BOTTOM_BG, highlightthickness=0)
        flag.pack(side="left", padx=(0, 14))
        flag.create_rectangle(0,  0, 56, 8, fill=MEP_BLUE,  outline="")
        flag.create_rectangle(18, 0, 38, 8, fill=CARD,       outline="")
        flag.create_rectangle(18, 0, 38, 8, fill=CARD,       outline="")
        flag.create_rectangle(0,  0, 56, 8, fill="",         outline="")
        # redraw properly:
        flag.delete("all")
        flag.create_rectangle( 0, 0, 19, 8, fill=MEP_BLUE,  outline="")
        flag.create_rectangle(19, 0, 37, 8, fill=CARD,       outline="")
        flag.create_rectangle(37, 0, 56, 8, fill="#d4202c",  outline="")

        tk.Label(left, text="Los votos se registran automáticamente",
                 font=self.fonts["footer"],
                 bg=BOTTOM_BG, fg=BOTTOM_TEXT).pack(side="left")

        right = tk.Frame(foot, bg=BOTTOM_BG)
        right.pack(side="right", padx=(0, 28))
        self._kbd_shortcut(right, "Espacio", "Panel del administrador")

    def _kbd_shortcut(self, parent, key, label):
        frame = tk.Frame(parent, bg="#1c2a40",
                         highlightthickness=1, highlightbackground="#2c3a55",
                         padx=8, pady=4)
        frame.pack(side="left")
        tk.Label(frame, text=key,
                 font=self.fonts["kbd"],
                 bg="#1c2a40", fg=CARD).pack(side="left")
        tk.Label(frame, text=f"  {label}",
                 font=self.fonts["footer"],
                 bg="#1c2a40", fg=BOTTOM_TEXT).pack(side="left")

    # ── Vote logic ────────────────────────────────────────────────────────────

    def _on_vote(self, party_id):
        if self.cooldown_active:
            return
        self.votes[party_id] = self.votes.get(party_id, 0) + 1
        self._save_votes()
        # Highlight selected card with its own party color
        selected_color = next(p["color"] for p in PARTIES if p["id"] == party_id)
        for pid, wrapper in self.card_frames.items():
            wrapper.configure(bg=selected_color if pid == party_id else LINE)
        self._start_cooldown()

    def _start_cooldown(self):
        self.cooldown_active = True
        for btn in self.checkbuttons.values():
            btn.configure(state="disabled", cursor="arrow")
        self._tick_cooldown(COOLDOWN_SECONDS)

    def _draw_pie(self, remaining):
        c = self.countdown_canvas
        c.delete("all")
        sz  = int(c["width"])
        pad = 4
        x0, y0, x1, y1 = pad, pad, sz - pad, sz - pad

        # Empty background circle
        c.create_oval(x0, y0, x1, y1, fill="#e5e7eb", outline="")

        if remaining > 0:
            fraction = remaining / COOLDOWN_SECONDS
            # Fixed start at 12 o'clock (90°), positive extent = counterclockwise (green)
            # so the empty gap grows clockwise from 12 — like a clock hand
            extent = min(359.9, fraction * 360)
            c.create_arc(x0, y0, x1, y1,
                         start=90, extent=extent,
                         fill=GOOD, outline=GOOD, style=tk.PIESLICE)

    def _tick_cooldown(self, remaining):
        if remaining <= 0:
            self._end_cooldown()
            return
        self._draw_pie(remaining)
        self.spinner_label.configure(
            text=f"Voto apuntado. Dale espacio al siguiente estudiante ({remaining}s)")
        self.cooldown_after_id = self.root.after(
            1000, self._tick_cooldown, remaining - 1)

    def _end_cooldown(self):
        self.cooldown_active = False
        self._draw_pie(0)
        self.spinner_label.configure(text="")
        for pid in self.card_frames:
            self.card_frames[pid].configure(bg=LINE)
        for party in PARTIES:
            self.checkbuttons[party["id"]].configure(state="normal", cursor="hand2")

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _show_hamburger_menu(self, event=None):
        menu = tk.Menu(self.root, tearoff=0,
                       bg=CARD, fg=INK,
                       activebackground=MEP_BLUE, activeforeground=CARD,
                       font=("Helvetica", 12), bd=0, relief="flat")
        menu.add_command(label="📊  Mostrar Votos",    command=self._show_votes_panel)
        menu.add_command(label="⛶  Pantalla completa", command=self._toggle_fullscreen)
        menu.add_separator()
        menu.add_command(label="Salir",                command=self.root.quit)
        try:
            menu.tk_popup(event.widget.winfo_rootx(),
                          event.widget.winfo_rooty() + event.widget.winfo_height())
        finally:
            menu.grab_release()

    def _show_votes_panel(self):
        pwd = simpledialog.askstring(
            "Acceso Restringido", "Ingresá la clave de administrador:",
            show="*", parent=self.root)
        if pwd is None:
            return
        if pwd == ADMIN_PASSWORD:
            win = VotesWindow(self.root, self.votes, on_clear=self._clear_votes)
            self.root.wait_window(win)
            self.root.focus_force()
        else:
            messagebox.showerror("Clave incorrecta",
                                 "La clave ingresada no es correcta.",
                                 parent=self.root)

    def _clear_votes(self):
        for pid in self.votes:
            self.votes[pid] = 0
        self._save_votes()


def main():
    # Tell Windows to render at native DPI instead of blurring/scaling the app
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system DPI aware
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()   # legacy fallback
                except Exception:
                    pass

    root = tk.Tk()
    VotingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
