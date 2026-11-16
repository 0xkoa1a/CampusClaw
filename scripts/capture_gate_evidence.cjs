// Render actual command output, clearly identified as an evidence document.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const fs=require('node:fs/promises');
(async()=>{
 const escape=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
 const red=await fs.readFile('reports/week10-local/gate-red.txt','utf8');
 const green=await fs.readFile('reports/week10-local/gate-green.txt','utf8');
 const html=`<!doctype html><meta charset="utf-8"><title>门禁真实执行记录</title><style>body{font-family:system-ui;padding:24px;color:#172331}section{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{border:1px solid #ccd5dd;padding:20px;border-radius:10px;min-width:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}h1{font-size:26px}</style><h1>隔离副本：make check 真实执行输出</h1><p>将未登录请求的预期状态从错误的 200 修正为 401。以下内容来自保存的命令日志。</p><section><article><h2>故意改坏：非零退出</h2><pre>${escape(red.split('\n').slice(-26).join('\n'))}</pre></article><article><h2>修复后：退出码 0</h2><pre>${escape(green)}</pre></article></section>`;
 await fs.writeFile('docs/evidence/classroom/week10/gate-output.html',html);
 const browser=await chromium.launch({channel:'chromium',headless:true});
 try{const page=await browser.newPage({viewport:{width:1440,height:1050}});await page.setContent(html);await page.screenshot({path:'docs/evidence/classroom/week10/03-门禁故意改坏与修复.png',fullPage:true});}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
