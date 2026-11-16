import { test, expect, type Page } from '@playwright/test';

// Disposable token for the throwaway E2E API (set in playwright.config.ts); not a real secret.
const E2E_REVIEW_TOKEN = 'e2e-review-token';

function trackErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  return errors;
}

test('discover, filter, casebook, evidence and correction', async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /从一个领域，认识一种判断力/ })).toBeVisible();
  await expect(page.locator('.expert-card')).toHaveCount(5);
  // Null metrics never render as 0%.
  await expect(page.locator('.expert-card').first()).toContainText('样本不足');
  await expect(page.locator('main')).not.toContainText('0%');
  await page.screenshot({ path: '../../docs/desktop.png', fullPage: true, animations: 'disabled' });

  await page.getByRole('group', { name: '按领域筛选' }).getByRole('button', { name: '新能源', exact: true }).click();
  await expect(page).toHaveURL(/domain=/);
  await expect(page.locator('.expert-card')).toHaveCount(1);

  await page.getByRole('link', { name: '国际能源署', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: /国际能源署的合订本/ })).toBeVisible();
  await expect(page.getByText('不据此排名或推荐')).toBeVisible();

  await page.getByRole('link', { name: '查看证据与判定' }).first().click();
  const drawer = page.getByRole('dialog', { name: '证据与判定' });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole('link', { name: 'IEA · Global EV Outlook 2024' })).toHaveAttribute('href', /iea.org/);

  await drawer.getByRole('textbox', { name: '纠错说明' }).fill('端到端测试：请人工复核此案例的时间与原文。');
  await drawer.getByRole('button', { name: '提交人工复核' }).click();
  await expect(drawer.locator('.review-list')).toContainText('端到端测试');
  await expect(drawer.locator('.audit-list')).toContainText('提交纠错');

  await page.getByRole('button', { name: '关闭证据', exact: true }).click();
  await expect(drawer).toBeHidden();
  expect(errors).toEqual([]);
});

test('as_of view and comparison without declaring a winner', async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto('/experts/kuo?as_of=2023-12-31');
  await expect(page.locator('.asof-flag')).toContainText('2023.12.31');
  // Before the launch the evidence did not exist yet.
  await expect(page.locator('.profile-timeline')).not.toContainText('结果吻合');

  await page.goto('/compare');
  await page.locator('.compare-picker').getByRole('button', { name: '郭明錤' }).click();
  await page.locator('.compare-picker').getByRole('button', { name: '国际能源署' }).click();
  await expect(page.locator('.comparison-grid article')).toHaveCount(2);
  await expect(page.locator('.comparison-notice')).toContainText('跨领域');
  await expect(page.locator('.comparison-notice')).toContainText('不宣布胜者');

  await page.goto('/compare?ids=kuo,gurman');
  await page.getByRole('button', { name: /按“消费科技”口径比较/ }).click();
  await expect(page).toHaveURL(/domain=/);
  await expect(page.locator('.comparison-notice')).not.toContainText('跨领域');
  await expect(page.locator('.comparison-grid')).toContainText('无共同事件');
  expect(errors).toEqual([]);
});

test('import creates persistent conservative report and follow persists', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: '添加判断记录' }).first().click();
  await page.getByPlaceholder('原文作者姓名').fill('测试预测者');
  await page.getByRole('textbox', { name: '原始正文' }).fill('我们预计这个公开项目将于2099年12月31日完成，仍需后续验证。');
  await page.getByRole('button', { name: '提取判断，建立档案' }).click();
  await expect(page.getByText('已为 测试预测者 建立记录')).toBeVisible();
  await page.getByRole('link', { name: '打开合订本' }).click();

  await expect(page.getByRole('heading', { level: 1, name: /测试预测者的合订本/ })).toBeVisible();
  await expect(page.locator('.profile-timeline')).toContainText('尚未到期');
  await expect(page.getByText('作者身份与日期未经核实')).toBeVisible();
  await page.getByRole('button', { name: '关注记录', exact: true }).click();
  await expect(page.getByRole('button', { name: '已关注', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: '已关注', exact: true })).toBeVisible();

  await page.getByRole('link', { name: /我的关注/ }).click();
  await expect(page.locator('.expert-card').filter({ hasText: '测试预测者' })).toBeVisible();
});

test('review console needs a valid token and writes an audit trail', async ({ page }) => {
  await page.goto('/review');
  await page.getByRole('tab', { name: '证据出处' }).click();
  await page.getByLabel('选择命题').selectOption('vision');
  await expect(page.getByText('请先在上方输入复核令牌')).toBeVisible();

  await page.getByRole('textbox', { name: '复核令牌' }).fill('wrong-token');
  await page.getByRole('button', { name: '使用令牌' }).click();
  const form = page.getByRole('form', { name: '证据出处标注' });
  await form.getByLabel('复核人 *').fill('E2E');
  await form.getByLabel('理由 *').fill('核对来源类型：苹果官网新闻稿属于一手发布');
  await form.getByLabel('来源类型').selectOption('primary');
  await form.getByRole('button', { name: '保存标注' }).click();
  await expect(form.getByRole('alert')).toContainText('有效的复核令牌');

  await page.getByRole('button', { name: '清除令牌' }).click();
  await page.getByRole('textbox', { name: '复核令牌' }).fill(E2E_REVIEW_TOKEN);
  await page.getByRole('button', { name: '使用令牌' }).click();
  await form.getByLabel('复核人 *').fill('E2E');
  await form.getByLabel('理由 *').fill('核对来源类型：苹果官网新闻稿属于一手发布');
  await form.getByLabel('来源类型').selectOption('primary');
  await form.getByRole('button', { name: '保存标注' }).click();
  await expect(page.getByText('证据元数据已更新')).toBeVisible();
  await expect(page.locator('.audit-list')).toContainText('证据出处标注');
});

test('mobile fits viewport and menu works', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.locator('.expert-card').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../../docs/mobile.png', fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: '切换菜单' }).click();
  await page.getByRole('link', { name: '对比判断记录' }).click();
  await expect(page.locator('.page-title')).toContainText('对比判断记录');
  await page.goto('/experts/kuo');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('legacy share link redirects to the casebook', async ({ page }) => {
  await page.goto('/?expert=kuo');
  await expect(page).toHaveURL(/\/experts\/kuo$/);
  await expect(page.getByRole('heading', { level: 1, name: /郭明錤的合订本/ })).toBeVisible();
});
