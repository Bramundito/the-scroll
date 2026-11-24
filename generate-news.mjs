/**
 * THE SCROLL — automated daily edition (v1)
 * Requires Node 20+ and OPENAI_API_KEY in the environment.
 * Researches with the Responses API's web_search tool, checks that lead URLs
 * were actually returned by the research tool, and writes news.json atomically.
 * No user API key is ever written into public site assets.
 *
 * Important: an automated source-linked draft is NOT independent fact-checking.
 * This first version uses labeled editorial SVG fallbacks instead of scraping
 * third-party news photographs or inventing image credits.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const key = process.env.OPENAI_API_KEY;
if (!key) throw new Error('Missing OPENAI_API_KEY GitHub Actions repository secret');
const model = process.env.OPENAI_MODEL || 'gpt-5.4-mini';
const dateParts = new Intl.DateTimeFormat('en-GB', {
  timeZone:'Asia/Jakarta', year:'numeric', month:'2-digit', day:'2-digit'
}).formatToParts(new Date());
const dateField = (type) => dateParts.find(p => p.type === type)?.value;
const editionDate = `${dateField('year')}-${dateField('month')}-${dateField('day')}`;
const editorial = await fs.readFile(path.join(root, 'editorial-prompt.md'), 'utf8');
let previousTitles = [];
try { const old = JSON.parse(await fs.readFile(path.join(root, 'news.json'),'utf8')); previousTitles = old.stories?.map(s=>s.title).slice(0,40)||[]; } catch {}

const beats = [
  {name:'Indonesia and Jakarta', target:9, focus:'National Indonesia news, government, economy, policy, justice, disasters, plus concrete Jakarta developments and local issues. Prefer 4+ Jakarta stories when newsworthy.'},
  {name:'World affairs and economy', target:8, focus:'Most consequential global news and diplomacy; geopolitics, conflicts, global economics, major scientific developments.'},
  {name:'Creative industries and art', target:7, focus:'Documented creative campaigns, experiential brand activations, advertising, art exhibitions, architecture and design launches relevant to Indonesia when possible. Only significant substantive news.'},
  {name:'Music, pop culture, games and technology', target:6, focus:'Music industry/releases/tours, significant film/television, gaming, internet culture, and technology news. Tangible verifiable developments; no empty trend filler.'}
];

const https = (s) => { try { const u = new URL(s); return u.protocol === 'https:' && !/^(example\.com|localhost|127\.0\.0\.1)$/i.test(u.hostname) ? u.toString() : ''; } catch { return ''; }};
const canonical = (s) => {const v=https(s); if(!v)return ''; const u = new URL(v); u.hash=''; for (const k of [...u.searchParams.keys()]) if (/^(utm_|fbclid|gclid|mc_)/i.test(k)) u.searchParams.delete(k); return u.origin.toLowerCase()+u.pathname.replace(/\/$/,'')+u.search;};
function sourcesFrom(result){
  const urls = new Set();
  for (const item of result.output || []) {
    if (item.type === 'web_search_call') {
      for (const src of item.action?.sources || []) {
        const v=canonical(src.url || src.source_url); if(v) urls.add(v);
      }
    }
    if (item.type === 'message') for (const c of item.content||[]) {
      for (const a of c.annotations||[]) {
        const v=canonical(a.url || a.url_citation?.url); if(v) urls.add(v);
      }
    }
  }
  return urls;
}
function outputText(result){return (result.output||[]).filter(x=>x.type==='message').flatMap(x=>x.content||[]).filter(x=>x.type==='output_text').map(x=>x.text).join('\n');}
function approxDuplicate(a,b){
  const words = s=>new Set(String(s).toLowerCase().replace(/[^a-z\d ]/gi,' ').split(/\s+/).filter(x=>x.length>3));
  const x=words(a), y=words(b);if(!x.size||!y.size)return false;
  let common=0;for(const w of x)if(y.has(w))common++;
  const minOverlap=common/Math.min(x.size,y.size);
  const jaccard=common/(x.size+y.size-common);
  return minOverlap>=0.8 && jaccard>=0.67;
}

async function researchBeat(beat){
  const oldNames=previousTitles.slice(0,30).join(' | ');
  const input = `TODAY IN JAKARTA: ${editionDate}. You are preparing ONE portion of a real sourced daily newspaper. Search the LIVE web for this beat: ${beat.name}. Focus: ${beat.focus}. Choose up to ${beat.target} SUBSTANTIVE separate recent developments from the last 36 hours; older only if newly relevant. Search thoroughly; don't invent anything. Do not pad categories. Avoid duplicating earlier editions unless a new significant update happened. Old topics: ${oldNames}.\n\n${editorial}\n\nReturn ONLY a valid JSON object of this format (no markdown): {"stories":[{"category":"INDONESIA","title":"...","lede":"...","published_at":"YYYY-MM-DD","source_name":"Publisher — date","source_url":"https://real-exact-url-from-web-search/","sections":[{"heading":"What happened","body":"..."},{"heading":"What matters","body":"..."}],"cards":[{"side":"left","type":"CONTEXT","title":"...","body":"...","color":"purple","sources":[{"label":"Publisher","url":"https://real-source-url/"}],"bullets":[]},{"side":"right","type":"WHY IT MATTERS","title":"...","body":"...","color":"lime","sources":[],"bullets":[]}],"images":[]}]} .\nRequirements: every story has a source_url that is an EXACT real URL you opened or found with the web search tool. Explain specifics with dates, place, figures, relevant context; two or three informative sections, 2 story-specific supporting cards. Total prose per story at least ~140 words where sources support it. Do not make up quotes, numerical values, competing views, or event imagery. Images MUST be [] in this v1; the website will draw explicitly labeled fallback illustrations. Match editorial mission; if thin, return fewer articles. Do not report uncertain events as confirmed. Output valid JSON only.`;
  const body = {
    model,
    reasoning: {effort:'low'},
    store:false,
    tools:[{type:'web_search', search_context_size:'high', user_location:{type:'approximate',country:'ID',city:'Jakarta',region:'Jakarta'}}],
    tool_choice:'auto',
    include:['web_search_call.action.sources'],
    max_output_tokens:16000,
    input
  };
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),240000);
  let response;
  try {response=await fetch('https://api.openai.com/v1/responses', {
    method:'POST',headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json'},
    body:JSON.stringify(body),signal:controller.signal
  });} finally {clearTimeout(timeout);}
  if(!response.ok) throw new Error(`OpenAI API ${response.status}: ${(await response.text()).slice(0,300)}`);
  const result=await response.json();
  if(result.status!=='completed') throw new Error(`${beat.name}: incomplete model response (${result.status})`);
  if(!(result.output||[]).some(x=>x.type==='web_search_call')) throw new Error(`${beat.name}: model did not use live web research`);
  const researchSources=sourcesFrom(result);
  if(!researchSources.size) throw new Error(`${beat.name}: no auditable web-search URLs returned`);
  const parsed=JSON.parse(outputText(result));
  if(!Array.isArray(parsed.stories))throw new Error(`${beat.name}: stories array missing`);
  const supported=parsed.stories.filter(s=> researchSources.has(canonical(s.source_url)));
  console.log(`${beat.name}: ${supported.length}/${parsed.stories.length} stories matched actual web-search URLs`);
  return supported;
}

let all=[];
for (const beat of beats){
  const found=await researchBeat(beat);
  for (const s of found){
    if(all.some(p=>canonical(p.source_url)===canonical(s.source_url)||approxDuplicate(p.title,s.title)))continue;
    if(!s.title || !s.lede || s.lede.length<65 || !Array.isArray(s.sections) || s.sections.length<2 || !Array.isArray(s.cards) || s.cards.length<1 || !https(s.source_url))continue;
    const clean={...s,
      id:`scroll-${editionDate}-${String(all.length+1).padStart(2,'0')}`,
      category:String(s.category||beat.name).toUpperCase(),
      published_at:String(s.published_at||editionDate),
      sections:s.sections.slice(0,4).map(z=>({heading:String(z.heading||'The story'),body:String(z.body||'')})).filter(z=>z.body.length>60),
      cards:s.cards.slice(0,6).map(z=>({side:z.side==='right'?'right':'left',type:String(z.type||'CONTEXT'),title:String(z.title||'Context'),body:String(z.body||''),color:['purple','yellow','blue','coral','lime'].includes(z.color)?z.color:'purple',sources:(Array.isArray(z.sources)?z.sources:[]).filter(x=>https(x.url)).map(x=>({label:String(x.label||'Source'),url:x.url})),bullets:Array.isArray(z.bullets)?z.bullets.slice(0,5):[]})).filter(z=>z.body.length>25),
      images:[]
    };
    if(clean.sections.length>=2 && clean.cards.length>=1)all.push(clean);
  }
}
if(all.length<14)throw new Error(`Only ${all.length} adequately sourced stories; refusing to replace existing edition. Try manual retry later.`);
all=all.slice(0,30);
const edition={date:editionDate, updated_at:new Date().toISOString(),demo:false,intro:`THE SCROLL — ${editionDate}. Automatically prepared from linked news sources; review original reports for consequential claims. Illustrations are not event photos.`,stories:all};
const temp=path.join(root,`news.json.tmp-${process.pid}`);
await fs.writeFile(temp, JSON.stringify(edition,null,2)+'\n');
await fs.rename(temp,path.join(root,'news.json'));
console.log(`Published valid JSON candidate: ${edition.stories.length} source-linked stories on ${edition.date}. Individual claims are not independently fact-checked.`);
