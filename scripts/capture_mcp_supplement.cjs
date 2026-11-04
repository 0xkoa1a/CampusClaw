// Browser plugin not available. Real CLab UI via the loopback SSH tunnel.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const dir = path.resolve('docs/evidence/classroom/week06-supplement');
  const quota = JSON.parse(await fs.readFile(path.join(dir, 'real-quota.json'), 'utf8'));
  const error = JSON.parse(await fs.readFile(path.join(dir, 'real-error.json'), 'utf8'));
  const browser = await chromium.launch({ channel: 'chromium', headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 960 }, timezoneId: 'Asia/Shanghai' });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  async function login(username, password) {
    await page.goto('http://127.0.0.1:18089/login');
    await page.locator('#username').fill(username);
    await page.locator('#password').fill(password);
    await Promise.all([page.waitForURL('**/materials'), page.locator('button[type=submit]').click()]);
  }
  async function logout() {
    await page.locator('#logout-form button').click();
    await page.waitForURL('**/login');
  }
  try {
    await login('teacher_a', 'teacher-test-password');
    await page.goto('http://127.0.0.1:18089/mcp');
    await page.locator('#audit-rows tr').first().waitFor();
    const statuses = await page.locator('#audit-rows tr td:nth-child(2)').allTextContents();
    for (const expected of ['ok', 'denied', 'error']) assert(statuses.includes(expected));
    await page.locator('.audit-panel').screenshot({ path: path.join(dir, '01-真实MCP成功拒绝错误审计.png') });
    await logout();
    await login('student_a1', 'student-a-test-password');
    await page.goto(`http://127.0.0.1:18089/conversations?id=${quota.conversation_id}`);
    assert.match(await page.title(), /解题助手/);
    await page.locator('.message.assistant').filter({ hasText: '84' }).waitFor();
    await page.screenshot({ path: path.join(dir, '02-调用上限后完成回答.png'), fullPage: false });
    await page.goto(`http://127.0.0.1:18089/conversations?id=${error.conversation_id}`);
    await page.locator('.message.assistant').filter({ hasText: '工具不可用' }).waitFor();
    await page.screenshot({ path: path.join(dir, '03-工具停机后完成错误说明.png'), fullPage: false });
    await logout();
    assert.deepEqual(errors, []);
    await fs.writeFile(path.join(dir, 'ui-result.json'), JSON.stringify({
      mode: 'CLab-real-MCP-and-course-gateway', browser_plugin: 'Browser plugin not available',
      viewport: '1280x960', checks: { audit_ok_denied_error: true, quota_answer: true,
        error_answer: true, no_runtime_or_console_errors: true }, errors
    }, null, 2) + '\n');
    console.log('Real MCP audit, quota and error UI checks passed.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
