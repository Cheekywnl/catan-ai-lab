import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { theftOutcomes } from '../dist/lab-math.js';
import { projects, components, stages } from '../dist/catalog.js';
const data = JSON.parse(await readFile(new URL('../dist/content.json', import.meta.url)));

test('all twelve chapters and all 37 evidence entries are present and linked', () => {
  assert.deepEqual(data.chapters.map(c=>c.id),Array.from({length:12},(_,i)=>i+1));
  assert.deepEqual(data.sources.map(s=>s.id),Array.from({length:37},(_,i)=>i+1));
  for(const s of data.sources){assert.ok(s.title && s.text && s.html);assert.equal(new URL(s.url).protocol,'https:');assert.equal(data.references[s.id],s.url);}
  for(const c of data.chapters){assert.ok(c.text.length>800);assert.doesNotMatch(c.html,/\[\d+\](?!<\/a>)/);}
  assert.match(data.chapters[2].text,/53.65%/);
  assert.match(data.chapters[2].text,/factored belief/);
  assert.match(data.chapters[6].text,/43,947/);
});
test('download is an exact copy of the research source after newline normalization',async()=>{
  const [source,download]=await Promise.all(['../research/catan-ai-research.md','../dist/catan-ai-research.md'].map(p=>readFile(new URL(p,import.meta.url),'utf8')));
  assert.equal(download.replace(/\r\n/g,'\n'),source.replace(/\r\n/g,'\n'));
});
test('all curated assessments and architecture nodes resolve to real evidence and chapters',()=>{
  assert.equal(projects.length,12);assert.equal(stages.length,5);
  for(const item of [...projects,...components])for(const id of item.refs)assert.ok(data.references[id]);
  for(const item of [...components,...stages])assert.ok(data.chapters.some(c=>c.id===item.chapter));
});
test('known two-ore one-wheat hand produces the correct correlated posterior',()=>{
  assert.deepEqual(theftOutcomes(2,1),[
    {stolen:'ore',probability:2/3,victim:{ore:1,wheat:1},thief:{ore:1,wheat:0}},
    {stolen:'wheat',probability:1/3,victim:{ore:2,wheat:0},thief:{ore:0,wheat:1}}
  ]);
});
test('every allowed demo hand conserves each resource and total probability',()=>{
  for(let ore=0;ore<=10;ore++)for(let wheat=0;wheat<=10;wheat++){
    if(!ore&&!wheat)continue;
    const outcomes=theftOutcomes(ore,wheat);
    assert.ok(Math.abs(outcomes.reduce((sum,o)=>sum+o.probability,0)-1)<1e-12);
    for(const o of outcomes){assert.equal(o.victim.ore+o.thief.ore,ore);assert.equal(o.victim.wheat+o.thief.wheat,wheat);assert.equal(o.thief.ore+o.thief.wheat,1);assert.ok(o.probability>0);}
  }
});
test('empty hands, fractions, negative counts and nonnumbers are rejected',()=>{
  for(const hand of [[0,0],[-1,2],[1.5,2],[NaN,2],[Infinity,2],['2',1]])assert.throws(()=>theftOutcomes(...hand),RangeError);
  assert.equal(theftOutcomes(0,3)[0].probability,1);
  assert.deepEqual(theftOutcomes(1,0)[0].victim,{ore:0,wheat:0});
});
