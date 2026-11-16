// The isolated local SQLite fixture contains a literal <script> lecture title.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const fs=require('node:fs/promises');const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chromium',headless:true});
 const page=await browser.newPage({viewport:{width:1280,height:960}});const dialogs=[];
 page.on('dialog',async d=>{dialogs.push(d.message());await d.dismiss();});
 try{
  await page.goto('http://127.0.0.1:18090/login');await page.locator('#username').fill('teacher_a');await page.locator('#password').fill('teacher-test-password');
  await Promise.all([page.waitForURL('**/materials'),page.locator('button[type=submit]').click()]);
  const title=page.locator('.row-title').filter({hasText:'<script>alert(1)</script>'});await title.waitFor();
  assert(await title.evaluate(n=>n.innerHTML.includes('&lt;script&gt;alert(1)&lt;/script&gt;')));
  assert.equal(await page.locator('.material-table script').count(),0);assert.deepEqual(dialogs,[]);
  await page.screenshot({path:'docs/evidence/classroom/week09/01-XSS内容按文本呈现.png',fullPage:false});
  await fs.writeFile('docs/evidence/classroom/week09/xss-dom.json',JSON.stringify({mode:'local-synthetic-lecture-title',input:'<script>alert(1)</script>',escaped_dom_source:true,injected_script_node:false,unexpected_dialog:false},null,2)+'\n');
  await page.locator('#logout-form button').click();await page.waitForURL('**/login');console.log('Lecture-title XSS escaped in actual DOM and visibly captured.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
