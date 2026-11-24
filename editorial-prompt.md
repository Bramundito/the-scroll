# THE SCROLL — Editorial content prompt

Use this prompt to generate **only the content** for `news.json`. Never rewrite or generate the website’s HTML, CSS, or JavaScript when producing an edition.

## Editorial mission

THE SCROLL is a finite, one-story-per-screen news reader. Aim for 20–30 substantive, independently verifiable stories per daily edition (fewer when a full lineup would require filler). Give meaningful attention to **Indonesia and Jakarta** plus major global developments. Selectively include noteworthy creative-industry, brand-activation, visual-art, music, pop-culture, gaming and internet-culture stories only when there is concrete news to report. Conversational, lively English; clarity over clickbait; no repetitive hype.

## Reporting standard

- Use published, dated sources. Verify names, dates, places, numbers and claims against primary materials or multiple independent reliable publications where feasible. Distinguish assertions from confirmed facts. Preserve important uncertainty; never manufacture consensus.
- Do not invent events, sources, links, eyewitness quotes, statistics, image credits or opposing viewpoints. Do not copy source articles verbatim.
- Every story needs a substantive lead, useful sections and source attribution. Supporting cards **must be specific to the story**: an obscure term explained; a documented disagreement between outlets; a location or museum for an artwork; a precise timeline; a government record; or helpful verified background. Do not force the same set of cards onto every story.
- A cross-publication comparison card requires direct links to *both* reports and an accurate explanation of where coverage actually differs. A difference in angle is not automatically a factual contradiction.
- For each story, aim for 2–3 **authentic relevant images**. Include usable direct HTTPS image URLs, descriptions, source/credit links and accurate `kind` labels (`event`, `archive`, `promotional`, `context`). Never substitute an unrelated stock image as though it documents the event. When suitable images are unavailable, leave `images` empty or include fewer; the app displays a labeled graphic fallback.
- Consider image copyright and hotlink restrictions before public deployment; use licensed or permissioned image assets in production.

## Output rules

Return **only one valid JSON object** matching the existing `news.json` shape. Never wrap in Markdown or HTML. Keep the story array in editorial priority order. Every property inside each story remains content, not presentation code:

```json
{
  "date": "YYYY-MM-DD",
  "updated_at": "ISO 8601 timestamp",
  "demo": false,
  "intro": "Brief edition description",
  "stories": [
    {
      "id": "story-1",
      "category": "Indonesia",
      "title": "Reported headline",
      "lede": "Direct factual summary",
      "published_at": "YYYY-MM-DD",
      "source_name": "News organization",
      "source_url": "https://example.com/source-article",
      "sections": [{"heading":"What happened","body":"Reporting with meaningful detail"}],
      "cards": [{
        "side":"left",
        "type":"TERM EXPLAINED",
        "title":"Useful, story-specific term",
        "body":"Accurate context",
        "bullets":[],
        "sources":[{"label":"Primary reference","url":"https://example.com/reference"}],
        "color":"purple"
      }],
      "images": [{
        "url":"https://example.com/photograph.jpg",
        "caption":"Accurate caption describing the image",
        "credit":"Image rights-holder or publisher",
        "credit_url":"https://example.com/photo-credit",
        "kind":"event"
      }]
    }
  ]
}
```

The example URLs are placeholders to illustrate the structure—**never emit them as actual news sources**. `backup_url` is optional for images. Preserve `accent`, `soft`, `background` or `visual` keys only if the article-specific existing data already supplies them; the app has visual defaults. Keep support cards rooted in evidence, not aesthetic filler.

## Publishing workflow

1. Build the next edition as JSON (without changing the reader).
2. Review claims, source links, image credits, and story-specific context.
3. Replace `news.json` atomically, run `npm run check`, and reload the reader.
4. A future 9 AM Jakarta-time AI job should update **only** `news.json`, not `index.html`, `styles.css` or `app.js`. This project does not yet schedule or run that job.
