"""
Matugen Color Palette Visualizer
Usage: uv run matugen_visualizer.py [image_path]
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pyperclip
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Label, Select, Static
from textual_fspicker import FileOpen, Filters


def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


DEFAULT_IMAGE_PATH = "~/Pictures/"

SCHEMES = [
    (s, s)
    for s in (
        "scheme-tonal-spot",
        "scheme-fruit-salad",
        "scheme-monochrome",
        "scheme-rainbow",
        "scheme-expressive",
        "scheme-fidelity",
        "scheme-content",
        "scheme-neutral",
    )
]

COLOR_GROUPS = {
    "Primary": ["primary", "on_primary", "primary_container", "on_primary_container"],
    "Secondary": [
        "secondary",
        "on_secondary",
        "secondary_container",
        "on_secondary_container",
    ],
    "Tertiary": [
        "tertiary",
        "on_tertiary",
        "tertiary_container",
        "on_tertiary_container",
    ],
    "Error": ["error", "on_error", "error_container", "on_error_container"],
    "Surface": [
        "surface",
        "on_surface",
        "surface_variant",
        "on_surface_variant",
        "surface_dim",
        "surface_bright",
        "surface_container",
        "surface_container_low",
        "surface_container_high",
        "surface_container_highest",
    ],
    "Background": ["background", "on_background"],
    "Outline": ["outline", "outline_variant"],
    "Misc": [
        "shadow",
        "scrim",
        "inverse_surface",
        "inverse_on_surface",
        "inverse_primary",
    ],
}


def run_matugen(
    image_path: str, scheme: str, index: int, dry_run: bool = False
) -> dict:
    cmd = [
        "matugen",
        "image",
        image_path,
        "-t",
        scheme,
        "--source-color-index",
        str(index),
        "--json",
        "hex",
    ]
    if dry_run:
        cmd.append("--dry-run")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"error": strip_ansi(r.stderr.strip()) or "matugen exited non-zero"}
        start = r.stdout.find("{")
        end = r.stdout.rfind("}") + 1
        return json.loads(r.stdout[start:end])
    except FileNotFoundError:
        return {"error": "matugen not found — is it on your PATH?"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse failed: {e}"}
    except subprocess.TimeoutExpired:
        return {"error": "matugen timed out after 30s"}
    except Exception as e:
        return {"error": str(e)}


def extract_colors(data: dict, mode: str = "dark") -> dict:
    colors: dict[str, str] = {}
    palette = data.get("colors", {})
    for key, val in palette.items():
        if isinstance(val, dict):
            inner = val.get(mode) or val.get("default") or {}
            hex_val = inner.get("color", "") if isinstance(inner, dict) else inner
        else:
            hex_val = val
        if isinstance(hex_val, str) and re.match(r"^#[0-9a-fA-F]{6}$", hex_val):
            colors[key] = hex_val
    return colors


def luminance(h: str) -> float:
    h = h.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def fg_for(bg: str) -> str:
    return "#ffffff" if luminance(bg) < 0.179 else "#000000"


class BrowseButton(Static):
    """Opens file picker."""

    def on_click(self) -> None:
        self.app.action_browse()


class GenerateButton(Static):
    """Clickable generate button."""

    def __init__(self, label: str = "▶  Generate", id: str | None = None) -> None:
        self._label = label
        super().__init__(label, id=id)

    def on_click(self) -> None:
        if self.id == "preview-btn":
            self.app.action_preview()
        else:
            self.app.action_generate()


class Swatch(Static):
    """A single color swatch — click to copy hex."""

    def __init__(self, role: str, hex_val: str) -> None:
        self.role = role
        self.hex_val = hex_val
        label = f"{role.replace('_', ' ')}\n{hex_val.upper()}"
        super().__init__(label)
        self.styles.background = hex_val
        self.styles.color = fg_for(hex_val)

    def on_click(self) -> None:
        try:
            pyperclip.copy(self.hex_val)
            self.app.notify(f"Copied {self.hex_val}", timeout=1.5)
        except Exception:
            self.app.notify(f"{self.hex_val}", title="Hex value", timeout=2)


class SwatchGroup(Vertical):
    """A labeled row of swatches for one color group."""

    def __init__(self, name: str, colors: dict[str, str]) -> None:
        super().__init__()
        self.group_name = name
        self.color_map = colors

    def compose(self) -> ComposeResult:
        yield Label(self.group_name.upper())
        with Horizontal():
            for role, hex_val in self.color_map.items():
                yield Swatch(role, hex_val)


class MatugenApp(App):
    CSS_PATH = "visualiser.tcss"

    TITLE = "Matugen Colour Visualiser"

    BINDINGS = [
        Binding("ctrl+b", "browse", "Browse", show=True),
        Binding("ctrl+g", "generate", "Generate", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    status_text: reactive[str] = reactive(
        "Select an image (CTRL+B), then press Ctrl+G or Enter to generate."
    )

    def __init__(self, initial_path: str = "") -> None:
        super().__init__()
        self.initial_path = initial_path
        self.current_path = initial_path
        self.starting_up = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="controls"):
            with Horizontal():
                yield Label("Image")
                yield Input(
                    placeholder="~/Pictures/image.png",
                    value=self.current_path,
                    id="path-input",
                )
                yield BrowseButton("󰏖  Browse", id="browse-btn")
                yield Label("Scheme")
                yield Select(
                    SCHEMES,
                    value="scheme-tonal-spot",
                    id="scheme-select",
                    allow_blank=False,
                )
                yield Label("Idx")
                yield Input(value="0", id="idx-input")
                yield GenerateButton("▶  Preview", id="preview-btn")
                yield GenerateButton("▶  Apply", id="generate-btn")
        yield Label("", id="status")
        yield ScrollableContainer(id="swatch-area")
        yield Footer()

    def action_browse(self) -> None:
        self.push_screen(
            FileOpen(
                self.current_path,
                filters=Filters(
                    (
                        "Images",
                        lambda p: (
                            p.suffix.lower()
                            in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
                        ),
                    ),
                    ("All files", lambda p: True),
                ),
            ),
            callback=self._on_file_selected,
        )

    def _on_file_selected(self, path) -> None:
        if path is not None:
            self.query_one("#path-input", Input).value = str(path)
            self.current_path = str(path.parent)
            print(self.current_path)
            self.action_preview()

    def watch_status_text(self, val: str) -> None:
        self.query_one("#status", Label).update(val)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_generate()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "scheme-select":
            self.action_preview()

    def action_generate(self) -> None:
        path = self.query_one("#path-input", Input).value.strip()
        if not path:
            self.status_text = "⚠  Please enter an image path."
            return
        expanded = str(Path(path).expanduser())
        if not Path(expanded).exists():
            self.status_text = f"⚠  File not found: {path}"
            return

        scheme_val = self.query_one("#scheme-select", Select).value
        if scheme_val is Select.BLANK:
            self.status_text = "⚠  Please select a scheme."
            return

        idx_raw = self.query_one("#idx-input", Input).value.strip()
        try:
            idx = int(idx_raw)
        except ValueError:
            self.status_text = "⚠  Index must be an integer."
            return

        self.status_text = "⏳  Running matugen..."
        self._clear_swatches()
        self._run_matugen(expanded, scheme_val, idx)

    def action_preview(self) -> None:
        if self.starting_up:
            self.starting_up = False
            return

        path = self.query_one("#path-input", Input).value.strip()
        if not path:
            self.status_text = "⚠  Please enter an image path."
            return
        expanded = str(Path(path).expanduser())
        if not Path(expanded).exists():
            self.status_text = f"⚠  File not found: {path}"
            return

        scheme_val = self.query_one("#scheme-select", Select).value
        if scheme_val is Select.BLANK:
            self.status_text = "⚠  Please select a scheme."
            return

        idx_raw = self.query_one("#idx-input", Input).value.strip()
        try:
            idx = int(idx_raw)
        except ValueError:
            self.status_text = "⚠  Index must be an integer."
            return

        self.status_text = "⏳  Running preview..."
        self._clear_swatches()
        self._run_matugen(expanded, scheme_val, idx, dry_run=True)

    @work(thread=True)
    def _run_matugen(
        self, path: str, scheme: str, idx: int, dry_run: bool = False
    ) -> None:
        data = run_matugen(path, scheme, idx, dry_run)
        self.call_from_thread(self._on_result, data, scheme)

    def _on_result(self, data: dict, scheme: str) -> None:
        if "error" in data:
            err = strip_ansi(data["error"])
            self.status_text = f"✖  {err}"
            area = self.query_one("#swatch-area", ScrollableContainer)
            area.mount(Label(f"[red]{err}[/red]"))
            return

        colors = extract_colors(data, "dark")
        if not colors:
            self.status_text = (
                "✖  No colors found. Does your matugen support --json hex?"
            )
            return

        self.status_text = f"✔  {len(colors)} roles  ·  {scheme}  ·  dark  —  click any swatch to copy hex"
        self._render_swatches(colors, scheme)

    def _clear_swatches(self) -> None:
        area = self.query_one("#swatch-area", ScrollableContainer)
        area.remove_children()

    def _render_swatches(self, colors: dict[str, str], scheme: str) -> None:
        area = self.query_one("#swatch-area", ScrollableContainer)
        area.mount(
            Label(
                f"  {scheme.upper()}  ·  DARK  ·  {len(colors)} roles",
                classes="palette-header",
            )
        )
        rendered: set[str] = set()
        for group_name, keys in COLOR_GROUPS.items():
            group = {k: colors[k] for k in keys if k in colors}
            if group:
                rendered.update(group)
                area.mount(SwatchGroup(group_name, group))
        leftover = {k: v for k, v in colors.items() if k not in rendered}
        if leftover:
            area.mount(SwatchGroup("Other", leftover))


if __name__ == "__main__":
    initial = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMAGE_PATH
    if "--serve" in sys.argv:
        MatugenApp(initial_path=initial).run()
    else:
        MatugenApp(initial_path=initial).run()
