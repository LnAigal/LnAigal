#!/usr/bin/env python3
"""Generate assets/activity-graph.svg from GitHub's contribution calendar.

The third-party service (github-readme-activity-graph.vercel.app) is disabled,
so the graph is rendered here from the same calendar GitHub shows on the
profile page. No token or third-party API is required.
"""

import argparse
import datetime
import html
import json
import re
import sys
import urllib.request

WIDTH = 1200
HEIGHT = 420
PLOT_LEFT = 90.0
PLOT_RIGHT = 1150.0
PLOT_TOP = 80.0
PLOT_BOTTOM = 350.0

BG = "#0d1117"
ACCENT = "#00f7ff"
POINT = "#ff6b35"


def fetch_calendar(username):
    url = "https://github.com/users/{}/contributions".format(username)
    req = urllib.request.Request(
        url, headers={"User-Agent": "readme-activity-graph-generator"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        page = resp.read().decode("utf-8", "replace")

    tips = {
        m.group(1): html.unescape(m.group(2))
        for m in re.finditer(
            r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>(.*?)</tool-tip>', page, re.S
        )
    }

    counts = {}
    for m in re.finditer(r"<td\b[^>]*>", page):
        tag = m.group(0)
        date = re.search(r'data-date="([\d-]+)"', tag)
        if not date:
            continue
        cell_id = re.search(r'id="([^"]+)"', tag)
        value = 0
        if cell_id and cell_id.group(1) in tips:
            match = re.search(r"(\d+)\s+contributions?", tips[cell_id.group(1)])
            if match:
                value = int(match.group(1))
        counts[date.group(1)] = value

    if len(counts) < 300:
        raise RuntimeError(
            "parsed {} contribution days from GitHub (expected a full year)".format(
                len(counts)
            )
        )
    return counts


def fetch_display_name(username):
    url = "https://api.github.com/users/{}".format(username)
    req = urllib.request.Request(
        url, headers={"User-Agent": "readme-activity-graph-generator"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            name = json.load(resp).get("name")
        if name:
            return name
    except Exception:
        pass
    return username


def nice_scale(max_value):
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000):
        if step * 5 >= max_value:
            return step
    return -(-max_value // 5) or 1


def render_svg(dates, values, title):
    count = len(dates)
    max_value = max(values)
    step = nice_scale(max_value)
    top_value = step * 5

    def x_at(index):
        if count == 1:
            return (PLOT_LEFT + PLOT_RIGHT) / 2
        return PLOT_LEFT + index * (PLOT_RIGHT - PLOT_LEFT) / (count - 1)

    def y_at(value):
        return PLOT_BOTTOM - (value / top_value) * (PLOT_BOTTOM - PLOT_TOP)

    points = [(x_at(i), y_at(v)) for i, v in enumerate(values)]
    line = "M" + " L".join("{:.2f},{:.2f}".format(x, y) for x, y in points)
    area = line + " L{:.2f},{:.2f} L{:.2f},{:.2f} Z".format(
        points[-1][0], PLOT_BOTTOM, points[0][0], PLOT_BOTTOM
    )

    parts = [
        '<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" '
        'xmlns="http://www.w3.org/2000/svg">'.format(w=WIDTH, h=HEIGHT),
        '<rect data-testid="card_bg" x="0" y="0" width="100%" height="100%" '
        'rx="0" fill="{}" stroke="none"/>'.format(BG),
        "<style>",
        "svg { font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; user-select: none; }",
        ".header {{ font: 600 20px 'Segoe UI', Ubuntu, Sans-Serif; fill: {}; }}".format(
            ACCENT
        ),
        ".ct-label {{ fill: {}; font-size: .75rem; }}".format(ACCENT),
        ".ct-grid {{ stroke: {}; stroke-width: 1px; stroke-opacity: 0.3; "
        "stroke-dasharray: 2px; }}".format(ACCENT),
        ".ct-line {{ fill: none; stroke: {}; stroke-width: 4px; "
        "stroke-linejoin: round; stroke-linecap: round; }}".format(ACCENT),
        ".ct-area {{ fill: {}; fill-opacity: 0.1; stroke: none; }}".format(ACCENT),
        ".ct-point {{ fill: {}; stroke: {}; stroke-width: 4px; "
        "stroke-linecap: round; }}".format(POINT, POINT),
        "</style>",
        '<text x="{}" y="45" text-anchor="middle" class="header">{}</text>'.format(
            WIDTH / 2, html.escape(title)
        ),
        '<g class="ct-grids">',
    ]

    for i in range(count):
        x = x_at(i)
        parts.append(
            '<line x1="{x:.2f}" x2="{x:.2f}" y1="{y1}" y2="{y2}" '
            'class="ct-grid"/>'.format(x=x, y1=PLOT_TOP, y2=PLOT_BOTTOM)
        )
    for tick in range(6):
        y = y_at(tick * step)
        parts.append(
            '<line x1="{x1}" x2="{x2}" y1="{y:.2f}" y2="{y:.2f}" '
            'class="ct-grid"/>'.format(x1=PLOT_LEFT, x2=PLOT_RIGHT, y=y)
        )
    parts.append("</g>")

    parts.append('<g class="ct-series ct-series-a">')
    parts.append('<path class="ct-area" d="{}"/>'.format(area))
    parts.append('<path class="ct-line" d="{}"/>'.format(line))
    for x, y in points:
        parts.append(
            '<circle cx="{x:.2f}" cy="{y:.2f}" r="5" class="ct-point"/>'.format(
                x=x, y=y
            )
        )
    parts.append("</g>")

    parts.append('<g class="ct-labels">')
    for i, date in enumerate(dates):
        parts.append(
            '<text x="{x:.2f}" y="370" text-anchor="middle" class="ct-label '
            'ct-horizontal">{day}</text>'.format(x=x_at(i), day=date.day)
        )
    for i, date in enumerate(dates):
        if i == 0 or date.day == 1:
            parts.append(
                '<text x="{x:.2f}" y="388" text-anchor="middle" class="ct-label '
                'ct-horizontal">{month}</text>'.format(
                    x=x_at(i), month=date.strftime("%b")
                )
            )
    for tick in range(6):
        value = tick * step
        parts.append(
            '<text x="80" y="{y:.2f}" text-anchor="end" class="ct-label '
            'ct-vertical">{value}</text>'.format(y=y_at(value) + 5, value=value)
        )
    parts.append(
        '<text x="{}" y="400" text-anchor="middle" class="ct-label">Days'
        "</text>".format(WIDTH / 2)
    )
    parts.append(
        '<text x="20" y="215" transform="rotate(-90, 20, 215)" text-anchor="middle" '
        'class="ct-label">Contributions</text>'
    )
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True, help="GitHub username")
    parser.add_argument("--title", default=None, help="graph title")
    parser.add_argument("--days", type=int, default=31, help="number of days to plot")
    parser.add_argument("-o", "--output", required=True, help="output SVG path")
    args = parser.parse_args()

    counts = fetch_calendar(args.user)
    today = datetime.date.today()
    dates = [
        today - datetime.timedelta(days=offset)
        for offset in range(args.days - 1, -1, -1)
    ]
    values = [counts.get(d.isoformat(), 0) for d in dates]

    title = args.title or "{}'s Contribution Graph".format(
        fetch_display_name(args.user)
    )
    svg = render_svg(dates, values, title)

    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(svg)

    print(
        "wrote {} ({} days, total {}, max {}/{})".format(
            args.output, args.days, sum(values), max(values), nice_scale(max(values)) * 5
        )
    )


if __name__ == "__main__":
    sys.exit(main())
