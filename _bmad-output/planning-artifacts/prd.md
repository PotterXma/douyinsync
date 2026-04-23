---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish']
inputDocuments:
  - product-brief-douyin-sync.md
  - product-brief-douyin-sync-distillate.md
workflowType: 'prd'
documentCounts:
  briefs: 1
  distillates: 1
  research: 0
  brainstorming: 0
  projectDocs: 0
classification:
  projectType: "Desktop App (后台管道 + 控制面板)"
  domain: "General (内容自动化/跨平台同步)"
  complexity: "中等 (外部 API 依赖风险)"
  projectContext: "Greenfield (有 youtebe搬运 架构参考)"
---

# Product Requirements Document - DouyinSync

**Author:** User
**Date:** 2026-04-19

## Executive Summary

**DouyinSync** is a Windows system tray application that automatically monitors specified Douyin accounts, periodically downloads newly published videos and covers, and uploads them to the user's YouTube channel. It eliminates the highly repetitive manual workflow of cross-platform content synchronization - including Douyin video downloading, cover format conversion (WebP to JPEG), YouTube metadata entry, and individual uploads.

The target users are content curators or multi-platform creators who own YouTube channels. They spend 30-60 minutes daily on repetitive transfer work and are prone to missing videos or duplicate uploads. DouyinSync automates the entire process into a reliable background pipeline: users configure Douyin accounts and YouTube API credentials once, and the tool handles the full fetch-download-upload-notify chain automatically.

The tool supports two scheduling modes (fixed interval / periodic timed), uses SQLite for intelligent deduplication, sends Bark push notifications to the user's phone at every step (success or failure), retries up to 3 times before giving up and notifying, and includes a built-in video management dashboard for real-time sync status visibility.

### What Makes This Special

- **End-to-end automation**: Most tools solve only the "download" or "upload" half; DouyinSync connects the full pipeline from Douyin collection to YouTube upload
- **Bidirectional ecosystem**: Complements the sister project `youtebe搬运` (YouTube to Douyin), enabling true two-way cross-platform content sync
- **Battle-tested collection engine**: Core download capability extracted from the open-source TikTokDownloader project with community-verified anti-crawl technology
- **Full observability**: Three-layer observability via Bark real-time push + video dashboard + log files ensures complete user control over sync status

## Project Classification

| Dimension | Classification |
|-----------|---------------|
| Project Type | Desktop App (background data pipeline + system tray control panel) |
| Domain | Content automation / cross-platform sync |
| Complexity | Medium - dual-platform external API dependencies (unofficial Douyin API + YouTube Data API v3), unpredictable Douyin anti-crawl algorithm updates |
| Project Context | Greenfield, with mature `youtebe搬运` sister project for architecture reference and code reuse |

## Success Criteria

### User Success

- **Zero manual operation**: Once configured, everyday sync happens automatically without launching the app manually
- **Full awareness**: Bark push notifications sent to user's phone for every critical step (fetch list, download video, download cover, upload success, upload failure)
- **At-a-glance visibility**: Video management dashboard to instantly check sync status (pending/processing/completed/failed) across all Douyin accounts

### Business Success

- **Reliability**: ≥ 95% sync success rate, with new videos synced within 24h of publication
- **Low maintenance**: ≤ 1 manual intervention required per week (e.g., only for Cookie expiration)
- **Fast onboarding**: First automatic sync triggers within 15 minutes of completing configuration

### Technical Success

- **Resource friendly**: < 1% CPU and < 50MB RAM usage when idle
- **Fault tolerant**: Automatically retry any failed step up to 3 times before giving up, notifying the user, and marking as `give_up`
- **Data consistency**: SQLite deduplication ensures the same video is NEVER uploaded twice
- **Architecture reuse**: Adopt identical structure to the `youtebe搬运` project (modules/ directory, Notifier/Database/Scheduler components)

### Measurable Outcomes

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| Sync success rate | ≥ 95% | Uploaded count / Fetched count |
| Initial sync delay | ≤ 15 min | Time from config save to first upload |
| Manual intervention | ≤ 1 time/week | Count of required manual actions |
| Idle memory | < 50MB | Task Manager observation |
| Retry success rate | ≥ 60% | Success after retry / Total retries |

## Product Scope

### MVP - Minimum Viable Product

- Configurable Douyin account list (post tab)
- Video + static cover image download (highest quality, no watermark removal)
- YouTube video upload + thumbnail setting (automatic WebP to JPEG conversion)
- Use original Douyin text (title, description, tags) as YouTube metadata
- Two scheduling modes: fixed interval and periodic timed
- Windows system tray app (right-click menu: start/stop monitor, manual run, open config/logs)
- SQLite deduplication database
- Bark push notifications (success/failure per step, giving up after 3 retries)
- Video management dashboard (view sync status by channel)
- Local daily log rotation

### Growth Features (Post-MVP)

- GUI configuration panel (replacing manual config.json edits)
- Automatic YouTube playlist management (categorized by Douyin account)
- Batch historical sync (one-click sync for all historical posts of an account)
- Automatic Cookie refresh (extract from browser to reduce manual updates)

### Vision (Future)

- Multi-platform expansion (TikTok, Bilibili, Xiaohongshu)
- Bidirectional sync (merge with `youtebe搬运` into a unified cross-platform sync hub)
- AI-assisted metadata optimization (title translation, SEO optimization)
- Web UI management dashboard (remote management of all sync tasks)
- Mac/Linux support

## User Journeys

### 1. Happy Path: First-time Configuration & Fully Autonomous Runs
**Persona:** Xiao Ming (Multi-platform Content Curator)
**Story:** Xiao Ming spends 40 minutes daily manually downloading Douyin videos and uploading them to YouTube. Exhausted by this repetitive work, he downloads DouyinSync.
- **Opening Scene**: Xiao Ming opens `config.json`, enters the URLs of 3 major Douyin creators he follows, extracts his browser Cookie, and pastes it in.
- **Rising Action**: He runs the executable. A discreet icon appears in the Windows system tray. 
- **Climax**: 15 minutes later, while grabbing a coffee, his phone buzzes with a Bark notification: "🎉 YouTube Upload Success - [Funny Video Title]". He checks YouTube and finds the video, its perfectly cropped thumbnail, and the original title/tags already live.
- **Resolution**: He closes his old manual scripts. For the next few weeks, he never interacts with the app directly; the daily Bark notifications are his only required proof that the "work is done."

### 2. Management Path: Monitoring System Health
**Persona:** Xiao Ming (Acting as Pipeline Administrator)
**Story:** After adding several new Douyin accounts to his config, Xiao Ming wants to verify that the sync volume is healthy across all channels.
- **Opening Scene**: Xiao Ming right-clicks the system tray icon and selects "Open Video Dashboard."
- **Rising Action**: A clean dashboard UI (Tkinter/Web) opens. At a glance, he sees that Channel A has synced 45 videos, Channel B has synced 12, and 2 are currently "Pending." 
- **Climax**: He spots one video flagged as "Failed." He clicks the log and realizes it failed because his home internet dropped yesterday during the upload phase.
- **Resolution**: He clicks "Manual Sync." The system immediately retries the failed video, and minutes later he gets the success notification.

### 3. Edge Case (Error Recovery): Cookie Expiration
**Persona:** Xiao Ming
**Story:** Douyin's security mechanisms invalidate sessions every few weeks. 
- **Opening Scene**: Xiao Ming is out running errands when his phone gets consecutive red Bark alerts: "⚠️ Douyin Cookie Expired, please update config" followed by "🚨 Video Download Failed (Retried 3 times)."
- **Rising Action**: He knows the system hasn't crashed; it has safely suspended operations to prevent account bans or junk data.
- **Climax**: He gets home, opens his browser, uses a cookie extraction extension to grab a new Cookie string, pastes it into the config, and clicks "Reload Config" from the system tray menu.
- **Resolution**: The icon flashes. Minutes later, the queue of failed videos is reprocessed, and a stream of success notifications hits his phone. No videos were lost.

### 4. Defense Path (System Protection): API Quota Exhaustion & Disk Cleanup
**Persona:** The System (Self-Healing Mechanisms)
**Story:** YouTube API quotas are strict, and hard drives have limits. The system must protect itself.
- **Opening Scene**: Xiao Ming adds an account with 500 historical videos. The system starts syncing.
- **Rising Action**: By noon, the daily 10,000 unit YouTube API quota is hit. A 403 Quota Exceeded error occurs. Instead of blindly retrying and failing, the "Global Circuit Breaker" trips.
- **Climax**: Xiao Ming receives a Bark alert: "⚠️ YouTube Quota Exhausted. System suspended until 00:00 tomorrow." Meanwhile, downloaded videos that couldn't be uploaded remain safely on disk. 
- **Resolution**: At midnight, the system wakes up and resumes uploading the remaining downloaded videos. Separately, a background Cleanup Task deletes any local `.mp4` and `.jpg` files that are older than 7 days, ensuring his local SSD doesn't fill up.

### Journey Requirements Summary

- **Configuration & Hot Reload**: The system tray menu must have a "Reload Config" command to apply `config.json` changes without an app restart.
- **Push Notification Tiers**: Bark integrations require tiered alert levels (e.g., Info for success, Warning for quotas, Error for Cookie expiration) and potential aggregation (e.g., "12 videos synced successfully" summary rather than 12 individual pings).
- **Video Dashboard UI**: A lightweight interface is required to query the SQLite database and display counts by channel and specific states (`pending`, `processing`, `uploaded`, `failed`, `give_up`).
- **Global Circuit Breaker**: The scheduler must be able to globally pause specific pipelines (like YouTube uploads) upon encountering hard rate-limit/quota errors, and auto-resume on schedule.
- **Auto-Cleanup Routine**: A scheduled local file watcher must delete aged, unneeded media files to guarantee disk space stability.

## Domain-Specific Requirements

### Compliance & Regulatory
- **OAuth 2.0 Desktop Auth**: Strict adherence to Google Cloud Platform's OAuth 2.0 flow for desktop applications, protecting the `client_secret.json`.
- **Local Credential Storage**: Douyin Cookies contain sensitive login tokens and MUST remain purely on the local machine. Under no circumstances should Cookies be transmitted to third parties or exposed in plaintext debug logs.

### Technical Constraints
- **YouTube API Quota Limits**: Hard ceiling of 10,000 units per day. The system MUST proactively catch `403 Quota Exceeded` errors, immediately suspend all upload scheduling, and auto-resume at 00:00 PST.
- **Metadata Sanitization**: Douyin `desc` blocks must be strictly truncated and sanitized to ensure they do not exceed YouTube's 100-character title limit or 5,000-character description limit, preventing `400 Bad Request` uploads.

### Integration Requirements
- **Anti-Crawl Mitigation**: Since Douyin utilizes unofficial endpoints secured by `a_bogus` signatures, the fetch interval must be throttled (e.g., minimum 1-hour interval) to avoid triggering risk controls (bot detection) on the user's IP/Cookie.

### Risk Mitigations
- **Upstream Algorithm Changes**: Douyin frequently updates their signature algorithms. The README/Documentation must clearly set user expectations that occasional fetch failures are normal and may require fetching an updated core script or manually refreshing Cookies.

## Desktop App Specific Requirements

### Project-Type Overview
As a background data pipeline running locally on the user's machine, DouyinSync's primary mandate is "invisible reliability." It must be non-intrusive, resilient to local environmental disruptions (network drops, power failures), and maintain strict self-healing capabilities without demanding technical troubleshooting from the user.

### Technical Architecture Considerations

- **Platform-Agnostic Core**: Core logic and modules strictly use abstract pathing (`os.path`, `pathlib`) and cross-platform compatible libraries (like `pystray`) to ensure the codebase can migrate to Mac/Linux seamlessly in the future.
- **Non-Invasive System Integration**: Auto-startup is achieved by generating a dynamic `.lnk` shortcut in the Windows `shell:startup` folder upon first execution, purposefully avoiding Windows Registry alterations.
- **Status Resilience (Zombie State Recovery)**: To defend against sudden power loss or process termination, the database state machine rolls back all `processing` states to `pending` upon application initialization.

### Implementation Considerations

- **Network-Aware Scheduling**: Before initiating any API-heavy tasks, the scheduler performs a lightweight pre-flight network check (ping). Network-induced failures are handled as temporary suspensions (Zero Retries Consumed) rather than critical pipeline errors.
- **Semi-Automated Update Probing**: The application checks an upstream repository release endpoint periodically. When structural upstream API breaking changes require a new build, it sends a Bark notification directing the user to download the update rather than auto-patching executables in place.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP focusing entirely on "Invisible Reliability." The goal is a rock-solid background data pipeline that tolerates local drops and upstream limits, rather than a polished graphic interface.  
**Resource Requirements:** Single developer. Strict reuse of the existing `youtebe搬运` architecture (Notifier/Database/Scheduler logic) to accelerate delivery.

### MVP Feature Set (Phase 1)

**Must-Have Capabilities:**
- **Collection Engine**: Extract video/cover URLs via Douyin user profile parsing (highest quality, no watermark removal).
- **Format Conversion**: WebP to JPEG cover conversion using `Pillow`.
- **Upload Engine**: YouTube Data API v3 integration with resumable uploads and metadata injection.
- **State Machine**: SQLite-backed tracker preventing duplicate uploads (`pending`, `processing`, `uploaded`, `failed`, `give_up`).
- **Proxy Support**: Global and request-level HTTP/HTTPS proxy configuration for network bridging.
- **Observability**: Multi-tier Bark notifications (progress, warnings, fatal errors) and Tkinter-based Dashboard.
- **Resilience**: 3-max retries, Global Circuit Breaker for Quota Exceeded, network-aware task suspension, and process-restart zombie state rollback.

### Post-MVP Features

**Phase 2 (Growth):**
- WSIWYG graphical settings panel (replacing `config.json` direct edits).
- Automated YouTube Playlist management (mapping Douyin creators to playlists).
- Background zombie-file cleanup daemon.

**Phase 3 (Expansion):**
- Automated Browser Cookie Extraction (high-risk due to OS-level DPAPI encryption and AV software).
- Multi-platform extensions (Bilibili, Xiaohongshu) and merging with `youtebe搬运` into a unified sync hub.

### Risk Mitigation Strategy

**Technical Risks:** Douyin's frequent anti-crawl updates breaking the fetcher. **Mitigation:** Isolate the parsing logic into an easily updateable module and rely on community-backed upstream scripts.
**Constraint Risks:** Hitting YouTube's 10,000 unit daily limit. **Mitigation:** Implement strict HTTP 403 interception and Global Circuit Breaking to sleep the queue until midnight PST, eliminating wasted retries.
**Resource/Scope Risks:** Overinvesting in Cookie automation. **Mitigation:** Explicitly move automated Cookie extraction to Phase 3; guarantee manual JSON injection remains the stable fallback.

## Functional Requirements

### 1. Configuration & Network Management
- **FR1:** The user can specify multiple target Douyin accounts to monitor via the configuration file.
- **FR2:** The user can inject Douyin authentication credentials (Cookies) and YouTube API OAuth 2.0 credentials via the configuration file.
- **FR3:** The user can define component-specific network proxies (Split-Tunneling Proxy) via the configuration file, allowing distinct default behaviors (e.g., direct connection for Douyin fetch, proxy layer for YouTube upload).
- **FR4:** The user can apply configuration changes via a "Reload Config" system tray command without restarting the application process.

### 2. Content Collection & Deduplication
- **FR5:** The system can parse a designated Douyin user's profile to retrieve a list of recently published posts.
- **FR6:** The system can extract the highest-quality, original watermark-free video download URL and the static cover URL for each video post.
- **FR7:** The system can detect unsupported media structures (e.g., Douyin Image Posts/图文集), log the encounter, and safely skip processing to avoid crashes.
- **FR8:** The system can download video and cover files to a designated, date-stamped local directory, safely overwriting existing partial files to support retry logic.
- **FR9:** The system can assign and verify a unique metadata identifier for each video to guarantee that a fully processed video is never downloaded or uploaded twice.

### 3. Media Processing & Local Storage
- **FR10:** The system can process downloaded WebP formatted cover images and convert them into lossless JPEG format to comply with downstream platform constraints.
- **FR11:** The system can autonomously sweep and delete local stale media files that exceed a configurable retention period to free up disk space.

### 4. Content Publishing System
- **FR12:** The system can construct and execute resumable chunked video uploads using the YouTube Data API v3.
- **FR13:** The system can process large video files (>500MB) using memory-efficient chunked I/O stream reading.
- **FR14:** The system can extract original Douyin copywriting (title, descriptions, hashtags), strictly sanitize/truncate them for length compliance, and inject them as YouTube metadata.
- **FR15:** The system can append the previously converted JPEG cover image as the custom thumbnail for the finalized YouTube video.

### 5. Pipeline Resilience & Scheduling
- **FR16:** The system can trigger background pipeline execution at fixed intervals or via specific periodic Cron scheduling.
- **FR17:** The system can probe active internet connectivity prior to initiating bulk network requests to prevent false-negative failure states.
- **FR18:** The system can automatically retry specific sub-tasks up to 3 times upon non-fatal network exceptions.
- **FR19:** The system can intercept global "Quota Exceeded" exceptions (HTTP 403) and forcefully suspend all related pipeline operations until the next chronological reset period.
- **FR20:** The system can automatically revert stranded `processing` database states back to `pending` during the initialization sequence to recover from sudden power loss or process termination.

### 6. Observability & Interface
- **FR21:** The system can render a primary control interface via a right-click Windows system tray icon (Start/Stop, Manual Run, Exit, Reload Config).
- **FR22:** The system can dispatch tiered push notifications (info, warning, critical) to a linked mobile device via the Bark API at designated pipeline milestones.
- **FR23:** The user can launch a visual dashboard querying the embedded SQLite database to review active backlog counts (pending, processing, uploaded, failed, give_up) categorized by target channel.
- **FR24:** The system will suspend operations and drop into a "Hard Sleep" mode (terminating scheduled waking) upon encountering consecutive authentication/cookie rejection errors, generating a critical Bark alert and requiring manual configuration refresh to unlock.

## Non-Functional Requirements

### Performance & Resource Utilization
- **NFR1 (Idle Overhead):** While not actively processing a task (Pending/Sleep states), the application process must maintain < 100MB of RAM usage and < 2% CPU utilization to remain invisible to the user's workload.
- **NFR2 (I/O Constraints):** During the handling and transfer of large media files (>500MB), peak memory footprint must not exceed 300MB, strictly enforcing the usage of chunked/streamed I/O patterns.

### Reliability & Resilience
- **NFR3 (State Preservation):** Database architecture must ensure Zero State Corruption even when traversing unexpected process termination (e.g., SIGKILL or sudden power loss) through strictly defined transactional checkpoints.
- **NFR4 (Resource Exhaustion Defense):** The database interaction layer MUST implement backoff retry strategies for lock acquisition (e.g., `timeout >= 10s`) to mitigate locking collisions during concurrent polling or GUI querying.
- **NFR5 (Local Isolation):** A failure occurring within one execution thread or target account pipeline must strictly be contained within that context and cannot trigger a fatal crash of the main scheduling daemon (Scheduler) or UI worker.

### Security
- **NFR6 (Credential Zero-Exfiltration):** Under no debug or operational logging level (`DEBUG`, `TRACE`, etc.) shall raw YouTube OAuth tokens or Douyin browser Cookies be written to the local disk unmasked.
- **NFR7 (Log Sanitization):** The logging module must implement a Sanitizer layer to proactively redact predictable sensitive patterns (e.g., `sessionid`, `access_token`) dynamically from uncaught HTTP response exception dumps before persisting.

### Observability & Maintenance
- **NFR8 (Log Rotation):** Local application logs must enforce automatic file rotation (size-based or daily) with a maximum single file size of 10MB and retention capped at 5 historic backups to prevent disk saturation.
- **NFR9 (Disk Exhaustion Protection):** Before invoking network fetching or media download logic, the Application MUST assert that the host system drive contains >= 2GB of available free space, halting execution and notifying the user if the threshold is breached to proactively prevent database corruption or OS instability.
