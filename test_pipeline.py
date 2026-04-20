import argparse
import logging
from modules.logger import logger
from modules.config_manager import config
from modules.douyin_fetcher import DouyinFetcher
from modules.database import VideoDAO
from modules.downloader import Downloader
from modules.youtube_uploader import YouTubeUploader
from modules.scheduler import PipelineCoordinator

def setup_logging():
    logging.getLogger().setLevel(logging.DEBUG)

def test_fetcher():
    logger.info("=== 测试抓取器 (DouyinFetcher) ===")
    fetcher = DouyinFetcher()
    accounts = config.get("douyin_accounts", [])
    if not accounts:
        logger.error("配置文件 (config.json) 中未发现 'douyin_accounts' 列表。")
        return

    first_account = accounts[0]
    url = first_account.get("url", "") if isinstance(first_account, dict) else str(first_account)
    logger.info(f"配置的首个目标账号URL: {url}")

    posts, next_cursor, has_more = fetcher.fetch_user_posts(url)
    if not posts:
        logger.error("抓取失败或返回0个视频 (可能遇到WAF墙或者Cookie失效)。")
        return

    logger.info(f"成功获取 {len(posts)} 个视频记录。前3个信息展示:")
    for p in posts[:3]:
        logger.info(f" - [ID:{p['douyin_id']}] 标题: {p['title']}")
        logger.info(f"   视频链接: {p['video_url']}")
        logger.info(f"   封面链接: {p['cover_url']}")
        
    return posts

def test_database():
    logger.info("=== 测试数据库模块 (VideoDAO) ===")
    logger.info("模拟写入一条测试数据...")
    test_data = {
        "douyin_id": "TEST_DB_001",
        "account_mark": "TEST_USER",
        "title": "这是一条本地测试视频数据",
        "description": "这是描述",
        "video_url": "http://example.com/video.mp4",
        "cover_url": "http://example.com/cover.jpg"
    }
    
    is_new = VideoDAO.insert_video_if_unique(test_data)
    logger.info(f"初次插入测试数据返回状态: {'成功 (新数据)' if is_new else '忽略 (数据已存在)'}")
    
    pending = VideoDAO.get_pending_videos(limit=5)
    logger.info(f"当前等待处理 (pending) 的视频数量有 {len(pending)} 个")
    for p in pending:
        logger.info(f" - 待处理ID: {p['douyin_id']}")

def test_downloader():
    logger.info("=== 测试下载器 (Downloader) ===")
    pending = VideoDAO.get_pending_videos(limit=1)
    if not pending:
        logger.warning("数据库中没有 'pending' 状态的视频，无法测试下载环节。")
        logger.warning("请先执行 'python test_pipeline.py fetcher' 或通过数据库预备数据。")
        return
        
    video = pending[0]
    dy_id = video['douyin_id']
    logger.info(f"正在测试下载等待中的视频ID: {dy_id}")
    
    downloader = Downloader()
    paths = downloader.download_media(dy_id, video['video_url'], video['cover_url'])
    
    if paths:
        logger.info(f"下载成功！资源保存在:")
        logger.info(f" - 视频文件: {paths['local_video_path']}")
        logger.info(f" - 封面文件: {paths['local_cover_path']}")
        # 将测试过的还原为 downloaded 或者 pending 
        VideoDAO.update_status(dy_id, 'downloaded', paths)
    else:
        logger.error("下载失败。")

def test_uploader():
    logger.info("=== 测试上传器 (YouTubeUploader) ===")
    uploader = YouTubeUploader()
    logger.info("测试上传器初始化及API认证 (不进行真实例外上传)。")
    api = uploader.get_authenticated_service()
    if api:
        logger.info("YouTube API 验证成功。客户端已准备就绪。")
    else:
        logger.error("YouTube API 验证失败，请检查 client_secret.json 及 credentials 等环境设置。")

def test_e2e():
    logger.info("=== 测试全链路 (pipeline End-to-End) ===")
    coord = PipelineCoordinator()
    coord.primary_sync_job()

def run_cli_mode():
    setup_logging()
    
    parser = argparse.ArgumentParser(description="分布式测试Douyin调度框架各个模块阶段")
    parser.add_argument("module", choices=["fetcher", "database", "downloader", "uploader", "e2e"],
                        help="选择要测试的模块")
    
    args = parser.parse_args()
    
    if args.module == "fetcher":
        test_fetcher()
    elif args.module == "database":
        test_database()
    elif args.module == "downloader":
        test_downloader()
    elif args.module == "uploader":
        test_uploader()
    elif args.module == "e2e":
        test_e2e()
    
    logger.info("---------- 测试流程结束 ----------")

if __name__ == "__main__":
    run_cli_mode()
