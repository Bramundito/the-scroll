#!/usr/bin/env python3
"""THE SCROLL V4: hot news + evergreen features + publisher article images.
No AI API, social login, or paid services. Source-linked publisher previews and images.
Candidate feeds are best-effort: unavailable/invalid feeds are skipped.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode, urljoin, unquote
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from threading import Lock
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from collections import Counter
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().with_name('news.json')
NOW = datetime.now(timezone.utc)
LOCAL = ZoneInfo('Asia/Jakarta')
TARGET = 25
MIN_STORIES = 8
HOT_HOURS = 72
FEATURE_YEARS = 3  # look back roughly three years; extend if desired
FEATURE_HOURS = FEATURE_YEARS * 366 * 24
ARCHIVE_PER_PAGE = 18
# Prefer substantive evergreen discoveries, not breaking-news freshness.
FEATURE_WEIGHTS = {'relevance': 35, 'originality': 30, 'culture': 25, 'feature_depth': 10}

# Editorial targets, not fill quotas. Change these to adjust the feed.
MIX = {'essential': .20, 'personal': .65, 'discovery': .15}
# Keyword/source proxies, not human editorial judgments or measured popularity.
WEIGHTS = {'relevance': 35, 'originality': 25, 'culture': 20, 'freshness': 15, 'popularity': 5}
ATOM = '{http://www.w3.org/2005/Atom}'
MEDIA = '{http://search.yahoo.com/mrss/}'
DC = '{http://purl.org/dc/elements/1.1/}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}'

# (lane, category, publisher, feed URL, specialist affinity 0-1).
# Includes existing feeds plus candidate specialist feeds; live availability varies.
FEEDS = [
 ('essential','INDONESIA','ANTARA English','https://en.antaranews.com/rss/latest-news.xml',0),
 ('essential','INDONESIA','ANTARA News','https://www.antaranews.com/rss/top-news.xml',0),
 ('essential','INDONESIA','ANTARA News','https://www.antaranews.com/rss/ekonomi.xml',0),
 ('essential','JAKARTA','ANTARA News','https://www.antaranews.com/rss/metro.xml',0),
 ('essential','WORLD','BBC News','https://feeds.bbci.co.uk/news/world/rss.xml',0),
 ('essential','WORLD','The Guardian','https://www.theguardian.com/world/rss',0),
 ('essential','WORLD','BBC News','https://feeds.bbci.co.uk/news/business/rss.xml',0),
 ('personal','CREATIVE','Creative Boom','https://www.creativeboom.com/feed/',.95),
 ('personal','CREATIVE',"It's Nice That",'https://feeds2.feedburner.com/itsnicethat/SlXC',.95),
 ('personal','CREATIVE','Designboom','https://www.designboom.com/feed/',.85),
 ('personal','ART & CULTURE','Colossal','https://www.thisiscolossal.com/feed/',.95),
 ('personal','CREATIVE','Dezeen','https://www.dezeen.com/design/feed/',.80),
 ('personal','CREATIVE','Campaign Brief Asia','https://campaignbriefasia.com/feed/',.95),
 ('personal','CREATIVE','Event Marketer','https://www.eventmarketer.com/feed/',.95),
 ('personal','CREATIVE','The Dieline','https://thedieline.com/feed/',.85),
 ('personal','ART & CULTURE','Whiteboard Journal','https://www.whiteboardjournal.com/feed/',.95),
 ('personal','ART & CULTURE','USS Feed','https://ussfeed.com/feed/',.75),
 ('personal','ART & CULTURE','Manual Jakarta','https://manual.co.id/feed/',.85),
 ('personal','ART & CULTURE','The Guardian','https://www.theguardian.com/artanddesign/rss',.65),
 ('personal','ART & CULTURE','ANTARA News','https://www.antaranews.com/rss/lifestyle.xml',.25),
 ('personal','MUSIC & POP CULTURE','Pitchfork','https://pitchfork.com/rss/news/',.80),
 ('personal','MUSIC & POP CULTURE','Mixmag','https://mixmag.net/rss-category/news',.90),
 ('personal','MUSIC & POP CULTURE','MusicRadar','https://www.musicradar.com/feeds.xml',.85),
 ('personal','MUSIC & POP CULTURE','Stereogum','https://www.stereogum.com/feed/',.80),
 ('personal','MUSIC & POP CULTURE','The Guardian','https://www.theguardian.com/music/rss',.60),
 ('personal','MUSIC & POP CULTURE','ANTARA News','https://www.antaranews.com/rss/hiburan.xml',.25),
 ('personal','GAMING & TECH','GamesIndustry.biz','https://www.gamesindustry.biz/rss/gamesindustry_news_feed.rss',.55),
 ('discovery','CULTURE & DISCOVERY','VICE','https://www.vice.com/en/feed/',.70),
 ('discovery','CULTURE & DISCOVERY','The Guardian','https://www.theguardian.com/lifeandstyle/rss',.25),
 ('discovery','SCIENCE & DISCOVERY','BBC News','https://feeds.bbci.co.uk/news/science_and_environment/rss.xml',.35),
 ('discovery','SCIENCE & DISCOVERY','Ars Technica','https://feeds.arstechnica.com/arstechnica/index',.30),
]

# Candidate public WordPress archives. The APIs may be disabled, blocked, or
# return no articles. We test at runtime and skip failures. No credentials.
# Non-WordPress publishers remain in the RSS pool; no arbitrary scraping.
ARCHIVES = [
 ('personal','CREATIVE','Designboom','https://www.designboom.com',.85),
 ('personal','ART & CULTURE','Colossal','https://www.thisiscolossal.com',.95),
 ('personal','CREATIVE','Campaign Brief Asia','https://campaignbriefasia.com',.95),
 ('personal','CREATIVE','The Dieline','https://thedieline.com',.85),
 ('personal','CREATIVE','Event Marketer','https://www.eventmarketer.com',.95),
 ('personal','ART & CULTURE','Whiteboard Journal','https://www.whiteboardjournal.com',.95),
 ('personal','ART & CULTURE','Manual Jakarta','https://manual.co.id',.85),
 ('personal','ART & CULTURE','USS Feed','https://ussfeed.com',.75),
 ('personal','MUSIC & POP CULTURE','Stereogum','https://www.stereogum.com',.80),
 ('discovery','CULTURE & DISCOVERY','VICE','https://www.vice.com',.70),
 ('discovery','SCIENCE & DISCOVERY','Ars Technica','https://arstechnica.com',.45),
]
# These are evidence proxies, not proof that a story is a feature.
FEATURE_SIGNALS = ('how','why','inside','behind the scenes','making of','interview','profile','retrospective','documentary','case study','explores','exploring','process','technique','craft','story behind','history','archives','transformed','installation','immersive','interactive','artwork','design','recording','sampling','subculture','community','wawancara','sejarah','proses','di balik','karya','eksperimen')
EXPIRING_SIGNALS = ('tickets on sale','buy tickets','this weekend','next week','opens tomorrow','coming soon','pre-order','preorder','lineup announced','announces tour','release date','event schedule','registration','daftar sekarang','tiket','jadwal','promo','coming to','to open','set to open','will open','will release','announces','announced','upcoming','nominees','nominations','chart','box office','recap today','breaking','live updates','price cut','discount','award winners','rumor','rumour')

CREATIVE = ('brand activation','experiential','immersive','installation','interactive','projection mapping','scenography','stage design','festival design','public art','artwork','exhibition','museum','visual identity','graphic design','creative direction','illustration','typography','photography','animation','motion design','art direction','campaign','art collective','pameran','seni rupa','instalasi','aktivasi','desain','karya seni')
MUSIC = ('electronic music','music production','music producer','sampling','synthesizer','synth','sound design','recording studio','live performance','album','music video','dj set','soundtrack','remix','club culture','festival','concert','indie','experimental music','musisi','konser','musik elektronik','produser musik')
CULTURE = ('subculture','independent artist','emerging artist','creative community','community art','documentary','film festival','cinema','independent film','video game','game design','internet culture','fashion show','runway','jakarta','indonesia','komunitas','budaya','film','seniman')
ORIGINAL = ('transforms','turns into','built','creates','designed','reimagines','interactive','immersive','unusual','experiment','first-ever','invention','installation','collaboration','responds to','sound design','behind the scenes','making of','recycled','handmade','craft','eksperimen','kolaborasi','inovasi')
DISCOVERY = ('discovery','discovered','unusual','unexpected','subculture','researchers','archaeology','architecture','community','phenomenon','invention','new species','documentary','internet culture','culture','creative','art','music','found','penemuan','budaya')
ESSENTIAL = ('earthquake','flood','disaster','evacuation','public transport','transjakarta','mrt','lrt','commuter','minimum wage','inflation','interest rate','budget','law passed','court ruling','earthquake','election result','ceasefire','war','sanctions','trade agreement','power outage','water supply','public health','banjir','gempa','upah minimum','ump','umk','transportasi','kebijakan','undang-undang','putusan','bencana','kebakaran','harga pangan','pajak','rupiah','resmi','parliament','president','election','government','policy','regulation','economy','minister')
LOW_VALUE = ('sponsored','advertorial','partner content','horoscope','zodiac','black friday','coupon','discount code','shopping deals','best deals','celebrity gossip','dating rumors','box office predictions','chart rankings','daily horoscope','weton','ramalan','promo diskon','opinion:','opini:')
ROUTINE = ('says','urges','calls for','hopes','vows','pledges','responds to','reacts to','komentar','menanggapi','berharap','mengimbau','menyebut','mendorong','menegaskan')

class FeedHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]; self.links=[]; self.images=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style'): self.skip+=1
        if tag=='a' and a.get('href'): self.links.append(a['href'])
        if tag=='img' and a.get('src'): self.images.append((a['src'],a.get('alt','')))
    def handle_endtag(self,tag):
        if tag in ('script','style') and self.skip: self.skip-=1
    def handle_data(self,data):
        if not self.skip: self.parts.append(data)

def parse_html(value):
    p=FeedHTML()
    try: p.feed(unescape(value or ''))
    except Exception: pass
    return p

def plain(value):
    return re.sub(r'\s+',' ',unescape(' '.join(parse_html(value).parts))).strip()

def text_at(node,*paths):
    for path in paths:
        el=node.find(path)
        if el is not None and el.text and el.text.strip(): return el.text.strip()
    return ''

def https(url):
    try:
        p=urlparse(url)
        return p.scheme=='https' and bool(p.hostname) and not p.username and not p.password
    except (ValueError,TypeError): return False

def canonical(url):
    try:
        p=urlsplit(url)
        q=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid','mc_cid','mc_eid')]
        return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip('/'),urlencode(sorted(q)),''))
    except ValueError: return url

def date_parse(raw):
    try: dt=parsedate_to_datetime(raw)
    except (ValueError,TypeError,IndexError):
        try: dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
        except (ValueError,TypeError,AttributeError): return None
    if not dt: return None
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def hits(text,terms):
    return sum(bool(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',text,re.I)) for t in terms)

def social_links(html):
    # Preserve only links explicitly supplied in publisher material; no scraping.
    out=[]; seen=set()
    for url in parse_html(html).links:
        if not https(url): continue
        p=urlsplit(url); host=(p.hostname or '').lower().removeprefix('www.')
        if ((host in ('instagram.com',) and re.match(r'^/(p|reel|tv)/[^/]+',p.path)) or
            (host in ('x.com','twitter.com') and re.search(r'/status/\d+',p.path)) or
            (host in ('youtube.com','youtu.be') and (host=='youtu.be' or p.path.startswith(('/watch','/shorts/')))) or
            (host=='reddit.com' and '/comments/' in p.path)):
            u=canonical(url)
            if u not in seen: seen.add(u); out.append(u)
    return out[:4]

def image_refs(item,publisher,link):
    candidates=[]
    for el in item.iter():
        if el.tag in (MEDIA+'thumbnail',MEDIA+'content','enclosure'):
            typ=el.get('type','').lower(); medium=el.get('medium','').lower()
            if typ and not typ.startswith('image/'): continue
            if medium and medium!='image': continue
            if el.tag=='enclosure' and not typ.startswith('image/'): continue
            u=el.get('url','')
            if https(u): candidates.append((u,text_at(el,MEDIA+'credit') or publisher))
        elif el.tag==ATOM+'link' and el.get('rel')=='enclosure' and el.get('type','').startswith('image/') and https(el.get('href','')):
            candidates.append((el.get('href'),publisher))
    out=[]; seen=set()
    for u,credit in candidates:
        # Many feeds list the same image in different resolutions.
        key=urlsplit(u).netloc+re.sub(r'/\d{2,4}(?=/)','/{size}',urlsplit(u).path)
        if key in seen: continue
        seen.add(key)
        out.append({'url':u,'caption':'Publisher-supplied feed image; see the source for its original context.','credit':credit,'credit_url':link,'kind':'feed'})
        if len(out)==3: break
    return out

# V4: article-level image discovery, only from the original publisher's
# public feed / article metadata and editorial image containers.
IMAGE_LIMIT = 3
IMAGE_AGENT = 'TheScrollReader/4.0 (+personal RSS reader)'
IMAGE_BAD = re.compile(r'(?:^|[\W_])(?:logo|favicon|avatar|sprite|placeholder|spacer|pixel|tracking|gravatar|newsletter|advertisement|sponsor-logo|social-icon|icon|badge|default-share|default-social)(?:$|[\W_])', re.I)
BLOCK_SCOPE = re.compile(r'(?:^|[\s_-])(?:related|recommended|recommendations|trending|sidebar|footer|newsletter|advertisement|advertising|advert|ads|comments|author-bio|masthead|navigation|promo|cookie|recirculation|more-stories|read-more)(?:$|[\s_-])',re.I)
BODY_SCOPE = re.compile(r'(?:article|entry|post|story)[\s_-]*(?:body|content|gallery|text|main|image|media|figure)|articlebody|articlecontent|storybody|entrycontent|postcontent|wp-block-gallery|wp-block-image',re.I)
VOID_TAGS = set('area base br col embed hr img input link meta param source track wbr'.split())

def image_url(raw, base):
    if not isinstance(raw,str) or not raw.strip(): return ''
    try: u=urljoin(base,unescape(raw.strip()))
    except (ValueError,TypeError): return ''
    if not https(u): return ''
    p=urlsplit(u)
    if p.path.lower().endswith(('.svg','.gif','.ico','.mp4','.webm','.pdf')): return ''
    if IMAGE_BAD.search(unquote(p.path)): return ''
    return u.split('#',1)[0]

def image_key(url):
    p=urlsplit(url)
    path=unquote(p.path).lower()
    # WordPress generated thumbnails, Guardian/BBC dimensions, common CDN crops.
    path=re.sub(r'-\d{2,5}x\d{2,5}(?=\.[a-z0-9]+$)','',path)
    path=re.sub(r'/(?:\d{2,5}x\d{2,5}|\d{2,4})(?=/)','/{size}',path)
    path=re.sub(r'/(?:w|h|c|q|f|dpr)_[^/]+(?=/)','',path)
    path=re.sub(r'/\d+:\d+/','/',path)
    # Ignore resizing/format/quality parameters, retain identifying parameters.
    resize={'w','h','width','height','size','resize','crop','fit','quality','q','format','fm','auto','dpr','rect','s','ixlib','v','f','aspect','ar','orient','trim'}
    q=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k.lower() not in resize and not k.lower().startswith('utm_')]
    return (p.netloc.lower(),path,urlencode(sorted(q)))

def make_image(u,publisher,link,caption='',credit=''):
    return {'url':u,'caption':plain(caption)[:280] or 'Image from the original publisher’s article; see the source for its context.', 'credit':plain(credit)[:160] or publisher+' (publisher source; original credit at source)', 'credit_url':link,'kind':'feed'}

def best_srcset(raw,base):
    options=[]
    for candidate in (raw or '').split(','):
        bits=candidate.strip().split()
        if not bits: continue
        u=image_url(bits[0],base)
        if not u: continue
        try:
            suffix=bits[1] if len(bits)>1 else '1000w'
            weight=float(suffix[:-1])*(1000 if suffix.endswith('x') else 1)
        except (ValueError,IndexError): weight=1000
        options.append((weight,u))
    if not options: return ''
    # Prefer high-res images but avoid huge 4K originals when a useful size exists.
    options.sort(key=lambda x:(x[0]>=900, -abs(x[0]-1500)),reverse=True)
    return options[0][1]

class ArticleImages(HTMLParser):
    def __init__(self,base,publisher,feed_fragment=False):
        super().__init__(convert_charrefs=True)
        self.base=base; self.publisher=publisher; self.fragment=feed_fragment
        self.stack=[]; self.hero=[]; self.body=[]; self.jsonld=[]; self.capture=None
        self.figures=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); mark=' '.join([a.get('class') or '',a.get('id') or '',a.get('role') or ''])
        parent=self.stack[-1] if self.stack else ('',self.fragment,False,False)
        blocked=parent[2] or tag in ('aside','nav','footer','header','noscript') or bool(BLOCK_SCOPE.search(mark))
        inside=parent[1] or tag=='article' or bool(BODY_SCOPE.search(mark))
        main=parent[3] or tag=='main' or a.get('role')=='main'
        if tag not in VOID_TAGS: self.stack.append((tag,inside,blocked,main))
        if tag=='script' and (a.get('type') or '').lower()=='application/ld+json': self.capture=[]
        if tag=='meta':
            key=(a.get('property') or a.get('name') or a.get('itemprop') or '').lower()
            if key in ('og:image','og:image:url','og:image:secure_url','twitter:image','twitter:image:src'):
                u=image_url(a.get('content'),self.base)
                if u: self.hero.append(make_image(u,self.publisher,self.base))
            elif key in ('og:image:alt','twitter:image:alt') and self.hero and a.get('content'):
                self.hero[-1]['caption']=plain(a['content'])[:280]
        if tag=='figure' and not blocked and (inside or main): self.figures.append({'images':[],'caption':[],'capturing':False})
        if tag=='figcaption' and self.figures: self.figures[-1]['capturing']=True
        if tag not in ('img','source') or blocked or not (inside or (main and self.figures)): return
        if tag=='source' and not any(s[0]=='picture' for s in self.stack): return
        alt=a.get('alt') or a.get('title') or ''
        if IMAGE_BAD.search(mark+' '+alt): return
        for k,minimum in [('width',240),('height',130)]:
            dim=re.fullmatch(r'\s*(\d+)(?:px)?\s*',a.get(k) or '')
            if dim and 0<int(dim.group(1))<minimum: return
        u=''
        for attr in ('data-srcset','data-lazy-srcset','srcset'):
            u=best_srcset(a.get(attr),self.base)
            if u: break
        if not u:
            for attr in ('data-full-src','data-original','data-lazy-src','data-src','data-image','src'):
                u=image_url(a.get(attr),self.base)
                if u: break
        if not u: return
        img=make_image(u,self.publisher,self.base,alt)
        if self.figures: self.figures[-1]['images'].append(img)
        else: self.body.append(img)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID_TAGS: self.handle_endtag(tag)
    def handle_data(self,data):
        if self.capture is not None: self.capture.append(data)
        if self.figures and self.figures[-1]['capturing']: self.figures[-1]['caption'].append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self.capture is not None:
            try: self.jsonld.append(json.loads(''.join(self.capture)))
            except (ValueError,TypeError): pass
            self.capture=None
        if tag=='figcaption' and self.figures: self.figures[-1]['capturing']=False
        if tag=='figure' and self.figures:
            f=self.figures.pop(); caption=plain(' '.join(f['caption']))[:280]
            for im in f['images']:
                if caption: im['caption']=caption
                self.body.append(im)
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:]; break
    def structured(self):
        result=[]
        def walk(value):
            if isinstance(value,list):
                for v in value: walk(v)
            elif isinstance(value,dict):
                types=value.get('@type',[]); types=[types] if isinstance(types,str) else types
                if isinstance(types,list) and any(t in ('Article','NewsArticle','BlogPosting','ReportageNewsArticle','AnalysisNewsArticle','ReviewNewsArticle','TechArticle','CreativeWork') for t in types):
                    imgs=value.get('image',[]); imgs=imgs if isinstance(imgs,list) else [imgs]
                    for pic in imgs:
                        raw=pic.get('contentUrl') or pic.get('url') if isinstance(pic,dict) else pic
                        u=image_url(raw,self.base)
                        if u:
                            caption=pic.get('caption','') if isinstance(pic,dict) else ''
                            credit=pic.get('creditText','') if isinstance(pic,dict) else ''
                            result.append(make_image(u,self.publisher,self.base,caption if isinstance(caption,str) else '',credit if isinstance(credit,str) else ''))
                # Restrict traversal to top-level graph/article entries, not unrelated recommendations.
                for k in ('@graph','mainEntity','mainEntityOfPage'):
                    if isinstance(value.get(k),(dict,list)): walk(value[k])
        for v in self.jsonld: walk(v)
        return result
    def candidates(self):
        # Metadata hero then editorial body, then structured variants. No sidebar pictures.
        return self.hero+self.body+self.structured()

def merge_images(*groups,limit=IMAGE_LIMIT):
    seen=set(); result=[]
    for group in groups:
        for im in group or []:
            if not isinstance(im,dict): continue
            raw=im.get('url',''); u=image_url(raw,im.get('credit_url',''))
            if not u: continue
            key=image_key(u)
            if key in seen: continue
            seen.add(key); result.append(dict(im,url=u))
            if len(result)>=limit: return result
    return result

# Respect robots.txt for article-page collection. No login/paywall bypass,
# JS rendering, image search scraping, or access to arbitrary social accounts.
_robots_cache={}; _robots_lock=Lock()
def page_allowed(url):
    p=urlsplit(url); origin=f'{p.scheme}://{p.netloc}'
    with _robots_lock:
        if origin in _robots_cache: rules=_robots_cache[origin]
        else:
            rules=None
            try:
                request=Request(origin+'/robots.txt',headers={'User-Agent':IMAGE_AGENT,'Accept':'text/plain'})
                with urlopen(request,timeout=5) as res:
                    body=res.read(200_001)
                    if len(body)<=200_000:
                        rules=RobotFileParser(); rules.parse(body.decode('utf-8','replace').splitlines())
            except HTTPError as e:
                if e.code in (404,410): rules=True
            except Exception: pass
            _robots_cache[origin]=rules
    return rules is True or (rules is not None and rules.can_fetch('TheScrollReader',url))

def article_images(url,publisher):
    if not https(url) or not page_allowed(url): return []
    try:
        request=Request(url,headers={'User-Agent':IMAGE_AGENT,'Accept':'text/html,application/xhtml+xml'})
        with urlopen(request,timeout=10) as res:
            final=res.geturl()
            if not https(final): return []
            # Do not follow cross-site publisher redirects to a new source for image selection.
            if urlsplit(final).hostname!=urlsplit(url).hostname and not page_allowed(final): return []
            if 'html' not in res.headers.get('Content-Type','').lower(): return []
            html=res.read(3_000_000).decode(res.headers.get_content_charset() or 'utf-8','replace')
        parser=ArticleImages(final,publisher); parser.feed(html); parser.close()
        return merge_images(parser.candidates(),limit=12)
    except Exception as e:
        print(f'IMAGE PAGE SKIP {publisher}: {e}',flush=True); return []

def enrich_images(items):
    def one(x):
        existing=merge_images(x.get('images',[]))
        if len(existing)>=IMAGE_LIMIT: return existing
        link=x.get('link') or x.get('source_url') or ''
        publisher=x.get('publisher') or x.get('source_name') or 'Original publisher'
        # The publisher page often provides a full gallery when the feed exposes one thumbnail.
        discovered=article_images(link,publisher)
        return merge_images(discovered,existing)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(one,x):x for x in items}
        for future in as_completed(futures):
            item=futures[future]
            try: item['images']=future.result()
            except Exception as e:
                print(f'IMAGE SKIP {item.get("title","")}: {e}',flush=True)
                item['images']=merge_images(item.get('images',[]))
    counts=Counter(len(x.get('images',[])) for x in items)
    print(f'IMAGE COVERAGE: {dict(sorted(counts.items()))} (image count: story count)',flush=True)


def feed_read(spec):
    lane,category,publisher,url,affinity=spec
    try:
        req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; TheScrollReader/2.0; RSS reader)','Accept':'application/rss+xml,application/atom+xml,application/xml,text/xml;q=0.8'})
        with urlopen(req,timeout=14) as res: blob=res.read(2_000_001)
        if len(blob)>2_000_000: raise ValueError('oversized feed')
        root=ET.fromstring(blob)
    except Exception as e:
        print(f'SKIP {publisher}: {e}',flush=True); return []
    entries=root.findall('./channel/item') or root.findall(ATOM+'entry')
    output=[]
    for item in entries[:70]:
        title=plain(text_at(item,'title',ATOM+'title'))
        desc=text_at(item,'description',ATOM+'summary',ATOM+'content',CONTENT+'encoded')
        content=text_at(item,CONTENT+'encoded',ATOM+'content') or desc
        preview=plain(desc)
        link=text_at(item,'link')
        if not link:
            for el in item.findall(ATOM+'link'):
                if el.get('rel','alternate')=='alternate': link=el.get('href',''); break
        stamp=date_parse(text_at(item,'pubDate',DC+'date',ATOM+'published',ATOM+'updated'))
        if not (title and len(preview)>=45 and https(link) and stamp): continue
        age=(NOW-stamp).total_seconds()/3600
        if age < -2 or age > (HOT_HOURS if lane=='essential' else FEATURE_HOURS): continue
        if hits(title,LOW_VALUE): continue
        # Do not republish full feed bodies. Preserve a source-linked excerpt.
        preview=preview if len(preview)<=450 else preview[:450].rsplit(' ',1)[0]+'…'
        fragment=ArticleImages(link,publisher,feed_fragment=True)
        try: fragment.feed(content); fragment.close()
        except Exception: pass
        images=merge_images(image_refs(item,publisher,link),fragment.candidates())
        output.append(dict(lane=lane,category=category,publisher=publisher,affinity=affinity,title=title,lede=preview,link=link,date=stamp,images=images,social=social_links(content+' '+desc)))
    print(f'OK {publisher} [{category}]: {len(output)} eligible feed items',flush=True)
    return output


def archive_windows(publisher):
    """Two rotating historical months: one in past year and one 1-3 years ago."""
    today=NOW.astimezone(LOCAL).date()
    salt=int(hashlib.sha256(publisher.encode()).hexdigest()[:8],16)
    for offset in (1+(today.toordinal()+salt)%12, 13+(today.toordinal()+salt)%max(1,FEATURE_YEARS*12-12)):
        month_index=today.year*12+today.month-1-offset
        year,month=divmod(month_index,12)
        start=datetime(year,month+1,1,tzinfo=timezone.utc)
        ny,nm=divmod(month_index+1,12)
        end=datetime(ny,nm+1,1,tzinfo=timezone.utc)-timedelta(seconds=1)
        yield start,end

def get_json(url):
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; TheScrollReader/3.0; personal reader)','Accept':'application/json'})
    with urlopen(req,timeout=10) as res: blob=res.read(2_000_001)
    if len(blob)>2_000_000: raise ValueError('oversized archive response')
    return json.loads(blob)

def wp_rendered(post,key):
    value=post.get(key,{})
    return value.get('rendered','') if isinstance(value,dict) else ''

def archive_read(spec):
    lane,category,publisher,base,affinity=spec
    results=[]
    for start,end in archive_windows(publisher):
        query=urlencode({'after':start.strftime('%Y-%m-%dT%H:%M:%S'),'before':end.strftime('%Y-%m-%dT%H:%M:%S'),'per_page':ARCHIVE_PER_PAGE,'orderby':'date','order':'desc','_fields':'date,date_gmt,link,title,excerpt,_links,_embedded','_embed':'wp:featuredmedia'})
        try:
            posts=get_json(base+'/wp-json/wp/v2/posts?'+query)
            if not isinstance(posts,list): raise ValueError('not a public posts list')
        except Exception as e:
            print(f'SKIP ARCHIVE {publisher}: {e}',flush=True)
            # WordPress archives sometimes expose dated RSS instead of REST.
            # Only accept entries genuinely published in the requested month.
            fallback=base+'/?'+urlencode({'m':start.strftime('%Y%m'),'feed':'rss2'})
            old=feed_read((lane,category,publisher,fallback,affinity))
            results.extend(dict(x,archive=True) for x in old if start-timedelta(days=1)<=x['date']<=end+timedelta(days=1))
            continue
        for post in posts:
            if not isinstance(post,dict): continue
            title=plain(wp_rendered(post,'title'))
            desc=wp_rendered(post,'excerpt'); preview=plain(desc)
            link=post.get('link','')
            stamp=date_parse(post.get('date_gmt') or post.get('date'))
            if not (title and len(preview)>=45 and https(link) and stamp): continue
            # Verify the API really returned the requested historical interval.
            if not start-timedelta(days=1)<=stamp<=end+timedelta(days=1): continue
            if (NOW-stamp).total_seconds()/3600>FEATURE_HOURS or stamp>NOW: continue
            if hits(title,LOW_VALUE): continue
            preview=preview if len(preview)<=450 else preview[:450].rsplit(' ',1)[0]+'…'
            images=[]
            embedded=post.get('_embedded') or {}
            media=embedded.get('wp:featuredmedia',[]) if isinstance(embedded,dict) else []
            for pic in media[:3] if isinstance(media,list) else []:
                if not isinstance(pic,dict) or not https(pic.get('source_url','')): continue
                caption=plain(wp_rendered(pic,'caption')) or 'Featured image from the original publisher; see original article for context and credits.'
                credit_url=pic.get('link','')
                images.append({'url':pic['source_url'],'caption':caption,'credit':publisher+' (publisher source; see original credit)','credit_url':credit_url if https(credit_url) else link,'kind':'feed'})
            results.append(dict(lane=lane,category=category,publisher=publisher,affinity=affinity,title=title,lede=preview,link=link,date=stamp,images=images,social=social_links(desc),archive=True))
    print(f'ARCHIVE {publisher}: {len(results)} candidate posts',flush=True)
    return results

STOP=set('the and for from with that this after into about says will have has are was yang dan untuk dari pada dengan akan telah jadi ini itu di ke of to a in on by as at an is new'.split())
def words(text): return {w for w in re.findall(r'[^\W_]+',text.casefold()) if len(w)>2 and w not in STOP}
def similarity(a,b):
    wa,wb=words(a),words(b)
    if not wa or not wb: return 0
    inter=len(wa&wb)
    if inter<3: return 0
    return max(inter/len(wa|wb),.85*inter/min(len(wa),len(wb)))

def score(item):
    title=item['title'].lower(); text=title+' '+item['lede'].lower()
    age=max(0,(NOW-item['date']).total_seconds()/3600)
    fresh=max(0,1-age/HOT_HOURS)
    if item['lane']=='essential' and age>HOT_HOURS: return -1
    if item['lane']!='essential' and age>FEATURE_HOURS: return -1
    feature_hits=hits(text,FEATURE_SIGNALS)
    # Archived announcements, expired offers and forecasts aren't evergreen features.
    if item['lane']!='essential' and age>168 and (hits(title,EXPIRING_SIGNALS) or not feature_hits): return -1
    relevance=hits(text,CREATIVE)+hits(text,MUSIC)+hits(text,CULTURE)
    if item['lane']=='essential':
        impact=hits(title,ESSENTIAL)*2+hits(text,ESSENTIAL)
        if not impact: return -1
        return 45*min(impact/6,1)+20*fresh+10*(item['category']=='JAKARTA')-10*min(hits(title,ROUTINE),2)
    if item['lane']=='discovery':
        if not hits(text,DISCOVERY): return -1
        return 40*min(hits(text,DISCOVERY)/4,1)+25*min(hits(text,ORIGINAL)/3,1)+20*min(feature_hits/3,1)+15*item['affinity']-10*hits(title,ROUTINE)
    # Require creative/cultural signals, not just a specialist publisher's name.
    if relevance<1: return -1
    if not feature_hits and not hits(text,ORIGINAL): return -1
    rel=min(1,.5*item['affinity']+.5*min(relevance/4,1))
    original=min(hits(text,ORIGINAL)/3,1)
    culture=min((hits(text,CULTURE)+hits(text,MUSIC)+hits(text,CREATIVE))/5,1)
    # Popularity is not available from publisher feeds. Do not invent it.
    available=sum(FEATURE_WEIGHTS.values()) or 1
    depth=min(feature_hits/3,1)
    value=100*(FEATURE_WEIGHTS['relevance']*rel+FEATURE_WEIGHTS['originality']*original+FEATURE_WEIGHTS['culture']*culture+FEATURE_WEIGHTS['feature_depth']*depth)/available
    if hits(title,('gossip','rumor','rumour','chart','price cut','deal','discount')): value-=20
    if item['category']=='GAMING & TECH' and not hits(text,CREATIVE+MUSIC+('game design','soundtrack','video game','indie game','internet culture')): value-=15
    return value

def previous_urls():
    if not OUT.exists(): return []
    try:
        edition=json.loads(OUT.read_text(encoding='utf-8'))
        # Keep a bounded URL history in the edition itself: no additional workflow files.
        return list(dict.fromkeys([canonical(s['source_url']) for s in edition.get('stories',[]) if s.get('source_url')]+[canonical(x) for x in edition.get('seen_urls',[]) if isinstance(x,str)]))
    except (ValueError,OSError,TypeError): return []

def allocation(total=TARGET):
    raw={k:total*v/sum(MIX.values()) for k,v in MIX.items()}
    n={k:int(v) for k,v in raw.items()}
    for k in sorted(raw,key=lambda k:raw[k]-n[k],reverse=True)[:total-sum(n.values())]: n[k]+=1
    return n

def select(items,seen=None):
    seen=set(seen or [])
    all_items=sorted(items,key=lambda x:(score(x), x['date'] if x['lane']=='essential' else datetime.min.replace(tzinfo=timezone.utc), hashlib.sha256((NOW.astimezone(LOCAL).date().isoformat()+x['link']).encode()).hexdigest()),reverse=True)
    selected=[]; links=set(); counts=Counter(); categories=Counter(); related={}
    caps=allocation()
    thresholds={'essential':8,'personal':28,'discovery':24}
    def add(x):
        url=canonical(x['link'])
        if url in seen or url in links: return False
        if counts[x['publisher']]>=3: return False
        if x['lane']=='personal' and categories[x['category']]>=9: return False
        for y in selected:
            if similarity(x['title'],y['title'])>=.70:
                if x['publisher']!=y['publisher']: related.setdefault(y['link'],[]).append(x)
                return False
        selected.append(x); links.add(url); counts[x['publisher']]+=1; categories[x['category']]+=1
        return True
    # Allocate creative-first, then essentials and discovery. Display an interleaved feed.
    for lane in ('personal','essential','discovery'):
        used=0
        candidates=[x for x in all_items if x['lane']==lane and score(x)>=thresholds[lane]]
        if lane=='essential':
            # Try one national, one Jakarta, one global story before other essentials.
            for cat in ('INDONESIA','JAKARTA','WORLD'):
                if used>=caps[lane]: break
                for x in candidates:
                    if x['category']==cat and add(x): used+=1; break
        if lane!='essential':
            # Reserve up to a third of the feature lane for strong older pieces,
            # but release the space when there are no worthy archives.
            archive_goal=caps[lane]//3
            for x in candidates:
                if used>=archive_goal: break
                if (NOW-x['date']).total_seconds()>14*86400 and score(x)>=max(42,thresholds[lane]) and add(x): used+=1
        for x in candidates:
            if used>=caps[lane]: break
            if add(x): used+=1
    # Never backfill an empty creative lane with routine politics.
    for x in selected:
        matches=related.get(x['link'],[])+[y for y in all_items if y['publisher']!=x['publisher'] and canonical(y['link'])!=canonical(x['link']) and similarity(x['title'],y['title'])>=.78]
        x['related']=[]; used=set()
        for y in matches:
            u=canonical(y['link'])
            if u not in used: used.add(u); x['related'].append(y)
            if len(x['related'])>=3: break
    queues={k:[x for x in selected if x['lane']==k] for k in MIX}
    ordered=[]
    while any(queues.values()):
        for lane in ('personal','personal','essential','personal','discovery'):
            if queues[lane]: ordered.append(queues[lane].pop(0))
    return ordered

def to_story(x):
    dt=x['date'].astimezone(LOCAL).strftime('%d %b %Y · %H:%M WIB')
    cards=[]
    feature=x['lane']!='essential'
    archive=feature and (NOW-x['date']).total_seconds()>7*86400
    label='ARCHIVE FEATURE' if archive else ('FEATURE' if feature else 'HOT NEWS')
    if archive:
        cards.append({'side':'left','type':'FROM THE ARCHIVE','title':'Originally published '+x['date'].astimezone(LOCAL).strftime('%d %b %Y'),'body':'An older discovery selected for its subject, not a claim that this event is happening today. Check the original article for historical context and any subsequent changes.','color':'purple','bullets':[],'sources':[{'label':'Read original publication','url':x['link']}]})
    if x.get('related'):
        cards.append({'side':'right','type':'OTHER COVERAGE','title':'Related reporting','body':'These reports have similar headlines; compare the original articles before treating their claims as equivalent.','color':'lime','bullets':[],'sources':[{'label':y['publisher']+': '+y['title'],'url':y['link']} for y in x['related']]})
    if x.get('social'):
        cards.append({'side':'left','type':'SOCIAL LINKS','title':'Posts and videos linked by the publisher','body':'These links were supplied by the publisher. They are discovery leads, not independently verified claims.','color':'purple','bullets':[],'sources':[{'label':urlsplit(u).hostname+' · open original post','url':u} for u in x['social']]})
    return {'id':'source-'+hashlib.sha256(canonical(x['link']).encode()).hexdigest()[:16],'category':label+' · '+x['category'],'story_type':label.lower().replace(' ','_'),'title':x['title'],'lede':x['lede'],'source_name':x['publisher'],'source_url':x['link'],'published_at':dt,'published_iso':x['date'].isoformat(),'feed_preview':True,'sections':[],'cards':cards,'images':x['images']}

def main():
    candidates=[]; successes=0
    with ThreadPoolExecutor(max_workers=12) as pool:
        jobs=[pool.submit(feed_read,s) for s in FEEDS]+[pool.submit(archive_read,s) for s in ARCHIVES]
        for future in as_completed(jobs):
            try: result=future.result()
            except Exception as e:
                print(f'SKIP SOURCE JOB: {e}',flush=True); continue
            if result: successes+=1; candidates.extend(result)
    seen=previous_urls()
    stories=select(candidates,seen)
    print(f'Collected {len(candidates)} candidates from {successes}/{len(FEEDS)+len(ARCHIVES)} source jobs; selected {len(stories)}: {dict(Counter(x["lane"] for x in stories))}',flush=True)
    if len(stories)<MIN_STORIES:
        print('Too few eligible new stories. Keeping previous stories and refreshing their image galleries.',flush=True)
        if not OUT.exists(): raise SystemExit('No existing edition to preserve.')
        payload=json.loads(OUT.read_text(encoding='utf-8'))
        enrich_images(payload.get('stories',[]))
        payload['updated_at']=NOW.astimezone(LOCAL).isoformat(timespec='seconds')
        tmp=OUT.with_suffix('.json.tmp'); tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); tmp.replace(OUT)
        return
    enrich_images(stories)
    current=[canonical(x['link']) for x in stories]
    history=list(dict.fromkeys(current+seen))[:700]
    payload={'date':NOW.astimezone(LOCAL).strftime('%Y-%m-%d'),'updated_at':NOW.astimezone(LOCAL).isoformat(timespec='seconds'),'demo':False,'feed_based':True,'intro':'Hot news covers recent developments; creative and discovery features include older original publisher reports. Archive features retain their original publication dates. Read the linked articles for full reporting. Selection uses free source and keyword rules, not AI fact-checking.','seen_urls':history,'stories':[to_story(x) for x in stories]}
    tmp=OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    json.loads(tmp.read_text(encoding='utf-8')); tmp.replace(OUT)
    print('Published',len(stories),'stories.',flush=True)

if __name__=='__main__': main()
