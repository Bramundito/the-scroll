# THE SCROLL — GitHub automated edition setup

The 10 root-level files go in `Bramundito/the-scroll` on branch `main`. The workflow goes in `.github/workflows/daily-scroll.yml` (GitHub's upload screen may hide `.github` on macOS).

1. In GitHub, go to the-scroll → Code → Add file → Upload files. Upload only the 10 files visible at ZIP root: index.html, styles.css, app.js, news.json, editorial-prompt.md, generate-news.mjs, validate-news.mjs, server.mjs, package.json, README.md. If GitHub says a file already exists, it should be shown as updated. Commit to main. Do NOT upload the .github folder here if your browser refuses directories.
2. In OpenAI Platform (platform.openai.com/api-keys), enable separate API billing and create a project API key. Do not paste it into ChatGPT or any repository file. Set a budget/usage alert.
3. In GitHub: repository Settings → Secrets and variables → Actions → New repository secret. Name: `OPENAI_API_KEY`. Value: the OpenAI secret API key. Save.
4. GitHub repository Code → Add file → Create new file. For filename enter `.github/workflows/daily-scroll.yml`. Open the supplied daily-scroll.yml file locally in TextEdit, copy all its text, paste into the browser editor, then Commit changes directly to main.
5. GitHub repository Settings → Pages → Build and deployment → Source: `GitHub Actions`. Save if a Save button is shown.
6. GitHub repository Actions → `THE SCROLL — Daily Edition` → Run workflow → choose `deploy-only` → Run workflow. This is a FREE deployment test; it uses existing 28-story news.json and does not consume the OpenAI API. Wait for a green check, open https://bramundito.github.io/the-scroll/, and refresh.
7. Go back to Actions → Run workflow → choose `generate` → Run workflow. This CALLS the paid OpenAI API. Watch logs for `Published valid JSON candidate`, `Valid edition:`, and a successful Pages deployment.
8. Scheduled workflow begins daily at 01:00 UTC = 08:00 Jakarta WIB to target a 09:00 edition. GitHub schedules may be delayed; there is no guaranteed 09:00 delivery.

## Safety and limitations

- No API key is committed to the repo; the workflow uses a GitHub Actions secret.
- If generation fails, the old `news.json` is not overwritten/deployed. The workflow can still fail/red-mark that day; old site remains live.
- The generator only accepts lead URLs exposed in the web-search response source metadata; this is NOT full human fact-checking of every claim or interpretation. Read the linked original source for consequential news.
- This first automatic version does NOT yet search for or license 2–3 news photographs per story; newly generated articles use labeled, automatically drawn editorial illustrations instead of potentially misleading/unlicensed photos. Existing `news.json` retains its earlier image references until the first generated edition.
- `editorial-prompt.md` contains your custom editorial rules. Edit that file only when you want to change the news selection/writing instructions.
- GitHub Actions's own commits do not trigger branch-based Pages builds; this custom workflow explicitly deploys the updated files. Keep Pages Source set to GitHub Actions.
- Images and articles are publicly accessible at the GitHub Pages URL even if the website is intended for personal reading.
