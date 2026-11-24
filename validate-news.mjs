import fs from 'node:fs/promises';
const edition = JSON.parse(await fs.readFile(new URL('./news.json', import.meta.url), 'utf8'));
if (!edition.date || !Array.isArray(edition.stories) || !edition.stories.length) {
  throw new Error('Edition needs a date and at least one story');
}
const ids=new Set();
for (const [i, s] of edition.stories.entries()) {
  if (!s.title || !s.lede || !s.source_name || !/^https:\/\//.test(s.source_url || '')) {
    throw new Error(`Story ${i+1}: missing title, preview or direct HTTPS source`);
  }
  if (ids.has(s.id)) throw new Error(`Story ${i+1}: duplicate ID`);
  ids.add(s.id);
  if (!Array.isArray(s.sections) || !Array.isArray(s.cards) || !Array.isArray(s.images)) {
    throw new Error(`Story ${i+1}: sections/cards/images must be arrays`);
  }
  for (const img of s.images) {
    if (!/^https:\/\//.test(img.url || '')) throw new Error(`Story ${i+1}: invalid image URL`);
  }
}
console.log(`Valid edition: ${edition.stories.length} stories, ${edition.date}, ${edition.stories.reduce((n,s)=>n+s.images.length,0)} feed media`);
