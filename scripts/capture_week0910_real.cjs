// Browser plugin unavailable; Playwright checks the real CLab service over SSH.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const fs=require('node:fs/promises');
const assert=require('node:assert/strict');
(async()=>{
 const root='docs/evidence/classroom/week10/';
 const browser=await chromium.launch({channel:'chromium',headless:true});
 const context=await browser.newContext({viewport:{width:1280,height:960},timezoneId:'Asia/Shanghai'});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:18100/login');
  await page.locator('#username').fill('teacher_a');
  await page.locator('#password').fill('teacher-test-password');
  await Promise.all([page.waitForURL('**/materials'),page.locator('button[type=submit]').click()]);
  await page.goto('http://127.0.0.1:18100/monitoring');
  await page.locator('#message').filter({hasText:'观测数据已更新'}).waitFor();
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/monitoring?window=86400')),page.selectOption('#window','86400')]);
  const dashboard=await page.evaluate(async()=>await(await fetch('/api/monitoring?window=86400')).json());
  assert(dashboard.has_skill_data && dashboard.skills.length>=3);
  await fs.writeFile('reports/week10-local/clab-monitoring.json',JSON.stringify(dashboard,null,2)+'\n');
  await page.screenshot({path:root+'04-CLab真实服务观测.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:root+'05-CLab手机观测.png',fullPage:true});
  await page.setViewportSize({width:1280,height:960});
  const audit=await page.evaluate(async()=>await(await fetch('/api/audit-events?user_id=2&limit=200')).json());
  const denied=audit.audit_events.filter(x=>x.fields.status===403 && x.fields.operation==='PUT');
  assert(denied.length);
  await fs.writeFile('reports/week10-local/clab-audit-denied.json',JSON.stringify({query:{user_id:2,limit:200},audit_events:denied},null,2)+'\n');
  await page.goto('http://127.0.0.1:18100/api/audit-events?user_id=2&limit=5');
  await page.locator('body').filter({hasText:'request_id'}).waitFor();
  await page.screenshot({path:'docs/evidence/classroom/week09/03-CLab教师审计回查.png',fullPage:true});
  await page.goto('http://127.0.0.1:18100/materials');
  await page.locator('#logout-form button').click();await page.waitForURL('**/login');
  const alert=JSON.parse(await fs.readFile('reports/week10-local/clab-alert-trigger.json','utf8'));
  const runtime=JSON.parse(await fs.readFile('reports/week10-local/clab-runtime.json','utf8'));
  const ci=JSON.parse(await fs.readFile('reports/week10-local/ci-green.json','utf8'));
  const container=JSON.parse(await fs.readFile('reports/week10-local/container-green.json','utf8'));
  const esc=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  const html=`<!doctype html><meta charset="utf-8"><title>CLab与CI运行记录摘录</title><style>body{font:16px system-ui;padding:30px;color:#182432;max-width:1180px;margin:auto}h1{font-size:26px}section{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{border:1px solid #cbd5dc;padding:20px;border-radius:12px;min-width:0}pre{font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>CLab 与 CI：实际运行记录摘录</h1><p>内容读取自仓库中保存的原始 JSON。告警演练在 CLab 容器内使用可控模型故障与真实 HTTP，持续条件为 300 秒。</p><section><article><h2>告警已触发并写入教师站内通知</h2><pre>${esc(JSON.stringify(alert,null,2))}</pre></article><article><h2>真实容器与发布门禁</h2><pre>${esc(JSON.stringify({containers:runtime.containers,runtime_probe:{...runtime.runtime_probe,skill_events:undefined},ci:{url:ci.url,conclusion:ci.conclusion},container:{url:container.url,conclusion:container.conclusion}},null,2))}</pre></article></section>`;
  await fs.writeFile(root+'clab-runtime-output.html',html);
  await page.setContent(html);await page.screenshot({path:root+'06-CLab告警与容器运行记录.png',fullPage:true});
  assert.deepEqual(errors,[]);
  await fs.writeFile(root+'clab-ui-result.json',JSON.stringify({mode:'CLab-real-gateway-over-SSH',desktop:'1280x960',mobile:'390x844',three_skill_series:true,mobile_no_overflow:true,teacher_audit_403_record:true,errors},null,2)+'\n');
  console.log('CLab desktop/mobile monitoring, teacher audit and runtime evidence captured.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
