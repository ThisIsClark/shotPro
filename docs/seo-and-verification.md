# FormRefine：关键词、内页与自动验证

调研：2026-11-10；实现／验收：2026-11-11（Asia/Shanghai）。

## 关键词判断的依据与边界

本次查看了公开搜索结果、同类产品的实际用语，以及 Google Search Central 的指南。尝试直接读取 Google 英文结果页时页面加载不完整，所以**不把它当成已采集的 Google 排名、相关问题或自动补全数据**。没有访问 Google Ads Keyword Planner、Search Console 或付费关键词数据库，因此没有可核验的月搜索量、竞争难度或增长趋势。

下表的 P1/P2 是根据产品匹配度和搜索意图制定的开发优先级，不是流量排名。“热词”应先理解为需要进一步验证的候选词。

| 优先级 | 关键词组 | 用户想做什么 | 本次承接页面 |
|---|---|---|---|
| P1 | basketball shooting form analyzer / shooting form analysis / basketball shot analysis | 找能分析视频的工具 | `/app` |
| P1 | basketball form check / basketball shooting form check / check my shooting form | 判断自己的动作，知道该检查哪里 | `/guides/basketball-shooting-form-check` → 工具 |
| P1 | how to film basketball shot / shooting form video / basketball shooting video analysis | 拍出能被分析的视频 | `/guides/how-to-film-basketball-shot` → 工具 |
| P2 | basketball shooting dip / should I dip when shooting / dip point | 理解沉球、区分低点和下蹲 | `/guides/basketball-shooting-dip` |
| P2 | basketball release point / shooting release point / release vs follow through | 找出手时刻、比较动作 | `/guides/basketball-release-point` |
| 品牌 | FormRefine / formrefine.ai / form refine | 找到你的产品 | 首页标题、品牌名称、站点结构化数据 |
| 暂缓 | shooting form / proper shooting form / improve shooting form | 很宽泛的教学或信息需求 | 在文章中自然使用，不再复制一堆同义词页面 |
| 不建页 | form chech | form check 的拼写错误 | 使用正确拼写；不为错字创建薄内容页面 |

`form check` 脱离篮球有多运动歧义，因此标题和主要描述加上 basketball 或 shooting。`form refine` 在这个项目里优先作为品牌用语，不声称它是已验证的热门通用搜索词。

### 可复核来源

- [FORMCHK 产品首页](https://formchk.com/)：使用 basketball analysis、shooting form、upload video 等工具意图用语。这里只参考搜索意图，不采纳其准确性或“科学验证”营销承诺。
- [Basketball Wurf Check](https://basketballwurfcheck.de/en/)：视频上传与 shot form analysis 的落地页意图。
- [Gymaholic Basketball Form Check](https://www.gymaholic.co/check-exercise-form/1581/basketball)：form check 的产品用法，也说明必须加篮球限定词。
- [Jr. NBA shooting guide](https://jr.nba.com/shooting/)：通用投篮教学来源，和工具意图不同。
- [Penner 2021 沉球研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC8273237/)：沉球文章只引用其测试条件下的结论，不推导个人最佳沉球幅度。
- [Google Search Essentials](https://developers.google.com/search/docs/essentials)：描述性关键词、可抓取链接、面向用户的内容。
- [Google canonical 指南](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)：统一规范地址。
- [Google sitemap 指南](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)：站点地图只是发现提示，不保证收录。
- [Google 结构化数据原则](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)：数据须与可见内容一致。
- [Google Keyword Planner](https://support.google.com/google-ads/answer/7337243?hl=en)：后续验证搜索量的入口。

## 本次实现

- 首页标题、摘要、H1 改为明确的 basketball shooting form analyzer / video form check，品牌统一为 FormRefine（依据 `docs/brand.md` 和现有推广域名）。
- 4 篇原创英文指南 + `/guides` 目录。内容由服务器直接返回 HTML，不依赖登录或 JavaScript。每篇解决一个具体问题，包含 FAQ、相关指南和分析入口；没有批量复制关键词页面。
- 首页新增普通 `<a>` 内链，指南互相链接并返回 `/app#oneUpload`，这些链接可以被爬虫直接跟踪。
- 所有 6 个公开页面具有独立 title、description、自引用 canonical、Open Graph 与 JSON-LD；使用 WebSite / WebPage / BreadcrumbList，没有虚构评分、评价、教练资质或优惠。结构化数据不保证富结果。
- `/sitemap.xml` 只列这 6 个 canonical 页面；不伪造 `lastmod`。
- `/` 用 308 永久重定向到 `/app`。保留 `/app` 原入口及验证回调路径。
- `/robots.txt` 允许抓取，以便 Google 能读到 `noindex` 响应头。robots 不是数据权限措施。
- 本地／非规范域名、管理页、API、反馈分享页、旧结果文件、模板文件及错误响应带 `X-Robots-Tag: noindex, nofollow`。现有鉴权仍负责私有内容的访问权限。
- 首页不再通过 body 的初始 `visibility:hidden` 等待 JS；即使脚本加载失败，介绍、指南和拍摄说明仍可读。上传仍需 JS，并有 noscript 提示。

## 部署配置

```dotenv
SEO_SITE_URL=https://formrefine.ai
SEO_INDEXABLE=true
```

`SEO_SITE_URL` 必须是 origin，不包含 `/app`、账号密码、query 或 fragment；canonical 不使用请求 Host 拼接，防止意外生成错误站点地址。生产服务器必须能收到正确的 `formrefine.ai` Host；若反向代理把 Host 改成 HF 预览域名，页面会被 noindex，发布后检查脚本能发现这个问题。

预发布环境设置 `SEO_INDEXABLE=false`；localhost 和不同域名默认也会 noindex。以后更换正式域名需要同时修改此配置和重定向策略。

本次未发布线上、未提交 Google Search Console，也未声称搜索排名已提高。

## 一条命令重复验证

从仓库根目录运行，依赖项目 Python 环境以及 Node.js 18+：

```bash
venv/bin/python scripts/verify_site.py
```

Windows／CI 或已激活虚拟环境可用 `python scripts/verify_site.py`。Node 自动从 PATH 查找；可通过 `--node /path/to/node` 或 `NODE_BINARY` 指定。

| 检查 | 内容 |
|---|---|
| public-pages | 6 个 SSR 页面；独立标题／摘要／H1；canonical；JSON-LD；所有本地内链、锚点和资源；sitemap；robots；308；404；noindex；Host 污染防护 |
| frontend-flow | 直接提取实际前端函数；未登录不上传；登录后继续；取消保留文件；重复回调与双击防重；401；次数不足；网络失败恢复；JS 语法 |
| core / imports | 依赖及核心模块导入 |
| keyframes | 14 项确定性关键帧时序回归 |
| feedback | 12 项隔离的反馈／复测 API 集成测试，临时视频和数据库 |

运行器会隔离上传／结果／反馈目录，并清空外部 Supabase、支付配置；ASGI 测试不执行生产启动清理。不会扣真实用户积分。前端流程使用 API 和 DOM 替身，**不是完整浏览器端到端测试**；不验证 Google 收录或实际邮箱服务可用性。

日志和可机读结果在 `artifacts/verification/`。任何检查失败，命令退出码为非零。

### 快速检查、运行中站点和真实视频

```bash
# 文案／SEO／页面修改后快速检查
venv/bin/python scripts/verify_site.py --quick

# 全套检查 + 对运行中的本地服务做只读 HTTP 验证
venv/bin/python scripts/verify_site.py --live-url http://localhost:8000

# 发布后只读验证（GET，不创建账号／上传／扣积分）
venv/bin/python scripts/verify_live_site.py https://formrefine.ai

# 可选：真实本地视频端到端流程；只连接 127.0.0.1:8000
# 会创建 Local QA 演示记录，使用 modelVideo/reddit1009.mov 和本地管理员
venv/bin/python scripts/feedback_smoke.py
```

真实视频流程检查分析完成、发布反馈、分享播放和撤销、复测完成和版本关联。算法失败或超时现在会明确让命令失败。默认日常回归不需要模型下载或生产账号；涉及分析管线或视频播放变更时，再加跑真实视频流程。

### CI

`.github/workflows/ci.yml` 已接入同一个 `verify_site.py`，安装 Node 20，并在失败时也上传验证日志。现有其他算法测试继续执行。新增内页会自动进入 sitemap 和页面检查，不需要逐个添加测试 URL。

## 发布后如何判断是否有效

### 本次本地验收（2026-11-11）

- `verify_site.py --live-url http://localhost:8000` 的 7 组检查全部通过：公开页面 9 项、前端流程 10 项、关键帧 14 项、反馈流程 12 项，以及核心模块、导入和运行中服务检查。
- 运行中服务的 6 个公开页面、资源、metadata、sitemap、重定向和 404 均通过检查。
- `feedback_smoke.py` 使用 `reddit1009.mov`，首次分析与复测均完成，结果对比和分享撤销通过。此流程会留下 Local QA 测试记录。
- 浏览器已查看首页、指南目录和沉球指南，验证返回上传入口及登录弹窗；页面截图位于 `artifacts/verification/guides-preview.png`。
- 汇总结果为 `artifacts/verification/summary.json`，真实视频结果为 `artifacts/feedback-qa/smoke-result.json`。本次未执行真实邮箱登录、支付或线上部署。

### 上线后的观察

1. 在已验证的 Search Console 资源中提交 `https://formrefine.ai/sitemap.xml`，检查首页、目录和 4 篇指南的抓取与 Google 选定 canonical。
2. 用 Keyword Planner 按实际目标市场（建议先分别看美国、英国、加拿大等英语市场）检查上述候选词。记录地域、语言、时间范围和数据来源；不要把广告竞争度当成自然搜索难度。
3. 在 Search Console 分开看品牌词与非品牌词、每个落地页的展示、点击、CTR 和平均排名。以连续时间段比较，流量少时不要凭几次点击下结论。
4. 从文章进入上传、完成登录、成功分析这些行为才说明内容带来相关用户。现有分析事件可作为起点，本次未新增第三方追踪服务。
5. 优先扩充有真实查询展示但内容尚未覆盖的问题。先更新现有指南，再考虑新页；不按同义词无限扩张 URL。
