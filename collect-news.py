        key=urlsplit(u).netloc+re.sub(r'/\d{2,4}(?=/)','/{size}',urlsplit(u).path)
        if key in seen: continue
        seen.add(key)
        out.append({'url':u,'caption':'Publisher-supplied feed image; see the source for its original context.','credit':credit,'credit_url':link,'kind':'feed'})
        if len(out)==3: break
    return out

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
        output.append(dict(lane=lane,category=category,publisher=publisher,affinity=affinity,title=title,lede=preview,link=link,date=stamp,images=image_refs(item,publisher,link),social=social_links(content+' '+desc)))
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
