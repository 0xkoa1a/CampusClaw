// Browser plugin not available. Captures the real CLab service through SSH loopback.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const phase = process.argv[2];
  if (!['pending', 'succeeded'].includes(phase)) throw Error('Pass pending or succeeded');
  const output = path.resolve('docs/evidence/classroom/week08');
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'chromium', headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 960 }, timezoneId: 'Asia/Shanghai' });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  try {
    await page.goto('http://127.0.0.1:18088/login');
    await page.locator('#username').fill('student_a1');
    await page.locator('#password').fill('student-a-test-password');
    await Promise.all([page.waitForURL('**/materials'), page.locator('button[type=submit]').click()]);
    await page.goto('http://127.0.0.1:18088/assignments');
    assert.match(await page.title(), /课堂作业/);
    await page.locator('.task-card').first().waitFor();
    const states = await page.locator('.task-state').allTextContents();
    assert(states.length >= 20);
    assert(states.every(s => s === (phase === 'pending' ? '等待处理' : '批改完成')));
    if (phase === 'succeeded') {
      await page.getByText('批改来源：课程网关', { exact: true }).first().waitFor();
      assert.equal(await page.getByText('批改来源：本地测试替身', { exact: true }).count(), 0);
      await page.reload();
      await page.getByText('批改来源：课程网关', { exact: true }).first().waitFor();
    }
    await page.locator('.task-card').first().scrollIntoViewIfNeeded();
    const name = phase === 'pending' ? '05-CLab真实队列等待处理.png' : '06-CLab真实网关批改结果.png';
    await page.screenshot({ path: path.join(output, name), fullPage: false });
    if (phase === 'succeeded') {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.locator('.task-card').first().scrollIntoViewIfNeeded();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: path.join(output, '07-CLab手机批改结果.png'), fullPage: false });
    }
    assert.deepEqual(errors, []);
    await fs.writeFile(path.join(output, `remote-ui-${phase}.json`), JSON.stringify({
      mode: 'CLab-real-RabbitMQ-and-course-gateway', phase, url: page.url(),
      browser: 'Chromium via Playwright', browser_plugin: 'Browser plugin not available',
      checks: { page_identity: true, meaningful_content: true, state_matches: true,
        no_runtime_or_console_errors: true, screenshot: true, reload: phase === 'succeeded' },
      task_count: states.length, errors
    }, null, 2) + '\n');
    await page.locator('#logout-form button').click();
    await page.waitForURL('**/login');
    console.log(`CLab ${phase} UI verified.`);
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
