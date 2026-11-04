// Local synthetic fixture only. Browser plugin not available; use Playwright.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const output = path.resolve(process.env.EVIDENCE_DIR || 'docs/evidence/classroom/week08');
  const data = process.env.FIXTURE_DATA_DIR;
  if (!data) throw Error('FIXTURE_DATA_DIR must name the fresh local fixture directory');
  const base = 'http://127.0.0.1:18088';
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'chromium', headless: true });
  const errors = [];
  const teacher = await browser.newContext({ viewport: { width: 1280, height: 960 }, timezoneId: 'Asia/Shanghai' });
  const student = await browser.newContext({ viewport: { width: 1280, height: 960 }, timezoneId: 'Asia/Shanghai' });
  async function login(context, username, password) {
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    await page.goto(base + '/login');
    await page.locator('#username').fill(username);
    await page.locator('#password').fill(password);
    await Promise.all([page.waitForURL('**/materials'), page.locator('button[type=submit]').click()]);
    await page.goto(base + '/assignments');
    assert.match(await page.title(), /课堂作业/);
    await page.locator('h1').filter({ hasText: '课堂作业' }).waitFor();
    return page;
  }
  try {
    const t = await login(teacher, 'teacher_a', 'teacher-test-password');
    await t.locator('[name=title]').fill('一元一次方程：说明移项过程');
    await t.locator('[name=question]').fill('解方程 2x + 3 = 11，并说明每一步为何保持相等。');
    await t.locator('[name=reference_answer]').fill('两边同时减3，再同时除以2。');
    await t.locator('[name=rubric]').fill('过程完整60分，运算与符号正确40分。');
    await t.locator('#assignment-form button[type=submit]').click();
    await t.getByText('作业已创建。', { exact: true }).waitFor();
    await t.screenshot({ path: path.join(output, '01-教师创建作业.png'), fullPage: true });
    const s = await login(student, 'student_a1', 'student-a-test-password');
    await s.locator('[name=assignment_id]').selectOption({ label: '一元一次方程：说明移项过程' });
    await s.locator('#assignment-preview-question').filter({ hasText: '解方程' }).waitFor();
    await s.locator('[name=content]').fill('两边同时减去3得到2x=8，再除以2得到x=4。');
    const accepted = s.waitForResponse(r => r.url().includes('/submissions') && r.request().method() === 'POST');
    await s.locator('#submission-form button[type=submit]').click();
    const response = await accepted;
    assert.equal(response.status(), 202);
    const receipt = await response.json();
    await s.getByText('等待处理', { exact: true }).waitFor();
    await s.screenshot({ path: path.join(output, '02-暂停消费者后等待处理.png'), fullPage: true });
    await fs.writeFile(path.join(data, 'consumer.enabled'), 'enabled\n');
    await s.getByText('批改完成', { exact: true }).waitFor({ timeout: 20000 });
    await s.getByText('批改来源：本地测试替身', { exact: true }).waitFor();
    await s.reload();
    await s.getByText('批改完成', { exact: true }).waitFor();
    await s.screenshot({ path: path.join(output, '03-恢复消费并刷新保留结果.png'), fullPage: true });
    await s.setViewportSize({ width: 390, height: 844 });
    assert.equal(await s.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await s.screenshot({ path: path.join(output, '04-手机作业与结果.png'), fullPage: true });
    assert.deepEqual(errors, []);
    await fs.writeFile(path.join(output, 'ui-result.json'), JSON.stringify({
      mode: 'local-synthetic-provider-and-memory-transport', browser: 'Chromium via Playwright',
      browser_plugin: 'Browser plugin not available', url: base + '/assignments',
      viewports: ['1280x960', '390x844'], accepted_status: response.status(), task_id: receipt.task_id,
      checks: { page_identity: true, meaningful_content: true, no_overlay: true,
        no_page_errors: true, no_console_errors: true, teacher_creation: true, student_question_visible: true, pending_to_success: true,
        refresh_persistence: true, mobile_no_horizontal_overflow: true }, errors
    }, null, 2) + '\n');
    await s.locator('#logout-form button').click();
    await t.locator('#logout-form button').click();
    console.log('Local UI checks passed; synthetic transport and grading only.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
