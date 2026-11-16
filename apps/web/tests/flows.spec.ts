import { test, expect } from '@playwright/test';

test('discover, filter, evidence, correction and comparison',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:/从一个领域，认识一种判断力/})).toBeVisible();
  await expect(page.locator('.expert-card')).toHaveCount(5);
  await page.screenshot({path:'../../docs/desktop.png',fullPage:true,animations:'disabled'});
  await page.getByRole('button',{name:'新能源',exact:true}).last().click();
  await expect(page.locator('.expert-card')).toHaveCount(1);
  await page.getByRole('button',{name:'国际能源署',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'国际能源署的合订本'})).toBeVisible();
  await page.getByRole('button',{name:'查看证据与判定'}).click();
  await expect(page.getByRole('dialog',{name:'证据与判定'})).toBeVisible();
  await expect(page.getByRole('link',{name:'IEA · Global EV Outlook 2024'})).toHaveAttribute('href',/iea.org/);
  await page.getByRole('textbox',{name:'纠错说明'}).fill('端到端测试：请人工复核此案例的时间与原文。');
  await page.getByRole('button',{name:'提交人工复核'}).click();
  await expect(page.locator('.review-list')).toContainText('端到端测试');
  await page.getByRole('button',{name:'关闭证据',exact:true}).click();
  await page.getByRole('button',{name:'关闭合订本',exact:true}).click();
  await page.getByRole('button',{name:'对比判断记录'}).click();
  await page.locator('.compare-picker').getByRole('button',{name:'郭明錤'}).click();
  await page.locator('.compare-picker').getByRole('button',{name:'国际能源署'}).click();
  await expect(page.locator('.comparison-grid article')).toHaveCount(2);
  await expect(page.locator('.comparison-notice')).toContainText('跨领域');
  expect(errors).toEqual([]);
});

test('import creates persistent conservative report',async({page})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'添加判断记录'}).click();
  await page.getByPlaceholder('原文作者姓名').fill('测试预测者');
  await page.getByRole('textbox',{name:'原始正文'}).fill('我们预计这个公开项目将于2099年12月31日完成，仍需后续验证。');
  await page.getByRole('button',{name:'提取判断，建立档案'}).click();
  await expect(page.getByRole('dialog',{name:'测试预测者的合订本'})).toBeVisible();
  await expect(page.locator('.profile-timeline')).toContainText('尚未到期');
  await page.getByRole('button',{name:'关注记录',exact:true}).click();
  await expect(page.getByRole('button',{name:'已关注',exact:true})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('dialog',{name:'测试预测者的合订本'})).toBeVisible();
  await page.getByRole('button',{name:'关闭合订本',exact:true}).click();
  await page.getByRole('button',{name:/我的关注/}).click();
  await expect(page.locator('.expert-card').filter({hasText:'测试预测者'}).first()).toBeVisible();
});

test('mobile fits viewport and menus work',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');
  await expect(page.locator('.expert-card').first()).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.getByRole('button',{name:'切换菜单'}).click();
  await page.getByRole('button',{name:'历史合订本',exact:true}).click();
  await expect(page.locator('.page-title')).toContainText('历史合订本');
  await page.screenshot({path:'../../docs/mobile.png',fullPage:true,animations:'disabled'});
});

test('share link opens profile and desktop screenshot',async({page})=>{
  await page.goto('/?expert=kuo');
  await expect(page.getByRole('dialog',{name:'郭明錤的合订本'})).toBeVisible();
  await page.getByRole('button',{name:'关闭合订本',exact:true}).click();
});
