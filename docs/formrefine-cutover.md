# FormRefine 正式域名切换与回滚

## 验收入口

通过 [测试站](https://staging.formrefine.ai/app) 验收 Google 登录、视频上传、模板对比、历史报告和原视频。第二个 Google 账号的线上验收按当前范围暂缓，隔离回归仍覆盖两个测试身份。

## 准备正式环境

1. 用相同版本部署独立 FastAPI 服务。设置 `ENGINE_AUTH_ORIGIN=https://formrefine.ai`、`SEO_SITE_URL=https://formrefine.ai` 和 `SEO_INDEXABLE=true`。正式服务使用独立持久卷，分别设置 `UPLOAD_DIR`、`RESULTS_DIR`、`TRIAL_DB_PATH` 和 `FEEDBACK_DIR`。`STAGING_ENGINE_AUTH` 仅用于正在运行的测试环境和其临时路径。
2. 把 [生产 Worker 配置](../deploy/production/wrangler.toml) 的 `FASTAPI_ORIGIN` 指向该服务的 HTTPS 地址。正式服务直连的页面应返回 `noindex`，公开页面只有经过绑定到 `formrefine.ai` 的生产 Worker 才会解除该响应头。准备阶段可在直连服务执行 `python scripts/verify_live_site.py https://<candidate-origin>`。
3. 从 Cloudflare 保存 `formrefine.ai` 和 `www.formrefine.ai` 的当前 DNS 记录与代理状态、Worker 自定义域和路由。保留旧 Railway 部署，记录它的服务和部署 ID。如果旧站当前有需要保留的账户或报告，先确认数据迁移范围。现有正式站的 sitemap 用作路径基线。

## 批准后的切换

1. 站长在 GeFeiSites 确认切换正式域名。确认新 Worker 自定义域成为源站，再附加独立生产代理的 `formrefine.ai/*` 路由。`/_auth/` 由引擎提供，分析、指南和 sitemap 由 FastAPI 提供。正式站继续使用 `/app`，并确认 `www` 到主域名的行为。
2. 执行 `python scripts/verify_live_site.py https://formrefine.ai`。检查 `/app?utm_source=test`、`/privacy` 和 sitemap 中的每篇指南。确认 canonical 仍为原绝对网址，公开页面允许收录，未知路径返回 404。
3. 用测试账户实际完成 Google 回调、上传、生成报告和重新打开原视频。请求私有报告和视频的直达链接，确认匿名请求返回 401。检查分析页里的条款和隐私文案适用于新流程。

## 回滚

若 Google 回调、视频上传、报告读取或公开路径出现阻断，先从 Cloudflare 移除本次附加的生产代理路由，再解除本次在 GeFeiSites 添加的正式域名绑定，恢复切换前记录的 DNS 和代理状态。保留新版的数据库和视频卷，便于找回切换窗口内的报告。用正式域名重测旧站 `/app`、`/privacy`、指南和 sitemap。回滚会把流量交回旧站，切换期间新生成的报告仍留在新版存储。
