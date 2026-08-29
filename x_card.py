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
# Known trumpstruth.org archive page for a TS status id (keep going if missing).
TS_ARCHIVE_KNOWN = {
    "117175567133618952": "https://trumpstruth.org/statuses/41356",
    "117176514317841811": "https://trumpstruth.org/statuses/41360",
}
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
