#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import unicodedata

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================
TIKTOK_USERNAME = "@namoinam"
TIKWM_API_URL = f"https://www.tikwm.com/api/user/posts?unique_id={TIKTOK_USERNAME}&count=15"

# Từ dừng (stop words) thông dụng để loại bỏ khi sinh từ khóa so khớp
STOP_WORDS = {
    "-", "bo", "cai", "chiec", "may", "cay", "va", "cho", "cua", "trong", "tai",
    "nhung", "cac", "la", "mot", "nhieu", "it", "de", "co", "kem", "mon", "dung",
    "treo", "inox", "go", "nhua", "mini", "cam", "tay", "da", "nang", "thong", "minh"
}

# ============================================================
# HELPERS
# ============================================================
def remove_accents(input_str: str) -> str:
    """Chuyển chuỗi tiếng Việt có dấu thành không dấu và viết thường"""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Thay thế các ký tự đặc biệt bằng khoảng trắng
    clean_str = re.sub(r'[^\w\s]', ' ', only_ascii)
    return clean_str.lower()

def get_db_connection():
    """Khởi tạo kết nối Supabase PostgreSQL"""
    conn_str = os.environ.get("DATABASE_URL")
    if not conn_str:
        # Fallback đọc từ file .env local của anh Nam
        env_file = Path("/Users/nambui/Documents/Nam_oi_Nam/Khong_Gian_Lam_Viec/Scripts/.env")
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        if k.strip() == "DATABASE_URL":
                            conn_str = v.strip().strip('"').strip("'")
    if conn_str:
        import pg8000.dbapi
        pattern = r"postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)"
        match = re.match(pattern, conn_str)
        if match:
            user, password, host, port, database = match.groups()
            port = int(port) if port else 5432
            if "?" in database:
                database = database.split("?")[0]
            
            return pg8000.dbapi.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database,
                ssl_context=True
            )
    return None

def get_telegram_config() -> tuple[str, str]:
    """Lấy token và chat ID của Telegram Bot"""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    if not bot_token or not chat_id:
        env_file = Path("/Users/nambui/Documents/Nam_oi_Nam/Khong_Gian_Lam_Viec/Scripts/.env")
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        key = k.strip()
                        val = v.strip().strip('"').strip("'")
                        if key == "TELEGRAM_BOT_TOKEN":
                            bot_token = val
                        elif key in ("TELEGRAM_CHAT_ID", "ALLOWED_CHAT_ID"):
                            chat_id = val
                            
    if not bot_token or not chat_id:
        # Fallback đọc từ file json config cũ
        config_path = Path("/Users/nambui/phan-cong-edit-video/telegram_config.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    bot_token = config.get("TELEGRAM_BOT_TOKEN", bot_token)
                    chat_id = config.get("TELEGRAM_CHAT_ID", chat_id)
            except Exception as e:
                print(f"⚠️ Không đọc được telegram_config.json: {e}")
                
    return bot_token.strip(), chat_id.strip()

def send_telegram_message(text: str) -> bool:
    """Gửi tin nhắn báo cáo qua Telegram"""
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        print("⚠️ Bỏ qua gửi Telegram do thiếu cấu hình")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return bool(res.get("ok"))
    except Exception as e:
        print(f"⚠️ Lỗi gửi tin nhắn Telegram: {e}")
        return False

# ============================================================
# DATABASE SETUP & QUERIES
# ============================================================
def init_db_tables(conn):
    """Khởi tạo bảng lưu trữ video TikTok đã xử lý trên Supabase"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_tiktok_videos (
            video_id VARCHAR(50) PRIMARY KEY,
            title TEXT,
            published_at TIMESTAMP,
            product_name TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ Lỗi khi khởi tạo bảng processed_tiktok_videos: {e}")
        raise e

def is_video_processed(conn, video_id: str) -> bool:
    """Kiểm tra video ID đã được trừ tồn kho trước đó chưa"""
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_tiktok_videos WHERE video_id = %s", (video_id,))
    return cursor.fetchone() is not None

def record_processed_video(conn, video_id: str, title: str, published_at: datetime, product_name: str):
    """Lưu lại video ID đã xử lý vào database"""
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO processed_tiktok_videos (video_id, title, published_at, product_name)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (video_id) DO NOTHING;
    """, (video_id, title, published_at, product_name))

def update_product_inventory(conn, product_name: str) -> int:
    """Trừ 1 vào tồn kho video (ton_video) của sản phẩm trong bảng products_inventory"""
    cursor = conn.cursor()
    # Lấy tồn kho hiện tại
    cursor.execute("SELECT ton_video FROM products_inventory WHERE name = %s", (product_name,))
    row = cursor.fetchone()
    if not row:
        return -1
    
    current_stock = row[0]
    new_stock = max(0, current_stock - 1)
    
    cursor.execute(
        "UPDATE products_inventory SET ton_video = %s WHERE name = %s",
        (new_stock, product_name)
    )
    return new_stock

def get_active_products(conn) -> list[dict]:
    """Lấy danh sách tất cả sản phẩm đang hoạt động hoặc có quota đăng bài"""
    cursor = conn.cursor()
    cursor.execute("SELECT name, so_video_ngay, ton_video FROM products_inventory")
    rows = cursor.fetchall()
    products = []
    for r in rows:
        products.append({
            "name": r[0],
            "so_video_ngay": r[1] or 0,
            "ton_video": r[2] or 0
        })
    return products

# ============================================================
# PRODUCT MATCHING LOGIC
# ============================================================
def extract_keywords(prod_name: str) -> tuple[str, list[str]]:
    """Phân tách tên sản phẩm thành thương hiệu và các từ khóa đặc trưng không dấu"""
    name_clean = remove_accents(prod_name)
    
    # Tách thương hiệu (nếu có dấu gạch ngang)
    if " - " in prod_name:
        parts = prod_name.split(" - ", 1)
        brand = remove_accents(parts[0]).strip()
        details = remove_accents(parts[1]).strip()
    else:
        # Nếu không có dấu gạch ngang, lấy từ đầu tiên làm thương hiệu
        words = name_clean.split()
        brand = words[0] if words else ""
        details = " ".join(words[1:]) if len(words) > 1 else name_clean
        
    # Tách các từ khóa chi tiết và loại bỏ từ dừng
    detail_words = details.split()
    keywords = [w for w in detail_words if w not in STOP_WORDS and len(w) >= 2]
    
    return brand, keywords

def match_video_to_product(video_title: str, products: list[dict]) -> dict | None:
    """So khớp tiêu đề video với sản phẩm phù hợp nhất sử dụng thang điểm từ khóa"""
    video_clean = remove_accents(video_title)
    
    best_match = None
    best_score = 0.0
    
    for prod in products:
        brand, keywords = extract_keywords(prod["name"])
        
        # 1. Kiểm tra khớp thương hiệu (nếu sản phẩm có định nghĩa thương hiệu rõ ràng)
        # Bắt buộc phải chứa thương hiệu trong tiêu đề/hashtag
        if brand and brand not in video_clean:
            continue
            
        if not keywords:
            continue
            
        # 2. Tính toán điểm số từ khóa khớp
        matches = 0
        # Kiểm tra xem có chứa model số/ký tự đặc biệt trước (ví dụ: Z1FC, E3, X9)
        # Những model này nếu có trong tên sản phẩm thì bắt buộc phải khớp
        model_words = [w for w in keywords if any(c.isdigit() for c in w) or len(w) >= 4]
        model_failed = False
        for mw in model_words:
            if mw not in video_clean:
                model_failed = True
                break
        if model_failed:
            continue
            
        # Đếm số từ khóa khớp
        for kw in keywords:
            # Kiểm tra xem từ khóa xuất hiện nguyên vẹn trong video title
            if re.search(r'\b' + re.escape(kw) + r'\b', video_clean) or kw in video_clean:
                matches += 1
                
        score = matches / len(keywords)
        
        # Cập nhật sản phẩm khớp tốt nhất
        if score > best_score and score >= 0.5: # Ngưỡng khớp tối thiểu 50% từ khóa
            best_score = score
            best_match = prod
            
    if best_match:
        print(f"   🎯 Khớp: '{video_title}' ➔ '{best_match['name']}' (Score: {best_score:.2f})")
    return best_match

# ============================================================
# MAIN WORKFLOW
# ============================================================
def main():
    print("=======================================================")
    print("🚀 Bắt đầu quét kiểm tra đăng bài TikTok...")
    print(f"📅 Thời gian chạy: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=======================================================")
    
    # 1. Kết nối cơ sở dữ liệu
    conn = get_db_connection()
    if not conn:
        print("❌ Kết nối database Supabase thất bại!")
        sys.exit(1)
        
    try:
        init_db_tables(conn)
        products = get_active_products(conn)
        print(f"ℹ️ Đang theo dõi {len(products)} sản phẩm trong kho.")
    except Exception as e:
        conn.close()
        sys.exit(1)
        
    # 2. Gọi API TikWM để lấy bài đăng gần nhất
    print(f"\n🔐 Kết nối API TikWM cho kênh {TIKTOK_USERNAME}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(TIKWM_API_URL, headers=headers)
    
    videos = []
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("code") == 0 and "data" in res_data:
                videos = res_data["data"].get("videos", [])
                print(f"   ✅ Lấy thành công {len(videos)} video gần nhất từ TikTok.")
            else:
                print(f"   ❌ API TikWM trả về lỗi: {res_data}")
                conn.close()
                sys.exit(1)
    except Exception as e:
        print(f"   ❌ Lỗi kết nối API TikWM: {e}")
        conn.close()
        sys.exit(1)
        
    if not videos:
        print("ℹ️ Không tìm thấy video nào trên kênh.")
        conn.close()
        sys.exit(0)
        
    # 3. Lọc video đăng trong vòng 24 giờ qua
    now_ts = time.time()
    cutoff_ts = now_ts - (24 * 3600)  # 24 giờ trước
    
    recent_videos = []
    for v in videos:
        pub_time = v.get("create_time", 0)
        if pub_time >= cutoff_ts:
            recent_videos.append(v)
            
    print(f"ℹ️ Phát hiện {len(recent_videos)} video được đăng trong 24 giờ qua.")
    
    # 4. Xử lý từng video
    processed_count = 0
    report_items = []
    
    # Danh sách thống kê số video đã đăng hôm nay của từng sản phẩm để check quota
    today_start = datetime.combine(datetime.today(), datetime.min.time())
    today_posts_by_product = {}
    
    for v in recent_videos:
        video_id = str(v.get("video_id"))
        title = v.get("title", "").strip()
        pub_time_dt = datetime.fromtimestamp(v.get("create_time", 0))
        
        print(f"\n🎬 Xử lý video ID: {video_id}")
        print(f"   Tiêu đề: {title}")
        print(f"   Đăng lúc: {pub_time_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Kiểm tra xem video này đã được xử lý trước đó chưa
        if is_video_processed(conn, video_id):
            print("   ℹ️ Video này đã được xử lý trước đây. Bỏ qua.")
            # Vẫn ghi nhận vào thống kê quota ngày hôm nay nếu đăng trong ngày
            matched_prod = match_video_to_product(title, products)
            if matched_prod:
                p_name = matched_prod["name"]
                today_posts_by_product[p_name] = today_posts_by_product.get(p_name, 0) + 1
            continue
            
        # So khớp video với danh mục sản phẩm
        matched_prod = match_video_to_product(title, products)
        if matched_prod:
            p_name = matched_prod["name"]
            
            try:
                # Trừ tồn kho trên Supabase
                new_stock = update_product_inventory(conn, p_name)
                # Lưu log tránh xử lý trùng lặp
                record_processed_video(conn, video_id, title, pub_time_dt, p_name)
                conn.commit()
                
                print(f"   ✅ Đã trừ 1 tồn kho của '{p_name}'. Tồn hiện tại: {new_stock}")
                report_items.append({
                    "title": title,
                    "product": p_name,
                    "new_stock": new_stock,
                    "status": "success"
                })
                processed_count += 1
                today_posts_by_product[p_name] = today_posts_by_product.get(p_name, 0) + 1
            except Exception as e:
                conn.rollback()
                print(f"   ❌ Gặp lỗi khi cập nhật DB cho video {video_id}: {e}")
                report_items.append({
                    "title": title,
                    "product": p_name,
                    "status": "error",
                    "error": str(e)
                })
        else:
            print("   ⚠️ Không tìm thấy sản phẩm nào trùng khớp với tiêu đề video này.")
            report_items.append({
                "title": title,
                "product": "Không xác định",
                "status": "unmatched"
            })
            
    # 5. Đánh giá Quota ngày hôm nay
    quota_report_lines = []
    for prod in products:
        quota = prod["so_video_ngay"]
        if quota > 0:
            posts_today = today_posts_by_product.get(prod["name"], 0)
            # Truy vấn thêm trong DB xem hôm nay đã có video nào khác được lưu chưa
            try:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT COUNT(*) FROM processed_tiktok_videos 
                WHERE product_name = %s AND published_at >= %s
                """, (prod["name"], today_start))
                db_posts_count = cursor.fetchone()[0]
                total_posts_today = max(posts_today, db_posts_count)
            except Exception:
                total_posts_today = posts_today
                
            status_emoji = "✅" if total_posts_today >= quota else "❌"
            quota_report_lines.append(
                f"- {prod['name']}: {total_posts_today}/{quota} video {status_emoji}"
            )
            
    conn.close()
    
    # 6. Gửi báo cáo Telegram
    print("\n📤 Đang gửi báo cáo tiến độ đăng bài lên Telegram...")
    msg_lines = ["📊 <b>BÁO CÁO ĐĂNG BÀI TIKTOK & TỒN KHO BUỔI TỐI</b>\n"]
    
    # Kết quả xử lý video mới
    msg_lines.append("<b>1. Video mới phát hiện (24 giờ qua):</b>")
    if report_items:
        for item in report_items:
            t = item["title"]
            if len(t) > 40:
                t = t[:40] + "..."
            if item["status"] == "success":
                msg_lines.append(f"✅ {t}\n   ➔ SP: <code>{item['product']}</code> (Tồn còn: {item['new_stock']})")
            elif item["status"] == "unmatched":
                msg_lines.append(f"⚠️ {t}\n   ➔ <i>Không tìm thấy sản phẩm trùng khớp</i>")
            else:
                msg_lines.append(f"❌ {t}\n   ➔ Lỗi: {item.get('error')}")
    else:
        msg_lines.append("ℹ️ Không phát hiện video mới nào được đăng tải.")
    msg_lines.append("")
    
    # Báo cáo Quota
    msg_lines.append("<b>2. Chỉ tiêu đăng bài trong ngày (Quota):</b>")
    if quota_report_lines:
        msg_lines.extend(quota_report_lines)
    else:
        msg_lines.append("ℹ️ Không có sản phẩm nào được thiết lập chỉ tiêu đăng bài.")
        
    msg_lines.append(f"\n<i>Cập nhật lúc: {datetime.now().strftime('%H:%M - %d/%m/%Y')}</i>")
    
    telegram_msg = "\n".join(msg_lines)
    if send_telegram_message(telegram_msg):
        print("✅ Đã gửi báo cáo Telegram thành công!")
    else:
        print("❌ Gửi báo cáo Telegram thất bại.")
        
    print("\n=======================================================")
    print(f"🎉 Hoàn tất! Đã xử lý trừ tồn kho {processed_count} video mới.")
    print("=======================================================")

if __name__ == "__main__":
    main()
