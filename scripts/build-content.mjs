import { readFile, writeFile } from 'node:fs/promises';
import { marked } from 'marked';

const root = new URL('../', import.meta.url);
const raw = (await readFile(new URL('research/catan-ai-research.md', root), 'utf8')).replace(/\r\n/g, '\n');
const definitions = [...raw.matchAll(/^\[(\d+)\]: (.+)$/gm)];
const references = Object.fromEntries(definitions.map(m => [m[1], m[2]]));
const defs = definitions.map(m => m[0]).join('\n');
const clean = raw.replace(/^\[\d+\]: .+$/gm, '').trim();
const sections = clean.split(/^## /m).slice(1);
const strip = html => html.replace(/<[^>]*>/g, ' ').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
const chapters = sections.filter(x => /^\d+\./.test(x)).map(section => {
  const split = section.indexOf('\n');
  const heading = section.slice(0, split).trim();
  const id = Number(heading.match(/^\d+/)[0]);
  const title = heading.replace(/^\d+\.\s*/, '');
  const body = section.slice(split).trim();
  const html = marked.parse(body + '\n\n' + defs);
  return { id, title, html, text: strip(html), minutes: Math.max(1, Math.ceil(body.split(/\s+/).length / 220)) };
});
const register = sections.find(x => x.startsWith('Sources and evidence register'));
const sourceGroups = {
  rules: [1,36,37], papers: [2,3,4,5,9,10,11,27,28,29,30,31,33],
  code: [13,14,15,19,20], data: [32,34,35]
};
const sources = [...register.matchAll(/^(\d+)\. (.+)$/gm)].map(m => {
  const id = Number(m[1]);
  const html = marked.parse(m[2]);
  const firstLink = m[2].match(/\[([^\]]+)\]\(([^\s]+?)\)(?:[,.; ]|$)/);
  return { id, title: firstLink?.[1] || `Source ${id}`, url: references[id], html, text: strip(html), group: Object.entries(sourceGroups).find(([, ids]) => ids.includes(id))?.[0] || 'projects' };
});
if (chapters.length !== 12 || sources.length !== 37 || Object.keys(references).length !== 37) throw new Error('Research structure changed: inspect chapter and source counts.');
await writeFile(new URL('dist/content.json', root), JSON.stringify({ date: '11 September 2026', chapters, sources, references }, null, 2) + '\n');
await writeFile(new URL('dist/catan-ai-research.md', root), raw);
process.stdout.write(`Generated ${chapters.length} chapters and ${sources.length} source entries.\n`);
