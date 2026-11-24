# Commandes pip à exécuter : pip install Pillow>=10.3.0

import argparse
import os
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFilter


class AppIconGenerator:
    """Génère les icônes SVG, PNG et ICO multi-résolutions d'AnonVault."""

    ICO_SIZES: List[Tuple[int, int]] = [
        (16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)
    ]

    SVG_TEMPLATE: str = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n'
        '  <defs>\n'
        '    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">\n'
        '      <stop offset="0%" stop-color="#1e293b"/>\n'
        '      <stop offset="100%" stop-color="#0f172a"/>\n'
        '    </linearGradient>\n'
        '    <linearGradient id="sh" x1="0" y1="0" x2="0" y2="1">\n'
        '      <stop offset="0%" stop-color="#3b82f6"/>\n'
        '      <stop offset="100%" stop-color="#1d4ed8"/>\n'
        '    </linearGradient>\n'
        '  </defs>\n'
        '  <rect x="30" y="30" width="452" height="452" rx="112" fill="url(#bg)" '
        'stroke="#2563eb" stroke-opacity="0.6" stroke-width="4"/>\n'
        '  <path d="M205 112 L318 158 L318 256 C318 330 205 380 205 380 '
        'C205 380 92 330 92 256 L92 158 Z" fill="url(#sh)" stroke="#60a5fa" stroke-width="5"/>\n'
        '  <rect x="230" y="138" width="170" height="250" rx="20" fill="#f8fafc" '
        'stroke="#cbd5e1" stroke-width="3"/>\n'
        '  <rect x="252" y="182" width="118" height="12" rx="6" fill="#1e293b"/>\n'
        '  <rect x="252" y="212" width="90" height="12" rx="6" fill="#1e293b"/>\n'
        '  <rect x="252" y="242" width="130" height="12" rx="6" fill="#1e293b"/>\n'
        '  <rect x="252" y="272" width="104" height="12" rx="6" fill="#1e293b"/>\n'
        '  <path d="M298 326 V314 A17 17 0 0 1 332 314 V326" fill="none" '
        'stroke="#059669" stroke-width="7" stroke-linecap="round"/>\n'
        '  <rect x="290" y="324" width="50" height="40" rx="9" fill="#059669"/>\n'
        '  <circle cx="315" cy="341" r="4" fill="#ffffff"/>\n'
        '  <rect x="313" y="343" width="4" height="9" rx="2" fill="#ffffff"/>\n'
        '</svg>\n'
    )

    @staticmethod
    def render_vector_icon(size: int = 512) -> Image.Image:
        """Dessine l'icône haute définition supersamplée 4x avec fond transparent."""
        scale: int = 4
        w: int = size * scale
        img: Image.Image = Image.new("RGBA", (w, w), (0, 0, 0, 0))
        draw: ImageDraw.ImageDraw = ImageDraw.Draw(img)
        pad, rad = int(w * 0.06), int(w * 0.22)
        draw.rounded_rectangle([pad, pad, w - pad, w - pad], radius=rad, fill=(15, 23, 42, 255))
        draw.rounded_rectangle([pad, pad, w - pad, w - pad], radius=rad, outline=(37, 99, 235, 170), width=max(4, w // 128))
        sx, sy, sw, sh = int(w * 0.40), int(w * 0.48), int(w * 0.22), int(w * 0.26)
        shield_pts: List[Tuple[int, int]] = [(sx, sy - sh), (sx + sw, sy - int(sh * 0.65)), (sx + sw, sy + int(sh * 0.10)), (sx, sy + sh), (sx - sw, sy + int(sh * 0.10)), (sx - sw, sy - int(sh * 0.65))]
        draw.polygon(shield_pts, fill=(37, 99, 235, 255), outline=(96, 165, 250, 255))
        dx1, dy1, dx2, dy2 = int(w * 0.45), int(w * 0.27), int(w * 0.78), int(w * 0.76)
        draw.rounded_rectangle([dx1, dy1, dx2, dy2], radius=int(w * 0.04), fill=(248, 250, 252, 255), outline=(203, 213, 225, 255), width=max(4, w // 160))
        bar_h: int = max(8, int(w * 0.024))
        for idx, ratio in enumerate((0.72, 0.55, 0.80, 0.64)):
            by: int = dy1 + int((dy2 - dy1) * (0.18 + idx * 0.12))
            draw.rounded_rectangle([dx1 + int(w * 0.04), by, dx1 + int((dx2 - dx1) * ratio), by + bar_h], radius=bar_h // 2, fill=(30, 41, 59, 255))
        lx, ly, lw, lh = (dx1 + dx2) // 2, dy1 + int((dy2 - dy1) * 0.76), int(w * 0.045), int(w * 0.038)
        draw.arc([lx - int(lw * 0.65), ly - int(lh * 1.45), lx + int(lw * 0.65), ly + int(lh * 0.2)], start=180, end=0, fill=(5, 150, 105, 255), width=max(6, w // 90))
        draw.rounded_rectangle([lx - lw, ly - int(lh * 0.4), lx + lw, ly + lh], radius=max(6, w // 80), fill=(5, 150, 105, 255))
        return img.resize((size, size), Image.Resampling.LANCZOS)
    @staticmethod
    def _strip_outer_white_bg(rgba_img: Image.Image) -> Image.Image:
        """Supprime tout fond clair extérieur et applique un masque arrondi net."""
        w, h = rgba_img.size
        px = rgba_img.load()
        visited = bytearray(w * h)
        stack: List[Tuple[int, int]] = []
        for x in range(w):
            stack.extend([(x, 0), (x, h - 1)])
        for y in range(h):
            stack.extend([(0, y), (w - 1, y)])
        while stack:
            cx, cy = stack.pop()
            if not (0 <= cx < w and 0 <= cy < h):
                continue
            idx: int = cy * w + cx
            if visited[idx]:
                continue
            visited[idx] = 1
            r, g, b, a = px[cx, cy]  # type: ignore[misc]
            lum: float = (r + g + b) / 3.0
            sat: int = max(r, g, b) - min(r, g, b)
            if a == 0 or (lum >= 135.0 and sat < 45):
                px[cx, cy] = (0, 0, 0, 0)  # type: ignore[index]
                stack.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])

        alpha_ch = rgba_img.getchannel("A").filter(ImageFilter.MinFilter(5))
        rgba_img.putalpha(alpha_ch)
        return rgba_img

    @classmethod
    def load_and_crop_source(cls, source_path: str, size: int = 512) -> Image.Image:
        """Détoure le fond clair extérieur, recadre sans halo et centre en carré."""
        raw: Image.Image = cls._strip_outer_white_bg(Image.open(source_path).convert("RGBA"))
        strict_mask = raw.getchannel("A").point(lambda v: 255 if v > 128 else 0)
        bbox = strict_mask.getbbox()
        if bbox:
            raw = raw.crop(bbox)
        side: int = max(raw.size)
        square: Image.Image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(raw, ((side - raw.width) // 2, (side - raw.height) // 2))
        return square.resize((size, size), Image.Resampling.LANCZOS)

    @classmethod
    def export_icons(
        cls, output_dir: str = "assets", base_name: str = "anonvault_icon", source_image: str = ""
    ) -> Tuple[str, str]:
        """Génère <base_name>.svg, <base_name>.png et <base_name>.ico haute netteté."""
        os.makedirs(output_dir, exist_ok=True)
        svg_path: str = os.path.abspath(os.path.join(output_dir, f"{base_name}.svg"))
        with open(svg_path, "w", encoding="utf-8") as f_svg:
            f_svg.write(cls.SVG_TEMPLATE)
        icon_img: Image.Image = (
            cls.load_and_crop_source(source_image)
            if source_image and os.path.isfile(source_image)
            else cls.render_vector_icon(size=512)
        )
        png_path: str = os.path.abspath(os.path.join(output_dir, f"{base_name}.png"))
        ico_path: str = os.path.abspath(os.path.join(output_dir, f"{base_name}.ico"))
        icon_img.save(png_path, format="PNG")
        icon_img.save(ico_path, format="ICO", sizes=cls.ICO_SIZES)
        return png_path, ico_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère l'icône SVG/PNG/ICO d'AnonVault.")
    parser.add_argument("--source", default="", help="Image source optionnelle.")
    parser.add_argument("--out-dir", default="assets", help="Dossier cible.")
    args = parser.parse_args()
    png_p, ico_p = AppIconGenerator.export_icons(output_dir=args.out_dir, source_image=args.source)
    print(f"[OK] Icônes générées :\n - PNG : {png_p}\n - ICO : {ico_p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
