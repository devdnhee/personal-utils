# /// script
# dependencies = [
#   "fire>=0.7.0",
#   "plotly>=5.0.0",
#   "kaleido>=0.2.1",
#   "requests>=2.32.0",
#   "rich>=13.0.0",
# ]
# requires-python = ">=3.12"
# ///

"""Plot cumulative GitHub stars over time for any repository.

Usage:
    uv run scripts/github_stars_plotter.py anthropics/claude-code
    uv run scripts/github_stars_plotter.py https://github.com/anthropics/claude-code
    uv run scripts/github_stars_plotter.py owner/repo --output /tmp/stars.png
    GITHUB_TOKEN=ghp_xxx uv run scripts/github_stars_plotter.py anthropics/claude-code
"""

import logging
import os
import time
from datetime import datetime, timezone

import fire
import plotly.graph_objects as go
import requests
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_repo(repo: str) -> tuple[str, str]:
    """Accept 'owner/repo' or a GitHub URL; return (owner, repo)."""
    repo = repo.rstrip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    # Strip scheme + host for URLs
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if repo.startswith(prefix):
            repo = repo[len(prefix):]
            break
    parts = [p for p in repo.split("/") if p]
    if len(parts) != 2:
        raise ValueError(
            f"Cannot parse '{repo}' as owner/repo. "
            "Use 'owner/repo' or 'https://github.com/owner/repo'."
        )
    return parts[0], parts[1]


def _default_output_path() -> str:
    return datetime.now().strftime("data/images/%y-%m-%d_stars.html")


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------


def _fetch_stargazers(owner: str, repo: str, token: str | None) -> list[datetime]:
    """Return a sorted list of star timestamps fetched from the GitHub API."""
    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github.v3.star+json"
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
        log.info("GitHub token detected — using authenticated requests.")

    url = f"https://api.github.com/repos/{owner}/{repo}/stargazers"
    dates: list[datetime] = []
    page = 1

    while True:
        resp = session.get(url, params={"per_page": 100, "page": page})

        if resp.status_code == 404:
            log.error(f"Repository '{owner}/{repo}' not found (404).")
            return []
        if resp.status_code in (401, 403):
            log.error(
                f"Authentication error ({resp.status_code}). "
                "Set GITHUB_TOKEN to an access token with public_repo scope."
            )
            return []
        resp.raise_for_status()

        # Rate limit handling
        remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
        if remaining == 0:
            reset_ts = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(0, reset_ts - int(time.time())) + 1
            log.warning(f"Rate limit reached. Resuming in {wait}s...")
            time.sleep(wait)

        batch = resp.json()
        if not batch:
            break

        for item in batch:
            starred_at = item.get("starred_at", "")
            if starred_at:
                dates.append(
                    datetime.fromisoformat(starred_at.replace("Z", "+00:00"))
                )

        log.info(f"  Page {page}: fetched {len(batch)} stars (total: {len(dates)})")

        # Check for next page via Link header
        link = resp.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        page += 1

    dates.sort()
    return dates


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------


def _build_cumulative(dates: list[datetime]) -> tuple[list, list]:
    return dates, list(range(1, len(dates) + 1))


# ---------------------------------------------------------------------------
# Plotly figure
# ---------------------------------------------------------------------------


def _make_figure(
    dates: list[datetime], counts: list[int], owner: str, repo: str
) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=dates,
            y=counts,
            mode="lines",
            fill="tozeroy",
            name="Stars",
        )
    )
    fig.update_layout(
        title=f"{owner}/{repo} — GitHub Stars Over Time",
        xaxis_title="Date",
        yaxis_title="Cumulative Stars",
        hovermode="x unified",
        template="plotly_white",
    )
    return fig


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def plot_stars(repo: str, output: str = None) -> None:
    """Fetch and plot cumulative GitHub stars over time.

    :param repo:   Repository as 'owner/repo' or a full GitHub URL.
    :param output: Output file path. Extension determines format:
                   .html (interactive, default), .png, .svg, .pdf, .jpeg.
    """
    try:
        owner, repo_name = _parse_repo(repo)
    except ValueError as exc:
        log.error(str(exc))
        return

    if output is None:
        output = _default_output_path()

    token = os.environ.get("GITHUB_TOKEN")

    log.info(f"Fetching stars for {owner}/{repo_name}...")
    dates = _fetch_stargazers(owner, repo_name, token)

    if not dates:
        log.warning("No stars fetched — nothing to plot.")
        return

    log.info(f"Total stars fetched: {len(dates)}")

    dates, counts = _build_cumulative(dates)
    fig = _make_figure(dates, counts, owner, repo_name)

    ext = os.path.splitext(output)[1].lower()
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)

    if ext == ".html" or not ext:
        fig.write_html(output)
    else:
        fig.write_image(output)

    log.info(f"Plot saved to: {output}")


if __name__ == "__main__":
    fire.Fire(plot_stars)
