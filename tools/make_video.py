"""商品写真からスライド動画（4:5・約8秒）を作る
使い方: python tools/make_video.py 出力名 "1行目|2行目" URL1 URL2 ...
出力: videos/出力名.mp4
"""
import io, os, subprocess, sys, tempfile, urllib.request
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1350
PER, FADE, FPS = 2.0, 0.4, 30
FONT = next((p for p in [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
] if os.path.exists(p)), None)


def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGB")


def frame(im):
    bg = im.copy()
    s = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1))
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (247, 244, 239)), 0.35)
    s = min(W / im.width, H / im.height)
    fg = im.resize((int(im.width * s), int(im.height * s)))
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    return bg


def title(im, text):
    lines = [t for t in text.split("|") if t.strip()]
    if not lines or not FONT:
        return im
    im = im.copy()
    d = ImageDraw.Draw(im, "RGBA")
    f = ImageFont.truetype(FONT, 66)
    lh = 92
    box_h = lh * len(lines) + 70
    y0 = H - box_h - 70
    d.rounded_rectangle((60, y0, W - 60, y0 + box_h), 28, fill=(255, 255, 255, 225))
    for i, t in enumerate(lines):
        w = d.textlength(t, font=f)
        d.text(((W - w) / 2, y0 + 35 + i * lh), t, font=f, fill=(58, 54, 49))
    return im


def main():
    name, text, urls = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs("videos", exist_ok=True)
    tmp = tempfile.mkdtemp()
    paths = []
    for i, u in enumerate(urls[:6]):
        try:
            im = frame(fetch(u))
        except Exception as e:
            print("skip", u, e)
            continue
        if not paths:
            im = title(im, text)
        p = os.path.join(tmp, f"{len(paths)}.jpg")
        im.save(p, quality=92)
        paths.append(p)
    if len(paths) < 2:
        sys.exit("画像が2枚以上必要です")
    n = len(paths)
    args = ["ffmpeg", "-y"]
    for p in paths:
        args += ["-loop", "1", "-t", str(PER), "-i", p]
    args += ["-f", "lavfi", "-t", str(n * PER - (n - 1) * FADE), "-i", "anullsrc=r=44100:cl=stereo"]
    fl = []
    frames = int(PER * FPS)
    for i in range(n):
        zin = "zoom+0.0010" if i % 2 == 0 else "if(eq(on,1),1.06,zoom-0.0010)"
        fl.append(f"[{i}:v]scale={W*2}:{H*2},zoompan=z='{zin}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p[v{i}]")
    last = "v0"
    for i in range(1, n):
        off = i * (PER - FADE)
        fl.append(f"[{last}][v{i}]xfade=transition=fade:duration={FADE}:offset={off:.2f}[x{i}]")
        last = f"x{i}"
    args += ["-filter_complex", ";".join(fl), "-map", f"[{last}]", "-map", f"{n}:a",
             "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", f"videos/{name}.mp4"]
    subprocess.run(args, check=True)
    print("OK", f"videos/{name}.mp4")


if __name__ == "__main__":
    main()
