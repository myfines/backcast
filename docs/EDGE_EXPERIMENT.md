# Edge DOM 采集实验（保留，不作为当前主线）

2026-11-17 保存代码检查点。当前产品优先走官方 API；本实验不宣称稳定可用。

- `requirements-edge.txt`：可选 Playwright 依赖，使用本机 Microsoft Edge。
- `scripts/zhihu-edge.py`：专用本机配置目录登录、状态查看、正文导出。
- `services/api/edge_collector.py`：DOM读取、作者校验、摘要拒绝、正文断点、加载预算。
- `services/api/edge_worker.py`：API隔离工作器；仅当明确设置 `ZHIHU_BACKEND=edge` 时启用。

此前在用户已登录的普通 Edge 中实际观察到80条回答卡片，并展开过1条正文，读取发表和编辑时间。这只证明该次浏览器操作成功，不等于此独立工作器已完成实采验证。

专用配置目录首次打开时触发知乎安全验证；用户停止电脑操作，登录联调未完成。随后代码已明确启用 Chromium sandbox，但这次启动参数修改没有重新进行真人登录实测。没有绕过验证。

核心9项离线测试已通过，包括断点续采、折叠摘要拒绝、作者不匹配、访问拒绝保留材料与加载停滞不冒充结束；本机完整工作区此前123项测试通过。没有证明长期稳定性、文章完整覆盖或部署后可无人值守。

需要重新研究此路线时，先在本机运行：

```powershell
python -m pip install -r requirements-edge.txt
python scripts/zhihu-edge.py login
python scripts/zhihu-edge.py collect zhang-jia-wei --limit 3 --pages 1
```

正常登录和网站要求的验证由用户完成。专用配置、登录态、断点、导出均位于被忽略的 `.local/`，不进入Git或APK。
