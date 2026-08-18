#!/usr/bin/env python3
"""
Build the static English blog (blog/) from Markdown posts in blog/_posts/.

Usage (from the repository root):
    python3 scripts/build_blog.py

Produces:
    blog/index.html          -- homepage: newest-first post list
    blog/posts/<slug>.html   -- one page per post

Rendering uses the `markdown` package when available (`pip install markdown`);
otherwise it falls back to a small built-in renderer so the scaffold works on
any Python 3 install. The generated HTML is committed so GitHub Pages serves
it as plain static files (see the root `.nojekyll` marker).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import markdown as _md

    _HAS_MARKDOWN = True
except ImportError:
    _HAS_MARKDOWN = False


ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "blog" / "_posts"
BLOG_DIR = ROOT / "blog"
POSTS_OUT = BLOG_DIR / "posts"

REPO_URL = "https://github.com/Martin-MQtech/open-matrix-publisher"
SITE_TITLE = "Open Matrix Journal"
SITE_TAGLINE = "One Content, Multi-Domain Distribution"


# --------------------------------------------------------------------------- #
# Minimal Markdown fallback (used only when the `markdown` package is absent)
# --------------------------------------------------------------------------- #
def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text: str) -> str:
    text = _escape(text)
    # inline code spans first so their content is not further processed
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # images before links
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def _render_fallback(text: str) -> str:
    out: list[str] = []
    para: list[str] = []
    in_list: str | None = None
    in_quote = False
    in_code = False
    code_buf: list[str] = []

    def flush_para() -> None:
        if para:
            out.append("<p>" + " ".join(para) + "</p>")
            para.clear()

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</" + in_list + ">")
            in_list = None

    for line in text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_para()
            close_list()
            if not in_code:
                in_code = True
                code_buf = []
            else:
                out.append("<pre><code>" + "\n".join(code_buf) + "</code></pre>")
                in_code = False
                code_buf = []
            continue
        if in_code:
            code_buf.append(line)
            continue

        if not stripped:
            flush_para()
            close_list()
            if in_quote:
                out.append("</blockquote>")
                in_quote = False
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para()
            close_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue

        if stripped.startswith(">"):
            flush_para()
            close_list()
            if not in_quote:
                out.append("<blockquote>")
                in_quote = True
            out.append("<p>" + _inline(stripped.lstrip(">").strip()) + "</p>")
            continue

        m = re.match(r"^[-*+]\s+(.*)$", stripped)
        if m:
            flush_para()
            if in_list != "ul":
                close_list()
                out.append("<ul>")
                in_list = "ul"
            out.append("<li>" + _inline(m.group(1)) + "</li>")
            continue

        m = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if m:
            flush_para()
            if in_list != "ol":
                close_list()
                out.append("<ol>")
                in_list = "ol"
            out.append("<li>" + _inline(m.group(1)) + "</li>")
            continue

        para.append(_inline(stripped))

    flush_para()
    close_list()
    if in_quote:
        out.append("</blockquote>")
    if in_code:
        out.append("<pre><code>" + "\n".join(code_buf) + "</code></pre>")
    return "\n".join(out)


def render_markdown(text: str) -> str:
    if _HAS_MARKDOWN:
        return _md.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])
    return _render_fallback(text)


# --------------------------------------------------------------------------- #
# Post loading
# --------------------------------------------------------------------------- #
def parse_post(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip()
            body = parts[2].lstrip("\n")
    return {"slug": path.stem, "meta": meta, "body": body}


def parse_tags(value: str) -> list[str]:
    value = value.strip().strip("[]")
    return [t.strip() for t in value.split(",") if t.strip()]


def load_posts() -> list[dict]:
    posts = [parse_post(p) for p in sorted(POSTS_DIR.glob("*.md"))]
    posts.sort(key=lambda p: p["meta"].get("date", ""), reverse=True)
    return posts


# --------------------------------------------------------------------------- #
# HTML templates
# --------------------------------------------------------------------------- #
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:type" content="website">
<link rel="icon" href="{root}favicon.ico" sizes="any">
<link rel="stylesheet" href="{css_path}">
</head>
<body>
<header class="site-head">
  <div class="head-inner">
    <a class="brand" href="{root}index.html">
      <img src="{root}logo.svg" alt="Open Matrix Publisher" class="brand-logo">
      <span class="brand-name">Open Matrix <em>Journal</em></span>
    </a>
    <nav class="head-nav">
      <a href="{root}index.html">Main Site</a>
      <a href="{blog_home}" class="active">Blog</a>
      <a href="{repo_url}">GitHub</a>
    </nav>
  </div>
</header>
<main class="wrap">
{body}
</main>
<footer class="site-foot">
  <p><a href="{root}index.html">Open Matrix Publisher</a> · {tagline} · MIT License</p>
  <p class="foot-muted">Incubated by <a href="https://www.emuqi.com">MUQI Tech</a> — AIGC × Hydrogen Health × Medical Devices</p>
</footer>
</body>
</html>
"""


def tag_html(tags: list[str]) -> str:
    return '<div class="post-tags">' + "".join(
        f'<span class="tag">{t}</span>' for t in tags
    ) + "</div>"


def homepage_body(posts: list[dict]) -> str:
    cards: list[str] = []
    for p in posts:
        meta = p["meta"]
        title = meta.get("title", p["slug"])
        date = meta.get("date", "")
        desc = meta.get("description", "")
        tags = parse_tags(meta.get("tags", ""))
        cards.append(
            f'<a class="post-card" href="posts/{p["slug"]}.html">'
            f'<div class="post-date">{date}</div>'
            f"<h2>{title}</h2>"
            f'<p class="post-desc">{desc}</p>'
            f"{tag_html(tags)}"
            f'<div class="read-more">Read more →</div>'
            f"</a>"
        )
    return (
        '<div class="journal-head">'
        f'<span class="journal-kicker">Field Notes &amp; Releases</span>'
        f'<h1 class="journal-title">{SITE_TAGLINE}</h1>'
        '<p class="journal-desc">A zero-risk, self-hosted channel for the Open Matrix '
        "Publisher project — cross-border commerce, hydrogen biology, and advanced "
        "materials, published here first.</p>"
        "</div>"
        '<div class="post-list">' + "".join(cards) + "</div>"
    )


def article_body(post: dict) -> str:
    meta = post["meta"]
    title = meta.get("title", post["slug"])
    date = meta.get("date", "")
    tags = parse_tags(meta.get("tags", ""))
    html = render_markdown(post["body"])
    # The title already lives in frontmatter; drop a duplicated leading <h1>.
    html = re.sub(r"^\s*<h1>.*?</h1>\s*", "", html, count=1, flags=re.S)
    return (
        '<article class="article">'
        f'<div class="post-date">{date}</div>'
        f"<h1>{title}</h1>"
        f"{tag_html(tags)}"
        f'<div class="article-body">{html}</div>'
        f'<a class="back-link" href="../index.html">All posts</a>'
        "</article>"
    )


def render_page(
    title: str,
    description: str,
    body: str,
    root: str,
    blog_home: str,
    css_path: str,
) -> str:
    return PAGE.format(
        title=title,
        description=description,
        body=body,
        root=root,
        blog_home=blog_home,
        css_path=css_path,
        repo_url=REPO_URL,
        tagline=SITE_TAGLINE,
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def main() -> int:
    if not POSTS_DIR.is_dir():
        print(f"error: no posts directory at {POSTS_DIR}", file=sys.stderr)
        return 1

    posts = load_posts()
    if not posts:
        print(f"warning: no .md files in {POSTS_DIR}", file=sys.stderr)

    # Homepage (depth 1 -> repo root is ../)
    write(
        BLOG_DIR / "index.html",
        render_page(
            title=f"{SITE_TITLE} · {SITE_TAGLINE}",
            description="A zero-risk, self-hosted journal for Open Matrix Publisher.",
            body=homepage_body(posts),
            root="../",
            blog_home="index.html",
            css_path="assets/blog.css",
        ),
    )

    # Individual posts (depth 2 -> repo root is ../../)
    for post in posts:
        meta = post["meta"]
        title = meta.get("title", post["slug"])
        desc = meta.get("description", "")
        write(
            POSTS_OUT / f'{post["slug"]}.html',
            render_page(
                title=f"{title} · {SITE_TITLE}",
                description=desc,
                body=article_body(post),
                root="../../",
                blog_home="../index.html",
                css_path="../assets/blog.css",
            ),
        )

    print(f"Built {len(posts)} post(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
