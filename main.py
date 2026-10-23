import json
import os

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
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

# Az öt időzítő másodpercben (átírhatod)
TIMES = [10, 30, 60, 120, 300]

SWIPE_MIN = dp(60)
ROW_HEIGHT = dp(56)
PANEL_HEIGHT = dp(52)

RED_GLASS = (1, 0.2, 0.28, 0.55)
RED_BORDER = (1, 0.65, 0.65, 0.9)
WHITE_GLASS = (1, 1, 1, 0.16)
WHITE_BORDER = (1, 1, 1, 0.45)


def fmt(seconds):
    if seconds >= 60:
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"
    return f"{seconds} mp"


def vibrate():
    try:
        from plyer import vibrator
        vibrator.vibrate(time=1)
    except Exception:
        pass  # gépen nincs rezgés, nem baj


# =================================================================
#  HÁTTÉR (színátmenet + puha színfoltok, hogy az üveg látszódjon)
# =================================================================
def make_gradient_texture():
    stops = [(0.0, (0.04, 0.62, 0.62)),
             (0.5, (0.10, 0.30, 0.78)),
             (1.0, (0.32, 0.13, 0.62))]  # 0 = alul, 1 = felül
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
            Color(1, 0.35, 0.6, 0.75)
            self.b1 = Rectangle(texture=blob)
            Color(0.3, 0.9, 1, 0.65)
            self.b2 = Rectangle(texture=blob)
            Color(0.75, 0.45, 1, 0.70)
            self.b3 = Rectangle(texture=blob)
        self.bind(pos=self.update_bg, size=self.update_bg)

    def update_bg(self, *args):
        x, y = self.pos
        w, h = self.size
        self.bg.pos, self.bg.size = (x, y), (w, h)
        big = max(w, h)
        for rect, fx, fy, scale in ((self.b1, 0.15, 0.80, 0.9),
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

    def init_glass(self, radius=18, tint=WHITE_GLASS, border=WHITE_BORDER):
        self.glass_radius = dp(radius)
        self._base_alpha = tint[3]
        with self.canvas.before:
            self._g_tint = Color(*tint)
            self._g_bg = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[self.glass_radius])
            Color(1, 1, 1, 0.08)
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
    def __init__(self, radius=20, tint=WHITE_GLASS, border=WHITE_BORDER, **kwargs):
        super().__init__(**kwargs)
        self.init_glass(radius, tint, border)


class TextButton(GlassMixin, ButtonBehavior, Label):
    def __init__(self, radius=14, tint=WHITE_GLASS, border=WHITE_BORDER, **kwargs):
        kwargs.setdefault("font_size", sp(16))
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
    """Üveg négyzet rajzolt ikonnal ('plus' vagy 'trash')."""

    def __init__(self, icon, radius=16, tint=WHITE_GLASS, border=WHITE_BORDER,
                 icon_color=(1, 1, 1, 0.95), passive=False, **kwargs):
        super().__init__(**kwargs)
        self.icon = icon
        self.icon_color = icon_color
        self.passive = passive
        self.init_glass(radius, tint, border)
        self.bind(pos=self.draw_icon, size=self.draw_icon)
        self.draw_icon()

    def on_touch_down(self, touch):
        if self.passive:
            return False
        return super().on_touch_down(touch)

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


class GlassCheck(GlassMixin, ButtonBehavior, Widget):
    """Üveg pipadoboz."""
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.init_glass(9, (1, 1, 1, 0.12), (1, 1, 1, 0.6))
        self.bind(pos=self.draw_tick, size=self.draw_tick, active=self.on_active_change)
        self.draw_tick()

    def on_release(self):
        self.active = not self.active

    def on_active_change(self, *args):
        if self.active:
            self.set_glass((0.3, 1, 0.55, 0.40), (0.75, 1, 0.85, 0.9))
        else:
            self.set_glass((1, 1, 1, 0.12), (1, 1, 1, 0.6))
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
class ItemRow(GlassMixin, FloatLayout):
    def __init__(self, text, app, **kwargs):
        super().__init__(size_hint_y=None, height=ROW_HEIGHT, **kwargs)
        self.app = app
        self.base = text
        self.panel_open = False
        self.remaining = 0
        self.event = None
        self.init_glass(18)

        self.content = BoxLayout(orientation="vertical", size_hint=(1, 1))

        top = BoxLayout(size_hint_y=None, height=ROW_HEIGHT, spacing=dp(8),
                        padding=(dp(16), dp(13), dp(38), dp(13)))
        self.label = Label(text=text, halign="left", valign="middle",
                           font_size=sp(17), shorten=True, shorten_from="right")
        self.label.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.check = GlassCheck(size_hint=(None, None), size=(dp(30), dp(30)),
                                pos_hint={"center_y": 0.5})
        top.add_widget(self.label)
        top.add_widget(self.check)
        self.content.add_widget(top)
        self.add_widget(self.content)

        # időzítő panel (csak húzásra kerül be a sorba)
        self.panel = BoxLayout(size_hint_y=None, height=PANEL_HEIGHT, spacing=dp(6),
                               padding=(dp(10), 0, dp(10), dp(8)))
        for secs in TIMES:
            btn = TextButton(text=fmt(secs), radius=12, font_size=sp(14))
            btn.bind(on_release=lambda b, s=secs: self.start_timer(s))
            self.panel.add_widget(btn)

        # kis piros kuka a jobb felső sarokban (törlés módban látszik)
        self.badge = IconButton("trash", radius=8, tint=RED_GLASS, border=RED_BORDER,
                                passive=True, size_hint=(None, None),
                                size=(dp(26), dp(26)),
                                pos_hint={"right": 0.99, "top": 0.95}, opacity=0)
        self.add_widget(self.badge)

    # ---------- törlés mód ----------
    def show_badge(self, flag):
        Animation.cancel_all(self.badge, "opacity")
        Animation(opacity=1 if flag else 0, duration=0.2).start(self.badge)

    # ---------- érintés: húzás + törlés ----------
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            touch.ud["sdx"] = 0
            touch.ud["sdy"] = 0
            if self.app.delete_mode:
                return True  # a pipa/gombok ne reagáljanak
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            touch.ud["sdx"] += touch.dx
            touch.ud["sdy"] += touch.dy
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            dx = touch.ud.get("sdx", 0)
            dy = touch.ud.get("sdy", 0)
            if self.app.delete_mode:
                if abs(dx) < dp(12) and abs(dy) < dp(12):
                    self.app.delete_row(self)
                return True
            if abs(dx) > SWIPE_MIN and abs(dx) > 2 * abs(dy):
                self.toggle_panel()
            return True
        return super().on_touch_up(touch)

    def toggle_panel(self):
        if self.panel_open:
            self.panel_open = False
            self.content.remove_widget(self.panel)
            self.height = ROW_HEIGHT
        else:
            self.panel_open = True
            self.panel.opacity = 0
            self.content.add_widget(self.panel)
            self.height = ROW_HEIGHT + PANEL_HEIGHT
            Animation(opacity=1, duration=0.2).start(self.panel)

    # ---------- időzítő ----------
    def start_timer(self, seconds):
        self.cancel_timer()
        self.remaining = seconds
        self.update_label()
        self.event = Clock.schedule_interval(self.tick, 1)

    def cancel_timer(self):
        if self.event:
            self.event.cancel()
            self.event = None

    def tick(self, dt):
        self.remaining -= 1
        if self.remaining <= 0:
            self.cancel_timer()
            self.label.text = f"{self.base}  -  KÉSZ!"
            vibrate()
            return False
        self.update_label()

    def update_label(self):
        self.label.text = f"{self.base}  -  {fmt(self.remaining)}"


# =================================================================
#  AZ ALKALMAZÁS
# =================================================================
class ChecklistApp(App):
    def build(self):
        Window.softinput_mode = "below_target"
        self.delete_mode = False
        self.rows = []

        root = Background()

        main = BoxLayout(orientation="vertical")

        # felső sáv: cím + Clear All
        bar = BoxLayout(size_hint_y=None, height=dp(70),
                        padding=(dp(18), dp(12), dp(14), dp(10)), spacing=dp(10))
        title = Label(text="Listám", font_size=sp(26), bold=True,
                      halign="left", valign="middle")
        title.bind(size=lambda w, s: setattr(w, "text_size", s))
        clear_btn = TextButton(text="Clear All", radius=14,
                               size_hint=(None, 1), width=dp(110))
        clear_btn.bind(on_release=self.clear_all)
        bar.add_widget(title)
        bar.add_widget(clear_btn)
        main.add_widget(bar)

        # görgethető lista
        self.scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(10),
                               padding=(dp(14), dp(6), dp(14), dp(110)))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        for text in self.load_items():
            row = ItemRow(text, self)
            self.rows.append(row)
            self.grid.add_widget(row)
        self.scroll.add_widget(self.grid)
        main.add_widget(self.scroll)
        root.add_widget(main)

        # jobb alsó sarok: kuka + plusz
        bottom = BoxLayout(size_hint=(None, None),
                           size=(dp(2 * 56 + 12 + 32), dp(56 + 32)),
                           padding=dp(16), spacing=dp(12),
                           pos_hint={"right": 1, "y": 0})
        self.trash_btn = IconButton("trash", icon_color=(1, 0.3, 0.36, 1))
        self.trash_btn.bind(on_release=self.toggle_delete_mode)
        plus_btn = IconButton("plus")
        plus_btn.bind(on_release=self.open_add)
        bottom.add_widget(self.trash_btn)
        bottom.add_widget(plus_btn)
        root.add_widget(bottom)

        return root

    # ---------- mentés ----------
    def items_path(self):
        return os.path.join(self.user_data_dir, "items.json")

    def load_items(self):
        try:
            with open(self.items_path(), encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:
            pass
        return list(ITEMS)

    def save_items(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.items_path(), "w", encoding="utf-8") as f:
                json.dump([r.base for r in self.rows], f, ensure_ascii=False)
        except Exception:
            pass

    # ---------- Clear All ----------
    def clear_all(self, *args):
        for row in self.rows:
            row.check.active = False

    # ---------- törlés mód ----------
    def toggle_delete_mode(self, *args):
        self.set_delete_mode(not self.delete_mode)

    def set_delete_mode(self, flag):
        self.delete_mode = flag
        for row in self.rows:
            row.show_badge(flag)
        if flag:
            self.trash_btn.set_glass(RED_GLASS, RED_BORDER)
        else:
            self.trash_btn.set_glass(WHITE_GLASS, WHITE_BORDER)

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

        view = ModalView(size_hint=(0.88, None), height=dp(190), background="",
                         background_color=(0, 0, 0, 0), overlay_color=(0, 0, 0, 0.5))
        box = GlassBox(radius=24, tint=(0.1, 0.12, 0.35, 0.60),
                       orientation="vertical", padding=dp(16), spacing=dp(14))

        field = GlassBox(radius=14, size_hint_y=None, height=dp(52),
                         padding=(dp(12), dp(4)))
        ti = TextInput(hint_text="Új elem...", multiline=False, font_size=sp(17),
                       background_normal="", background_active="",
                       background_color=(0, 0, 0, 0), foreground_color=(1, 1, 1, 1),
                       hint_text_color=(1, 1, 1, 0.5), cursor_color=(1, 1, 1, 1),
                       padding=(0, dp(11), 0, dp(11)))
        field.add_widget(ti)

        buttons = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(12))
        cancel = TextButton(text="Mégse")
        ok = TextButton(text="Hozzáadás", tint=(0.3, 0.8, 1, 0.38),
                        border=(0.75, 0.95, 1, 0.85))
        buttons.add_widget(cancel)
        buttons.add_widget(ok)

        box.add_widget(field)
        box.add_widget(buttons)
        view.add_widget(box)

        def add(*a):
            text = ti.text.strip()
            if text:
                self.add_item(text)
            view.dismiss()

        ti.bind(on_text_validate=add)
        ok.bind(on_release=add)
        cancel.bind(on_release=lambda *a: view.dismiss())
        view.open()
        Clock.schedule_once(lambda dt: setattr(ti, "focus", True), 0.25)

    def add_item(self, text):
        row = ItemRow(text, self)
        row.opacity = 0
        self.rows.append(row)
        self.grid.add_widget(row)  # a lista végére kerül
        Animation(opacity=1, duration=0.3).start(row)
        self.save_items()

        def scroll_down(dt):
            try:
                self.scroll.scroll_to(row)
            except Exception:
                pass
        Clock.schedule_once(scroll_down, 0.15)


if __name__ == "__main__":
    ChecklistApp().run()
