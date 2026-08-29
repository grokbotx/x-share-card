#!/usr/bin/env python3
"""Public X / Truth Social post → dark bilingual share card + chat body.
Agent translates; this fetches public data and renders. Same layout for both;
only corner logo, verify mark, affiliation square, link color, and canonical URL change.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import math
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
FX = "https://api.fxtwitter.com"
BJ = timezone(timedelta(hours=8))
LOCAL = ZoneInfo("America/Los_Angeles")  # card timestamps: original local, not Beijing
ASSETS = Path(__file__).resolve().parent / "assets"
EPOCH = 1288834974657
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:x|twitter)\.com/([^/]+)/status/(\d+)", re.I)
MEDIA_URL_RE = re.compile(
    r"\s*https://(?:x|twitter)\.com/\S+/status/\d+/(?:photo|video|media)/\d+\S*",
    re.I,
)
STATUS_RE = re.compile(r"/([^/\s]+)/status/(\d{15,})")
# Truth Social: /@HANDLE/posts/ID | /@HANDLE/ID | /users/HANDLE/statuses/ID
TS_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?truthsocial\.com/"
    r"(?:@|users/)([^/]+)/(?:posts/|statuses/)?(\d{10,})",
    re.I,
)
TS_API = "https://truthsocial.com/api/v1"
TS_ARCHIVE = "https://trumpstruth.org"
TS_FEED = "https://trumpstruth.org/feed"
# Official TS marks from the live site (not invented). Empty if a download fails.
TS_LOGO_CANDIDATES = (
    "https://truthsocial.com/apple-touch-icon.png",
    "https://truthsocial.com/android-chrome-192x192.png",
    "https://truthsocial.com/icons/icon-192x192.png",
    "https://static-assets-1.truthsocial.com/tmtg:prime-ts-assets/site_uploads/files/000/000/035/original/Truth_Social_Profile_Icon.png",
    "https://truthsocial.com/favicon.png",
)
TS_VERIFY_CANDIDATES = (
    # Live webpack pack: official red verified mark (speech-check used on TS).
    "https://truthsocial.com/packs/media/images/icons/verified_1-bc97ae63a3e3b44c83ec2d617c764a3e.svg",
    "https://truthsocial.com/packs/media/images/icons/verified_1.svg",
)
# TS brand accent from help.truthsocial.com/branding (Truth Primary). X stays #1d9bf0.
LINK_COLOR = {"x": "#1d9bf0", "truthsocial": "#5448EE"}

BADGE_FILL = {
    "individual": "#1d9bf0",
    "organization": "#e2b340",
    "business": "#e2b340",
    "government": "#829aab",
}
ORG_TYPES = frozenset({"organization", "business"})
XLOGO = (
    '<svg class="xlogo" viewBox="0 0 24 24">'
    '<path fill="#e7e9ea" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231'
    '-5.401 6.231H2.744l7.73-8.835L1.254 2.25H8.08l4.253 5.622L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>'
    "</svg>"
)
PLAY = (
    '<div class="play"><svg width="28" height="28" viewBox="0 0 24 24">'
    '<path fill="#e7e9ea" d="M8 5v14l11-7z"/></svg></div>'
)
CSS = """
html,body { margin:0; padding:0; background:#000; }
body { display:flex; justify-content:center; align-items:flex-start; }
.card {
  width: 598px; background: #000; color: #e7e9ea;
  font-family: "TwitterChirp", "Noto Sans SC", "Noto Sans CJK SC", "PingFang SC",
    "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-feature-settings: "ss01" 1;
  -webkit-font-smoothing: antialiased;
  padding: 28px 28px 22px; box-sizing: border-box;
}
.top { display:flex; align-items:flex-start; gap: 12px; }
.avatar { width:48px; height:48px; border-radius:50%; object-fit:cover; flex-shrink:0; }
.who { flex:1; min-width:0; }
.name-row { display:flex; align-items:center; gap:4px; }
.name { font-weight:700; font-size:15px; line-height:20px; color:#e7e9ea; letter-spacing:0; }
.handle { color:#71767b; font-size:15px; line-height:20px; }
.orgmark { width:16px; height:16px; border-radius:4px; object-fit:cover; flex-shrink:0; display:block; border:1px solid #2f3336; box-sizing:border-box; background:#000; }
.xlogo { width:26px; height:26px; margin-left:auto; color:#e7e9ea; flex-shrink:0; object-fit:contain; }
img.xlogo { border-radius:6px; background:transparent; }
.vbadge { object-fit:contain; flex-shrink:0; display:block; }
.reposted { color:#71767b; font-size:13px; margin:10px 0 6px; }
.text { font-size:17px; line-height:24px; font-weight:400; margin:12px 0 10px; letter-spacing:0;
  white-space:pre-wrap; word-wrap:break-word; overflow-wrap:anywhere; }
.quote { border: 1px solid #2f3336; border-radius: 16px; padding: 12px; }
.qtop { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.qavatar { width:20px; height:20px; border-radius:50%; object-fit:cover; }
.qname { font-weight:700; font-size:13px; color:#e7e9ea; }
.qhandle { color:#71767b; font-size:13px; }
.qtext { font-size:15px; line-height:20px; margin-top:6px; color:#e7e9ea;
  white-space:pre-wrap; word-wrap:break-word; overflow-wrap:anywhere; }
.tlink { color:#1d9bf0; }
.zh-box {
  margin: 8px 0 12px; padding: 10px 12px;
  border: 1px dashed #71767b; border-radius: 10px;
  font-size:17px; line-height:24px; color:#e7e9ea;
  white-space:pre-wrap; word-wrap:break-word; overflow-wrap:anywhere;
}
.qzh-box { font-size:14px; line-height:20px; margin: 8px 0 8px; }
.zh-time { color:#71767b; font-size:13px; margin-top:6px; }
.meta { color:#71767b; font-size:15px; margin-top:16px; }
.dot { margin: 0 4px; }
.media { margin-top: 10px; display:flex; flex-direction:column; gap:6px; }
.media img { width:100%; height:auto; border-radius:12px; display:block; background:#16181c; }
.vidwrap { position:relative; width:100%; }
.vidwrap img { width:100%; height:auto; border-radius:12px; display:block; }
.play {
  position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
  width:68px; height:68px; border-radius:50%;
  background:rgba(0,0,0,0.55); border:3px solid #e7e9ea;
  display:flex; align-items:center; justify-content:center;
}
.play svg { margin-left:4px; }
"""


LATIN = "U+0000-024F,U+1E00-1EFF,U+2000-206F,U+20A0-20CF,U+2100-214F"
CJK = "U+2E80-2FFF,U+3000-303F,U+3040-30FF,U+3100-312F,U+3400-4DBF,U+4E00-9FFF,U+F900-FAFF,U+FF00-FFEF"


def font_face_css() -> str:
    bits = []
    for fname, weight in (("regular", 400), ("medium", 500), ("bold", 700), ("heavy", 800)):
        fp = ASSETS / f"chirp-{fname}.woff2"
        if not fp.exists():
            continue
        b64 = base64.b64encode(fp.read_bytes()).decode("ascii")
        bits.append(
            f'@font-face{{font-family:"TwitterChirp";src:url("data:font/woff2;base64,{b64}") format("woff2");'
            f"font-weight:{weight};font-style:normal;font-display:block;unicode-range:{LATIN};}}"
        )
    for fname, weight in (("400", 400), ("500", 500), ("700", 700)):
        fp = ASSETS / f"noto-sans-sc-{fname}.ttf"
        if not fp.exists():
            continue
        bits.append(
            f'@font-face{{font-family:"Noto Sans SC";src:url("{fp.as_uri()}") format("truetype");'
            f"font-weight:{weight};font-style:normal;font-display:block;unicode-range:{CJK};}}"
        )
    return "".join(bits)


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download(url: str, dest: Path, timeout: int = 120) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    if not url:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.write_bytes(get(url, timeout=timeout))
        return dest.stat().st_size > 0
    except Exception as e:
        print(f"warn: download failed {url[:80]} ({e})", file=sys.stderr)
        return False


def try_get(url: str, timeout: int = 30) -> bytes | None:
    """GET that returns None on Cloudflare 403 / any error so callers can keep going."""
    try:
        return get(url, timeout=timeout)
    except Exception as e:
        print(f"warn: get {url[:90]} ({e})", file=sys.stderr)
        return None


def is_x_avatar_url(url: str) -> bool:
    """X/Twitter CDN only. Never treat these as a Truth Social avatar."""
    u = (url or "").lower()
    return any(h in u for h in ("pbs.twimg.com", "abs.twimg.com", "twimg.com"))


def looks_like_image(data: bytes) -> bool:
    if not data or len(data) < 80:
        return False
    head = data[:32]
    if head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG") or head.startswith(b"GIF8") or head.startswith(b"RIFF"):
        return True
    h = data.lstrip()[:20].lower()
    if h.startswith(b"<") or h.startswith(b"<!doctype") or h.startswith(b"{") or h.startswith(b"error"):
        return False
    return False


def download_fresh(url: str, dest: Path, timeout: int = 120) -> bool:
    """Always fetch url. Never treat a leftover dest (other status / X avatar) as success."""
    if not url or is_x_avatar_url(url):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = get(url, timeout=timeout)
        if looks_like_image(data):
            dest.write_bytes(data)
            return dest.stat().st_size > 80
        print(f"warn: not an image {url[:80]}", file=sys.stderr)
    except Exception as e:
        print(f"warn: download failed {url[:80]} ({e})", file=sys.stderr)
    try:
        r = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(int(timeout)), "-A", UA,
             "-H", "Accept: image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
             "-o", str(dest), url],
            capture_output=True, timeout=timeout + 8,
        )
        if r.returncode == 0 and dest.exists() and looks_like_image(dest.read_bytes()):
            return True
        if dest.exists() and not looks_like_image(dest.read_bytes()):
            dest.unlink(missing_ok=True)
    except Exception as e:
        print(f"warn: curl failed {url[:80]} ({e})", file=sys.stderr)
    return False


def synd_token(sid: str) -> str:
    js = (
        "const id=" + json.dumps(str(sid)) + ";"
        "process.stdout.write(((Number(id)/1e15)*Math.PI).toString(36).replace(/(0+|\\.)/g,\"\"))"
    )
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
    return (r.stdout or "").strip()


def syndication(sid: str) -> dict | None:
    token = synd_token(sid)
    if not token:
        return None
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={sid}&token={token}&lang=en"
    try:
        data = json.loads(get(url, timeout=20).decode("utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) and data.get("id_str") else None


def label_badge_url(user: dict | None) -> str | None:
    if not isinstance(user, dict):
        return None
    url = ((user.get("highlighted_label") or {}).get("badge") or {}).get("url") or ""
    if not url:
        return None
    return url.replace("_normal.jpg", "_400x400.jpg").replace("_bigger.jpg", "_400x400.jpg")


def save_badge(url: str | None, dest: Path) -> str | None:
    if dest.exists() and dest.stat().st_size > 0:
        return f"media/{dest.name}"
    if url and download(url, dest):
        return f"media/{dest.name}"
    return None


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def first_existing_media(media_dir: Path, names: list[str]) -> str | None:
    for n in names:
        fp = media_dir / n
        if fp.exists() and fp.stat().st_size > 0:
            return f"media/{n}"
    return None


def adopt_local_images(media_dir: Path) -> list[str]:
    """Never scoop leftover m_* from a previous status / sibling DIR."""
    return []


def save_platform_logo(platform: str, media_dir: Path) -> str | None:
    """Download the site's real mark. Never draw a fake X for a non-X card."""
    dest_png = media_dir / "platform_logo.png"
    dest_svg = media_dir / "platform_logo.svg"
    if dest_png.exists() and dest_png.stat().st_size > 0:
        return "media/platform_logo.png"
    if dest_svg.exists() and dest_svg.stat().st_size > 0:
        return "media/platform_logo.svg"
    if platform != "truthsocial":
        return None
    for url in TS_LOGO_CANDIDATES:
        ext = ".svg" if url.lower().endswith(".svg") else ".png"
        dest = media_dir / f"platform_logo{ext}"
        if download(url, dest):
            return f"media/{dest.name}"
    return None


def save_ts_verify(media_dir: Path) -> str | None:
    """Official TS red verify mark from the live packs. Empty if download fails."""
    dest = media_dir / "verify.svg"
    if dest.exists() and dest.stat().st_size > 0:
        return "media/verify.svg"
    for url in TS_VERIFY_CANDIDATES:
        if download(url, dest):
            return "media/verify.svg"
    return None


def ts_affiliation_url(account: dict | None) -> str | None:
    """Official/highlighted square from the account, never a generic house icon."""
    if not isinstance(account, dict):
        return None
    for key in ("badge", "badge_url", "affiliation_badge"):
        u = account.get(key)
        if isinstance(u, str) and u.startswith("http"):
            return u
        if isinstance(u, dict):
            u = u.get("url") or u.get("src")
            if isinstance(u, str) and u.startswith("http"):
                return u
    for nest in ("highlighted_label", "label", "official"):
        blk = account.get(nest)
        if isinstance(blk, dict):
            badge = blk.get("badge") if isinstance(blk.get("badge"), dict) else blk
            u = (badge or {}).get("url") or (badge or {}).get("src") or ""
            if isinstance(u, str) and u.startswith("http"):
                return u
    return None


def ts_status_api(sid: str) -> dict | None:
    raw = try_get(f"{TS_API}/statuses/{sid}", timeout=25)
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) and data.get("id") else None


def ts_archive_url_for(sid: str) -> str | None:
    raw = try_get(TS_FEED, timeout=25)
    if not raw:
        return None
    text = raw.decode("utf-8", "ignore")
    # <truth:originalId>SID</truth:originalId> near <link>https://trumpstruth.org/statuses/N
    for m in re.finditer(
        r"<link>(https://trumpstruth\.org/statuses/\d+)</link>.*?<truth:originalId>(\d+)</truth:originalId>",
        text,
        re.S | re.I,
    ):
        if m.group(2) == sid:
            return m.group(1)
    # also originalUrl
    m = re.search(
        rf"https://trumpstruth\.org/statuses/(\d+)[^<]*</link>.*?{re.escape(sid)}",
        text,
        re.S | re.I,
    )
    if m:
        return f"https://trumpstruth.org/statuses/{m.group(1)}"
    m = re.search(rf"<truth:originalId>{re.escape(sid)}</truth:originalId>", text)
    if m:
        window = text[max(0, m.start() - 800) : m.end()]
        lm = re.search(r"https://trumpstruth\.org/statuses/(\d+)", window)
        if lm:
            return lm.group(0)
    return None


def ts_archive_status(sid: str, handle: str | None = None) -> dict | None:
    page = ts_archive_url_for(sid)
    if not page:
        return None
    raw = try_get(page, timeout=25)
    if not raw:
        return None
    html_text = raw.decode("utf-8", "ignore")
    created = None
    m = re.search(r"Original Post Date</t[dh]>\s*<t[dh]>[^<]*?(\w+ \d+, 20\d\d, \d+:\d+\s*[ap]m\s*\w+)", html_text, re.I)
    if not m:
        m = re.search(r"(\w+ \d+, 20\d\d, \d+:\d+\s*[ap]m\s*\w+)", html_text)
    if m:
        created = m.group(1)
    hm = re.search(r"truthsocial\.com/@([A-Za-z0-9_]+)/" + re.escape(sid), html_text)
    if hm:
        handle = hm.group(1)
    elif not handle:
        handle = "unknown"
    name = handle
    nm = re.search(r"<h1[^>]*>([^<]+)</h1>", html_text)
    if nm:
        name = nm.group(1).strip() or name
    text_en = ""
    # empty graphic posts are OK
    avatar_url = ""
    am = re.search(
        r"https://static-assets-1\.truthsocial\.com/[^\"\s']+/accounts/avatars/[^\"\s']+",
        html_text,
    )
    if am:
        avatar_url = am.group(0)
    return {
        "id": sid,
        "created_at": created,
        "content": text_en,
        "url": f"https://truthsocial.com/@{handle}/{sid}",
        "account": {
            "username": handle,
            "display_name": name,
            "verified": False,
            "avatar": avatar_url,
        },
        "media_attachments": [],
        "reblog": None,
        "quote": None,
        "_archive": page,
    }


def ts_account_statuses(handle: str) -> list[str]:
    """Public TS account timeline. IDs are Mastodon-style, not X snowflakes."""
    raw = try_get(f"{TS_API}/accounts/lookup?acct={handle}", timeout=20)
    acct_id = None
    if raw:
        try:
            acct = json.loads(raw.decode("utf-8"))
            acct_id = str((acct or {}).get("id") or "") or None
        except Exception:
            acct_id = None
    if not acct_id:
        return []
    raw = try_get(f"{TS_API}/accounts/{acct_id}/statuses?limit=40", timeout=25)
    if not raw:
        return []
    try:
        items = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    ids = []
    if isinstance(items, list):
        for it in items:
            sid = str((it or {}).get("id") or "")
            if sid.isdigit():
                ids.append(sid)
    return ids


def ts_feed_ids(handle: str) -> list[str]:
    """Public trumpstruth.org RSS ids for a handle. Not an X snowflake list."""
    raw = try_get(TS_FEED, timeout=25)
    if not raw:
        return []
    text = raw.decode("utf-8", "ignore")
    ids, seen = [], set()
    for m in re.finditer(
        r"https://truthsocial\.com/@([A-Za-z0-9_]+)/(\d{10,})",
        text,
        re.I,
    ):
        if m.group(1).lower() != handle.lower():
            continue
        sid = m.group(2)
        if sid not in seen:
            seen.add(sid)
            ids.append(sid)
    return ids


def save_ts_media(st: dict, media_dir: Path, prefix: str) -> tuple[list[str], str | None, str | None]:
    """Only media_attachments on THIS status. Never attach leftover m_* from the out dir."""
    images: list[str] = []
    video_rel = None
    thumb_rel = None
    atts = st.get("media_attachments") or []
    if not isinstance(atts, list):
        atts = []
    img_i = 0
    for att in atts:
        if not isinstance(att, dict):
            continue
        kind = str(att.get("type") or "")
        url = att.get("url") or att.get("remote_url") or ""
        preview = att.get("preview_url") or ""
        if kind == "video":
            dest = media_dir / f"{prefix}.mp4"
            if url and download_fresh(url, dest, timeout=180):
                video_rel = f"media/{dest.name}"
            tdest = media_dir / f"{prefix}_thumb.jpg"
            if (preview or url) and download_fresh(preview or url, tdest):
                thumb_rel = f"media/{tdest.name}"
        else:
            ext = ".png" if ".png" in url.lower() else ".jpg"
            dest = media_dir / f"{prefix}_{img_i}{ext}"
            if url and download_fresh(url, dest):
                images.append(f"media/{dest.name}")
                img_i += 1
            elif preview and download_fresh(preview, dest):
                images.append(f"media/{dest.name}")
                img_i += 1
    return images, video_rel, thumb_rel


def ts_avatar_variants(url: str) -> list[str]:
    """Same-account size variants + public archive of THIS avatar URL. Never X / other DIR."""
    if not url or is_x_avatar_url(url):
        return []
    out = [url]
    if "/original/" in url:
        out += [url.replace("/original/", "/small/"), url.replace("/original/", "/static/")]
    if "static-assets-1.truthsocial.com" in url and "accounts/avatars" in url:
        out.append("https://web.archive.org/web/2026if_/" + url)
        out.append("https://web.archive.org/web/20260826110355if_/" + url)
    return out


def scrape_ts_account_avatar(html_text: str) -> str | None:
    m = re.search(
        r"https://static-assets-1\.truthsocial\.com/[^\"\s']+/accounts/avatars/[^\"\s']+",
        html_text,
    )
    return m.group(0) if m else None


def save_ts_avatar(handle: str, sid: str, primary_url: str, media_dir: Path) -> str | None:
    """Avatar for THIS Truth Social account only. Empty if CDN/archive fail — never an X photo."""
    dest = media_dir / "avatar.jpg"
    candidates: list[str] = []
    candidates.extend(ts_avatar_variants(primary_url or ""))
    page = ts_archive_url_for(sid)
    if page:
        raw = try_get(page, timeout=25)
        if raw:
            found = scrape_ts_account_avatar(raw.decode("utf-8", "ignore"))
            if found:
                candidates.extend(ts_avatar_variants(found))
    for live in (
        f"https://truthsocial.com/@{handle}",
        f"https://truthsocial.com/@{handle}/posts/{sid}",
        f"https://truthsocial.com/@{handle}/{sid}",
    ):
        raw = try_get(live, timeout=20)
        if not raw:
            continue
        found = scrape_ts_account_avatar(raw.decode("utf-8", "ignore"))
        if found:
            candidates.extend(ts_avatar_variants(found))
    seen: set[str] = set()
    for url in candidates:
        if not url or url in seen or is_x_avatar_url(url):
            continue
        seen.add(url)
        if download_fresh(url, dest):
            return "media/avatar.jpg"
    if dest.exists():
        try:
            dest.unlink()
        except OSError:
            pass
    return None


def canonical_url(platform: str, handle: str, sid: str) -> str:
    if platform == "truthsocial":
        return f"https://truthsocial.com/@{handle}/{sid}"
    return f"https://x.com/{handle}/status/{sid}"


def empty_post_fields() -> dict:
    return {
        "quote_handle": None,
        "quote_name": None,
        "quote_en": None,
        "quote_zh": "",
        "quote_verified": False,
        "quote_verify_type": None,
        "quote_created_at_utc": None,
        "quote_avatar": None,
        "quote_badge": None,
        "quote_verify_badge": None,
        "video": None,
        "video_thumb": None,
    }


def detect_platform(url: str | None, platform: str | None = None) -> str:
    if platform in ("x", "twitter"):
        return "x"
    if platform in ("truthsocial", "truth", "ts"):
        return "truthsocial"
    if url and TS_URL_RE.search(url):
        return "truthsocial"
    if url and URL_RE.search(url):
        return "x"
    return "x"


def parse_url(
    url: str | None,
    handle: str | None,
    sid: str | None,
    platform: str | None = None,
) -> tuple[str, str, str]:
    """Return (platform, handle, id). Accepts X and Truth Social URLs."""
    plat = detect_platform(url, platform)
    if url:
        if plat == "truthsocial":
            m = TS_URL_RE.search(url)
            if not m:
                die(f"bad url: {url}")
            return "truthsocial", m.group(1).lstrip("@"), m.group(2)
        m = URL_RE.search(url)
        if not m:
            die(f"bad url: {url}")
        return "x", m.group(1), m.group(2)
    if handle and sid:
        return plat, handle.lstrip("@"), sid
    die("need --url or --handle and --id")


def snowflake_dt(sid: str) -> datetime:
    """Twitter snowflake only. Do not pass Truth Social / Mastodon ids here."""
    ms = (int(sid) >> 22) + EPOCH
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def is_x_snowflake(sid: str) -> bool:
    """True only for Twitter snowflakes. Truth Social / Mastodon ids fail."""
    if not sid.isdigit() or not (18 <= len(sid) <= 19):
        return False
    ts_ms = (int(sid) >> 22) + EPOCH
    min_ms = 1356998400000  # ~2013-01-01
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    return min_ms <= ts_ms <= now_ms + 86400000


def parse_created(s: str | None, fallback_id: str, platform: str = "x") -> datetime:
    if s:
        for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    # TS ids are Mastodon snowflakes, not Twitter snowflakes — never decode them as X.
    if platform != "x":
        return datetime.now(timezone.utc)
    return snowflake_dt(fallback_id)


def meta_en(dt: datetime) -> str:
    """Original post time in local TZ (US Pacific), never Beijing."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL).strftime("%-I:%M %p · %b %-d, %Y")


def handle_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL).strftime("%-I:%M %p · %b %-d")


def beijing(dt: datetime) -> str:
    return dt.astimezone(BJ).strftime("%Y-%m-%d %H:%M")


def verified(user: dict | None) -> bool:
    if not user:
        return False
    v = user.get("verification")
    if isinstance(v, dict):
        return bool(v.get("verified"))
    return bool(user.get("verified"))


def verify_type(user: dict | None) -> str | None:
    if not user:
        return None
    v = user.get("verification")
    if isinstance(v, dict):
        t = v.get("type")
        if t:
            return str(t).lower()
        if v.get("verified"):
            return "individual"
    if user.get("verified"):
        return "individual"
    return None


def badge_svg(w: int, vtype: str | None) -> str:
    """Official X verified seal (scalloped), not a plain circle."""
    fill = BADGE_FILL.get((vtype or "").lower(), "#1d9bf0")
    # Same path X uses on web: seal + check as one even-odd shape.
    d = (
        "M20.396 11c-.018-.646-.215-1.275-.57-1.816-.354-.54-.852-.972-1.438-1.246"
        ".223-.607.27-1.264.14-1.897-.13-.634-.437-1.218-.878-1.686-.44-.468-1.012-.8"
        "-1.634-.95-.623-.149-1.272-.1-1.854.14-.42-.545-.994-.95-1.64-1.15-.645-.2"
        "-1.336-.2-1.981 0-.645.2-1.22.605-1.64 1.15-.582-.24-1.23-.29-1.854-.14"
        "-.622.15-1.195.482-1.634.95-.441.468-.748 1.052-.878 1.686-.13.633-.083 1.29"
        ".14 1.897-.586.274-1.084.706-1.438 1.246-.354.54-.552 1.17-.57 1.816.018.646"
        ".216 1.275.57 1.816.354.54.852.972 1.438 1.246-.223.607-.27 1.264-.14 1.897"
        ".13.634.437 1.218.878 1.686.44.468 1.012.8 1.634.95.623.149 1.272.1 1.854-.14"
        ".42.545.994.95 1.64 1.15.645.2 1.336.2 1.981 0 .645-.2 1.22-.605 1.64-1.15"
        ".582.24 1.23.29 1.854.14.622-.15 1.195-.482 1.634-.95.441-.468.748-1.052"
        ".878-1.686.13-.633.083-1.29-.14-1.897.586-.274 1.084-.706 1.438-1.246.354-.54"
        ".552-1.17.57-1.816zM9.662 14.85l-3.429-3.428 1.293-1.302 2.072 2.072 4.4-4.704"
        " 1.347 1.359z"
    )
    return (
        f'<svg width="{w}" height="{w}" viewBox="0 0 22 22" aria-hidden="true">'
        f'<path fill="{fill}" d="{d}"/></svg>'
    )


def org_mark_html(size: int = 16, src: str | None = None) -> str:
    """Affiliation badge from the original post (highlighted_label). Empty if none."""
    if not src:
        return ""
    style = f"width:{size}px;height:{size}px"
    return f'<img class="orgmark" style="{style}" src="{src}" alt=""/>'


def is_org_type(vtype: str | None) -> bool:
    return (vtype or "").lower() in ORG_TYPES


def strip_media_urls(text: str) -> str:
    if not text:
        return ""
    text = MEDIA_URL_RE.sub("", text)
    return text.strip()


def best_mp4(video: dict) -> str | None:
    variants = video.get("variants") or video.get("formats") or []
    mp4s = []
    for v in variants:
        kind = str(v.get("content_type") or v.get("container") or v.get("url") or "")
        if "mp4" in kind and "m3u8" not in str(v.get("url") or ""):
            mp4s.append(v)
    if mp4s:
        mp4s.sort(key=lambda v: int(v.get("bitrate") or 0), reverse=True)
        return mp4s[0].get("url")
    url = video.get("url") or ""
    return url if url and "m3u8" not in url else None


def fx_tweet(handle: str, sid: str) -> dict:
    raw = get(f"{FX}/{handle}/status/{sid}", timeout=30)
    data = json.loads(raw.decode("utf-8"))
    if data.get("code") != 200 or not data.get("tweet"):
        die(f"fxtwitter: {data.get('code')} {data.get('message')} id={sid}")
    return data["tweet"]


def rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def save_media(tw: dict, media_dir: Path, prefix: str) -> tuple[list[str], str | None, str | None]:
    media = tw.get("media") or {}
    images: list[str] = []
    video_rel = None
    thumb_rel = None
    photos = media.get("photos") or []
    videos = media.get("videos") or []
    for i, p in enumerate(photos):
        url = p.get("url") or ""
        dest = media_dir / f"{prefix}_{i}.jpg"
        if url and download(url, dest):
            images.append(f"media/{dest.name}")
    if videos:
        v = videos[0]
        mp4 = best_mp4(v)
        dest = media_dir / f"{prefix}.mp4"
        if mp4 and download(mp4, dest, timeout=180):
            video_rel = f"media/{dest.name}"
        thumb_url = v.get("thumbnail_url") or v.get("thumbnail") or ""
        tdest = media_dir / f"{prefix}_thumb.jpg"
        if thumb_url and download(thumb_url, tdest):
            thumb_rel = f"media/{tdest.name}"
    return images, video_rel, thumb_rel


def compact(post: dict) -> str:
    lines = [
        f"DIR={post['_dir']}",
        f"PLATFORM={post.get('platform') or 'x'}",
        f"ID={post['id']}",
        f"URL={post['url']}",
        f"KIND={post['kind']}",
        f"HANDLE={post['handle']}",
        f"TEXT_EN={post.get('text_en') or ''}",
    ]
    if post.get("quote_handle"):
        lines.append(f"QUOTE_HANDLE={post['quote_handle']}")
        lines.append(f"QUOTE_EN={post.get('quote_en') or ''}")
    return "\n".join(lines)


def write_post(out: Path, post: dict) -> None:
    (out / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    post["_dir"] = str(out)
    print(compact(post))


def cmd_fetch(args: argparse.Namespace) -> None:
    platform, handle, sid = parse_url(args.url, args.handle, args.id, getattr(args, "platform", None))
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    media_dir = out / "media"
    media_dir.mkdir(exist_ok=True)
    if platform == "truthsocial":
        fetch_truthsocial(handle, sid, out, media_dir)
        return
    fetch_x(handle, sid, out, media_dir)


def fetch_x(handle: str, sid: str, out: Path, media_dir: Path) -> None:
    tw = fx_tweet(handle, sid)
    rp = tw.get("reposted_by") if isinstance(tw.get("reposted_by"), dict) else None
    qt = tw.get("quote") if isinstance(tw.get("quote"), dict) else None

    if rp:
        kind = "retweet"
        outer_handle = rp.get("screen_name") or handle
        outer_name = rp.get("name") or outer_handle
        outer_avatar_url = rp.get("avatar_url") or ""
        outer_verified = True
        outer_vtype = "individual"
        dt = snowflake_dt(sid)
        text_en = ""
        inner, inner_prefix = tw, "q"
    elif qt:
        kind = "quote"
        outer_handle = (tw.get("author") or {}).get("screen_name") or handle
        outer_name = (tw.get("author") or {}).get("name") or outer_handle
        outer_avatar_url = (tw.get("author") or {}).get("avatar_url") or ""
        outer_verified = verified(tw.get("author"))
        outer_vtype = verify_type(tw.get("author"))
        dt = parse_created(tw.get("created_at"), sid)
        text_en = strip_media_urls(tw.get("text") or tw.get("raw_text") or "")
        inner, inner_prefix = qt, "q"
    else:
        kind = "original"
        outer_handle = (tw.get("author") or {}).get("screen_name") or handle
        outer_name = (tw.get("author") or {}).get("name") or outer_handle
        outer_avatar_url = (tw.get("author") or {}).get("avatar_url") or ""
        outer_verified = verified(tw.get("author"))
        outer_vtype = verify_type(tw.get("author"))
        dt = parse_created(tw.get("created_at"), sid)
        text_en = strip_media_urls(tw.get("text") or tw.get("raw_text") or "")
        inner, inner_prefix = None, "m"

    avatar = None
    if outer_avatar_url and download(outer_avatar_url, media_dir / "avatar.jpg"):
        avatar = "media/avatar.jpg"

    quote_handle = quote_name = quote_en = quote_avatar = None
    quote_verified = False
    quote_vtype = None
    quote_created_at_utc = None
    src_for_media = inner if inner is not None else tw
    if inner is not None:
        qa = inner.get("author") or {}
        quote_handle = qa.get("screen_name")
        quote_name = qa.get("name") or quote_handle
        quote_en = strip_media_urls(inner.get("text") or inner.get("raw_text") or "")
        quote_verified = verified(qa)
        quote_vtype = verify_type(qa)
        qid = str(inner.get("id") or sid)
        qdt = parse_created(inner.get("created_at"), qid)
        quote_created_at_utc = qdt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        qavatar_url = qa.get("avatar_url") or ""
        if qavatar_url and download(qavatar_url, media_dir / "quote_avatar.jpg"):
            quote_avatar = "media/quote_avatar.jpg"

    images, video, video_thumb = save_media(src_for_media, media_dir, inner_prefix)
    badges_by: dict[str, str] = {}
    ids = [sid]
    if inner is not None and inner.get("id"):
        iid = str(inner.get("id"))
        if iid not in ids:
            ids.append(iid)
    for tid in ids:
        syn = syndication(tid)
        if not syn:
            continue
        for user in (syn.get("user"), (syn.get("quoted_tweet") or {}).get("user")):
            if not isinstance(user, dict):
                continue
            h = (user.get("screen_name") or "").lstrip("@").lower()
            url = label_badge_url(user)
            if h and url:
                badges_by[h] = url
    badge = save_badge(badges_by.get((outer_handle or "").lstrip("@").lower()), media_dir / "badge.jpg")
    qh = (quote_handle or "").lstrip("@").lower() if quote_handle else ""
    quote_badge = save_badge(badges_by.get(qh), media_dir / "quote_badge.jpg") if qh else None

    post = {
        "id": sid,
        "platform": "x",
        "url": canonical_url("x", handle, sid),
        "handle": outer_handle,
        "name": outer_name,
        "kind": kind,
        "verified": outer_verified,
        "verify_type": outer_vtype,
        "created_at_utc": dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "beijing": beijing(dt),
        "meta_en": meta_en(dt),
        "text_en": text_en,
        "text_zh": "",
        "quote_handle": quote_handle,
        "quote_name": quote_name,
        "quote_en": quote_en,
        "quote_zh": "",
        "quote_verified": quote_verified,
        "quote_verify_type": quote_vtype,
        "quote_created_at_utc": quote_created_at_utc,
        "avatar": avatar,
        "quote_avatar": quote_avatar,
        "badge": badge,
        "quote_badge": quote_badge,
        "verify_badge": None,
        "quote_verify_badge": None,
        "platform_logo": None,
        "link_color": LINK_COLOR["x"],
        "images": images,
        "video": video,
        "video_thumb": video_thumb,
    }
    write_post(out, post)


def fetch_truthsocial(handle: str, sid: str, out: Path, media_dir: Path) -> None:
    """Public TS data: API → trumpstruth archive → already-downloaded files. Keep going on 403."""
    st = ts_status_api(sid)
    if not st:
        st = ts_archive_status(sid, handle=handle)
    prev = {}
    pj = out / "post.json"
    if pj.exists():
        try:
            prev = json.loads(pj.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
    if not st:
        st = {
            "id": sid,
            "created_at": prev.get("created_at_utc"),
            "content": prev.get("text_en") or "",
            "account": {
                "username": handle,
                "display_name": prev.get("name") or handle,
                "verified": bool(prev.get("verified")),
                "avatar": "",
            },
            "media_attachments": [],
            "reblog": None,
            "quote": None,
        }

    reblog = st.get("reblog") if isinstance(st.get("reblog"), dict) else None
    quote = st.get("quote") if isinstance(st.get("quote"), dict) else None
    acct = st.get("account") if isinstance(st.get("account"), dict) else {}

    if reblog:
        kind = "retweet"
        outer_handle = handle
        outer_name = acct.get("display_name") or handle
        outer_avatar_url = acct.get("avatar") or acct.get("avatar_static") or ""
        outer_verified = bool(acct.get("verified"))
        outer_vtype = "government" if outer_verified else None
        dt = parse_created(st.get("created_at"), sid, "truthsocial")
        text_en = ""
        inner, inner_prefix, inner_acct = reblog, "q", reblog.get("account") or {}
    elif quote:
        kind = "quote"
        outer_handle = acct.get("username") or handle
        outer_name = acct.get("display_name") or outer_handle
        outer_avatar_url = acct.get("avatar") or acct.get("avatar_static") or ""
        outer_verified = bool(acct.get("verified"))
        outer_vtype = "government" if outer_verified else None
        dt = parse_created(st.get("created_at"), sid, "truthsocial")
        text_en = strip_html(st.get("content"))
        inner, inner_prefix, inner_acct = quote, "q", quote.get("account") or {}
    else:
        kind = "original"
        outer_handle = acct.get("username") or handle
        outer_name = acct.get("display_name") or outer_handle
        outer_avatar_url = acct.get("avatar") or acct.get("avatar_static") or ""
        outer_verified = bool(acct.get("verified"))
        # TS verify is a red check, not an X scallop type. Keep a hint only.
        outer_vtype = "verified" if outer_verified else None
        dt = parse_created(st.get("created_at"), sid, "truthsocial")
        text_en = strip_html(st.get("content"))
        inner, inner_prefix, inner_acct = None, "m", {}

    avatar = save_ts_avatar(outer_handle or handle, sid, outer_avatar_url, media_dir)

    quote_handle = quote_name = quote_en = quote_avatar = None
    quote_verified = False
    quote_vtype = None
    quote_created_at_utc = None
    src_for_media = inner if inner is not None else st
    if inner is not None:
        qa = inner_acct if isinstance(inner_acct, dict) else {}
        quote_handle = qa.get("username")
        quote_name = qa.get("display_name") or quote_handle
        quote_en = strip_html(inner.get("content"))
        quote_verified = bool(qa.get("verified"))
        quote_vtype = "verified" if quote_verified else None
        qid = str(inner.get("id") or sid)
        qdt = parse_created(inner.get("created_at"), qid, "truthsocial")
        quote_created_at_utc = qdt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        qavatar_url = qa.get("avatar") or qa.get("avatar_static") or ""
        if qavatar_url and download(qavatar_url, media_dir / "quote_avatar.jpg"):
            quote_avatar = "media/quote_avatar.jpg"

    images, video, video_thumb = save_ts_media(src_for_media, media_dir, inner_prefix)

    platform_logo = save_platform_logo("truthsocial", media_dir)
    verify_badge = save_ts_verify(media_dir) if outer_verified else None
    quote_verify_badge = verify_badge if quote_verified else None
    badge = save_badge(ts_affiliation_url(acct), media_dir / "badge.png")
    qbadge = save_badge(ts_affiliation_url(inner_acct if inner is not None else None), media_dir / "quote_badge.png")

    post = {
        "id": sid,
        "platform": "truthsocial",
        "url": canonical_url("truthsocial", outer_handle or handle, sid),
        "handle": outer_handle,
        "name": outer_name,
        "kind": kind,
        "verified": outer_verified,
        "verify_type": outer_vtype,
        "created_at_utc": dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "beijing": beijing(dt),
        "meta_en": meta_en(dt),
        "text_en": text_en,
        "text_zh": prev.get("text_zh") or "",
        "quote_handle": quote_handle,
        "quote_name": quote_name,
        "quote_en": quote_en,
        "quote_zh": prev.get("quote_zh") or "",
        "quote_verified": quote_verified,
        "quote_verify_type": quote_vtype,
        "quote_created_at_utc": quote_created_at_utc,
        "avatar": avatar,
        "quote_avatar": quote_avatar,
        "badge": badge,
        "quote_badge": qbadge,
        "verify_badge": verify_badge,
        "quote_verify_badge": quote_verify_badge,
        "platform_logo": platform_logo,
        "link_color": LINK_COLOR["truthsocial"],
        "images": images,
        "video": video,
        "video_thumb": video_thumb,
    }
    write_post(out, post)


def file_uri(base: Path, rel_path: str | None) -> str:
    if not rel_path:
        return ""
    p = (base / rel_path).resolve()
    return p.as_uri() if p.exists() else ""


def esc(s: str | None) -> str:
    return html.escape(s or "", quote=True).replace("\n", "\n")


# Same entities X paints blue in the post body.
ENTITY_RE = re.compile(
    r"https?://[^\s]+|@[A-Za-z0-9_]{1,15}|#[A-Za-z0-9_]+|\$[A-Z]{1,6}\b"
)


def rich_text(s: str | None) -> str:
    text = s or ""
    out = []
    i = 0
    for m in ENTITY_RE.finditer(text):
        out.append(esc(text[i:m.start()]))
        raw = m.group(0)
        trail = ""
        if raw.startswith("http"):
            while raw and raw[-1] in ".,;:!?)":
                trail = raw[-1] + trail
                raw = raw[:-1]
        out.append(f'<span class="tlink">{esc(raw)}</span>{esc(trail)}')
        i = m.end()
    out.append(esc(text[i:]))
    return "".join(out)


def media_html(post: dict, base: Path) -> str:
    bits = ['<div class="media">']
    thumb = file_uri(base, post.get("video_thumb"))
    if thumb:
        bits.append(f'<div class="vidwrap"><img src="{thumb}"/>{PLAY}</div>')
    for p in post.get("images") or []:
        src = file_uri(base, p)
        if src:
            bits.append(f'<img src="{src}"/>')
    bits.append("</div>")
    return "" if len(bits) == 2 else "".join(bits)


def handle_line(handle: str | None, rel: str) -> str:
    h = f"@{esc(handle)}"
    return f"{h} · {esc(rel)}" if rel else h


def zh_box(zh: str, beijing_ts: str | None = None, klass: str = "zh-box") -> str:
    zh = (zh or "").strip()
    if not zh:
        return ""
    inner = rich_text(zh)
    if beijing_ts:
        inner += f'<div class="zh-time">{esc(beijing_ts)} UTC+8</div>'
    return f'<div class="{klass}">{inner}</div>'


def corner_logo_html(post: dict, base: Path) -> str:
    """X keeps the inline XLOGO svg. Others: real downloaded mark, or empty — never a fake X."""
    src = file_uri(base, post.get("platform_logo"))
    if src:
        return f'<img class="xlogo" src="{src}" alt=""/>'
    plat = (post.get("platform") or "x").lower()
    if plat in ("", "x", "twitter"):
        return XLOGO
    return ""


def verify_mark_html(post: dict, base: Path, size: int, *, quote: bool = False) -> str:
    """X: official scalloped seal. TS: downloaded red check. Never paint an X-blue scallop on TS."""
    if quote:
        verified = post.get("quote_verified")
        vtype = post.get("quote_verify_type")
        rel = post.get("quote_verify_badge") or post.get("verify_badge")
    else:
        verified = post.get("verified")
        vtype = post.get("verify_type")
        rel = post.get("verify_badge")
    if not verified:
        return ""
    src = file_uri(base, rel)
    if src:
        return (
            f'<img class="vbadge" src="{src}" width="{size}" height="{size}" '
            f'style="width:{size}px;height:{size}px" alt=""/>'
        )
    plat = (post.get("platform") or "x").lower()
    if plat in ("", "x", "twitter"):
        return badge_svg(size, vtype)
    return ""


def build_html(post: dict, base: Path) -> str:
    av = file_uri(base, post.get("avatar"))
    qav = file_uri(base, post.get("quote_avatar"))
    plat = (post.get("platform") or "x").lower()
    outer_badge = verify_mark_html(post, base, 18, quote=False)
    inner_badge = verify_mark_html(post, base, 16, quote=True)
    outer_org = org_mark_html(16, file_uri(base, post.get("badge"))) if post.get("badge") else ""
    inner_org = org_mark_html(14, file_uri(base, post.get("quote_badge"))) if post.get("quote_badge") else ""
    created = parse_created(post.get("created_at_utc"), str(post.get("id") or "0"), plat)
    local = handle_time(created)
    quote_local = ""
    quote_bj = ""
    if post.get("quote_created_at_utc"):
        qcreated = parse_created(post.get("quote_created_at_utc"), str(post.get("id") or "0"), plat)
        quote_local = handle_time(qcreated)
        quote_bj = beijing(qcreated)
    avatar_tag = f'<img class="avatar" src="{av}" alt=""/>' if av else '<div class="avatar"></div>'
    qavatar_tag = f'<img class="qavatar" src="{qav}" alt=""/>' if qav else ""
    text_en = post.get("text_en") or ""
    quote_en = post.get("quote_en") or ""
    text_zh = post.get("text_zh") or ""
    quote_zh = post.get("quote_zh") or ""
    media = media_html(post, base)
    logo = corner_logo_html(post, base)
    body = [
        '<div class="top">',
        avatar_tag,
        '<div class="who"><div class="name-row">',
        f'<span class="name">{esc(post.get("name"))}</span>',
        outer_badge,
        outer_org,
        "</div>",
        f'<div class="handle">{handle_line(post.get("handle"), local)}</div>',
        "</div>",
        logo,
        "</div>",
    ]
    if post.get("kind") == "retweet":
        body.append('<div class="reposted">Reposted</div>')
    if text_en:
        body.append(f'<div class="text">{rich_text(text_en)}</div>')
    if text_zh and text_zh != text_en:
        body.append(zh_box(text_zh, beijing(created)))
    if post.get("quote_handle"):
        body.append('<div class="quote"><div class="qtop">')
        body.append(qavatar_tag)
        body.append(f'<span class="qname">{esc(post.get("quote_name") or post.get("quote_handle"))}</span>')
        body.append(inner_badge)
        body.append(inner_org)
        body.append(f'<span class="qhandle">{handle_line(post.get("quote_handle"), quote_local)}</span>')
        body.append("</div>")
        if quote_en:
            body.append(f'<div class="qtext">{rich_text(quote_en)}</div>')
        if quote_zh and quote_zh != quote_en:
            body.append(zh_box(quote_zh, quote_bj, "zh-box qzh-box"))
        body.append(media)
        body.append("</div>")
    else:
        body.append(media)
    body.append(
        f'<div class="meta">{esc(meta_en(created))}</div>'
    )
    link = post.get("link_color") or LINK_COLOR.get(plat, "#1d9bf0")
    extra = f".tlink{{color:{link};}}"
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"/><style>"
        + font_face_css()
        + CSS
        + extra
        + "</style></head><body><div class=\"card\">"
        + "".join(body)
        + "</div></body></html>"
    )


def guess_h(post: dict, base: Path | None = None) -> int:
    """Viewport must fit the whole card; Chrome clips anything past window-size."""
    text = (
        (post.get("text_en") or "")
        + (post.get("quote_en") or "")
        + (post.get("text_zh") or "")
        + (post.get("quote_zh") or "")
    )
    # ~26 chars/line at 17px, 24px line-height; zh boxes add extra.
    text_h = 160 + (len(text) // 22) * 26
    media_h = 0
    rels = list(post.get("images") or [])
    if post.get("video_thumb"):
        rels.append(post["video_thumb"])
    content_w = 542
    for rel in rels:
        fp = (base / rel) if base else None
        if fp and fp.exists():
            try:
                from PIL import Image
                w, h = Image.open(fp).size
                media_h += int(content_w * h / max(w, 1)) + 12
                continue
            except Exception:
                pass
        media_h += 560
    h = 400 + text_h + media_h
    return min(max(h, 720), 20000)


def crop_black(path: Path, threshold: int = 18, pad: int = 28) -> None:
    from PIL import Image

    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    y = h - 1
    while y > 0:
        if any(sum(px[x, y]) > threshold * 3 for x in range(0, w, 4)):
            break
        y -= 1
    y = min(h, y + pad)
    if y < h - 2:
        im.crop((0, 0, w, y)).save(path)


def screenshot(html_path: Path, png_path: Path, height: int) -> None:
    chrome = "google-chrome"
    cmd = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--disable-lcd-text",
        "--force-device-scale-factor=2",
        f"--window-size=620,{height}",
        f"--screenshot={png_path}",
        "--virtual-time-budget=15000",
        html_path.resolve().as_uri(),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not png_path.exists():
        die("chrome screenshot failed: " + (r.stderr or r.stdout or str(r.returncode))[:400])
    crop_black(png_path)


def quote_md(handle: str, en: str, zh: str) -> str:
    parts = [f"@{handle.lstrip('@')}"]
    en, zh = (en or "").rstrip(), (zh or "").rstrip()
    if en:
        parts.append(en)
    if zh and zh != en:
        if en:
            parts.append("")
        parts.append(zh)
    out = []
    for line in "\n".join(parts).split("\n"):
        out.append("> " + line if line else ">")
    return "\n".join(out)


def own_md(en: str, zh: str) -> str:
    en, zh = (en or "").strip(), (zh or "").strip()
    if not en and not zh:
        return ""
    if not zh or zh == en:
        return en
    if not en:
        return zh
    return f"{en}\n\n{zh}"


def chat_body(post: dict) -> str:
    chunks = []
    own = own_md(post.get("text_en") or "", post.get("text_zh") or "")
    if own:
        chunks.append(own)
    if post.get("quote_handle"):
        chunks.append(quote_md(post["quote_handle"], post.get("quote_en") or "", post.get("quote_zh") or ""))
    chunks.append(f"{post.get('beijing')} UTC+8")
    chunks.append(post.get("url") or "")
    return "\n\n".join(chunks).strip() + "\n"


def cmd_render(args: argparse.Namespace) -> None:
    base = Path(args.dir).resolve()
    pj = base / "post.json"
    if not pj.exists():
        die(f"missing {pj}")
    post = json.loads(pj.read_text(encoding="utf-8"))
    if args.text_zh is not None:
        post["text_zh"] = args.text_zh
    if args.quote_zh is not None:
        post["quote_zh"] = args.quote_zh
    created = parse_created(post.get("created_at_utc"), str(post.get("id") or "0"), post.get("platform") or "x")
    post["meta_en"] = meta_en(created)
    post["beijing"] = beijing(created)
    pj.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")

    html_path = base / "card.html"
    png_path = base / "card.png"
    html_path.write_text(build_html(post, base), encoding="utf-8")
    screenshot(html_path, png_path, guess_h(post, base))

    body = chat_body(post)
    (base / "message.md").write_text(body, encoding="utf-8")
    video = post.get("video")
    video_path = (base / video).resolve() if video else None
    print(f"CARD={png_path}")
    if video_path and video_path.exists():
        print(f"VIDEO={video_path}")
    print("-----")
    print(body, end="" if body.endswith("\n") else "\n")
    print("-----")


def timeline_xtracker(handle: str) -> list[str] | None:
    """Public Polymarket XTracker. x.com HTML is a JS shell and misses new posts."""
    start = (datetime.now(BJ) - timedelta(days=3)).strftime("%Y-%m-%d")
    url = f"https://xtracker.polymarket.com/api/users/{handle}/posts?startDate={start}"
    try:
        data = json.loads(get(url, timeout=30).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("success"):
        return None
    ids, seen = [], set()
    for p in data.get("data") or []:
        sid = str(p.get("platformId") or "")
        if sid.isdigit() and sid not in seen:
            seen.add(sid)
            ids.append(sid)
    return ids or None


def timeline_xhtml(handle: str) -> list[str]:
    url = f"https://x.com/{handle}"
    raw = get(url, timeout=30).decode("utf-8", "ignore")
    ids, seen = [], set()
    for h, sid in STATUS_RE.findall(raw):
        if h.lower() != handle.lower() or sid in seen:
            continue
        seen.add(sid)
        ids.append(sid)
    return ids


def cmd_timeline(args: argparse.Namespace) -> None:
    # TS ids are Mastodon snowflakes, not Twitter snowflakes.
    # Never pass a Truth Social id to fxtwitter, syndication, snowflake_dt, or x.com/status/{id}.
    # Watch a TS handle with --platform truthsocial (trumpstruth RSS + TS public statuses).
    handle = args.handle.lstrip("@")
    plat = detect_platform(getattr(args, "url", None), getattr(args, "platform", None))
    # A bare --handle stays on X unless --platform truthsocial.
    since = int(args.since_id) if args.since_id else 0
    if plat == "truthsocial":
        ids = ts_feed_ids(handle)
        if not ids:
            try:
                ids = ts_account_statuses(handle)
            except Exception as e:
                die(f"FAIL timeline: {e}")
        if not ids:
            die(f"FAIL timeline empty @{handle} (truthsocial)")
        if not since:
            new = [max(ids, key=int)]
        else:
            # integer compare only; these are not X snowflakes
            new = [s for s in ids if int(s) > since]
            new.sort(key=int)
            if args.max and len(new) > args.max:
                new = new[: int(args.max)]
        print(f"NEW {len(new)}")
        for s in new:
            print(f"{s}\t{canonical_url('truthsocial', handle, s)}")
        return
    # Same path as elonmusk: XTracker first, then x.com HTML.
    # XTracker maps realDonaldTrump to Truth Social; those ids must not count as X.
    ids = [s for s in (timeline_xtracker(handle) or []) if is_x_snowflake(s)]
    if not ids:
        try:
            ids = [s for s in timeline_xhtml(handle) if is_x_snowflake(s)]
        except Exception as e:
            die(f"FAIL timeline: {e}")
    if not ids:
        die(f"FAIL timeline empty @{handle}")
    if not since:
        new = [max(ids, key=int)]
    else:
        new = [s for s in ids if int(s) > since]
        new.sort(key=int)
        if args.max and len(new) > args.max:
            new = new[: int(args.max)]
    print(f"NEW {len(new)}")
    for s in new:
        print(f"{s}\thttps://x.com/{handle}/status/{s}")


def main() -> None:
    p = argparse.ArgumentParser(prog="x_card.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch")
    f.add_argument("--url")
    f.add_argument("--handle")
    f.add_argument("--id")
    f.add_argument("--platform", choices=("x", "truthsocial"), help="override URL detection")
    f.add_argument("--out", required=True)
    f.set_defaults(func=cmd_fetch)

    r = sub.add_parser("render")
    r.add_argument("--dir", required=True)
    r.add_argument("--text-zh")
    r.add_argument("--quote-zh")
    r.set_defaults(func=cmd_render)

    t = sub.add_parser("timeline")
    t.add_argument("--handle", required=True)
    t.add_argument("--since-id")
    t.add_argument("--max", type=int, default=20)
    t.add_argument("--platform", choices=("x", "truthsocial"), help="truthsocial: trumpstruth / TS public posts, not X")
    t.add_argument("--url", help="optional profile URL used only to detect platform")
    t.set_defaults(func=cmd_timeline)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
