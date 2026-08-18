# Open Matrix Journal — static blog

A zero-risk, self-hosted English blog served by GitHub Pages. This is the
project's "own the channel first" home base: content lives here before it is
distributed anywhere else.

- Live path: `https://martin-mqtech.github.io/open-matrix-publisher/blog/`
- Brand rules: see the repo root `AGENTS.md` (charcoal/grey + orange, flat, no glow).

## Write a post

1. Create a Markdown file in `blog/_posts/`, named with a URL-friendly slug:
   `blog/_posts/my-new-post.md`.
2. Put a small header at the top (title, date, description, tags):

   ```markdown
   ---
   title: Your Post Title
   date: 2026-08-18
   description: One-sentence summary shown on the homepage.
   tags: [cross-border, materials]
   ---

   # Your Post Title

   Body text in Markdown…
   ```

3. Rebuild the static HTML from the repo root:

   ```bash
   python3 scripts/build_blog.py
   ```

   This regenerates `blog/index.html` and `blog/posts/<slug>.html`. Commit both
   the Markdown source and the generated HTML.

## Publish

The generated HTML is committed, so **GitHub Pages serves it as plain static
files** — no build step on GitHub's side, no Jekyll (see the root `.nojekyll`
marker).

- Make sure GitHub Pages is enabled on the repository:
  **Settings → Pages → Build and deployment → Source: Deploy from a branch →
  Branch: `main` / `/ (root)`**.
- Push to `main`; the blog is live at `…/open-matrix-publisher/blog/`.

If you need `pip install markdown` for richer Markdown support, the build script
falls back to a built-in renderer otherwise, so it always runs.

## Writing notes (avoid triggering platform spam filters)

- Use real, human titles — never machine-test titles like "E2E test 123".
- Publish here first, mirror elsewhere later. A static site has no algorithm
  and no moderation queue.
- Platform counts never appear as a slogan — keep them in fact tables only.
