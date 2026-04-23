---
title: "Product Brief Distillate: DouyinSync"
type: llm-distillate
source: "product-brief-douyin-sync.md"
created: "2026-04-19"
purpose: "Token-efficient context for downstream PRD creation"
---

# DouyinSync 详情蒸馏包

## 技术上下文 — 抖音采集引擎

### 核心 API 端点（从 TikTokDownloader 提取）

- **账号作品列表**: `https://www.douyin.com/aweme/v1/web/aweme/post/`
  - 参数: `sec_user_id`, `max_cursor`, `count=18`
  - 响应: `aweme_list[]`, `max_cursor`, `has_more`
  - 需要分页遍历获取全部作品

- **单作品详情**: `https://www.douyin.com/aweme/v1/web/aweme/detail/`
  - 参数: `aweme_id`
  - 响应: `aweme_detail` 对象

### 反爬机制（关键难点）

- **a_bogus 签名**: 必须移植 `src/encrypt/aBogus.py` (16KB)
  - 基于 URL 参数 + User-Agent 生成
  - 算法定期变化，需要跟进更新
- **msToken**: `src/encrypt/msToken.py` (14KB) 生成 token
- **Cookie**: 必须提供登录后的抖音 Cookie，含 `sessionid`, `ttwid` 等
  - Cookie 有效期有限，需要定期更新
  - 项目支持 `rookiepy` 从浏览器自动提取
- **请求头**: 必须携带完整浏览器指纹参数

### 视频 URL 提取路径

```
data.video.bit_rate → 按 (height, width, FPS, bit_rate) 排序 → 取最大 → play_addr.url_list[-1]
```

### 封面 URL 提取路径

- 静态封面: `data.video.cover.url_list[-1]` → JPEG
- 动态封面: `data.video.dynamic_cover.url_list[-1]` → WebP

### 下载请求头

```python
headers = {
    "Accept": "*/*",
    "Range": "bytes=0-",
    "Referer": "https://www.douyin.com/?recommend=1",
    "User-Agent": "Mozilla/5.0 ... Chrome/139.0.0.0 ..."
}
```

### 其他元数据提取

- `desc` → 作品描述
- `author.nickname` → 作者昵称
- `text_extra[].hashtag_name` → 话题标签
- `music.title`, `music.author` → 背景音乐
- `statistics.digg_count/comment_count/share_count/play_count` → 互动数据
- `create_time` → 发布时间戳

## 技术上下文 — YouTube 上传

### API 配额限制

- 默认 10,000 units/天
- `videos.insert` = 1,600 units
- `thumbnails.set` = 50 units
- 理论日上传上限 ≈ 6 个视频（含缩略图）
- 可通过 Google Cloud Console 申请提升

### 缩略图要求

- 格式: JPG, GIF, PNG（不支持 WebP → 需转换）
- 大小: < 2MB
- 推荐尺寸: 1280×720, 最小宽度 640px

### 认证流程

- 需要 Google Cloud 项目 + OAuth 2.0 credentials
- 首次需要浏览器授权流程
- 之后使用 refresh_token 自动续期

## 需求提示（用户明确表达的）

- 抖音频道可自由配置（支持多账号）
- 使用原始抖音文字，不做翻译
- 调度模式：固定间隔（每 N 小时）+ 周期定时（每周几/每天几点）
- Windows 系统托盘常驻应用
- 用户已有 YouTube 频道

## 范围信号

### MVP 内

- 抖音账号发布作品批量下载
- 视频 + 静态封面下载
- YouTube 上传（视频 + 缩略图 + 元数据）
- 双模式定时调度
- 系统托盘最小化运行
- SQLite 去重
- 日志

### 明确排除

- GUI 配置界面（首版用配置文件 settings.json）
- 直播录制
- YouTube 播放列表自动管理
- 多 YouTube 频道
- 多语言翻译

### 需决策

- Cookie 过期提醒机制：弹窗通知 vs 仅日志记录？
- 上传失败重试策略：重试次数？间隔？
- 视频处理是否需要去水印？
- 是否需要视频质量选项（最高画质 vs 指定画质）？

## 竞品/替代方案

- 手动下载+上传（当前方案，耗时高）
- TikTokDownloader 本身（只解决下载环节）
- 各类在线视频下载网站（不稳定，功能单一）
- 无发现完整的抖音→YouTube 自动同步一站式开源工具

## 关键依赖

| 依赖 | 风险等级 | 说明 |
|------|----------|------|
| 抖音 a_bogus 算法 | 🔴 高 | 抖音反爬策略可能更新，需跟进 TikTokDownloader 社区 |
| 抖音 Cookie | 🟡 中 | 有效期有限，过期需手动更新 |
| YouTube API 配额 | 🟡 中 | 默认配额限制日上传量 |
| httpx 库稳定性 | 🟢 低 | 成熟库，社区活跃 |
| pystray | 🟢 低 | 轻量系统托盘库 |

## 项目结构建议

```
douyin搬运/
├── src/
│   ├── douyin/          ← 抖音采集引擎（从 TikTokDownloader 提取简化）
│   │   ├── api.py       → API 请求
│   │   ├── encrypt.py   → a_bogus 加密
│   │   ├── extractor.py → 数据提取
│   │   └── downloader.py → 文件下载
│   ├── youtube/         ← YouTube 上传模块
│   │   ├── auth.py      → OAuth2 认证
│   │   ├── uploader.py  → 视频上传
│   │   └── thumbnail.py → 缩略图处理
│   ├── scheduler/       ← 定时调度
│   │   └── scheduler.py → APScheduler 配置
│   ├── tray/            ← 系统托盘 UI
│   │   └── tray_app.py  → pystray 应用
│   ├── db/              ← 数据持久化
│   │   └── database.py  → SQLite 操作
│   └── config/          ← 配置管理
│       └── settings.py  → JSON 配置
├── settings.json        ← 用户配置
├── main.py              ← 入口
└── requirements.txt
```
