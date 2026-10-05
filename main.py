# -*- coding: utf-8 -*-
"""
PixelDraw para Android (Kivy)
Port do app Tkinter original: mesma lógica (malha, paleta, pincel, salvar PNG),
agora com interface de toque. Funciona em Android 32 e 64 bits e também no PC
(basta rodar:  python main.py).
"""

import os
import struct
import zlib
from datetime import datetime

from kivy.config import Config

# No PC, evita os "pontos vermelhos" do clique direito (multitouch simulado)
Config.set("input", "mouse", "mouse,disable_multitouch")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import NoTransition, Screen, ScreenManager
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex, platform

# --------------------------------------------------------------------------
# Configurações (iguais às do app original)
# --------------------------------------------------------------------------
GRID_SIZES = [8, 16, 24, 32, 64]
BG = "#1e1f22"
FG = "#e6e6e6"
ACCENT = "#0a84ff"
BTN = "#3a3b3f"
EXPORT_SCALE = 16  # o PNG salvo é ampliado 16x (nearest), como no original

PALETTE = [
    "#FF0000", "#FF00FF", "#E3BB97", "#FFA500",
    "#FFFF00", "#00FF00", "#006400", "#ADD8E6",
    "#A020F0", "#00008B", "#964B00", "#000000",
    "#FFFFFF", "#989A91", "#484D50", "#FDE7B6",
]

HERE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(HERE, "icon.png")


# --------------------------------------------------------------------------
# Funções puras (sem Kivy) - fáceis de testar
# --------------------------------------------------------------------------
def hex_to_rgba(h):
    """'#RRGGBB' -> (r, g, b, a). Qualquer coisa inválida vira transparente."""
    try:
        h = h.lstrip("#")
        if len(h) == 6:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255
    except Exception:
        pass
    return 0, 0, 0, 0


def contrast_color(h):
    """Preto ou branco, conforme o que for mais legível sobre a cor h."""
    r, g, b, _ = hex_to_rgba(h)
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#FFFFFF"


def line_cells(r0, c0, r1, c1):
    """Bresenham: células entre duas posições (evita 'buracos' em arrastes rápidos)."""
    cells = []
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    sr = 1 if r0 < r1 else -1
    sc = 1 if c0 < c1 else -1
    err = dc - dr
    while True:
        cells.append((r0, c0))
        if r0 == r1 and c0 == c1:
            break
        e2 = 2 * err
        if e2 > -dr:
            err -= dr
            c0 += sc
        if e2 < dc:
            err += dc
            r0 += sr
    return cells


def encode_png(rows, scale):
    """
    Gera um PNG RGBA a partir de uma matriz de tuplas (r, g, b, a), ampliada
    'scale' vezes sem suavização. Implementação própria (zlib + struct) para
    não depender do Pillow no Android - menos coisa para compilar nas 2 arquiteturas.
    """
    n = len(rows)
    side = n * scale
    raw = bytearray()
    for row in rows:
        line = bytearray()
        for px in row:
            line += bytes(px) * scale
        raw += (b"\x00" + bytes(line)) * scale  # filtro 0 + linha repetida

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", side, side, 8, 6, 0, 0, 0)  # 8 bits, RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


# --------------------------------------------------------------------------
# Salvar a imagem
# --------------------------------------------------------------------------
def save_png(data, name):
    """Salva o PNG e devolve um texto dizendo onde ficou."""
    if platform == "android":
        return _save_android(data, name)
    folder = os.path.join(os.path.expanduser("~"), "Pictures", "PixelDraw")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def _save_android(data, name):
    from jnius import autoclass

    sdk = autoclass("android.os.Build$VERSION").SDK_INT
    activity = autoclass("org.kivy.android.PythonActivity").mActivity

    if sdk >= 29:
        # Android 10+: MediaStore (não precisa de permissão; aparece na Galeria)
        tmp = os.path.join(App.get_running_app().user_data_dir, "_export.png")
        with open(tmp, "wb") as f:
            f.write(data)
        try:
            ContentValues = autoclass("android.content.ContentValues")
            Media = autoclass("android.provider.MediaStore$Images$Media")
            Integer = autoclass("java.lang.Integer")
            BitmapFactory = autoclass("android.graphics.BitmapFactory")
            CompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")

            resolver = activity.getContentResolver()
            values = ContentValues()
            values.put("_display_name", name)
            values.put("mime_type", "image/png")
            values.put("relative_path", "Pictures/PixelDraw")
            values.put("is_pending", Integer(1))
            uri = resolver.insert(Media.EXTERNAL_CONTENT_URI, values)
            if uri is None:
                raise IOError("o Android recusou criar o arquivo")

            bitmap = BitmapFactory.decodeFile(tmp)
            stream = resolver.openOutputStream(uri)
            try:
                bitmap.compress(CompressFormat.PNG, 100, stream)
            finally:
                stream.close()
            bitmap.recycle()

            values.clear()
            values.put("is_pending", Integer(0))
            resolver.update(uri, values, None, None)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        return "Imagens/PixelDraw"

    # Android 9 ou inferior: grava direto em Pictures (precisa da permissão)
    Environment = autoclass("android.os.Environment")
    pictures = Environment.getExternalStoragePublicDirectory(
        Environment.DIRECTORY_PICTURES
    ).getAbsolutePath()
    folder = os.path.join(pictures, "PixelDraw")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "wb") as f:
        f.write(data)
    autoclass("android.media.MediaScannerConnection").scanFile(
        activity, [path], ["image/png"], None
    )
    return path


# --------------------------------------------------------------------------
# Widgets
# --------------------------------------------------------------------------
def make_button(text, bg=BTN, **kw):
    return Button(
        text=text,
        background_normal="",
        background_down="",
        background_color=get_color_from_hex(bg),
        color=get_color_from_hex(contrast_color(bg)),
        font_size="16sp",
        **kw
    )


class Swatch(ButtonBehavior, Widget):
    """Quadradinho de cor (paleta e prévia do pincel)."""

    hex_color = StringProperty("#FFFFFF")
    selected = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(
            pos=self._draw, size=self._draw,
            hex_color=self._draw, selected=self._draw,
        )
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            if self.selected:
                Color(*get_color_from_hex(ACCENT))
                inset = dp(4)
            else:
                Color(0.45, 0.45, 0.45, 1)
                inset = dp(1)
            Rectangle(pos=self.pos, size=self.size)
            Color(*get_color_from_hex(self.hex_color))
            Rectangle(
                pos=(self.x + inset, self.y + inset),
                size=(max(0, self.width - 2 * inset), max(0, self.height - 2 * inset)),
            )


class PixelCanvas(Widget):
    """A malha de pixels. Usa uma textura NxN (rápido até em 64x64)."""

    def __init__(self, n, color_getter, **kw):
        super().__init__(**kw)
        self.n = n
        self.color_getter = color_getter
        # Igual ao original: a malha começa toda branca
        self.grid = [["#FFFFFF"] * n for _ in range(n)]
        self.buf = bytearray(b"\xff" * (n * n * 4))
        self.cell = 0
        self.side = 0
        self.x0 = self.y0 = 0
        self._last = None

        self.texture = Texture.create(size=(n, n), colorfmt="rgba")
        self.texture.mag_filter = "nearest"
        self.texture.min_filter = "nearest"
        self.texture.flip_vertical()  # linha 0 do buffer = topo da imagem
        self._upload()

        self.bind(pos=self._redraw, size=self._redraw)

    # ---- desenho --------------------------------------------------------
    def _upload(self):
        self.texture.blit_buffer(bytes(self.buf), colorfmt="rgba", bufferfmt="ubyte")
        self.canvas.ask_update()

    def _redraw(self, *_):
        side = min(self.width, self.height)
        self.side = side
        self.cell = side / self.n if self.n else 0
        self.x0 = self.x + (self.width - side) / 2
        self.y0 = self.y + (self.height - side) / 2

        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=self.texture, pos=(self.x0, self.y0), size=(side, side))
            Color(0.18, 0.18, 0.18, 1 if self.n <= 24 else 0.5)
            for i in range(self.n + 1):
                off = i * self.cell
                Line(points=[self.x0 + off, self.y0, self.x0 + off, self.y0 + side], width=1)
                Line(points=[self.x0, self.y0 + off, self.x0 + side, self.y0 + off], width=1)

    # ---- pintura --------------------------------------------------------
    def _cell_at(self, x, y):
        if self.cell <= 0:
            return None
        c = int((x - self.x0) // self.cell)
        r = int((self.y0 + self.side - y) // self.cell)
        if 0 <= r < self.n and 0 <= c < self.n:
            return r, c
        return None

    def _paint(self, cells):
        color = self.color_getter()
        rgba = bytes(hex_to_rgba(color))
        changed = False
        for r, c in cells:
            if self.grid[r][c] != color:
                self.grid[r][c] = color
                i = (r * self.n + c) * 4
                self.buf[i:i + 4] = rgba
                changed = True
        if changed:
            self._upload()

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        touch.grab(self)
        cell = self._cell_at(*touch.pos)
        self._last = cell
        if cell:
            self._paint([cell])
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False
        cell = self._cell_at(*touch.pos)
        if cell is None:
            self._last = None
        else:
            if self._last:
                self._paint(line_cells(*self._last, *cell))
            else:
                self._paint([cell])
            self._last = cell
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._last = None
            return True
        return False

    # ---- exportação -----------------------------------------------------
    def to_png(self):
        rows = [[hex_to_rgba(c) for c in row] for row in self.grid]
        return encode_png(rows, EXPORT_SCALE)


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
class PixelDrawApp(App):
    title = "PixelDraw"

    def build(self):
        Window.clearcolor = get_color_from_hex(BG)
        Window.softinput_mode = "below_target"

        self.brush_color = "#FFFFFF"
        self.selected_color = self.brush_color

        self.sm = ScreenManager(transition=NoTransition())
        self.sm.add_widget(self._build_start())
        Window.bind(on_keyboard=self._on_keyboard)
        return self.sm

    def on_start(self):
        # Android 9 ou inferior precisa pedir permissão para gravar na Galeria
        if platform == "android":
            try:
                from jnius import autoclass
                if autoclass("android.os.Build$VERSION").SDK_INT < 29:
                    from android.permissions import Permission, request_permissions
                    request_permissions([Permission.WRITE_EXTERNAL_STORAGE])
            except Exception as e:
                print("PixelDraw: não foi possível pedir permissão:", e)

    # ---- tela inicial ---------------------------------------------------
    def _build_start(self):
        scr = Screen(name="start")
        box = BoxLayout(orientation="vertical", padding=dp(32), spacing=dp(14))
        box.add_widget(Widget())

        if os.path.exists(ICON):
            logo = Image(source=ICON, size_hint_y=None, height=dp(120), fit_mode="contain")
            if logo.texture:
                logo.texture.mag_filter = "nearest"
            box.add_widget(logo)

        fg = get_color_from_hex(FG)
        box.add_widget(Label(text="PixelDraw", font_size="32sp", bold=True,
                             color=fg, size_hint_y=None, height=dp(52)))
        box.add_widget(Label(text="Escolha o tamanho da malha:", color=fg,
                             size_hint_y=None, height=dp(32)))

        self.spinner = Spinner(
            text=f"{GRID_SIZES[0]}x{GRID_SIZES[0]}",
            values=[f"{s}x{s}" for s in GRID_SIZES],
            size_hint_y=None, height=dp(52), font_size="18sp",
            background_normal="", background_down="",
            background_color=get_color_from_hex(BTN), color=fg,
        )
        box.add_widget(self.spinner)

        start_btn = make_button("Começar arte!", bg=ACCENT, size_hint_y=None, height=dp(56))
        start_btn.bind(on_release=self._start)
        box.add_widget(start_btn)

        box.add_widget(Widget())
        scr.add_widget(box)
        return scr

    def _start(self, *_):
        n = int(self.spinner.text.split("x")[0])
        self._open_drawing(n)

    # ---- tela de desenho ------------------------------------------------
    def _open_drawing(self, n):
        if self.sm.has_screen("draw"):
            self.sm.remove_widget(self.sm.get_screen("draw"))

        scr = Screen(name="draw")
        root = BoxLayout(orientation="vertical")

        top = BoxLayout(size_hint_y=None, height=dp(64), padding=dp(8), spacing=dp(8))
        self.color_btn = make_button("Mudar cor", bg=self.brush_color, size_hint_x=0.4)
        self.color_btn.bind(on_release=self.open_color_picker)
        save_btn = make_button("Salvar", size_hint_x=0.3)
        save_btn.bind(on_release=self.open_save_dialog)
        top.add_widget(self.color_btn)
        top.add_widget(save_btn)
        top.add_widget(Label(text="Pincel:", color=get_color_from_hex(FG),
                             size_hint_x=None, width=dp(56)))
        self.preview = Swatch(hex_color=self.brush_color, size_hint_x=None, width=dp(36))
        top.add_widget(self.preview)

        self.pixel = PixelCanvas(n, lambda: self.selected_color)
        area = BoxLayout(padding=dp(8))
        area.add_widget(self.pixel)

        root.add_widget(top)
        root.add_widget(area)
        scr.add_widget(root)
        self.sm.add_widget(scr)
        self.sm.current = "draw"

    # ---- seletor de cor -------------------------------------------------
    def open_color_picker(self, *_):
        chosen = {"c": self.selected_color}
        swatches = []

        grid = GridLayout(cols=4, spacing=dp(10), padding=dp(4))

        def choose(sw):
            chosen["c"] = sw.hex_color
            for s in swatches:
                s.selected = s is sw

        for col in PALETTE:
            sw = Swatch(hex_color=col, selected=(col.lower() == self.selected_color.lower()))
            sw.bind(on_release=choose)
            swatches.append(sw)
            grid.add_widget(sw)

        ok = make_button("Ok", bg=ACCENT, size_hint_y=None, height=dp(48))
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        content.add_widget(grid)
        content.add_widget(ok)

        popup = self._popup("Escolher cor", content, size_hint=(0.9, 0.6))

        def confirm(*_):
            self.selected_color = self.brush_color = chosen["c"]
            self.color_btn.background_color = get_color_from_hex(self.selected_color)
            self.color_btn.color = get_color_from_hex(contrast_color(self.selected_color))
            self.preview.hex_color = self.selected_color
            popup.dismiss()

        ok.bind(on_release=confirm)
        popup.open()

    # ---- salvar ---------------------------------------------------------
    def open_save_dialog(self, *_):
        default = datetime.now().strftime("pixeldraw_%Y%m%d_%H%M%S")
        ti = TextInput(text=default, multiline=False, write_tab=False,
                       size_hint_y=None, height=dp(44), font_size="16sp")

        cancel = make_button("Cancelar")
        save = make_button("Salvar", bg=ACCENT)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        row.add_widget(cancel)
        row.add_widget(save)

        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(12))
        content.add_widget(Label(text="Nome do arquivo:", color=get_color_from_hex(FG),
                                 size_hint_y=None, height=dp(28)))
        content.add_widget(ti)
        content.add_widget(row)

        popup = self._popup("Salvar como", content, size_hint=(0.9, None), height=dp(230))
        cancel.bind(on_release=popup.dismiss)

        def do_save(*_):
            popup.dismiss()
            self._save(ti.text)

        save.bind(on_release=do_save)
        popup.open()
        Clock.schedule_once(lambda dt: setattr(ti, "focus", True), 0.2)

    def _save(self, name):
        name = "".join(ch for ch in name.strip() if ch not in '\\/:*?"<>|') or "pixeldraw"
        if not name.lower().endswith(".png"):
            name += ".png"
        try:
            where = save_png(self.pixel.to_png(), name)
            self.toast(f"Salvo em:\n{where}\n({name})")
        except Exception as e:
            self.toast(f"Erro ao salvar:\n{e}")

    # ---- utilidades de interface ----------------------------------------
    def _popup(self, title, content, **kw):
        return Popup(
            title=title, content=content,
            background="", background_color=get_color_from_hex("#2b2d31"),
            title_color=get_color_from_hex(FG),
            separator_color=get_color_from_hex(ACCENT),
            **kw
        )

    def toast(self, text):
        lbl = Label(text=text, halign="center", color=get_color_from_hex(FG))
        lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        p = self._popup("PixelDraw", lbl, size_hint=(0.85, 0.3))
        p.open()
        Clock.schedule_once(lambda dt: p.dismiss(), 3)

    def confirm_back(self):
        fg = get_color_from_hex(FG)
        lbl = Label(text="Voltar ao início?\nO desenho atual será perdido.",
                    halign="center", color=fg)
        no = make_button("Não")
        yes = make_button("Sim", bg="#d9534f")
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        row.add_widget(no)
        row.add_widget(yes)
        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(12))
        content.add_widget(lbl)
        content.add_widget(row)
        popup = self._popup("Atenção", content, size_hint=(0.85, 0.3))
        no.bind(on_release=popup.dismiss)

        def go(*_):
            popup.dismiss()
            self.sm.current = "start"

        yes.bind(on_release=go)
        popup.open()

    def _on_keyboard(self, window, key, *args):
        # 27 = botão Voltar do Android (ou Esc no PC)
        if key == 27:
            if any(isinstance(w, ModalView) for w in Window.children):
                return False  # deixa o popup aberto se fechar sozinho
            if self.sm.current == "draw":
                self.confirm_back()
                return True
        return False


if __name__ == "__main__":
    PixelDrawApp().run()
