#!/usr/bin/env python3
"""THE SCROLL — source-first daily news collection, no AI/API key.

Only publisher-provided RSS/Atom metadata is collected. No full articles are
scraped or republished, no unverifiable contextual claims are generated, and
source links stay intact. This is a reading/discovery product; full articles
remain on publishers' websites unless redistribution rights are established.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
OUT = HERE / 'news.json'
NOW = datetime.now(timezone.utc)
LOCAL = ZoneInfo('Asia/Jakarta')
MAX_STORIES = 30
MIN_STORIES = 12
MEDIA = '{http://search.yahoo.com/mrss/}'
ATOM = '{http://www.w3.org/2005/Atom}'
DC = '{http://purl.org/dc/elements/1.1/}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}'

# A source may stop publishing or block automation. We skip it, never invent it.
# Feed destinations were selected from publishers' feed directories or reported
# public feeds; links can change over time. Social sources can join later when
# authenticated, permitted, stable read access is available at no cost.
FEEDS = [
    ('INDONESIA', 'ANTARA English', 'https://en.antaranews.com/rss/latest-news.xml'),
    ('INDONESIA', 'ANTARA English', 'https://en.antaranews.com/rss/current-issue.xml'),
    ('INDONESIA', 'ANTARA English', 'https://en.antaranews.com/rss/business-investment.xml'),
    ('INDONESIA', 'ANTARA News', 'https://www.antaranews.com/rss/top-news.xml'),
    ('INDONESIA', 'ANTARA News', 'https://www.antaranews.com/rss/politik.xml'),
    ('INDONESIA', 'ANTARA News', 'https://www.antaranews.com/rss/ekonomi.xml'),
    ('JAKARTA', 'ANTARA Jakarta', 'https://www.antaranews.com/rss/metro.xml'),
    ('JAKARTA', 'ANTARA Jakarta', 'https://www.antaranews.com/rss/metro-lintas-kota.xml'),
    ('JAKARTA', 'ANTARA Jakarta', 'https://www.antaranews.com/rss/metro-lenggang-jakarta.xml'),
    ('WORLD', 'BBC News', 'https://feeds.bbci.co.uk/news/world/rss.xml'),
    ('WORLD', 'BBC News', 'https://feeds.bbci.co.uk/news/business/rss.xml'),
    ('WORLD', 'BBC News', 'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml'),
    ('WORLD', 'The Guardian', 'https://www.theguardian.com/world/rss'),
    ('CREATIVE', 'Creative Boom', 'https://www.creativeboom.com/feed/'),
    ('CREATIVE', 'Dezeen', 'https://www.dezeen.com/feed/'),
    ('CREATIVE', "It's Nice That", 'https://feeds2.feedburner.com/itsnicethat/SlXC'),
    ('ART & CULTURE', 'The Guardian', 'https://www.theguardian.com/artanddesign/rss'),
    ('ART & CULTURE', 'Dezeen', 'https://www.dezeen.com/design/feed/'),
    ('ART & CULTURE', 'ANTARA News', 'https://www.antaranews.com/rss/lifestyle.xml'),
    ('MUSIC & POP CULTURE', 'BBC News', 'https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml'),
    ('MUSIC & POP CULTURE', 'The Guardian', 'https://www.theguardian.com/music/rss'),
    ('MUSIC & POP CULTURE', 'ANTARA News', 'https://www.antaranews.com/rss/hiburan.xml'),
    ('GAMING & TECH', 'BBC News', 'https://feeds.bbci.co.uk/news/technology/rss.xml'),
    ('GAMING & TECH', 'GamesIndustry.biz', 'https://www.gamesindustry.biz/rss/gamesindustry_news_feed.rss'),
    ('GAMING & TECH', 'ANTARA News', 'https://www.antaranews.com/rss/tekno.xml'),
]

# Targets, not fixed quotas: the script never fabricates or pads stories.
TARGETS = [('INDONESIA', 7), ('JAKARTA', 4), ('WORLD', 7),
           ('CREATIVE', 4), ('ART & CULTURE', 3),
           ('MUSIC & POP CULTURE', 3), ('GAMING & TECH', 2)]

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def strip_markup(value):
    p = PlainText()
    p.feed(unescape(value or ''))
    return re.sub(r'\s+', ' ', unescape(' '.join(p.parts))).strip()

def text_at(node, paths):
    for path in paths:
        found = node.find(path)
        if found is not None and found.text and found.text.strip():
            return found.text.strip()
    return ''

def https(url):
    try:
        p = urlparse(url)
        return p.scheme == 'https' and bool(p.hostname)
    except (TypeError, ValueError):
        return False

def date_parse(raw):
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (ValueError, TypeError, IndexError):
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def image_refs(item, publisher, link):
    """Only image URLs deliberately attached by a feed provider (up to 3)."""
    candidates = []
    for el in item.findall(f'{MEDIA}thumbnail') + item.findall(f'{MEDIA}content'):
        u = el.get('url', '')
        if not https(u):
            continue
        medium = (el.get('medium') or '').lower()
        typ = (el.get('type') or '').lower()
        if medium and medium != 'image':
            continue
        if typ and not typ.startswith('image/'):
            continue
        credit = text_at(el, (f'{MEDIA}credit',)) or publisher
        candidates.append((u, credit))
    for el in item.findall('enclosure'):
        u = el.get('url', '')
        if https(u) and (el.get('type') or '').lower().startswith('image/'):
            candidates.append((u, publisher))
    seen = set()
    imgs = []
    for u, credit in candidates:
        if u in seen:
            continue
        seen.add(u)
        imgs.append({'url': u, 'caption': 'Image supplied in the publisher RSS feed; see the original report for full context.',
                     'credit': credit, 'credit_url': link, 'kind': 'feed'})
        if len(imgs) == 3:
            break
    return imgs

def feed_read(spec):
    category, publisher, url = spec
    req = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; TheScrollReader/1.0; RSS personal news reader)',
        'Accept': 'application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.8',
    })
    try:
        with urlopen(req, timeout=16) as res:
            blob = res.read(2_000_001)
        if len(blob) > 2_000_000:
            raise ValueError('oversized feed')
        root = ET.fromstring(blob)
    except Exception as err:
        print(f'SKIP {publisher} / {category}: {err}', flush=True)
        return []
    entries = root.findall('./channel/item')
    if not entries:
        entries = root.findall(f'./{ATOM}entry')
    output = []
    max_days = 10 if category in {'CREATIVE', 'ART & CULTURE'} else 4
    for item in entries[:90]:
        title = strip_markup(text_at(item, ('title', f'{ATOM}title')))
        desc = strip_markup(text_at(item, ('description', f'{ATOM}summary', f'{ATOM}content', f'{CONTENT}encoded')))
        source_link = text_at(item, ('link',))
        if not source_link:
            for el in item.findall(f'{ATOM}link'):
                if el.get('rel', 'alternate') == 'alternate':
                    source_link = el.get('href', '')
                    break
        stamp = date_parse(text_at(item, ('pubDate', f'{DC}date', f'{ATOM}published', f'{ATOM}updated')))
        if not (title and desc and stamp and https(source_link)):
            continue
        if stamp > NOW + timedelta(hours=2) or stamp < NOW - timedelta(days=max_days):
            continue
        if len(title) < 18 or len(desc) < 50:
            continue
        if re.search(r'\b(sponsored|advertorial|partner content|horoscope|zodiac|quiz)\b', title, re.I):
            continue
        if re.search(r'\b(opinion|advertisement|sponsored)\b', title, re.I):
            continue  # Daily news, not unlabelled opinion or promotion
        # This is source-supplied feed text, not a reconstructed full article.
        preview = desc[:450].rsplit(' ', 1)[0] if len(desc) > 450 else desc
        output.append({'category': category, 'publisher': publisher, 'title': title,
                       'lede': preview.strip(), 'link': source_link, 'date': stamp,
                       'images': image_refs(item, publisher, source_link)})
    print(f'OK {publisher} / {category}: {len(output)} fresh entries', flush=True)
    return output

def words(title):
    stop = {'the','and','for','from','with','that','this','after','into','about','says','will','have','has','are','was','ada','yang','dan','untuk','dari','pada','dengan','akan','telah','jadi','ini','itu','di','ke','of','to','a','in','on','by','as','at','an','is'}
    return {w for w in re.findall(r'[a-z0-9]+', title.casefold()) if len(w) > 2 and w not in stop}

def likeness(a, b):
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    overlap = len(wa & wb)
    return overlap / len(wa | wb) if overlap >= 3 else 0.0

def importance(item):
    age = max(0, (NOW - item['date']).total_seconds() / 3600)
    value = max(0, 40 - age / 4)
    headline = item['title'].lower()
    hard_news = ('government','president','parliament','court','policy','flood','earthquake',
                 'election','budget','inflation','investigation','security','disaster','transport',
                 'jakarta','kebijakan','presiden','pemerintah','banjir','gempa','anggaran',
                 'kebakaran','ekonomi','pengadilan','dpr','mrt','transjakarta')
    value += min(18, sum(6 for word in hard_news if word in headline))
    if item['category'] in {'CREATIVE', 'ART & CULTURE', 'MUSIC & POP CULTURE', 'GAMING & TECH'}:
        news_signal = ('launch','open','announce','release','unveil','exhibition','festival',
                       'museum','album','concert','studio','award','campaign','installation',
                       'luncur','rilis','gelar','pameran')
        value += min(12, sum(4 for word in news_signal if word in headline))
    return value

def select(items):
    items.sort(key=lambda x: (importance(x), x['date']), reverse=True)
    selected = []
    by_link = set()
    source_counts = {}
    extras = {}  # published articles about similar topics, with actual links
    def add(item):
        url = item['link'].split('#', 1)[0].rstrip('/')
        if url in by_link:
            return False
        for existing in selected:
            if likeness(item['title'], existing['title']) >= 0.75:
                if item['publisher'] != existing['publisher']:
                    extras.setdefault(existing['link'], []).append(item)
                by_link.add(url)
                return False
        if source_counts.get(item['publisher'], 0) >= 10:
            return False
        selected.append(item)
        source_counts[item['publisher']] = source_counts.get(item['publisher'], 0) + 1
        by_link.add(url)
        return True
    for category, cap in TARGETS:
        count = 0
        for item in items:
            if item['category'] == category and add(item):
                count += 1
                if count == cap:
                    break
    if len(selected) < 24:
        for item in items:
            if len(selected) == MAX_STORIES:
                break
            add(item)
    # Related reports might arrive after selection. Link them only at high confidence.
    for story in selected:
        matches = extras.get(story['link'], [])
        for item in items:
            if item['link'] == story['link'] or item['publisher'] == story['publisher']:
                continue
            if likeness(story['title'], item['title']) >= 0.75:
                matches.append(item)
        seen = set()
        story['related'] = []
        for x in matches:
            if x['link'] not in seen and x['link'] != story['link']:
                seen.add(x['link'])
                story['related'].append(x)
            if len(story['related']) >= 3:
                break
    return selected[:MAX_STORIES]

def to_story(item, idx):
    dt = item['date'].astimezone(LOCAL).strftime('%d %b %Y · %H:%M WIB')
    link = item['link']
    cards = [{
        'side': 'left', 'type': 'ORIGINAL SOURCE', 'title': 'Where this report comes from',
        'body': f'{item["publisher"]} published this report on {dt}. The original headline and source link are preserved.',
        'color': 'purple', 'sources': [{'label': 'Open the publisher report', 'url': link}],
    }]
    related = item.get('related', [])
    if related:
        cards.append({
            'side': 'right', 'type': 'OTHER COVERAGE', 'title': 'Other reporting on this development',
            'body': 'These independently published articles have closely matching headlines. Read them to compare reporting; matching topics do not guarantee identical findings.',
            'color': 'lime',
            'sources': [{'label': f'{x["publisher"]}: {x["title"][:62]}', 'url': x['link']} for x in related],
        })
    return {
        'id': 'source-' + hashlib.sha256(link.encode()).hexdigest()[:16],
        'category': item['category'], 'title': item['title'], 'lede': item['lede'],
        'source_name': item['publisher'], 'source_url': link,
        'published_at': dt, 'published_iso': item['date'].isoformat(),
        'feed_preview': True, 'sections': [], 'cards': cards, 'images': item['images'],
    }

def main():
    print('THE SCROLL: free publisher feeds, no paid AI API', flush=True)
    candidates = []
    successes = 0
    with ThreadPoolExecutor(max_workers=9) as pool:
        fs = [pool.submit(feed_read, spec) for spec in FEEDS]
        for future in as_completed(fs):
            group = future.result()
            if group:
                successes += 1
                candidates.extend(group)
    stories = select(candidates)
    print(f'Read {len(candidates)} articles from {successes}/{len(FEEDS)} working feeds; selected {len(stories)}.', flush=True)
    if len(stories) < MIN_STORIES:
        print(f'Not enough trustworthy recent entries ({len(stories)} < {MIN_STORIES}); previous edition preserved.', flush=True)
        if not OUT.exists():
            raise SystemExit('No existing edition and too few working feeds')
        return
    payload = {
        'date': NOW.astimezone(LOCAL).strftime('%Y-%m-%d'),
        'updated_at': NOW.astimezone(LOCAL).isoformat(timespec='seconds'),
        'demo': False, 'feed_based': True,
        'intro': ('THE SCROLL selects real publisher reports. The website shows the original headline and RSS-provided preview; '
                  'full articles and updates remain on the linked publisher sites. No AI rewriting or invented context.'),
        'stories': [to_story(x, i + 1) for i, x in enumerate(stories)],
    }
    temp = OUT.with_name('news.json.tmp')
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    json.loads(temp.read_text(encoding='utf-8'))
    temp.replace(OUT)
    print(f'Published {len(payload["stories"])} source-linked news entries for {payload["date"]}', flush=True)

if __name__ == '__main__':
    main()
