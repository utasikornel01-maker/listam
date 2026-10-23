import json
import math
import os
import time

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.stencilview import StencilView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# ---------------------------------------------------------------
# KEZDŐ LISTA (csak az első indításkor kell; utána az app elmenti,
# amit a + és a kuka gombbal beállítasz)
# ---------------------------------------------------------------
ITEMS = [
    "Első feladat",
    "Második feladat",
    "Harmadik feladat",
    "Negyedik feladat",
    "Ötödik feladat",
]

# Az előre elkészített időzítők másodpercben (az appban törölhetők, újak menthetők)
DEFAULT_PRESETS = [10, 30, 60, 120, 300]
MAX_PRESETS = 5  # ennyi időt lehet elmenteni

ROW_HEIGHT = dp(56)
PANEL_HEIGHT = dp(52)

# Fekete-fehér-szürke téma
GLASS = (1, 1, 1, 0.10)
GLASS_BORDER = (1, 1, 1, 0.38)
GLASS_ON = (1, 1, 1, 0.34)
GLASS_ON_BORDER = (1, 1, 1, 0.95)
TEXT = (0.95, 0.95, 0.95, 1)


def fmt(seconds):
    """Rövid visszaszámláló felirat a listasorokhoz."""
    seconds = int(seconds)
    if seconds >= 3600:
        h, r = divmod(seconds, 3600)
        m, s = divmod(r, 60)
        return f"{h}:{m:02d}:{s:02d}"
    if seconds >= 60:
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"
    return f"{seconds} mp"


def fmt_clock(seconds):
    """Óra-formátum a nagy körhöz."""
    s = int(max(0, math.ceil(seconds)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def fmt_short(seconds):
    """Mentett idők felirata: pl. 10 mp, 2 p, 1 p 30 mp, 1 ó 5 p."""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} ó")
    if m:
        parts.append(f"{m} p")
    if s or not parts:
        parts.append(f"{s} mp")
    return " ".join(parts)


def vibrate():
    try:
        from plyer import vibrator
        vibrator.vibrate(time=1)
    except Exception:
        pass  # gépen nincs rezgés, nem baj


# =================================================================
#  HÁTTÉR (fekete-szürke színátmenet + puha fényfoltok)
# =================================================================
def make_gradient_texture():
    stops = [(0.0, (0.02, 0.02, 0.03)),
             (0.5, (0.10, 0.10, 0.12)),
             (1.0, (0.26, 0.26, 0.29))]  # 0 = alul, 1 = felül
    h = 256
    buf = bytearray()
    for i in range(h):
        t = i / (h - 1)
        c = stops[-1][1]
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                c = [c0[k] + (c1[k] - c0[k]) * f for k in range(3)]
                break
        buf.extend(int(v * 255) for v in c)
        buf.append(255)
    tex = Texture.create(size=(1, h), colorfmt="rgba")
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    tex.mag_filter = "linear"
    return tex


def make_blob_texture(size=64):
    buf = bytearray()
    c = (size - 1) / 2
    for yy in range(size):
        for xx in range(size):
            d = (((xx - c) ** 2 + (yy - c) ** 2) ** 0.5) / c
            a = max(0.0, 1.0 - d)
            a = a * a
            buf.extend((255, 255, 255, int(a * 255)))
    tex = Texture.create(size=(size, size), colorfmt="rgba")
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    tex.mag_filter = "linear"
    return tex


class Background(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        grad = make_gradient_texture()
        blob = make_blob_texture()
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg = Rectangle(texture=grad)
            Color(1, 1, 1, 0.22)
            self.b1 = Rectangle(texture=blob)
            Color(0.8, 0.8, 0.85, 0.20)
            self.b2 = Rectangle(texture=blob)
            Color(1, 1, 1, 0.14)
            self.b3 = Rectangle(texture=blob)
        self.bind(pos=self.update_bg, size=self.update_bg)

    def update_bg(self, *args):
        x, y = self.pos
        w, h = self.size
        self.bg.pos, self.bg.size = (x, y), (w, h)
        big = max(w, h)
        for rect, fx, fy, scale in ((self.b1, 0.15, 0.85, 0.9),
                                    (self.b2, 0.90, 0.45, 0.8),
                                    (self.b3, 0.30, 0.08, 0.9)):
            d = big * scale
            rect.size = (d, d)
            rect.pos = (x + w * fx - d / 2, y + h * fy - d / 2)


# =================================================================
#  GLASS (üveg) ALAPOK
# =================================================================
class GlassMixin:
    """Áttetsző, lekerekített, fényes szélű 'üveg' háttér bármilyen widgetnek."""

    def init_glass(self, radius=18, tint=GLASS, border=GLASS_BORDER):
        self.glass_radius = dp(radius)
        self._base_alpha = tint[3]
        with self.canvas.before:
            self._g_tint = Color(*tint)
            self._g_bg = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[self.glass_radius])
            Color(1, 1, 1, 0.07)
            self._g_hl = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[self.glass_radius, self.glass_radius, 0, 0])
            self._g_border_color = Color(*border)
            self._g_border = Line(rounded_rectangle=(0, 0, 10, 10, 5), width=1.1)
        self.bind(pos=self._update_glass, size=self._update_glass)
        if hasattr(self, "state"):
            self.bind(state=self._glass_press)
        self._update_glass()

    def set_glass(self, tint, border):
        self._base_alpha = tint[3]
        self._g_tint.rgba = tint
        self._g_border_color.rgba = border

    def _glass_press(self, inst, state):
        self._g_tint.a = self._base_alpha + (0.15 if state == "down" else 0)

    def _update_glass(self, *args):
        x, y = self.pos
        w, h = self.size
        r = max(0, min(self.glass_radius, w / 2, h / 2))
        self._g_bg.pos, self._g_bg.size = (x, y), (w, h)
        self._g_bg.radius = [r]
        self._g_hl.pos, self._g_hl.size = (x, y + h / 2), (w, h / 2)
        self._g_hl.radius = [r, r, 0, 0]
        self._g_border.rounded_rectangle = (x, y, w, h, r)


class GlassBox(GlassMixin, BoxLayout):
    def __init__(self, radius=20, tint=GLASS, border=GLASS_BORDER, **kwargs):
        super().__init__(**kwargs)
        self.init_glass(radius, tint, border)


class TextButton(GlassMixin, ButtonBehavior, Label):
    def __init__(self, radius=14, tint=GLASS, border=GLASS_BORDER, **kwargs):
        kwargs.setdefault("font_size", sp(16))
        kwargs.setdefault("color", TEXT)
        super().__init__(**kwargs)
        self.init_glass(radius, tint, border)


def draw_trash(cx, cy, s, color, width):
    Color(*color)
    Line(points=[cx - s, cy + s * 0.55, cx + s, cy + s * 0.55],
         width=width, cap="round")
    Line(points=[cx - s * 0.35, cy + s * 0.55, cx - s * 0.35, cy + s * 0.9,
                 cx + s * 0.35, cy + s * 0.9, cx + s * 0.35, cy + s * 0.55],
         width=width, joint="round", cap="round")
    Line(points=[cx - s * 0.75, cy + s * 0.55, cx - s * 0.6, cy - s * 0.95,
                 cx + s * 0.6, cy - s * 0.95, cx + s * 0.75, cy + s * 0.55],
         width=width, joint="round", cap="round")
    Line(points=[cx - s * 0.22, cy + s * 0.15, cx - s * 0.22, cy - s * 0.55],
         width=width, cap="round")
    Line(points=[cx + s * 0.22, cy + s * 0.15, cx + s * 0.22, cy - s * 0.55],
         width=width, cap="round")


class IconButton(GlassMixin, ButtonBehavior, Widget):
    """Üveg négyzet rajzolt ikonnal ('plus', 'trash' vagy 'timer')."""
    dot = BooleanProperty(False)  # kis pötty a sarokban (pl. fut az időzítő)

    def __init__(self, icon, radius=16, tint=GLASS, border=GLASS_BORDER,
                 icon_color=(1, 1, 1, 0.95), **kwargs):
        super().__init__(**kwargs)
        self.icon = icon
        self.icon_color = icon_color
        self.init_glass(radius, tint, border)
        self.bind(pos=self.draw_icon, size=self.draw_icon, dot=self.draw_icon)
        self.draw_icon()

    def draw_icon(self, *args):
        self.canvas.after.clear()
        cx, cy = self.center
        m = min(self.width, self.height)
        width = max(1.2, m * 0.04)
        with self.canvas.after:
            if self.icon == "plus":
                a = m * 0.22
                Color(*self.icon_color)
                Line(points=[cx - a, cy, cx + a, cy], width=width * 1.3, cap="round")
                Line(points=[cx, cy - a, cx, cy + a], width=width * 1.3, cap="round")
            elif self.icon == "trash":
                draw_trash(cx, cy, m * 0.23, self.icon_color, width)
            elif self.icon == "timer":
                r = m * 0.24
                oy = cy - m * 0.05
                Color(*self.icon_color)
                Line(circle=(cx, oy, r), width=width * 1.2)
                Line(points=[cx, oy, cx, oy + r * 0.65], width=width * 1.2, cap="round")
                Line(points=[cx, oy, cx + r * 0.45, oy], width=width * 1.2, cap="round")
                Line(points=[cx, oy + r, cx, oy + r + m * 0.07], width=width * 1.2, cap="round")
                Line(points=[cx - m * 0.07, oy + r + m * 0.07, cx + m * 0.07, oy + r + m * 0.07],
                     width=width * 1.2, cap="round")
            if self.dot:
                Color(1, 1, 1, 1)
                Ellipse(pos=(self.right - dp(15), self.top - dp(15)), size=(dp(9), dp(9)))


class GlassCheck(GlassMixin, ButtonBehavior, Widget):
    """Üveg pipadoboz."""
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.init_glass(9, (1, 1, 1, 0.08), (1, 1, 1, 0.6))
        self.bind(pos=self.draw_tick, size=self.draw_tick, active=self.on_active_change)
        self.draw_tick()

    def on_release(self):
        self.active = not self.active

    def on_active_change(self, *args):
        if self.active:
            self.set_glass(GLASS_ON, GLASS_ON_BORDER)
        else:
            self.set_glass((1, 1, 1, 0.08), (1, 1, 1, 0.6))
        self.draw_tick()

    def draw_tick(self, *args):
        self.canvas.after.clear()
        if not self.active:
            return
        x, y = self.pos
        w, h = self.size
        with self.canvas.after:
            Color(1, 1, 1, 1)
            Line(points=[x + w * 0.24, y + h * 0.52,
                         x + w * 0.43, y + h * 0.30,
                         x + w * 0.78, y + h * 0.72],
                 width=max(1.5, w * 0.075), joint="round", cap="round")


# =================================================================
#  LISTASOR
# =================================================================
class ItemRow(GlassMixin, BoxLayout):
    badge_alpha = NumericProperty(0)

    def __init__(self, text, app, boxes=1, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None,
                         height=ROW_HEIGHT, **kwargs)
        self.app = app
        self.base = text
        self.boxes = max(1, min(3, int(boxes)))
        self.panel_open = False
        self.running = None
        self.end_time = 0
        self.event = None
        self.init_glass(18)

        # felső sor: szöveg + időzítő gomb + pipa
        top = BoxLayout(size_hint_y=None, height=ROW_HEIGHT, spacing=dp(10),
                        padding=(dp(16), dp(13), dp(38), dp(13)))
        self.label = Label(text=text, halign="left", valign="middle",
                           font_size=sp(17), color=TEXT,
                           shorten=True, shorten_from="right")
        self.label.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.timer_btn = IconButton("timer", radius=9, size_hint=(None, None),
                                    size=(dp(30), dp(30)), pos_hint={"center_y": 0.5})
        self.timer_btn.bind(on_release=lambda *a: self.toggle_panel())
        top.add_widget(self.label)
        top.add_widget(self.timer_btn)
        self.checks = []
        for _ in range(self.boxes):
            chk = GlassCheck(size_hint=(None, None), size=(dp(30), dp(30)),
                             pos_hint={"center_y": 0.5})
            self.checks.append(chk)
            top.add_widget(chk)
        self.add_widget(top)

        # időzítő panel (az óra gombra jelenik meg, a mentett időket mutatja)
        self.panel = BoxLayout(size_hint_y=None, height=PANEL_HEIGHT, spacing=dp(6),
                               padding=(dp(10), 0, dp(10), dp(8)))

        # kis kuka a jobb felső sarokban (törlés módban látszik)
        self.bind(badge_alpha=self.draw_badge, pos=self.draw_badge, size=self.draw_badge)

    # ---------- törlés mód ----------
    def show_badge(self, flag):
        Animation.cancel_all(self, "badge_alpha")
        Animation(badge_alpha=1 if flag else 0, duration=0.2).start(self)

    def draw_badge(self, *args):
        self.canvas.after.clear()
        a = self.badge_alpha
        if a <= 0.01:
            return
        s = dp(24)
        m = dp(5)
        x = self.right - s - m
        y = self.top - s - m
        with self.canvas.after:
            Color(1, 1, 1, 0.30 * a)
            RoundedRectangle(pos=(x, y), size=(s, s), radius=[dp(8)])
            Color(1, 1, 1, 0.9 * a)
            Line(rounded_rectangle=(x, y, s, s, dp(8)), width=1.1)
            draw_trash(x + s / 2, y + s / 2, s * 0.23, (1, 1, 1, a), max(1.2, s * 0.05))

    # ---------- érintés (csak törlés módban) ----------
    def on_touch_down(self, touch):
        if self.app.delete_mode and self.collide_point(*touch.pos):
            touch.grab(self)
            touch.ud["rowmove"] = [0, 0]
            return True  # a gombok ne reagáljanak törlés módban
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            d = touch.ud["rowmove"]
            d[0] += touch.dx
            d[1] += touch.dy
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            dx, dy = touch.ud["rowmove"]
            if abs(dx) < dp(12) and abs(dy) < dp(12):
                self.app.delete_row(self)
            return True
        return super().on_touch_up(touch)

    # ---------- időzítő panel ----------
    def toggle_panel(self):
        if self.panel_open:
            self.close_panel()
            return
        if not self.event:
            self.label.text = self.base  # a régi "KÉSZ!" felirat eltűnik
        self.panel.clear_widgets()
        if self.app.presets:
            for secs in self.app.presets:
                btn = TextButton(text=fmt_short(secs), radius=12, font_size=sp(13))
                btn.bind(on_release=lambda b, s=secs: self.start_timer(s))
                self.panel.add_widget(btn)
        else:
            self.panel.add_widget(Label(text="Nincs mentett idő (lásd az Időzítő oldalt)",
                                        font_size=sp(13), color=(1, 1, 1, 0.6)))
        self.panel_open = True
        self.panel.opacity = 0
        self.add_widget(self.panel)
        self.height = ROW_HEIGHT + PANEL_HEIGHT
        Animation(opacity=1, duration=0.2).start(self.panel)

    def close_panel(self):
        if self.panel_open:
            self.panel_open = False
            self.remove_widget(self.panel)
            self.height = ROW_HEIGHT

    # ---------- időzítő ----------
    def start_timer(self, seconds):
        if self.event and self.running == seconds:
            self.stop_timer()  # ugyanarra újra nyomva leáll
            self.close_panel()
            return
        self.cancel_timer()
        self.running = seconds
        self.end_time = time.time() + seconds
        self.update_label(seconds)
        self.event = Clock.schedule_interval(self.tick, 0.25)
        self.close_panel()

    def cancel_timer(self):
        if self.event:
            self.event.cancel()
            self.event = None

    def stop_timer(self):
        self.cancel_timer()
        self.running = None
        self.label.text = self.base

    def tick(self, dt):
        remaining = math.ceil(self.end_time - time.time())
        if remaining <= 0:
            self.cancel_timer()
            self.running = None
            self.label.text = f"{self.base}  -  KÉSZ!"
            vibrate()
            return False
        self.update_label(remaining)

    def update_label(self, remaining):
        self.label.text = f"{self.base}  -  {fmt(remaining)}"


# =================================================================
#  GÖRGETHETŐ IDŐ-ÁLLÍTÓ KERÉK
# =================================================================
class Wheel(StencilView):
    """Fel-le húzással állítható számkerék (körbeforgó, 0-tól n-1-ig)."""
    pos_f = NumericProperty(0.0)
    value = NumericProperty(0)
    locked = BooleanProperty(False)

    def __init__(self, n, **kwargs):
        super().__init__(**kwargs)
        self.n = n
        self.item_h = dp(38)
        self._moves = []
        self.slots = []
        for k in range(-3, 4):
            lbl = Label(text="", font_size=sp(26), color=(1, 1, 1, 1),
                        size_hint=(None, None), halign="center", valign="middle")
            lbl.k = k
            self.slots.append(lbl)
            self.add_widget(lbl)
        with self.canvas.before:
            Color(1, 1, 1, 0.12)
            self._bar = RoundedRectangle(radius=[dp(10)])
        self.bind(pos=self._layout, size=self._layout, pos_f=self._on_pos)
        self._layout()

    def _layout(self, *args):
        h = self.item_h
        cx, cy = self.center
        self._bar.pos = (self.x + dp(4), cy - h / 2)
        self._bar.size = (max(0, self.width - dp(8)), h)
        base = math.floor(self.pos_f)
        frac = self.pos_f - base
        for lbl in self.slots:
            k = lbl.k
            y = cy - (k - frac) * h
            lbl.size = (self.width, h)
            lbl.text_size = lbl.size
            lbl.pos = (self.x, y - h / 2)
            txt = f"{(base + k) % self.n:02d}"
            if lbl.text != txt:
                lbl.text = txt
            dist = abs(k - frac)
            lbl.opacity = max(0.0, 1.0 - dist / 2.4) ** 1.3

    def _on_pos(self, *args):
        self._layout()
        v = int(round(self.pos_f)) % self.n
        if v != self.value:
            self.value = v

    def set_value(self, v):
        """Szépen odagörgeti a kereket a kért értékhez (a legrövidebb úton)."""
        Animation.cancel_all(self, "pos_f")
        cur = round(self.pos_f)
        diff = (int(v) - cur) % self.n
        if diff > self.n / 2:
            diff -= self.n
        Animation(pos_f=cur + diff, duration=0.3, t="out_cubic").start(self)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and not self.locked:
            Animation.cancel_all(self, "pos_f")
            touch.grab(self)
            self._moves = []
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.pos_f += touch.dy / self.item_h
            self._moves.append((time.time(), touch.dy))
            self._moves = self._moves[-6:]
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            now = time.time()
            recent = [(t, dy) for t, dy in self._moves if now - t < 0.12]
            vel = 0.0
            if recent:
                span = max(now - recent[0][0], 0.03)
                vel = sum(dy for t, dy in recent) / self.item_h / span  # kerék-lépés / mp
                vel = max(-30.0, min(30.0, vel))
            target = round(self.pos_f + vel * 0.25)
            Animation(pos_f=target, duration=0.35, t="out_cubic").start(self)
            return True
        return super().on_touch_up(touch)


# =================================================================
#  KÖR (vizuális visszaszámlálás)
# =================================================================
class Ring(Widget):
    fraction = NumericProperty(1.0)  # 1 = teljes kör, 0 = lejárt

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main = Label(text="01:00", font_size=sp(46), bold=True, color=(1, 1, 1, 1),
                          size_hint=(None, None))
        self.sub = Label(text="Beállított idő", font_size=sp(14), color=(1, 1, 1, 0.65),
                         size_hint=(None, None))
        for lbl in (self.main, self.sub):
            lbl.bind(texture_size=lambda w, ts: setattr(w, "size", ts))
            lbl.bind(size=self._place)
            self.add_widget(lbl)
        self.bind(pos=self._redraw, size=self._redraw, fraction=self._redraw)

    def _place(self, *args):
        cx, cy = self.center
        d = min(self.width, self.height)
        self.main.center = (cx, cy + dp(8))
        self.sub.center = (cx, cy - d * 0.17)

    def _redraw(self, *args):
        self.canvas.before.clear()
        d = min(self.width, self.height) - dp(24)
        if d <= 0:
            return
        cx, cy = self.center
        lw = max(dp(6), d * 0.045)
        r = d / 2 - lw / 2
        f = self.fraction
        with self.canvas.before:
            Color(1, 1, 1, 0.12)
            Line(circle=(cx, cy, r), width=lw)
            if f > 0.002:
                Color(1, 1, 1, 0.95)
                if f >= 0.998:
                    Line(circle=(cx, cy, r), width=lw)
                else:
                    Line(circle=(cx, cy, r, 360 * (1 - f), 360), width=lw, cap="round")
        self.main.font_size = max(sp(28), min(sp(52), d * 0.20))
        self._place()


# =================================================================
#  MENTETT IDŐ GOMB
# =================================================================
class PresetChip(GlassMixin, ButtonBehavior, Label):
    def __init__(self, secs, page, **kwargs):
        super().__init__(text=fmt_short(secs), font_size=sp(15), color=TEXT, **kwargs)
        self.secs = secs
        self.edit = False
        self.init_glass(12)
        self.bind(on_release=lambda *a: page.chip_pressed(secs))
        self.bind(pos=self.draw_x, size=self.draw_x)

    def set_edit(self, flag):
        self.edit = flag
        if flag:
            self.set_glass(GLASS_ON, GLASS_ON_BORDER)
        else:
            self.set_glass(GLASS, GLASS_BORDER)
        self.draw_x()

    def draw_x(self, *args):
        self.canvas.after.clear()
        if not self.edit:
            return
        s = dp(5)
        cx = self.right - dp(15)
        cy = self.center_y
        with self.canvas.after:
            Color(1, 1, 1, 0.95)
            Line(points=[cx - s, cy - s, cx + s, cy + s], width=dp(1.4), cap="round")
            Line(points=[cx - s, cy + s, cx + s, cy - s], width=dp(1.4), cap="round")


# =================================================================
#  IDŐZÍTŐ OLDAL
# =================================================================
class TimerPage(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.app = app
        self.state = "idle"  # idle / running / paused / done
        self.total = 60
        self.remaining = 60
        self.end_time = 0.0
        self.event = None
        self.edit_mode = False
        self._flash_ev = None

        # fejléc
        bar = BoxLayout(size_hint_y=None, height=dp(70),
                        padding=(dp(18), dp(12), dp(14), dp(10)))
        title = Label(text="Időzítő", font_size=sp(26), bold=True, color=TEXT,
                      halign="left", valign="middle")
        title.bind(size=lambda w, s: setattr(w, "text_size", s))
        bar.add_widget(title)
        self.add_widget(bar)

        body = BoxLayout(orientation="vertical", spacing=dp(10),
                         padding=(dp(16), 0, dp(16), 0))

        # kör
        self.ring = Ring()
        body.add_widget(self.ring)

        # görgethető idő-állító (óra : perc : mp)
        pick = GlassBox(radius=20, orientation="horizontal", size_hint_y=None,
                        height=dp(150), padding=dp(8), spacing=dp(4))
        self.wh = Wheel(24)
        self.wm = Wheel(60)
        self.ws = Wheel(60)
        for wheel, unit in ((self.wh, "óra"), (self.wm, "perc"), (self.ws, "mp")):
            col = BoxLayout(orientation="vertical")
            col.add_widget(wheel)
            col.add_widget(Label(text=unit, size_hint_y=None, height=dp(20),
                                 font_size=sp(13), color=(1, 1, 1, 0.6)))
            pick.add_widget(col)
        body.add_widget(pick)

        # mentett idők
        block = BoxLayout(orientation="vertical", size_hint_y=None,
                          height=dp(142), spacing=dp(6))
        head = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        heading = Label(text="Mentett idők", halign="left", valign="middle",
                        font_size=sp(15), color=(1, 1, 1, 0.75))
        heading.bind(size=lambda w, s: setattr(w, "text_size", s))
        save_btn = TextButton(text="Mentés", radius=10, font_size=sp(14),
                              size_hint=(None, 1), width=dp(84))
        save_btn.bind(on_release=self.save_current)
        self.edit_btn = TextButton(text="Szerk.", radius=10, font_size=sp(14),
                                   size_hint=(None, 1), width=dp(84))
        self.edit_btn.bind(on_release=self.toggle_edit)
        head.add_widget(heading)
        head.add_widget(save_btn)
        head.add_widget(self.edit_btn)
        block.add_widget(head)
        self.chips = GridLayout(cols=3, size_hint_y=None, height=dp(96), spacing=dp(8),
                                row_default_height=dp(44), row_force_default=True)
        block.add_widget(self.chips)
        body.add_widget(block)
        self.add_widget(body)

        # alsó sor: Indítás / Nullázás (jobbra a váltó gomb helye marad)
        ctrl = BoxLayout(size_hint_y=None, height=dp(88), spacing=dp(12),
                         padding=(dp(16), dp(16), dp(96), dp(16)))
        self.start_btn = TextButton(text="Indítás", font_size=sp(17),
                                    tint=(1, 1, 1, 0.26), border=(1, 1, 1, 0.8))
        self.start_btn.bind(on_release=self.toggle_run)
        reset_btn = TextButton(text="Nullázás", font_size=sp(16))
        reset_btn.bind(on_release=self.reset)
        ctrl.add_widget(self.start_btn)
        ctrl.add_widget(reset_btn)
        self.add_widget(ctrl)

        # kezdőérték: 1 perc
        self.wm.pos_f = 1
        self.wh.bind(value=self.on_wheel)
        self.wm.bind(value=self.on_wheel)
        self.ws.bind(value=self.on_wheel)
        self.rebuild_chips()
        self.on_wheel()
        self.set_state("idle")

    # ---------- kerekek ----------
    def wheel_seconds(self):
        return int(self.wh.value) * 3600 + int(self.wm.value) * 60 + int(self.ws.value)

    def set_wheels(self, secs):
        h, rem = divmod(int(secs), 3600)
        m, s = divmod(rem, 60)
        self.wh.set_value(min(h, 23))
        self.wm.set_value(m)
        self.ws.set_value(s)

    def on_wheel(self, *args):
        if self.state in ("idle", "done"):
            if self.state == "done":
                self.state = "idle"
                self.refresh_sub()
            self.total = self.wheel_seconds()
            self.remaining = self.total
            self.ring.fraction = 1.0
            self.ring.main.text = fmt_clock(self.total)

    # ---------- állapot ----------
    def refresh_sub(self):
        self.ring.sub.text = {"idle": "Beállított idő", "running": "Fut",
                              "paused": "Szünet", "done": "Letelt"}[self.state]

    def flash(self, msg):
        self.ring.sub.text = msg
        if self._flash_ev:
            self._flash_ev.cancel()
        self._flash_ev = Clock.schedule_once(lambda dt: self.refresh_sub(), 2.2)

    def set_state(self, st):
        self.state = st
        locked = st in ("running", "paused")
        for w in (self.wh, self.wm, self.ws):
            w.locked = locked
            Animation(opacity=0.4 if locked else 1, duration=0.2).start(w)
        self.start_btn.text = {"idle": "Indítás", "running": "Szünet",
                               "paused": "Folytatás", "done": "Indítás"}[st]
        self.refresh_sub()
        self.app.update_timer_dot()

    # ---------- vezérlés ----------
    def toggle_run(self, *args):
        if self.state == "running":
            self.pause()
        elif self.state == "paused":
            self.resume()
        else:
            secs = self.wheel_seconds()
            if secs <= 0:
                self.flash("Állíts be időt!")
                return
            self.start(secs)

    def cancel_event(self):
        if self.event:
            self.event.cancel()
            self.event = None

    def start(self, secs):
        self.cancel_event()
        self.total = secs
        self.remaining = secs
        self.end_time = time.time() + secs
        self.set_state("running")
        self.event = Clock.schedule_interval(self.tick, 1 / 30.0)
        self.tick(0)

    def pause(self):
        self.remaining = max(0.0, self.end_time - time.time())
        self.cancel_event()
        self.set_state("paused")

    def resume(self):
        self.end_time = time.time() + self.remaining
        self.event = Clock.schedule_interval(self.tick, 1 / 30.0)
        self.set_state("running")

    def reset(self, *args):
        self.cancel_event()
        self.set_state("idle")
        self.on_wheel()

    def tick(self, dt):
        self.remaining = self.end_time - time.time()
        if self.remaining <= 0:
            self.finish()
            return False
        self.ring.fraction = self.remaining / self.total
        self.ring.main.text = fmt_clock(self.remaining)

    def finish(self):
        self.cancel_event()
        self.remaining = 0
        self.ring.fraction = 0
        self.ring.main.text = "KÉSZ!"
        self.set_state("done")
        vibrate()

    # ---------- mentett idők ----------
    def rebuild_chips(self):
        self.chips.clear_widgets()
        for secs in self.app.presets:
            chip = PresetChip(secs, self)
            chip.set_edit(self.edit_mode)
            self.chips.add_widget(chip)

    def chip_pressed(self, secs):
        if self.edit_mode:
            self.app.remove_preset(secs)
            self.rebuild_chips()
        else:
            self.set_wheels(secs)
            self.start(secs)

    def save_current(self, *args):
        secs = self.wheel_seconds()
        if secs <= 0:
            self.flash("Állíts be időt!")
        elif secs in self.app.presets:
            self.flash("Ez az idő már mentve van")
        elif len(self.app.presets) >= MAX_PRESETS:
            self.flash(f"Legfeljebb {MAX_PRESETS} idő menthető, törölj egyet")
        else:
            self.app.add_preset(secs)
            self.rebuild_chips()
            self.flash("Elmentve")

    def toggle_edit(self, *args):
        self.edit_mode = not self.edit_mode
        self.edit_btn.text = "Kész" if self.edit_mode else "Szerk."
        for chip in self.chips.children:
            chip.set_edit(self.edit_mode)
        if self.edit_mode:
            self.flash("Koppints egy időre a törléshez")


# =================================================================
#  ÚJ ELEM ABLAK (a képernyő tetején, hogy a billentyűzet ne takarja)
# =================================================================
class AddDialog(FloatLayout):
    def __init__(self, on_add, **kwargs):
        super().__init__(size_hint=(1, 1), **kwargs)
        self.on_add = on_add
        self.boxes = 1
        with self.canvas.before:
            Color(0, 0, 0, 0.65)
            self._dim = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

        self.card = GlassBox(radius=24, tint=(0.16, 0.16, 0.18, 0.94),
                             border=(1, 1, 1, 0.4), orientation="vertical",
                             padding=dp(16), spacing=dp(14), size_hint=(0.88, None),
                             height=dp(262), pos_hint={"center_x": 0.5, "top": 0.85})

        field = GlassBox(radius=14, size_hint_y=None, height=dp(52),
                         padding=(dp(12), dp(4)))
        self.ti = TextInput(hint_text="Új elem...", multiline=False, font_size=sp(17),
                            background_normal="", background_active="",
                            background_color=(0, 0, 0, 0), foreground_color=(1, 1, 1, 1),
                            hint_text_color=(1, 1, 1, 0.5), cursor_color=(1, 1, 1, 1),
                            padding=(0, dp(11), 0, dp(11)))
        field.add_widget(self.ti)

        # pipadobozok száma: 1, 2 vagy 3
        picker = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(12))
        self.num_btns = {}
        for n in (1, 2, 3):
            b = TextButton(text=str(n), font_size=sp(20), radius=14)
            b.bind(on_release=lambda w, n=n: self.pick(n))
            self.num_btns[n] = b
            picker.add_widget(b)
        self.pick(1)

        buttons = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(12))
        cancel = TextButton(text="Mégse")
        ok = TextButton(text="Hozzáadás", tint=(1, 1, 1, 0.26), border=(1, 1, 1, 0.8))
        buttons.add_widget(cancel)
        buttons.add_widget(ok)

        self.card.add_widget(field)
        self.card.add_widget(picker)
        self.card.add_widget(buttons)
        self.add_widget(self.card)

        self.ti.bind(on_text_validate=self.submit)
        ok.bind(on_release=self.submit)
        cancel.bind(on_release=lambda *a: self.close())
        Clock.schedule_once(lambda dt: setattr(self.ti, "focus", True), 0.2)

    def _upd(self, *args):
        self._dim.pos = self.pos
        self._dim.size = self.size

    def pick(self, n):
        self.boxes = n
        for k, b in self.num_btns.items():
            if k == n:
                b.set_glass(GLASS_ON, GLASS_ON_BORDER)
            else:
                b.set_glass(GLASS, GLASS_BORDER)

    def submit(self, *args):
        text = self.ti.text.strip()
        boxes = self.boxes
        self.close()
        if text:
            self.on_add(text, boxes)

    def close(self):
        self.ti.focus = False
        if self.parent:
            self.parent.remove_widget(self)

    def on_touch_down(self, touch):
        if not self.card.collide_point(*touch.pos):
            self.close()
            return True
        super().on_touch_down(touch)
        return True


# =================================================================
#  AZ ALKALMAZÁS
# =================================================================
class ChecklistApp(App):
    def build(self):
        self.delete_mode = False
        self.rows = []
        self.dialog = None
        self.on_timer_page = False
        self.presets = self.load_presets()

        root = Background()

        # --- Listám oldal ---
        self.list_page = BoxLayout(orientation="vertical")
        bar = BoxLayout(size_hint_y=None, height=dp(70),
                        padding=(dp(18), dp(12), dp(14), dp(10)), spacing=dp(10))
        title = Label(text="Listám", font_size=sp(26), bold=True, color=TEXT,
                      halign="left", valign="middle")
        title.bind(size=lambda w, s: setattr(w, "text_size", s))
        clear_btn = TextButton(text="Clear All", radius=14,
                               size_hint=(None, 1), width=dp(110))
        clear_btn.bind(on_release=self.clear_all)
        bar.add_widget(title)
        bar.add_widget(clear_btn)
        self.list_page.add_widget(bar)

        self.scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(10),
                               padding=(dp(14), dp(6), dp(14), dp(110)))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        for text, boxes in self.load_items():
            row = ItemRow(text, self, boxes)
            self.rows.append(row)
            self.grid.add_widget(row)
        self.scroll.add_widget(self.grid)
        self.list_page.add_widget(self.scroll)

        # --- Időzítő oldal ---
        self.timer_page = TimerPage(self)

        # az éppen látható oldal
        self.page_box = BoxLayout()
        self.page_box.add_widget(self.list_page)
        root.add_widget(self.page_box)

        # jobb alsó sarok: plusz, kuka, időzítő
        bottom = BoxLayout(size_hint=(None, None),
                           size=(dp(3 * 56 + 2 * 12 + 32), dp(56 + 32)),
                           padding=dp(16), spacing=dp(12),
                           pos_hint={"right": 1, "y": 0})
        self.plus_btn = IconButton("plus")
        self.plus_btn.bind(on_release=self.open_add)
        self.trash_btn = IconButton("trash")
        self.trash_btn.bind(on_release=self.toggle_delete_mode)
        self.timer_btn = IconButton("timer")
        self.timer_btn.bind(on_release=self.toggle_timer_page)
        bottom.add_widget(self.plus_btn)
        bottom.add_widget(self.trash_btn)
        bottom.add_widget(self.timer_btn)
        root.add_widget(bottom)

        self.update_timer_dot()
        return root

    # ---------- oldalváltás ----------
    def toggle_timer_page(self, *args):
        if self.delete_mode:
            self.set_delete_mode(False)
        if self.dialog is not None and self.dialog.parent:
            self.dialog.close()
        self.on_timer_page = not self.on_timer_page
        page = self.timer_page if self.on_timer_page else self.list_page
        self.page_box.clear_widgets()
        page.opacity = 0
        self.page_box.add_widget(page)
        Animation(opacity=1, duration=0.2).start(page)
        for b in (self.plus_btn, self.trash_btn):
            b.opacity = 0 if self.on_timer_page else 1
            b.disabled = self.on_timer_page
        if self.on_timer_page:
            self.timer_btn.set_glass(GLASS_ON, GLASS_ON_BORDER)
        else:
            self.timer_btn.set_glass(GLASS, GLASS_BORDER)

    def update_timer_dot(self):
        page = getattr(self, "timer_page", None)
        btn = getattr(self, "timer_btn", None)
        if page is not None and btn is not None:
            btn.dot = page.state in ("running", "paused")

    # ---------- mentés: lista ----------
    def items_path(self):
        return os.path.join(self.user_data_dir, "items.json")

    def load_items(self):
        try:
            with open(self.items_path(), encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                out = []
                for x in data:
                    if isinstance(x, dict):  # új formátum
                        out.append((str(x.get("text", "")), int(x.get("boxes", 1))))
                    else:  # régi formátum: csak szöveg
                        out.append((str(x), 1))
                return out
        except Exception:
            pass
        return [(t, 1) for t in ITEMS]

    def save_items(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.items_path(), "w", encoding="utf-8") as f:
                json.dump([{"text": r.base, "boxes": r.boxes} for r in self.rows],
                          f, ensure_ascii=False)
        except Exception:
            pass

    # ---------- mentés: időzítők ----------
    def presets_path(self):
        return os.path.join(self.user_data_dir, "presets.json")

    def load_presets(self):
        try:
            with open(self.presets_path(), encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                vals = [int(x) for x in data if int(x) > 0]
                return vals[:MAX_PRESETS]
        except Exception:
            pass
        return list(DEFAULT_PRESETS)

    def save_presets(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.presets_path(), "w", encoding="utf-8") as f:
                json.dump(self.presets, f)
        except Exception:
            pass

    def add_preset(self, secs):
        if secs > 0 and secs not in self.presets and len(self.presets) < MAX_PRESETS:
            self.presets.append(int(secs))
            self.save_presets()

    def remove_preset(self, secs):
        if secs in self.presets:
            self.presets.remove(secs)
            self.save_presets()

    # ---------- Clear All ----------
    def clear_all(self, *args):
        for row in self.rows:
            for chk in row.checks:
                chk.active = False

    # ---------- törlés mód ----------
    def toggle_delete_mode(self, *args):
        self.set_delete_mode(not self.delete_mode)

    def set_delete_mode(self, flag):
        self.delete_mode = flag
        for row in self.rows:
            row.show_badge(flag)
        if flag:
            self.trash_btn.set_glass(GLASS_ON, GLASS_ON_BORDER)
        else:
            self.trash_btn.set_glass(GLASS, GLASS_BORDER)

    def delete_row(self, row):
        if row not in self.rows:
            return
        self.rows.remove(row)
        row.cancel_timer()
        self.set_delete_mode(False)
        anim = Animation(opacity=0, height=0, duration=0.3, t="in_quad")
        anim.bind(on_complete=lambda *a: self.grid.remove_widget(row))
        anim.start(row)
        self.save_items()

    # ---------- hozzáadás ----------
    def open_add(self, *args):
        if self.delete_mode:
            self.set_delete_mode(False)
        if self.dialog is not None and self.dialog.parent:
            return
        self.dialog = AddDialog(self.add_item)
        self.root.add_widget(self.dialog)

    def add_item(self, text, boxes=1):
        row = ItemRow(text, self, boxes)
        row.opacity = 0
        self.rows.append(row)
        self.grid.add_widget(row)  # a lista végére kerül
        Animation(opacity=1, duration=0.3).start(row)
        self.save_items()

        def scroll_down(dt):
            if self.grid.height > self.scroll.height:
                self.scroll.scroll_y = 0
        Clock.schedule_once(scroll_down, 0.2)


if __name__ == "__main__":
    ChecklistApp().run()
