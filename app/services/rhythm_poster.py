"""Render a feed-sized shot rhythm print from the report's actual replay."""
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import reportlab
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_DIR = Path(reportlab.__file__).parent / "fonts"
INK = "#22251f"
PAPER = "#f5f1e6"
STYLES = {
    "one_motion": ("One", "#1d5548", "Lift and extension overlap."),
    "two_motion": ("Two", "#953e31", "The lift settles before extension."),
}


def _type(draw, xy, label, size, color=INK, font="VeraBd.ttf"):
    draw.text(xy, label, font=ImageFont.truetype(str(FONT_DIR / font), size),
              fill=color, anchor="lt")


def _basketball_mark(draw, x, y, size, ink):
    box = (x, y, x + size, y + size)
    draw.ellipse(box, outline=ink, width=3)
    draw.line((x, y + size//2, x + size, y + size//2), fill=ink, width=3)
    draw.line((x + size//2, y, x + size//2, y + size), fill=ink, width=3)
    radius = size / 2
    angles = np.linspace(0, np.pi, 32)
    for side in (-1, 1):
        seam = [(x + radius + side * radius * 0.62 * np.sin(t),
                 y + radius - radius * np.cos(t)) for t in angles]
        draw.line(seam, fill=ink, width=2)


def _frame_panel(poster, photo, box, monochrome=False, vertical_center=0.40):
    x, y, width, height = box
    shot = ImageOps.fit(photo, (width, height), centering=(0.5, vertical_center))
    gray = ImageOps.autocontrast(ImageOps.grayscale(shot), cutoff=0.5)
    toned = ImageOps.colorize(gray, "#202724", "#eee7d8")
    poster.paste(toned if monochrome else Image.blend(shot, toned, 0.20), (x, y))


def _trim_bars(photo):
    # Many social clips are portrait recordings embedded in a black landscape frame.
    bright = np.asarray(photo.convert("L")) > 13
    rows = np.flatnonzero(bright.mean(axis=1) > 0.05)
    cols = np.flatnonzero(bright.mean(axis=0) > 0.05)
    if len(rows) and len(cols):
        return photo.crop((cols[0], rows[0], cols[-1]+1, rows[-1]+1))
    return photo


def rhythm_poster(folder, result):
    rhythm = result.get("shot_rhythm") or {}
    if rhythm.get("style") not in STYLES or not rhythm.get("replay_url"):
        raise ValueError("No classified shot replay is available for this report.")
    word, accent, caption = STYLES[rhythm["style"]]
    origin = rhythm["replay_start"]
    midpoint = (rhythm["evidence_start"] + rhythm["evidence_end"]) / 2
    release = next((f["timestamp"] for f in result.get("key_frames", [])
                    if f["phase"] == "release_frame"), rhythm["evidence_end"])
    dip = next((f["timestamp"] for f in result.get("key_frames", [])
                if f["phase"] == "sync_frame_1"), origin)
    cap = cv2.VideoCapture(str(folder / "rhythm.mp4"))
    photos = []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not cap.isOpened() or fps <= 0 or count < 1:
            raise ValueError("The replay could not be read.")
        for moment in (max(dip, origin), midpoint, release):
            frame = min(count-1, max(0, round((moment-origin)*fps)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, pixels = cap.read()
            if not ok:
                raise ValueError("The replay frame is unavailable.")
            photos.append((_trim_bars(Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))),
                           origin+frame/fps))
    finally:
        cap.release()

    poster = Image.new("RGB", (1080, 1350), PAPER)
    draw = ImageDraw.Draw(poster)
    margin = 56
    _basketball_mark(draw, margin, 52, 34, accent)
    _type(draw, (102, 54), "FormRefine", 33, INK, "Vera.ttf")
    _type(draw, (776, 51), "Basketball / Film study", 28, INK, "_ei_____.pfb")
    draw.line((margin, 120, 1024, 120), fill=INK, width=2)

    _type(draw, (margin, 153), "Likely shot rhythm", 35, accent)
    _type(draw, (margin-2, 214), f"{word} motion.", 180, accent, "_ebi____.pfb")

    # One large evidence still, with the earlier and later poses on the film strip.
    hero_x, side_x, top = margin, 740, 394
    _frame_panel(poster, photos[1][0], (hero_x, top, 668, 587))
    for i, y, label in ((0, top, "Lift"), (2, 695, "Release")):
        _frame_panel(poster, photos[i][0], (side_x, y, 284, 232), monochrome=True,
                         vertical_center=0.12 if label == "Release" else 0.40)
        _type(draw, (side_x, y+247), label, 27)
        _type(draw, (914, y+247), f"{photos[i][1]:.2f} s", 27, INK, "Vera.ttf")

    # Keep the label in its own strip so it cannot cover a hand or the ball.
    draw.rectangle((hero_x, 981, 723, 1037), fill=accent)
    _type(draw, (hero_x+16, 996), "Rhythm frame", 27, PAPER)
    _type(draw, (598, 996), f"{photos[1][1]:.2f} s", 27, PAPER, "Vera.ttf")
    draw.line((side_x, 1036, 1024, 1036), fill=INK, width=2)

    _type(draw, (margin, 1072), caption, 43, INK)
    # Keep the invitation on one baseline and inside a centered square crop.
    invitation = "Check your shot at "
    body_font = ImageFont.truetype(str(FONT_DIR / "Vera.ttf"), 35)
    domain_font = ImageFont.truetype(str(FONT_DIR / "VeraBd.ttf"), 35)
    baseline = 1187
    draw.text((margin, baseline), invitation, font=body_font, fill="#454c42", anchor="ls")
    domain_x = margin + draw.textlength(invitation, font=body_font)
    draw.text((domain_x, baseline), "formrefine.ai", font=domain_font, fill=accent, anchor="ls")
    draw.line((margin, 1246, 1024, 1246), fill=INK, width=2)
    _type(draw, (margin, 1272), "Evidence in clip", 29, INK, "Vera.ttf")
    _type(draw, (792, 1272), f"{rhythm['evidence_start']:.2f} – {rhythm['evidence_end']:.2f} s",
          29, INK, "Vera.ttf")
    output = BytesIO()
    poster.save(output, format="PNG")
    return output.getvalue()
