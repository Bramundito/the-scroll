(() => {
'use strict';
const $ = (id) => document.getElementById(id);
const deck = $('newsDeck');
// Content is loaded exclusively from news.json.
// Do not embed stories in this file: new editions need no design changes.
let edition = null;
let stories = [];
let activeIndex = 0;
const gallerySlides = new Map();
let lastWheelChange = -Infinity;
let wheelAccumulator = 0;
let wheelDirection = 0;
let wheelIdleAt = 0;
let scrollRaf = false;

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = (v) => {try{const u=new URL(v);return u.protocol==='https:'?u.href:''}catch{return ''}};
const isColor = v => /^#[0-9a-fA-F]{6}$/.test(String(v || ''));
const palettes=[['#d3baff','#f2e9ff','#faf5ff'],['#aae6ff','#e7f7ff','#f1faff'],['#ffbfa1','#ffefe5','#fff7f1'],['#d7ef86','#f1facb','#fbfdef']];
const cardColors=['purple','yellow','lime','blue','coral'];
const icons={LOCATION:'⌖','TERM EXPLAINED':'Aa','OTHER COVERAGE':'≠','CROSS-CHECK':'≠','WHAT WOULD VERIFY IT?':'✓',CONTEXT:'↺','TIMELINE':'↗','BACKSTORY':'⌁','SOURCE':'↗','GLOSSARY':'Aa','WHY IT MATTERS':'✳'};

function normalize(s,i) {
  const p=palettes[i%palettes.length];
  const sections=Array.isArray(s.sections) ? s.sections.map(x=>({heading:String(x.heading||''),body:String(x.body||'')})).filter(x=>x.body.trim()) : [
    {heading:'The story',body:String(s.summary||'')},
    {heading:'The background',body:String(s.backstory||'')},
    {heading:'What happens next?',body:String(s.what_next||'')}
  ].filter(x=>x.body.trim());
  let cards = Array.isArray(s.cards) ? s.cards : Array.isArray(s.supporting_info) ? s.supporting_info : [];
  if (!cards.length) {
    cards = [
      {side:'left',type:'BACKGROUND',title:'What led here?',body:s.backstory||'',color:'purple'},
      {side:'left',type:'TERM OR DETAIL',title:'Worth knowing',body:(s.key_facts||[]).join(' • '),color:'yellow'},
      {side:'right',type:'WHY IT MATTERS',title:'The significance',body:s.why_it_matters||'',color:'lime'},
      {side:'right',type:'WHAT NEXT?',title:'Keep an eye on',body:s.what_next||'',color:'blue'},
    ].filter(x=>x.body);
  }
  return {
    ...s, title:String(s.title||'Untitled story'),category:String(s.category||'NEWS'),
    id:String(s.id || `story-${i+1}`), lede:String(s.lede || s.summary || ''), sections,
    source_name:String(s.source_name||'Source not provided'), source_url:safeUrl(s.source_url),
    published_at:String(s.published_at||''),feed_preview:Boolean(s.feed_preview), visual:String(s.visual||['art','city','music','games'][i%4]),
    images:Array.isArray(s.images)?s.images.slice(0,3).map(x=>({url:safeUrl(x.url),caption:String(x.caption||'Image supporting the story'),credit:String(x.credit||'Image source'),credit_url:safeUrl(x.credit_url),kind:String(x.kind||'context'),backup_url:safeUrl(x.backup_url)})).filter(x=>x.url):[],
    accent:isColor(s.accent)?s.accent:p[0],soft:isColor(s.soft)?s.soft:p[1],background:isColor(s.background)?s.background:p[2],
    cards:cards.slice(0,8).map((card,j)=>({
      side:card.side==='right'||card.placement==='right'?'right':'left',
      type:String(card.type || card.eyebrow || 'MORE CONTEXT').replace(/_/g,' '),
      title:String(card.title||'Useful context'),body:String(card.body||''),
      icon:String(card.icon||icons[card.type]||'✳'),bullets:Array.isArray(card.bullets)?card.bullets.slice(0,5):[],
      color:cardColors.includes(card.color)?card.color:cardColors[(i+j)%cardColors.length],
      sources:Array.isArray(card.sources)?card.sources.slice(0,3):[]
    }))
  };
}

function cardMarkup(card) {
  const list=card.bullets.length?`<ul>${card.bullets.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'';
  const links=card.sources.map(x=>{
    const u=safeUrl(x.url),label=esc(x.label||x.publisher||'Reference');
    return u?`<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${label} ↗</a>`:`<span>${label}</span>`;
  }).join('');
  return `<section class="context-card" data-color="${card.color}">
    <div class="context-type"><span>${esc(card.type)}</span><span class="context-stamp" aria-hidden="true">${esc(card.icon)}</span></div>
    <h3>${esc(card.title)}</h3><p>${esc(card.body)}</p>${list}
    ${links?`<div class="context-source">${links}</div>`:''}
  </section>`;
}

const svgBase=(bg,content) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 420" role="img" aria-label="Stylized editorial illustration, not a news photograph" preserveAspectRatio="xMidYMid slice"><rect width="900" height="420" fill="${bg}"/>${content}</svg>`;
const artSlides=[
  svgBase('#eecbff',`<rect y="295" width="900" height="125" fill="#ad86d8"/><path d="M0 290h900" stroke="#35253c" stroke-width="5"/><path d="M0 420 188 295M900 420 710 295" stroke="#8d64b7" stroke-width="4"/><rect x="232" y="43" width="420" height="236" rx="4" fill="#ffcb61" stroke="#2a1b36" stroke-width="15"/><rect x="251" y="63" width="382" height="196" fill="#25487d"/><circle cx="500" cy="128" r="48" fill="#ffda7b"/><path d="M250 220 Q325 135 385 204T520 203T640 202V258H250" fill="#e88da7"/><path d="M250 245 Q320 175 403 237T640 224V258H250" fill="#5577b9"/><path d="M85 140h83M726 140h84" stroke="#8564a7" stroke-width="3"/><circle cx="124" cy="109" r="8" fill="#fbf8dd"/><circle cx="768" cy="108" r="8" fill="#fbf8dd"/><g fill="#2b1c38"><circle cx="710" cy="311" r="23"/><path d="M688 339h45l21 76h-88z"/><circle cx="176" cy="330" r="18"/><path d="M160 353h33l12 67h-58z"/></g>`),
  svgBase('#fff3cc',`<rect x="80" y="20" width="740" height="380" rx="20" fill="#dfb1e8" stroke="#2a1c38" stroke-width="8"/><rect x="180" y="54" width="540" height="309" rx="5" fill="#fff9e8" stroke="#2a1c38" stroke-width="12"/><circle cx="521" cy="143" r="67" fill="#e8ae51"/><path d="M192 310Q280 130 387 268T711 247V350H192" fill="#5464bc"/><path d="M193 335Q317 228 408 309T711 283V350H193" fill="#94b4d2"/><path d="M188 140Q272 98 352 159" fill="none" stroke="#bf6cac" stroke-width="14" stroke-linecap="round"/><path d="M600 80Q654 108 678 175" fill="none" stroke="#af60b4" stroke-width="12" stroke-linecap="round"/><g stroke="#2e2543" stroke-width="3"><path d="M100 55h50M100 65h40M100 75h50M755 295h44M755 310h33"/></g>`),
  svgBase('#c1eaff',`<rect x="61" y="57" width="777" height="310" rx="16" fill="#f6f2e8" stroke="#2a1d35" stroke-width="7"/><text x="95" y="104" font-size="24" font-weight="800" font-family="Arial" fill="#30253e">GALLERY MAP</text><path d="M120 135h650v190H120z" fill="#fff4c6" stroke="#33243a" stroke-width="4"/><path d="M360 135v190M555 135v190" stroke="#2d2533" stroke-width="6"/><circle cx="465" cy="230" r="54" fill="#cfa6f9"/><text x="465" y="242" font-family="Arial" font-size="41" font-weight="800" text-anchor="middle" fill="#33233d">01</text><path d="M185 213h103M626 213h93" stroke="#a68cb0" stroke-width="9" stroke-linecap="round"/><g fill="#fa927b"><circle cx="240" cy="230" r="12"/><circle cx="670" cy="230" r="12"/></g><path d="M450 348l-18-28h36z" fill="#33243b"/>`)
];
const citySlides=[
  svgBase('#bce9ff',`<circle cx="753" cy="74" r="47" fill="#fff4a9"/><g fill="#598bce"><rect x="20" y="126" width="117" height="194"/><rect x="145" y="86" width="123" height="235"/><rect x="284" y="157" width="107" height="163"/><rect x="405" y="116" width="160" height="205"/><rect x="587" y="146" width="93" height="174"/><rect x="705" y="113" width="154" height="209"/></g><g fill="#cfefff">${[50,88,170,211,310,353,442,478,514,606,733,767,817].map(x=>`<rect x="${x}" y="181" width="13" height="22" rx="2"/>`).join('')}</g><rect y="318" width="900" height="102" fill="#30324e"/><path d="M0 370h900" stroke="#f8eea9" stroke-width="7" stroke-dasharray="48 28"/><g transform="translate(180 205)"><rect x="0" y="0" width="507" height="145" rx="22" fill="#f5a9a1" stroke="#2f2746" stroke-width="8"/><path d="M42 26h391v69H42z" fill="#b9eaff" stroke="#2f2746" stroke-width="6"/><path d="M124 25v69m106-69v69m102-69v69" stroke="#302747" stroke-width="7"/><circle cx="91" cy="148" r="33" fill="#f6e6c4" stroke="#302747" stroke-width="10"/><circle cx="410" cy="148" r="33" fill="#f6e6c4" stroke="#302747" stroke-width="10"/><text x="256" y="121" text-anchor="middle" font-family="Arial" font-weight="800" font-size="22" fill="#2f2746">NIGHT ROUTE</text></g>`),
  svgBase('#faf6dc',`<g stroke="#302b42" stroke-width="8" fill="none" stroke-linecap="round"><path d="M125 125Q270 60 364 156T575 192T765 97" stroke="#e08b91" stroke-width="17"/><path d="M165 312Q300 221 423 282T722 280" stroke="#7c9bd0" stroke-width="15"/></g>${[[127,125],[265,103],[368,157],[508,212],[615,170],[765,97]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="18" fill="#fffdf5" stroke="#303044" stroke-width="8"/>`).join('')}<path d="M368 157L423 282" stroke="#373147" stroke-width="7" stroke-dasharray="10 14"/><text x="95" y="53" font-family="Arial" font-size="25" font-weight="800" fill="#302c44">HOW THE ROUTE CONNECTS</text><text x="95" y="395" font-family="Arial" font-size="18" fill="#56506a">Concept illustration — not an official route map</text>`),
  svgBase('#30315a',`<circle cx="740" cy="88" r="65" fill="#fff3ad"/><g fill="#7c79c1">${Array.from({length:12},(_,i)=>`<rect x="${i*85-20}" y="${155+(i%3)*35}" width="${60+(i%2)*16}" height="${255-(i%3)*35}"/>`).join('')}</g><rect y="339" width="900" height="81" fill="#1d243c"/><path d="M0 370h900" stroke="#c1d3f5" stroke-width="5" stroke-dasharray="24 28"/><g fill="#fff1a5">${Array.from({length:20},(_,i)=>`<rect x="${i*47+15}" y="${178+(i%3)*35}" width="9" height="17"/>`).join('')}</g><g transform="translate(206 240)"><rect width="475" height="111" rx="21" fill="#c1f1ca" stroke="#141b2c" stroke-width="7"/><path d="M29 23h402v45H29z" fill="#b4d9ff"/><circle cx="95" cy="110" r="27" fill="#28243a"/><circle cx="387" cy="110" r="27" fill="#28243a"/></g>`)
];
const musicSlides=[
  svgBase('#ffd7c5',`<rect x="116" y="28" width="670" height="355" rx="21" fill="#fff4c7" stroke="#332538" stroke-width="8"/><circle cx="448" cy="205" r="164" fill="#36314e" stroke="#272235" stroke-width="5"/>${[141,119,96,73,49].map(r=>`<circle cx="448" cy="205" r="${r}" fill="none" stroke="#736a80" stroke-width="2"/>`).join('')}<circle cx="448" cy="205" r="53" fill="#ff907a"/><circle cx="448" cy="205" r="12" fill="#fff8de"/><path d="M570 65l124 96-84 128" fill="none" stroke="#2b2434" stroke-width="10" stroke-linecap="round"/><circle cx="610" cy="289" r="19" fill="#f0c9a5" stroke="#2b2434" stroke-width="7"/><g fill="#b676c1"><path d="M85 130l24-40 24 40-24 40z"/><path d="M810 275l24-40 24 40-24 40z"/></g>`),
  svgBase('#d9c9fa',`<rect x="65" y="51" width="770" height="321" rx="25" fill="#fef9ea" stroke="#2e2643" stroke-width="8"/><path d="M95 211h710" stroke="#e7dbe8" stroke-width="5"/><g fill="none" stroke="#6354c8" stroke-width="9" stroke-linecap="round"><path d="M110 203v-67M153 203V84M196 203v-95M239 203V155M282 203V73M325 203V133M368 203V41M411 203V158M454 203V96M497 203V129M540 203V61M583 203V150M626 203V100M669 203V79M712 203V156M755 203V99"/><path d="M110 214v50M153 214v90M196 214v75M239 214v33M282 214v105M325 214v61M368 214v125M411 214v37M454 214v78M497 214v50M540 214v112M583 214v54M626 214v75M669 214v92M712 214v38M755 214v82"/></g>`),
  svgBase('#f5b9ba',`<g fill="#2f2844"><rect x="105" y="65" width="690" height="300" rx="29"/><rect x="139" y="100" width="622" height="230" rx="17" fill="#fef6d2"/></g><g fill="#bcacef">${Array.from({length:8},(_,i)=>`<rect x="${165+i*76}" y="140" width="44" height="140" rx="6"/>`).join('')}</g><g fill="#333047">${Array.from({length:7},(_,i)=>`<rect x="${200+i*76}" y="141" width="31" height="91" rx="4"/>`).join('')}</g><text x="450" y="79" font-size="18" font-weight="800" font-family="Arial" text-anchor="middle" fill="#fef6d2">UNDER THE HOOD: ROYALTIES</text>`)
];
const gameSlides=[
  svgBase('#dff6aa',`<g transform="rotate(-7 450 210)"><rect x="143" y="70" width="618" height="294" rx="90" fill="#bfaaf6" stroke="#30263f" stroke-width="10"/><rect x="259" y="91" width="382" height="254" rx="12" fill="#302c52" stroke="#30263f" stroke-width="7"/><rect x="275" y="107" width="350" height="223" fill="#91e0e2"/><path d="M275 270Q347 157 421 232T625 173V329H275" fill="#7ca4d7"/><path d="M276 303Q370 224 456 283T625 240V330H276" fill="#6b66bb"/><circle cx="200" cy="217" r="31" fill="#f6d5af" stroke="#30263f" stroke-width="7"/><path d="M163 217h74M200 180v74" stroke="#30263f" stroke-width="12" stroke-linecap="round"/><circle cx="702" cy="185" r="16" fill="#ffac90" stroke="#30263f" stroke-width="5"/><circle cx="674" cy="220" r="16" fill="#f6d891" stroke="#30263f" stroke-width="5"/></g>`),
  svgBase('#bce7fb',`<g transform="translate(145 65)"><rect x="0" y="0" width="240" height="289" rx="14" fill="#fef2c9" stroke="#2d293f" stroke-width="7"/><circle cx="120" cy="123" r="89" fill="#d7bafd" stroke="#2d293f" stroke-width="6"/><circle cx="120" cy="123" r="33" fill="#fef2c9"/><text x="120" y="260" text-anchor="middle" font-weight="800" font-size="17" font-family="Arial" fill="#2d293f">PHYSICAL</text></g><path d="M442 218h103m-25-28 30 28-30 28" stroke="#33283f" stroke-width="12" fill="none" stroke-linecap="round"/><g transform="translate(585 80)"><rect width="188" height="235" rx="23" fill="#393257"/><rect x="19" y="20" width="150" height="172" rx="10" fill="#e3e4a9"/><path d="M26 141Q85 41 167 136V189H26" fill="#97bca5"/><text x="94" y="218" text-anchor="middle" font-weight="800" font-size="17" font-family="Arial" fill="#fff6df">DIGITAL</text></g>`),
  svgBase('#fce6ad',`<rect x="125" y="40" width="650" height="345" rx="18" fill="#fffdf4" stroke="#2e2938" stroke-width="8"/><path d="M128 109h644" stroke="#2e2938" stroke-width="5"/><circle cx="161" cy="76" r="11" fill="#f7ae98"/><circle cx="196" cy="76" r="11" fill="#f1d188"/><circle cx="231" cy="76" r="11" fill="#a2d3aa"/><g font-size="21" font-weight="700" font-family="Arial" fill="#42364a"><text x="170" y="161">LICENCE</text><text x="170" y="224">ACCESS</text><text x="170" y="287">OFFLINE PLAY</text><text x="170" y="350">REGION</text></g><g stroke="#b0a9b5" stroke-width="4"><path d="M430 155h255M430 218h255M430 281h255M430 344h255"/></g><path d="m670 165 17 17 30-36" fill="none" stroke="#608d71" stroke-width="8" stroke-linecap="round"/>`)
];
const visuals={art:artSlides,city:citySlides,music:musicSlides,games:gameSlides};

// Story-specific editorial slide graphics. These are not photos or invented event imagery.
function wrapWords(value,limit=31,maxLines=4){
  const words=String(value||'').split(/\s+/).filter(Boolean),lines=[];let line='';
  for(const word of words){
    if((line+' '+word).trim().length>limit&&line){lines.push(line);line=word}
    else line=(line+' '+word).trim();
    if(lines.length>=maxLines)break;
  }
  if(lines.length<maxLines&&line)lines.push(line);
  return lines.slice(0,maxLines);
}
function storySvg(story,slide,index){
  const bg=slide===0?story.accent:slide===1?story.soft:story.background;
  const card=story.cards[slide-1]||story.cards[0];
  const isMain=slide===0;
  const head=isMain?story.title:(card?.title||story.title);
  const subtitle=isMain?story.category:(card?.type||'STORY CONTEXT');
  const detail=isMain?`THE SCROLL · ${edition?.date||'LATEST EDITION'}`:(card?.body||story.lede);
  const headLines=wrapWords(head,isMain?28:33,4);
  const factLines=wrapWords(detail,65,3);
  const textLines=headLines.map((line,j)=>`<text x="62" y="${153+j*57}" font-family="Arial,sans-serif" font-size="${isMain?45:44}" font-weight="900" letter-spacing="-1.8" fill="#241e2c">${esc(line)}</text>`).join('');
  const textFact=factLines.map((line,j)=>`<text x="63" y="${330+j*24}" font-family="Arial,sans-serif" font-size="17" fill="#34303c">${esc(line)}</text>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 420" role="img" aria-label="Editorial typographic graphic about ${esc(story.title)}; not a news photograph" preserveAspectRatio="xMinYMid meet">
    <rect width="900" height="420" fill="${bg}"/>
    <circle cx="770" cy="67" r="130" fill="#fff" opacity=".32"/>
    <circle cx="807" cy="84" r="93" fill="none" stroke="#241e2c" stroke-width="6" opacity=".25"/>
    <path d="M688 420 C710 260 905 220 930 20" fill="none" stroke="#241e2c" stroke-width="10" opacity=".15"/>
    <rect x="56" y="35" width="${Math.min(700,120+subtitle.length*12)}" height="40" rx="20" fill="#fbf8ed" stroke="#241e2c" stroke-width="2"/>
    <text x="76" y="61" font-family="Arial,sans-serif" font-size="17" font-weight="900" letter-spacing="1.3" fill="#241e2c">${esc(subtitle.toUpperCase())}</text>
    ${textLines}
    <path d="M60 291h605" stroke="#241e2c" stroke-width="2" opacity=".4"/>
    ${textFact}
    <text x="812" y="370" text-anchor="end" font-size="60" fill="#241e2c" font-weight="900" opacity=".15" font-family="Arial">0${slide+1}</text>
    <rect x="0" y="410" width="900" height="10" fill="#241e2c" />
  </svg>`;
}
function renderGalleryVisual(index) {
  const story=stories[index], images=story.images || [];
  const total=images.length||3;
  const slide=Math.min(gallerySlides.get(index)||0,total-1);
  const scene=$(`visual-${index}`);
  if(!scene)return;
  const photo=images.length?images[slide]:null;
  scene.style.background=slide===0?story.accent:slide===1?story.soft:story.background;
  const fallback=storySvg(story,slide,index);
  const arrows=`<button type="button" class="gallery-arrow left-arrow" aria-label="Previous image" data-gallery="-1" data-index="${index}">←</button><button type="button" class="gallery-arrow right-arrow" aria-label="Next image" data-gallery="1" data-index="${index}">→</button>`;
  if(photo){
    scene.innerHTML=`<div class="photo-fallback" aria-hidden="true">${fallback}</div><img class="gallery-photo" alt="${esc(photo.caption)}" src="${esc(photo.url)}" loading="${index<=activeIndex+1?'eager':'lazy'}" decoding="async" referrerpolicy="no-referrer"><span class="image-badge">${esc(photo.kind.toUpperCase())} IMAGE · ${slide+1} / ${total}</span>${arrows}`;
    const img=scene.querySelector('.gallery-photo');
    const label=scene.querySelector('.image-badge');
    let triedBackup=false;
    img.addEventListener('error',()=>{
      if(!triedBackup && photo.backup_url && photo.backup_url!==photo.url){
        triedBackup=true;img.src=photo.backup_url;
        if(label)label.textContent='ILLUSTRATIVE IMAGE · '+(slide+1)+' / '+total;
        const caption=$(`galleryCaption-${index}`);
        if(caption)caption.textContent='The original image could not be loaded. Displaying a contextual illustration instead.';
      }else{
        img.remove();
        if(label)label.textContent='IMAGE NOT AVAILABLE · '+(slide+1)+' / '+total;
        const caption=$(`galleryCaption-${index}`);
        if(caption)caption.textContent='Publisher photo unavailable in this browser. Use the original source link below.';
      }
    },{once:false});
    const caption=$(`galleryCaption-${index}`);
    if(caption) caption.innerHTML=`${esc(photo.caption)} ${photo.credit_url?`<a class="photo-credit" href="${esc(photo.credit_url)}" target="_blank" rel="noopener noreferrer">${esc(photo.credit)} ↗</a>`:`<span>${esc(photo.credit)}</span>`}`;
  }else{
    scene.innerHTML=fallback+`<span class="image-badge">EDITORIAL ILLUSTRATION · ${slide+1} / 3</span>${arrows}`;
    const caption=$(`galleryCaption-${index}`);
    if(caption)caption.textContent='No verified photo provided for this story. Editorial illustration only.';
  }
  const pagination=$(`galleryPagination-${index}`);
  if(pagination)pagination.innerHTML=`<span class="gallery-page">${String(slide+1).padStart(2,'0')} / ${String(total).padStart(2,'0')}</span>`+Array.from({length:total},(_,k)=>`<span class="tiny-dot ${slide===k?'on':''}"></span>`).join('');
  scene.classList.remove('slide-transition');void scene.offsetWidth;scene.classList.add('slide-transition');
}
function slideGallery(index,offset) {
  const total=stories[index]?.images?.length||3;
  gallerySlides.set(index,((gallerySlides.get(index)||0)+offset+total)%total);
  renderGalleryVisual(index);
}

function renderStory(story,i) {
  const left=story.cards.filter(c=>c.side==='left');
  const right=story.cards.filter(c=>c.side==='right');
  const contexts=story.cards.map(cardMarkup).join('');
  const sections=story.sections.map(x=>`<h2 class="section-heading">${esc(x.heading)}</h2><p class="article-p">${esc(x.body)}</p>`).join('');
  const link=story.source_url ? `<a class="source-button" href="${esc(story.source_url)}" target="_blank" rel="noopener noreferrer">OPEN ORIGINAL ↗</a>` : '';
  const original=story.source_url ? `<a class="original-report" href="${esc(story.source_url)}" target="_blank" rel="noopener noreferrer" aria-label="Read the full original report from ${esc(story.source_name)}">
      <span class="original-report-mark" aria-hidden="true">↗</span><span class="original-report-copy"><strong>READ THE COMPLETE ORIGINAL REPORT</strong><small>${esc(story.source_name)} · ${esc(story.published_at||'Published date unavailable')}</small></span><span class="original-report-arrow" aria-hidden="true">→</span>
    </a>` : '';
  const leftMarkup=left.length ? left.map(cardMarkup).join('') : '<p class="context-empty">No independently sourced background attached to this story yet. The original report is linked in the center.</p>';
  const rightMarkup=right.length ? right.map(cardMarkup).join('') : '<p class="context-empty">We have not found another closely matching report to cross-link. That is not evidence of disagreement or confirmation.</p>';
  const titleRight=right.length?'Another perspective.':'Source first.';
  const excerptNote=story.feed_preview?'<p class="source-disclaimer"><strong>Publisher-feed preview.</strong> This is not the complete article. Open the original report above to read all the details, updates and qualifications.</p>':'';
  const sourceLabel=story.feed_preview?'ORIGINAL REPORT · SOURCE PREVIEW':'REPORTING · SOURCE-ATTRIBUTED';
  return `<section id="story-${i}" class="story-screen" data-story-index="${i}" aria-label="Story ${i+1}: ${esc(story.title)}">
      <aside class="panel left" aria-label="Supporting information for ${esc(story.title)}"><div class="panel-header"><span class="panel-header-title">THE DETAILS BEHIND IT</span><span class="panel-mark" aria-hidden="true">↘</span></div><div class="side-scroll"><h2 class="context-title">Look a little closer.</h2>${leftMarkup}<p class="side-footnote">Only linked and source-supported context appears here.</p></div></aside>
      <article class="panel center" aria-labelledby="title-${i}"><div class="panel-header"><span class="story-count"><strong>${String(i+1).padStart(2,'0')}</strong> / ${String(stories.length).padStart(2,'0')}</span><div class="story-topic"><span class="topic-pill">${esc(story.category)}</span><span class="topic-mark" aria-hidden="true">✳</span></div></div>
        <div class="article-scroll" tabindex="0" aria-label="Read the story and its original source"><div class="gallery"><div class="visual-canvas" id="visual-${i}"></div><div class="gallery-meta"><span class="gallery-caption" id="galleryCaption-${i}">Loading image details…</span><div id="galleryPagination-${i}" class="gallery-pagination" aria-hidden="true"></div></div></div>
        <div class="story-article"><div class="story-meta"><span class="meta-kicker">${sourceLabel}</span><span class="meta-date">${esc(story.published_at||'')}</span></div><h1 id="title-${i}">${esc(story.title)}</h1><p class="story-publisher">REPORTED BY <strong>${esc(story.source_name)}</strong></p><p class="story-dek">${esc(story.lede)}</p>
          ${original}${excerptNote}${sections}
          ${contexts?`<div class="inside-context"><h2>More to the story ✳</h2><div class="inline-context-grid">${contexts}</div></div>`:''}
          <div class="story-source"><p><strong>Original source:</strong> ${esc(story.source_name)}${edition.demo?'<br>Demo article — verify linked reporting before relying on its claims.':''}</p>${link}</div><p class="read-cue">${i===stories.length-1?'THAT’S THE LAST STORY. YOU’RE CAUGHT UP.':'DONE READING? SCROLL OR TAP NEXT TO MOVE ON →'}</p>
        </div></div></article>
      <aside class="panel right" aria-label="Further perspectives and evidence for ${esc(story.title)}"><div class="panel-header"><span class="panel-header-title">ANOTHER ANGLE</span><span class="panel-mark" aria-hidden="true">✳</span></div><div class="side-scroll"><h2 class="context-title">${titleRight}</h2>${rightMarkup}<p class="side-footnote">Different coverage is linked only when sourced, not invented.</p></div></aside>
    </section>`;
}

function setActive(index) {
  const next=Math.max(0,Math.min(index,stories.length-1));
  if (!stories.length)return;
  activeIndex=next;
  const story=stories[next];
  $('pageLabel').innerHTML=`${String(next+1).padStart(2,'0')} <span class="slash">/</span> ${String(stories.length).padStart(2,'0')}`;
  $('currentCategory').textContent=story.category;
  $('topProgressFill').style.width=`${(next+1)/stories.length*100}%`;
  const prev=$('previousButton'),nxt=$('nextButton');
  prev.disabled=next===0;
  nxt.disabled=next===stories.length-1;
  nxt.innerHTML=next===stories.length-1?'YOU’RE CAUGHT UP <span aria-hidden="true">✓</span>':'NEXT STORY <span aria-hidden="true">→</span>';
  $('pageDots').querySelectorAll('button').forEach((b,i)=>{b.classList.toggle('active',i===next);b.setAttribute('aria-current',i===next?'step':'false')});
  const pip=$('pageDots').querySelectorAll('button')[next]; if(pip){$('pageDots').scrollLeft=pip.offsetLeft-$('pageDots').offsetLeft-$('pageDots').clientWidth/2;}
  $('notice').textContent=`Story ${next+1} of ${stories.length}. ${story.title}`;
  history.replaceState(null,'',`#story-${next}`);
}
function goto(index,instant=false) {
  if(index<0||index>=stories.length)return;
  const destination=deck.querySelector(`[data-story-index="${index}"]`);
  if(destination)deck.scrollTo({top:destination.offsetTop-deck.offsetTop,behavior:instant||matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  setActive(index);
}
function render() {
  if (edition.demo) {
    $('demoBadge').textContent='DEMO / NOT VERIFIED';
    $('editionDate').textContent=edition.date||'DEMO';
    deck.innerHTML='<div class="initial-load" style="padding:28px;text-align:center;line-height:1.7;flex-direction:column;gap:8px"><strong>THE SCROLL is switching to real publisher sources.</strong><span style="font-size:14px;font-weight:400;color:#6b6170;max-width:550px">The old demo is not verified reporting. Run the free daily workflow to publish current stories from actual news feeds.</span></div>';
    return;
  }
  stories=(edition.stories||[]).map(normalize).filter(s=>s.title.trim());
  if(!stories.length){deck.innerHTML='<div class="initial-load">No stories available for this edition.</div>';return}
  $('demoBadge').textContent=edition.demo?'DEMO EDITION':'SOURCE-LED EDITION';
  $('demoBadge').style.display='inline-block';
  try {$('editionDate').textContent=new Intl.DateTimeFormat('en-GB',{weekday:'short',day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${edition.date||'2026-11-23'}T12:00:00Z`)).toUpperCase().replace(',',' ·')}catch{$('editionDate').textContent=edition.date||'LATEST EDITION'}
  deck.innerHTML=stories.map(renderStory).join('');
  $('pageDots').innerHTML=stories.map((s,i)=>`<button type="button" class="story-pip ${i===0?'active':''}" data-page="${i}" aria-label="Go to story ${i+1}: ${esc(s.title)}"></button>`).join('');
  stories.forEach((_,i)=>renderGalleryVisual(i));
  const hashIndex=Number((location.hash.match(/^#story-(\d+)$/)||[])[1]||0);
  goto(Math.min(stories.length-1,hashIndex),true);
}

deck.addEventListener('click',evt=>{
  const gal=evt.target.closest('button[data-gallery]');
  if(gal){slideGallery(Number(gal.dataset.index),Number(gal.dataset.gallery));return}
});
let galleryTouch=null;
deck.addEventListener('touchstart',evt=>{
  const panel=evt.target.closest('.visual-canvas');
  if(panel && evt.touches.length===1)galleryTouch={x:evt.touches[0].clientX,y:evt.touches[0].clientY,index:Number(panel.id.replace('visual-',''))};
},{passive:true});
deck.addEventListener('touchend',evt=>{
  if(!galleryTouch||!evt.changedTouches.length)return;
  const dx=evt.changedTouches[0].clientX-galleryTouch.x,dy=evt.changedTouches[0].clientY-galleryTouch.y;
  if(Math.abs(dx)>40 && Math.abs(dx)>Math.abs(dy)*1.25)slideGallery(galleryTouch.index,dx<0?1:-1);
  galleryTouch=null;
},{passive:true});
$('pageDots').addEventListener('click',evt=>{const b=evt.target.closest('[data-page]');if(b)goto(Number(b.dataset.page))});
$('nextButton').addEventListener('click',()=>goto(activeIndex+1));
$('previousButton').addEventListener('click',()=>goto(activeIndex-1));
$('homeLink').addEventListener('click',evt=>{evt.preventDefault();goto(0)});

function canInnerScroll(elem,delta) {
 if(!elem)return false;
 const max=elem.scrollHeight-elem.clientHeight;
 if(max<3)return false;
 return delta>0?elem.scrollTop<max-3:elem.scrollTop>3;
}
// Trackpad / mouse wheel: read the full article naturally, but snap between stories.
deck.addEventListener('wheel',evt=>{
 if(Math.abs(evt.deltaY)<Math.abs(evt.deltaX)||Math.abs(evt.deltaY)<1)return;
 const inner=evt.target.closest('.article-scroll,.side-scroll');
 if(canInnerScroll(inner,evt.deltaY)){wheelAccumulator=0;return}
 evt.preventDefault();
 const now=performance.now(),direction=Math.sign(evt.deltaY);
 if(now-lastWheelChange<900)return;
 if(wheelDirection!==direction||now-wheelIdleAt>350)wheelAccumulator=0;
 wheelDirection=direction;wheelIdleAt=now;wheelAccumulator+=Math.abs(evt.deltaY);
 if(wheelAccumulator>90){wheelAccumulator=0;lastWheelChange=now;goto(activeIndex+direction)}
},{passive:false});

deck.addEventListener('scroll',()=>{
 if(scrollRaf)return;
 scrollRaf=true;
 requestAnimationFrame(()=>{
  scrollRaf=false;
  const idx=Math.round(deck.scrollTop/Math.max(1,deck.clientHeight));
  if(idx!==activeIndex)setActive(idx);
 });
},{passive:true});
window.addEventListener('keydown',evt=>{
 const t=evt.target;
 if(t.matches('input,textarea,select')||t.isContentEditable)return;
 if(evt.key==='ArrowRight'||evt.key==='PageDown'){evt.preventDefault();goto(activeIndex+1)}
 else if(evt.key==='ArrowLeft'||evt.key==='PageUp'){evt.preventDefault();goto(activeIndex-1)}
 else if(evt.key==='Home'&&!evt.metaKey){evt.preventDefault();goto(0)}
 else if(evt.key==='End'&&!evt.metaKey){evt.preventDefault();goto(stories.length-1)}
});
window.addEventListener('resize',()=>goto(activeIndex,true));

async function init() {
  if (location.protocol === 'file:') {
    deck.innerHTML='<div class="initial-load error-load">Open this project via its local server: <code>npm start</code> → <code>http://127.0.0.1:4173</code></div>';
    return;
  }
  try {
    // Deliberately read only news.json; the HTML/CSS/JS never contain the edition itself.
    const response = await fetch('./news.json', {cache:'no-store'});
    if (!response.ok) throw new Error(`Could not load news.json (HTTP ${response.status})`);
    const nextEdition = await response.json();
    if (!Array.isArray(nextEdition.stories) || !nextEdition.stories.length) {
      throw new Error('news.json must contain at least one story.');
    }
    edition = nextEdition;
    render();
  } catch(error) {
    deck.innerHTML=`<div class="initial-load error-load" role="alert">Cannot open today's edition. Check that <code>news.json</code> is uploaded beside <code>index.html</code> and contains valid JSON.<small>${esc(error.message)}</small></div>`;
    console.error('[THE SCROLL]',error);
  }
}
init();
})();
