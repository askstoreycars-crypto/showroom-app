"""
Showroom photo processing pipeline.

This is the exact recipe we settled on after a lot of iteration:
  1. Real AI segmentation (rembg / u2net) to cut the car out precisely.
  2. Hard-edge alpha cleanup so the cutout edge is crisp against white,
     instead of leaving a faint "halo" of the original background color
     around soft/anti-aliased edge pixels.
  3. A flat, pure white background (no gradients, no floor texture,
     no reflections) -- kept deliberately plain per final direction.
  4. One soft, light "contact" shadow under the car for grounding.
  5. NO color/contrast/saturation enhancement -- the car's colors are
     left exactly as shot.

If you want to reintroduce the grey studio floor, the floor reflection,
or the subtle "showroom room" cues (wall/floor seam, soft overhead
light streaks) we built along the way, look at the comments marked
OPTIONAL below -- those variations are kept simple to re-enable.
"""

from io import BytesIO
from PIL import Image, ImageFilter, ImageDraw
import numpy as np
from rembg import remove, new_session

# Loaded once per process and reused across requests -- this is the
# expensive part (loads the ~176MB u2net model into memory).
_session = None


def get_session():
    global _session
    if _session is None:
        _session = new_session("u2net")
    return _session


def _clean_alpha(alpha_img: Image.Image, low: int = 60, high: int = 150, feather: float = 1.0) -> Image.Image:
    """
    Push the alpha channel's soft/antialiased edge pixels toward fully
    opaque or fully transparent, instead of leaving a long, faintly
    tinted transition band. That transition band is what caused the
    grey "ghost outline" around the car when composited onto white --
    those semi-transparent edge pixels still carry a blend of the
    original background color.

    low/high define the input range that gets stretched to 0-255.
    Raise `low` if halos persist; lower it if the edge starts looking
    jagged/cut off (e.g. thin antenna, side mirrors).
    """
    a = np.asarray(alpha_img).astype(np.float32)
    a = np.clip((a - low) / max(1, (high - low)) * 255, 0, 255)
    out = Image.fromarray(a.astype("uint8"))
    if feather > 0:
        out = out.filter(ImageFilter.GaussianBlur(feather))
    return out


def cutout_car(img: Image.Image, max_dim: int = 2000) -> Image.Image:
    """Run segmentation and return a tightly-cropped RGBA cutout of the car."""
    img = img.convert("RGB")
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

    cutout = remove(img, session=get_session())
    r, g, b, a = cutout.split()
    a = _clean_alpha(a, low=60, high=150, feather=1.0)
    cutout = Image.merge("RGBA", (r, g, b, a))

    bbox = a.getbbox() or (0, 0, img.width, img.height)
    return cutout.crop(bbox)


def compose_showroom(
    car: Image.Image,
    out_w: int = 1600,
    out_h: int = 1200,
    margin: float = 0.08,
    shadow_strength: float = 1.0,
) -> Image.Image:
    """Place the cutout car onto a flat white background with one soft shadow."""
    canvas = Image.new("RGB", (out_w, out_h), (255, 255, 255)).convert("RGBA")

    avail_w = out_w * (1 - margin * 2)
    avail_h = out_h * (1 - margin * 2) * 0.86
    scale = min(avail_w / car.width, avail_h / car.height)
    new_w, new_h = int(car.width * scale), int(car.height * scale)
    car_resized = car.resize((new_w, new_h), Image.LANCZOS)

    dest_x = int((out_w - new_w) / 2)
    dest_y = int(out_h * (1 - margin) - new_h - out_h * 0.02)
    contact_y = dest_y + new_h

    if shadow_strength > 0:
        shadow_layer = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        shadow_w = int(new_w * 0.72)
        shadow_h = max(10, int(new_h * 0.045))
        alpha = int(70 * shadow_strength)
        sd.ellipse(
            [
                dest_x + new_w // 2 - shadow_w // 2,
                contact_y - shadow_h // 2,
                dest_x + new_w // 2 + shadow_w // 2,
                contact_y + shadow_h // 2,
            ],
            fill=(20, 20, 20, alpha),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_h * 0.9))
        canvas = Image.alpha_composite(canvas, shadow_layer)

    canvas.paste(car_resized, (dest_x, dest_y), car_resized)
    return canvas.convert("RGB")


def process_image(file_bytes: bytes, out_w: int = 1600, out_h: int = 1200) -> bytes:
    """Full pipeline: raw uploaded photo bytes in, finished JPEG bytes out."""
    img = Image.open(BytesIO(file_bytes))
    car = cutout_car(img)
    result = compose_showroom(car, out_w=out_w, out_h=out_h)

    buf = BytesIO()
    result.save(buf, format="JPEG", quality=95)
    return buf.getvalue()
