// Browser plugin not available. Real local HTTP with explicitly stubbed models.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const fs=require('node:fs/promises');
const assert=require('node:assert/strict');
(async()=>{
  await fs.mkdir('docs/evidence/classroom/week09',{recursive:true});
  await fs.mkdir('docs/evidence/classroom/week10',{recursive:true});
  const browser=await chromium.launch({channel:'chromium',headless:true});
  const context=await browser.newContext({viewport:{width:1280,height:960},timezoneId:'Asia/Shanghai'});
  const page=await context.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',async d=>{errors.push('Unexpected dialog');await d.dismiss();});
  async function login(name,password){
    await page.goto('http://127.0.0.1:18090/login');await page.locator('#username').fill(name);await page.locator('#password').fill(password);
    await Promise.all([page.waitForURL('**/materials'),page.locator('button[type=submit]').click()]);
  }
  try{
    await login('teacher_a','teacher-test-password');
    await page.goto('http://127.0.0.1:18090/monitoring');
    await page.locator('#message').filter({hasText:'观测数据已更新'}).waitFor();
    assert.equal(await page.locator('#calls-legend').locator('span').count()>=3,true);
    await page.screenshot({path:'docs/evidence/classroom/week10/01-本地三技能观测面板.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:'docs/evidence/classroom/week10/02-手机观测面板.png',fullPage:true});
    await page.setViewportSize({width:1280,height:960});
    await page.goto('http://127.0.0.1:18090/conversations');
    await page.locator('#agent-form').waitFor({state:'attached'});
    await page.locator('details').first().locator('summary').click();
    await page.locator('select option').filter({hasText:'<script>alert(1)</script>'}).first().waitFor({state:'attached'});
    const escaped=await page.locator('select').evaluateAll(nodes=>nodes.some(n=>n.innerHTML.includes('&lt;script&gt;alert(1)&lt;/script&gt;')));
    assert(escaped);assert(!(await page.locator('script').allTextContents()).some(s=>s.includes('alert(1)')));
    await fs.writeFile('docs/evidence/classroom/week09/xss-dom.json',JSON.stringify({mode:'local-synthetic',escaped_dom_source:escaped,injected_script_node:false,unexpected_dialog:false},null,2));
    await page.screenshot({path:'docs/evidence/classroom/week09/01-XSS内容按文本呈现.png',fullPage:false});
    await page.goto('http://127.0.0.1:18090/api/audit-events?user_id=2&limit=3');
    await page.locator('body').filter({hasText:'request_id'}).waitFor();
    await page.screenshot({path:'docs/evidence/classroom/week09/02-教师查询脱敏审计.png',fullPage:false});
    await page.goto('http://127.0.0.1:18090/materials');await page.locator('#logout-form button').click();await page.waitForURL('**/login');
    assert.deepEqual(errors,[]);
    await fs.writeFile('docs/evidence/classroom/week10/ui-result.json',JSON.stringify({mode:'local-stub-model-real-HTTP',browser_plugin:'Browser plugin not available',desktop:'1280x960',mobile:'390x844',checks:{three_skill_series:true,mobile_no_overflow:true,xss_source_escaped:true,audit_query:true},errors},null,2));
    console.log('Local monitoring, mobile, XSS source and audit UI verified.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
