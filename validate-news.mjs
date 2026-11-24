import fs from 'node:fs/promises';
const edition=JSON.parse(await fs.readFile(new URL('./news.json',import.meta.url),'utf8'));
if(!Array.isArray(edition.stories)||!edition.stories.length)throw new Error('stories must be a non-empty array');
for(const [i,s] of edition.stories.entries()){
 if(!s.title||!s.lede||!Array.isArray(s.sections)||!s.sections.length)throw new Error(`Story ${i+1}: missing headline, lede, or sections`);
 if(!Array.isArray(s.images))throw new Error(`Story ${i+1}: images must be an array`);
 if(!Array.isArray(s.cards)&&!Array.isArray(s.supporting_info))throw new Error(`Story ${i+1}: support cards missing`);
 for(const im of s.images){if(!im.url||!/^https:\/\//.test(im.url))throw new Error(`Story ${i+1}: invalid image URL`);}
}
console.log(`Valid edition: ${edition.stories.length} stories · ${edition.stories.reduce((sum,s)=>sum+s.images.length,0)} image references · ${edition.date}`);
