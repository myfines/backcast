import { test, expect, type Page } from '@playwright/test';

// Disposable token for the throwaway E2E API (set in playwright.config.ts); not a real secret.
const E2E_REVIEW_TOKEN = 'e2e-review-token';
const E2E_WORKER_TOKEN = 'e2e-worker-token';
const E2E_API = 'http://127.0.0.1:8001/api/v1';

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
  await page.getByRole('button', { name: '关注', exact: true }).click();
  await expect(page.getByRole('button', { name: '已关注', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: '已关注', exact: true })).toBeVisible();

  await page.getByRole('link', { name: /我的关注/ }).click();
  await expect(page.locator('.expert-card').filter({ hasText: '测试预测者' })).toBeVisible();
  // Unfollowing from the follow list removes the card without a manual refresh.
  await page.getByRole('button', { name: '已关注：测试预测者' }).click();
  await expect(page.locator('.expert-card').filter({ hasText: '测试预测者' })).toHaveCount(0);
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

test('search, append import and casebook domain filter', async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto('/');
  await page.getByRole('searchbox').fill('Gurman');
  await expect(page).toHaveURL(/q=Gurman/);
  await expect(page.locator('.expert-card')).toHaveCount(1);
  await expect(page.locator('.expert-card')).toContainText('Mark Gurman');

  await page.goto('/import?author=iea');
  await expect(page.getByRole('tab', { name: '追加到已有档案' })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('textbox', { name: '原始正文' }).fill('国际能源署预计全球电动车年销量将于2030年12月31日前突破4000万辆，仍需后续数据验证。');
  await page.getByRole('button', { name: '提取判断，建立档案' }).click();
  await expect(page.getByText('已为 国际能源署 建立记录')).toBeVisible();
  await page.getByRole('link', { name: '打开合订本' }).click();
  await expect(page.getByText('原始材料 2 份')).toBeVisible();

  await page.getByRole('combobox', { name: '领域' }).selectOption('新能源');
  await expect(page).toHaveURL(/domain=/);
  await expect(page.locator('.profile-timeline article').first()).toBeVisible();
  expect(errors).toEqual([]);
});

test('reviewer can resolve a claim and record sampling', async ({ page }) => {
  await page.goto('/review');
  await page.getByRole('textbox', { name: '复核令牌' }).fill(E2E_REVIEW_TOKEN);
  await page.getByRole('button', { name: '使用令牌' }).click();

  await page.getByRole('tab', { name: '命题裁定' }).click();
  await page.getByLabel('选择命题').selectOption('vision');
  const resolve = page.getByRole('form', { name: '命题裁定' });
  await expect(resolve.getByRole('checkbox').first()).toBeChecked();
  await resolve.getByLabel('判定 *').selectOption('correct');
  await resolve.getByLabel('独立事件标识 *').fill('vision-pro-us-launch-2024');
  await resolve.getByLabel('结果发生时间 *').fill('2024-02-02');
  await resolve.getByLabel('裁定理由 *').fill('苹果官网确认 2 月 2 日在美国上市，落在所述窗口内。');
  await resolve.getByLabel('复核人 *').fill('E2E');
  await resolve.getByRole('button', { name: '提交裁定' }).click();
  await expect(page.getByText(/^已裁定/)).toBeVisible();
  await expect(page.locator('.audit-list')).toContainText('人工裁定');

  await page.getByRole('tab', { name: '采样声明' }).click();
  const sampling = page.getByRole('form', { name: '采样声明' });
  await sampling.getByLabel('作者 *').selectOption('kuo');
  await sampling.getByLabel('窗口开始 *').fill('2023-01-01');
  await sampling.getByLabel('窗口结束 *').fill('2024-06-30');
  await sampling.getByLabel('来源索引 URL *').fill('https://example.com/kuo-index');
  await sampling.getByLabel('复核人 *').fill('E2E');
  await sampling.getByLabel('说明 *').fill('核对作者公开文章索引，窗口内判断已全部收录。');
  await sampling.getByRole('button', { name: '保存采样声明' }).click();
  await expect(page.getByText('已记录 郭明錤 在 消费科技 的采样声明')).toBeVisible();
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

test('research: rejects non-profile targets and audits a public excerpt without inventing a verdict', async ({ page, request }) => {
  const errors = trackErrors(page);
  await page.goto('/research');
  await expect(page.getByRole('heading', { level: 1, name: '调查知乎答主' })).toBeVisible();

  // A question link is not a person: the backend refuses before any network access.
  await page.getByRole('textbox', { name: '答主主页' }).fill('https://www.zhihu.com/question/123456');
  await page.getByRole('textbox', { name: '想判断什么' }).fill('检查他的技术说法');
  await page.getByRole('button', { name: '开始调查' }).click();
  await expect(page.getByRole('form', { name: '调查表单' }).getByRole('alert')).toContainText('知乎个人主页');

  await page.getByRole('tab', { name: '核查一段公开文字' }).click();
  await page.getByRole('textbox', { name: '原文链接' }).fill('https://zhuanlan.zhihu.com/p/678912290');
  await page.getByRole('textbox', { name: '标题' }).fill('端到端测试节选');
  await page.getByRole('textbox', { name: '公开节选' }).fill('OpenAI通过训练一个1750亿参数的自回归语言模型，即GPT-3，随后继续迭代。');
  await page.getByRole('textbox', { name: '想判断什么' }).fill('检查这条技术事实');
  await page.getByRole('button', { name: '开始调查' }).click();

  await expect(page).toHaveURL(/\/research\/[0-9a-f-]{36}$/);
  const id = page.url().split('/').pop()!;
  await expect(page.getByRole('status')).toContainText('等待分析');
  await expect(page.getByText('输入节选不是按答主采集的历史列表')).toBeVisible();
  await expect(page.getByRole('link', { name: /端到端测试节选/ })).toHaveAttribute('href', /zhihu\.com/);
  // No analysis yet: no verdict counts and no recommendation wording.
  await expect(page.getByRole('heading', { name: '核查结果' })).toHaveCount(0);

  // The analyst returns a claim without evidence; the backend must keep it as "insufficient".
  const submit = await request.post(`${E2E_API}/research-jobs/${id}/analysis`, {
    headers: { 'X-Worker-Token': E2E_WORKER_TOKEN },
    data: {
      model: 'e2e-analyst',
      claims: [{ quote: '1750亿参数的自回归语言模型', statement: 'GPT-3 是 1750 亿参数的自回归语言模型。', kind: 'fact', status: 'insufficient', reason: '测试中没有提供可下载的外部证据。', evidence: [] },
        { quote: '随后继续迭代', statement: '作者认为模型还会继续迭代。', kind: 'opinion', mode: 'intuition', reading: '作者凭直觉认为模型会继续更新。', reason: '直觉判断，没有推导，也没有外部证据。', evidence: [] }],
      summary: '端到端测试：没有证据。',
      limitations: ['测试数据，不代表真实调查。'],
    },
  });
  expect(submit.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByRole('heading', { name: '核查结果' })).toBeVisible();
  await expect(page.getByText('不据此推荐或否定这个人')).toBeVisible();
  await expect(page.getByText('证据不足（条）')).toBeVisible();
  // Judgements are counted on their own line, not folded into the fact counts.
  await expect(page.getByText('另外分析的判断（1 条）')).toBeVisible();
  await page.getByRole('link', { name: 'GPT-3 是 1750 亿参数的自回归语言模型。' }).click();
  await expect(page).toHaveURL(/\/claims\//);
  await expect(page.getByRole('heading', { name: '原意解读' })).toBeVisible();
  await expect(page.getByText('明确断言')).toBeVisible();
  expect(errors).toEqual([]);
});
