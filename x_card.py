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

# SOURCE: /home/box/agent-data/workflows/x-share-card/scripts/x_card.py
# Full 56154-byte script follows in this commit via identical local file.
