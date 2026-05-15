"""OCR tool — reads screen text using Tesseract via pytesseract + mss.

Requires: brew install tesseract
Enabled via: ENABLE_OCR_TOOL=true in .env
"""

import logging

import mss
import pytesseract
from PIL import Image
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _capture_region(monitor_index: int, region: dict | None) -> Image.Image:
    with mss.mss() as sct:
        if region:
            shot = sct.grab(region)
        else:
            monitors = sct.monitors
            if monitor_index < 0 or monitor_index >= len(monitors):
                raise ValueError(
                    f"monitor_index {monitor_index} out of range "
                    f"(0 = all monitors, 1..{len(monitors)-1} = individual)"
                )
            shot = sct.grab(monitors[monitor_index])
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


@tool
def ocr_read_screen(
    monitor_index: int = 1,
    left: int = 0,
    top: int = 0,
    width: int = 0,
    height: int = 0,
    lang: str = "eng",
) -> str:
    """Read text from the screen (or a rectangular region) using Tesseract OCR.

    Use this when the Accessibility API cannot read the content (e.g. canvas-based
    apps, games, PDFs rendered as images, terminal emulators, or web content).

    Args:
        monitor_index: Which monitor to capture (1 = primary, 2 = secondary, …).
                       0 captures all monitors combined. Default 1.
        left:   X offset of the region to capture (pixels). Ignored if width=0.
        top:    Y offset of the region to capture (pixels). Ignored if height=0.
        width:  Width of the region in pixels. 0 = full monitor width.
        height: Height of the region in pixels. 0 = full monitor height.
        lang:   Tesseract language code (default "eng"). Use "eng+fra" for multiple.

    Returns the extracted text, or an error message if Tesseract is not installed.
    """
    try:
        region = {"left": left, "top": top, "width": width, "height": height} if width and height else None
        image = _capture_region(monitor_index, region)
    except Exception as e:
        return f"[Error] Screen capture failed: {e}"

    try:
        text = pytesseract.image_to_string(image, lang=lang).strip()
    except pytesseract.TesseractNotFoundError:
        return (
            "[Error] Tesseract is not installed. Install it with:\n"
            "  brew install tesseract\n"
            "Then set ENABLE_OCR_TOOL=true in your .env and restart the agent."
        )
    except Exception as e:
        return f"[Error] OCR failed: {e}"

    if not text:
        return "(No text detected in the captured region)"

    location = f"monitor {monitor_index}" if not region else f"region ({left},{top}) {width}x{height}"
    return f"=== OCR output ({location}) ===\n{text}"
