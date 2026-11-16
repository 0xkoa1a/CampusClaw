// Real mobile-sized browser walk-through; no device or human feedback is implied.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const fs=require('node:fs/promises');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chromium',headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Asia/Shanghai'});
 const errors=[],states=[];page.on('pageerror',e=>errors.push(e.message));
 const base='http://127.0.0.1:18100';
 async function login(name,password){await page.goto(base+'/login');await page.locator('#username').fill(name);await page.locator('#password').fill(password);await Promise.all([page.waitForURL('**/materials'),page.locator('button[type=submit]').click()]);}
 async function logout(){await page.goto(base+'/materials');await page.locator('#logout-form button').click();await page.waitForURL('**/login');}
 try{
  await login('student_a1','student-a-test-password');
  await page.goto(base+'/assignments');
  const select=page.locator('#submission-form select');
  await select.locator('option[value="2"]').waitFor({state:'attached'});await select.selectOption('2');
  await page.locator('#submission-form textarea').fill('4');
  const acceptedWait=page.waitForResponse(r=>r.url().endsWith('/api/assignments/2/submissions')&&r.request().method()==='POST');
  await page.locator('#submission-form button[type=submit]').click();
  const accepted=await acceptedWait;assert.equal(accepted.status(),202);
  const receipt=await accepted.json();states.push(receipt.status);
  assert.equal(typeof receipt.task_id,'string');
  page.on('response',async r=>{if(r.url().endsWith('/api/tasks/'+receipt.task_id)){try{states.push((await r.json()).task.status);}catch{}}});
  await page.locator('.task-succeeded').filter({hasText:receipt.task_id}).waitFor({timeout:180000});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('.task-succeeded').filter({hasText:receipt.task_id}).scrollIntoViewIfNeeded();
  await page.screenshot({path:'docs/evidence/classroom/week10/07-手机提交与真实批改完成.png',fullPage:false});
  await logout();
  await login('student_b1','student-b-test-password');
  const foreign=await page.evaluate(async()=>{const r=await fetch('/api/materials/7');return {status:r.status,body:await r.json()};});
  assert.equal(foreign.status,404);await logout();
  await login('teacher_a','teacher-test-password');
  const ownAudit=await page.evaluate(async()=>await(await fetch('/api/audit-events?user_id=2&limit=50')).json());
  const submitted=ownAudit.audit_events.filter(e=>e.fields.status===202&&e.fields.operation==='POST');
  assert(submitted.length>0);
  const foreignAudit=await page.evaluate(async()=>await(await fetch('/api/audit-events?user_id=3&limit=30')).json());
  assert.equal(foreignAudit.audit_events.length,0);await logout();assert.deepEqual(errors,[]);
  await fs.writeFile('reports/week10-local/clab-mobile-walkthrough.json',JSON.stringify({mode:'real-CLab-mobile-viewport',viewport:'390x844',submission_http_status:202,task_id:receipt.task_id,observed_statuses:[...new Set(states)],completed:true,cross_class_material:foreign,teacher_own_class_submission_audit:submitted,foreign_class_audit_visible:false,errors},null,2)+'\n');
  console.log('Mobile submission, real grading, cross-class 404 and teacher audit verified.');
 }finally{await page.evaluate(async()=>{const token=sessionStorage.getItem('campusclaw.accessToken');if(token)await fetch('/api/logout',{method:'POST',headers:{Authorization:'Bearer '+token}});}).catch(()=>{});await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
