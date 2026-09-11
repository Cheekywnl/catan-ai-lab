import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('overview, all chapters, source citations, and direct-link reloads',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const failed=[];page.on('response',r=>{if(r.url().startsWith('http://127.0.0.1')&&r.status()>=400)failed.push(r.url());});
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'A smarter way to play.'})).toBeVisible();
  await page.getByRole('link',{name:'Explore the blueprint'}).click();
  await expect(page.locator('.research-article h1')).toContainText('Recommendation');
  for(let id=1;id<=12;id++){
    await page.goto(`/#research/${id}`);
    await expect(page.locator('.research-article')).toBeVisible();
    expect(await page.locator('.prose').innerText()).toHaveLengthGreaterThan(700);
    await expect(page.locator('.chapter-nav a[aria-current="page"]')).toHaveCount(1);
  }
  await page.goto('/#research/3');
  await expect(page.locator('.prose a[href="https://ojs.aaai.org/index.php/AIIDE/article/view/13014"]').first()).toBeVisible();
  await page.reload();await expect(page.locator('.research-article h1')).toContainText('Existing work');
  expect(errors).toEqual([]);expect(failed).toEqual([]);
});

test('project and source filters provide real, recoverable results',async({page})=>{
  await page.goto('/#projects');
  await expect(page.locator('.project-card')).toHaveCount(12);
  await page.getByLabel('Focus',{exact:true}).selectOption('Search');
  await expect(page.locator('.project-card')).toHaveCount(2);
  await page.getByLabel('Find a project').fill('Rust');
  await expect(page.locator('.project-card')).toHaveCount(1);
  await expect(page.locator('.project-card h2')).toHaveText('Monte Catano');
  await page.getByLabel('Find a project').fill('not-a-project');
  await expect(page.getByText('No projects match.')).toBeVisible();
  await page.getByLabel('Find a project').fill('');
  await page.getByLabel('Focus',{exact:true}).selectOption('all');
  await expect(page.locator('.project-card')).toHaveCount(12);
  await page.goto('/#sources');
  await expect(page.locator('.source-entry')).toHaveCount(37);
  await page.getByLabel('Source type').selectOption('code');
  await expect(page.locator('.source-entry')).toHaveCount(5);
  await page.getByLabel('Search the evidence').fill('Gym');
  await expect(page.locator('.source-entry')).toHaveCount(1);
  await expect(page.locator('#source-count')).toHaveText('1 source');
  await page.getByLabel('Source type').selectOption('all');
  await page.getByLabel('Search the evidence').fill('37');
  await expect(page.locator('.source-entry')).toHaveCount(1);
  await expect(page.locator('.source-copy')).toContainText('Community Guidelines');
});

test('global search, query escaping, unknown routes, and report download',async({page})=>{
  await page.goto('/');
  await page.getByLabel('Search all research').fill('POMCP');
  await page.getByLabel('Search all research').press('Enter');
  await expect(page.locator('.search-result').first()).toBeVisible();
  await expect(page.locator('.source-entry').first()).toBeVisible();
  await page.getByLabel('Search all research').fill('<img src=x onerror=alert(1)>');
  await page.getByLabel('Search all research').press('Enter');
  await expect(page.getByText('No matches found.')).toBeVisible();
  await expect(page.locator('main img')).toHaveCount(0);
  await page.goto('/#missing');
  await expect(page.getByRole('heading',{name:'That page could not be found.'})).toBeVisible();
  await page.getByRole('link',{name:'Back to overview'}).click();
  await page.goto('/#research/1');
  const downloadPromise=page.waitForEvent('download');
  const response=await page.request.get('/catan-ai-research.md');
  expect(response.ok()).toBeTruthy();expect(await response.text()).toContain('Sources and evidence register');
  await page.getByRole('link',{name:'Download the full report'}).click();
  const download=await downloadPromise;expect(download.suggestedFilename()).toBe('catan-ai-research.md');
});

test('architecture selection and exact correlated belief calculations',async({page})=>{
  await page.goto('/#architecture');
  await page.locator('a[href="#architecture/believe"]').click();
  await expect(page.locator('#component-detail h2')).toHaveText('Keep possible hands, with probabilities.');
  await page.goto('/#belief');
  await expect(page.locator('.outcome')).toHaveCount(2);
  await expect(page.locator('.outcome-header').first()).toContainText('66.7');
  await expect(page.locator('.outcome-header').last()).toContainText('33.3');
  await page.getByLabel('Ore cards').fill('0');
  await expect(page.locator('.outcome')).toHaveCount(1);
  await expect(page.locator('.outcome-header')).toContainText('100.0');
  await page.getByLabel('Wheat cards').fill('0');
  await expect(page.getByRole('alert')).toContainText('at least one card');
  await page.getByRole('button',{name:'Reset example'}).click();
  await expect(page.locator('.outcome')).toHaveCount(2);
  await page.getByLabel('Ore cards').fill('1.5');
  await expect(page.getByRole('alert')).toBeVisible();
});

test('all principal views meet automated WCAG checks and fit the viewport',async({page})=>{
  test.setTimeout(120000);
  for(const route of ['overview','research/3','projects','architecture','belief','roadmap','sources','search?q=POMCP']){
    await page.goto('/#'+route);
    await expect(page.locator('main h1')).toHaveCount(1);
    await page.evaluate(()=>document.fonts.ready);
    const a11y=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
    expect.soft(a11y.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),route).toEqual([]);
    const width=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
    expect(width.scroll,route).toBeLessThanOrEqual(width.viewport+1);
  }
});

test('keyboard skip link and navigation preserve a usable focus target',async({page},testInfo)=>{
  test.skip(testInfo.project.name==='mobile','Hardware keyboard behavior is checked on desktop.');
  await page.goto('/');await page.keyboard.press('Tab');
  await expect(page.getByRole('link',{name:'Skip to content'})).toBeFocused();
  await page.keyboard.press('Enter');await expect(page.locator('main')).toBeFocused();
  await expect(page.getByRole('heading',{name:'A smarter way to play.'})).toBeVisible();
  await page.getByRole('link',{name:'Build roadmap',exact:true}).click();
  await expect(page.locator('main')).toBeFocused();
  await expect(page.locator('.roadmap-stage')).toHaveCount(5);
});

expect.extend({toHaveLengthGreaterThan(received,minimum){return {pass:received.length>minimum,message:()=>`Expected text length ${received.length} to exceed ${minimum}`};}});
