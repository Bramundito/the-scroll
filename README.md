# THE SCROLL — GitHub Pages edition

THE SCROLL is a **static website**. Once deployed, only `news.json` needs to be replaced to publish new content. The website reads it on each page load.

## Publish to GitHub Pages

1. Open the GitHub repository `Bramundito/the-scroll`.
2. Click **Add file → Upload files**.
3. **Open the unzipped `the-scroll-github-ready` folder**, select all nine files *inside* it, and drag those files (not the ZIP or parent folder) into the upload area. Keep all nine files at the root of the repository alongside any existing `README.md`.
4. Commit changes to the `main` branch. Allow GitHub Pages to deploy, then open `https://bramundito.github.io/the-scroll/`.
5. Test the story navigation and images on desktop and mobile.

The site requires these four files side-by-side at the repository root:

- `index.html` — website structure
- `styles.css` — site appearance
- `app.js` — rendering, scrolling and interactions; reads `./news.json`
- `news.json` — the ONLY edition content (text, facts, links and remotely hosted image references)

Other files are optional development references, not needed by GitHub Pages:

- `editorial-prompt.md` — separate instructions for future AI news creation
- `server.mjs` and `package.json` — optional local development server (`npm start`)
- `validate-news.mjs` — optional structural data check (`npm run check`)

## Updating stories

To change the edition, replace **only** `news.json` with a new JSON file matching the same format. Keep the filename exactly `news.json`, no `(1)` or `.txt` suffix. GitHub Pages will redeploy when you commit manual changes to `main`. An AI generator and a 9 AM schedule are **not configured yet**.

## Important notes

- The existing 2026-11-23 edition is marked as a reused/demo edition. Its validator checks file structure **not factual accuracy**, image availability, licensing, or source truth. Do an editorial review before treating it as verified news.
- Images are external URLs and can break, be blocked by their host, or have reuse restrictions. The reader provides labeled visual fallbacks.
- Your repository and the GitHub Pages website are public. Never put private API keys or credentials into any of these files.
- GitHub Pages serves HTML, CSS, JS and JSON but **does not run `server.mjs`**. `npm start` is only for local preview, not for website hosting.

### Automatic daily publishing (v1)

See `generate-news.mjs` and `.github/workflows/daily-scroll.yml`. Create an OpenAI API key, store it as `OPENAI_API_KEY` in **GitHub repository Settings → Secrets and variables → Actions**, then change **Settings → Pages → Source** to **GitHub Actions**. In Actions, run THE SCROLL — Daily Edition with `deploy-only` first, then `generate`. The scheduled workflow starts at 08:00 WIB, targeting readiness by 09:00; GitHub schedule timing is not guaranteed. Automated story generation is not human fact-checking; the current generator checks that lead links were in the model’s actual web search sources, and fails without replacing old content if too few stories pass. It does not yet license or retrieve photographs; it leaves story `images` arrays empty and the UI shows clearly labeled editorial illustrations. API charges are separate from ChatGPT.
