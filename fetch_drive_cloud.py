#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
fetch_drive.py — Quản lý Drive + Download video
==============================================================
Chạy mỗi sáng, tự động:
  1. Tạo folder ngày mai trong Drive + 8 subfolder editor
  2. Xóa folder cũ (> 7 ngày gần nhất)
  3. Tự động phát hiện & tải bù các ngày bị lỡ (catch-up)
  4. Download video ngày hôm qua về máy, gom tất cả vào 1 thư mục chung
  5. Cập nhật tồn kho products.json lên GitHub

Cách dùng:
  python3 fetch_drive.py                    # full auto (bao gồm catch-up)
  python3 fetch_drive.py --skip-drive       # bỏ qua quản lý Drive, chỉ download
  python3 fetch_drive.py --date 2026-06-01  # chỉ định ngày cụ thể (bỏ qua catch-up)
  python3 fetch_drive.py --no-catchup       # tắt catch-up, chỉ xử lý hôm qua
"""

import sys
import json
import shutil
import subprocess
import argparse
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================
ROOT_FOLDER_ID      = "1Gsi9TkpfRioSWrR2RIwAVdI2naYY-uME"  # Drive FINAL folder
KEEP_DAYS           = 7
EDITORS             = ["Sơn", "Duyên", "Tuyên", "Hiếu", "Dung", "Thắm", "Thư", "Trân"]

SCRIPT_DIR      = Path(__file__).parent
FOLDER_CACHE    = SCRIPT_DIR / "drive_folder_cache.json"
DOWNLOAD_BASE   = Path.home() / "Downloads"
# products.json sống hoàn toàn trên GitHub — không dùng file local
import os
token_file = SCRIPT_DIR / "github_token.txt"
if token_file.exists():
    GITHUB_TOKEN = token_file.read_text(encoding="utf-8").strip()
else:
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO     = "namoinam/phan-cong-edit-video"
GITHUB_PRODUCTS = "products.json"

# Tên viết tắt / hay sai trên file Drive → tên đầy đủ trong products.json (chữ thường)
# Thêm alias mới vào đây khi editor đặt tên lệch — KHÔNG xóa alias cũ
NAME_ALIASES = {
    "tmt store": "tieu man thau store",
    # HAPAS
    "hapas - quà tặng set thân thương": "hapas - quà tặng set \"thân thương\"",
    # ULUCKY — editor hay bỏ chữ Đai hoặc dùng brand LUCK
    "ulucky - chườm ấm bụng": "ulucky - đai chườm ấm bụng",
    "luck - đai chường ấm bụng": "ulucky - đai chườm ấm bụng",
    "luck - đai chườm ấm bụng": "ulucky - đai chườm ấm bụng",
    # VUA NỆM — editor hay viết thêm OFFICIAL + tên dòng sản phẩm
    "vua nem official - nệm lò xo goodnight sleep": "vua nệm - nệm lò xo",
    "vua nem - nệm lò xo": "vua nệm - nệm lò xo",
    # JETZ — editor hay viết thêm chữ T
    "jetzt - máy hút bụi x9": "jetz - máy hút bụi x9",
    # TORRAS — editor hay thêm 'không viền' vào tên
    "torras - kính cường lực không viền": "torras - kính cường lực",
    "torras - kính cường lực khong vien": "torras - kính cường lực",
    # ONECHI — sửa lỗi chính tả và rút gọn tên file
    "onechi - dây dán velcro quản chống rối": "onechi - dây dán velcro quấn chống rối",
    "dây dán velcro quản chống rối": "onechi - dây dán velcro quấn chống rối",
    "ajido - cân điện tử ajido s5 pro": "ajido - cân điện tử thông minh",
    "edc vn - đèn pin led f35 vs f37": "edc vn - đèn pin led zoom f35",
    "tosudo - móc kẹp, treo đồ": "tosudo - móc treo đồ",
    "deli - ổ cắm điện chữ t": "deli - ổ điện chữ t",
    "hapas - quà tặng hapas set \"chân thành\"": "hapas - quà tặng set \"chân thành\"",
    "luck - bình đựng dầu ăn thủy tinh": "luck - bình đựng dầu ăn đa năng",
    "royal towel - khăn tắm": "royal - khăn tắm cotton",
    "thinshop88 - cây đâm lưng ngải cứu": "thinshop88 - cây đấm lưng ngải cứu",
    "arzopa - màn hình di động": "arzopa - màn hình di động z1fc",
}


# ============================================================
# UTILITIES
# ============================================================
def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _notify(title: str, message: str):
    """Bật thông báo macOS (popup góc màn hình). Bỏ qua nếu không chạy được."""
    try:
        msg = message.replace('"', "'")
        ttl = title.replace('"', "'")
        subprocess.run(
            ["osascript", "-e", f'display notification "{msg}" with title "{ttl}"'],
            check=False,
        )
    except Exception:
        pass


# ============================================================
# TELEGRAM REPORT CONFIG & UTILS
# ============================================================
RUN_REPORT = {
    "success": True,
    "downloaded_dates": {},  # date_str -> count of videos downloaded
    "updated_products": {},  # product_name -> {"added": X, "total": Y}
    "unmatched_files": [],   # list of (raw_name, count)
    "errors": [],            # list of error strings
    "corrupt_files": [],     # list of corrupted file names
    "submission_check": {},  # editor_name -> {"actual": A, "expected": E, "has_expected": bool}
    "today_assignments": {}  # editor_name -> list of video titles
}

def get_db_connection():
    conn_str = os.environ.get("DATABASE_URL")
    if not conn_str:
        # Fallback to local .env file
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
        import re
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


_history_cache = None

def _github_get_history() -> dict | None:
    """Fetch history từ Supabase và cache kết quả."""
    global _history_cache
    if _history_cache is not None:
        return _history_cache
        
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot connect to Supabase database for history!")
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT date, remainder_ptr, assignments FROM assignments_history")
        rows = cursor.fetchall()
        history = {}
        for r in rows:
            date_str, remainder_ptr, assignments_data = r[0], r[1], r[2]
            if isinstance(assignments_data, str):
                assignments_data = json.loads(assignments_data)
            # Format history[date_str] exactly as the old JSON structure
            history[date_str] = assignments_data
            history[date_str]["remainder_ptr"] = remainder_ptr
        _history_cache = history
        return _history_cache
    except Exception as e:
        print(f"   ⚠️ Lỗi khi tải history từ Supabase: {e}")
        return None
    finally:
        conn.close()


def get_telegram_config() -> tuple[str, str]:
    """Đọc cấu hình Telegram từ file telegram_config.json hoặc biến môi trường hoặc file .env local"""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    # 1. Đọc từ file .env local của anh Nam
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
                        if key == "TELEGRAM_BOT_TOKEN" and not bot_token:
                            bot_token = val
                        elif key in ("TELEGRAM_CHAT_ID", "ALLOWED_CHAT_ID") and not chat_id:
                            chat_id = val
                            
    # 2. Dự phòng từ telegram_config.json
    if not bot_token or not chat_id:
        config_path = SCRIPT_DIR / "telegram_config.json"
        if config_path.exists():
            try:
                config = load_json(config_path)
                bot_token = config.get("TELEGRAM_BOT_TOKEN", bot_token)
                chat_id = config.get("TELEGRAM_CHAT_ID", chat_id)
            except Exception as e:
                print(f"   ⚠️ Lỗi đọc telegram_config.json: {e}")
            
    return bot_token.strip(), chat_id.strip()

def send_telegram_message(text: str) -> bool:
    """Gửi tin nhắn qua Telegram Bot API sử dụng POST request"""
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        print("   ⚠️ Bỏ qua gửi Telegram do thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        import urllib.request
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("ok"):
                print("   ✅ Đã gửi báo cáo qua Telegram")
                return True
            else:
                print(f"   ❌ Gửi Telegram thất bại: {res}")
                return False
    except Exception as e:
        print(f"   ⚠️ Lỗi khi gửi Telegram: {e}")
        return False

def send_run_report():
    """Gửi báo cáo tóm tắt theo từng bước buổi sáng qua Telegram"""
    # Nếu gặp lỗi hệ thống nghiêm trọng
    if RUN_REPORT["errors"]:
        msg_lines = ["🔴 <b>[CẢNH BÁO TIKTOK WORKFLOW] GẶP LỖI HỆ THỐNG</b>\n"]
        for err in RUN_REPORT["errors"]:
            msg_lines.append(f"- {err}")
        send_telegram_message("\n".join(msg_lines))
        return

    # Lấy phân công của ngày hôm nay (today) để đưa vào Báo cáo bước 5
    today_str = datetime.today().strftime("%Y-%m-%d")
    history = _github_get_history()
    if history:
        today_data = history.get(today_str)
        if today_data and "assignments" in today_data:
            for ed, assign_info in today_data["assignments"].items():
                vids = assign_info.get("videos", [])
                if vids:
                    assigned_vids = []
                    for v in vids:
                        if isinstance(v, dict):
                            name = v.get("name", "").strip()
                            count = v.get("count", 0)
                            assigned_vids.append(f"{name} ({count})" if count else name)
                        else:
                            assigned_vids.append(str(v).strip())
                    RUN_REPORT["today_assignments"][ed] = assigned_vids

    msg_lines = ["🟢 <b>BÁO CÁO TIẾN ĐỘ BUỔI SÁNG (08:00)</b>\n"]

    # 📥 Bước 1: Tải video
    msg_lines.append("<b>1. Kết quả tải video từ Drive:</b>")
    if RUN_REPORT["downloaded_dates"]:
        for date_str, count in RUN_REPORT["downloaded_dates"].items():
            msg_lines.append(f"✅ Đã tải video ngày {date_str} thành công: {count} video")
    else:
        msg_lines.append("⚠️ Không có video nào được tải về.")
    msg_lines.append("")

    # 🔍 Bước 2: Kiểm tra lỗi video
    msg_lines.append("<b>2. Kiểm tra lỗi file video (Corrupt Check):</b>")
    if RUN_REPORT["corrupt_files"]:
        msg_lines.append(f"❌ Phát hiện {len(RUN_REPORT['corrupt_files'])} video bị lỗi hỏng:")
        for cf in RUN_REPORT["corrupt_files"]:
            msg_lines.append(f"- <code>{cf}</code>")
    else:
        msg_lines.append("✅ Không phát hiện video nào bị lỗi hỏng.")
    msg_lines.append("")

    # 📊 Bước 3: Đối chiếu số lượng video nộp
    msg_lines.append("<b>3. Đối chiếu số lượng video nộp (thực tế vs yêu cầu):</b>")
    sub_checks = RUN_REPORT["submission_check"]
    if sub_checks:
        for ed, info in sub_checks.items():
            actual = info["actual"]
            expected = info["expected"]
            if info["has_expected"]:
                status = "✅ Đủ" if actual >= expected else f"❌ Thiếu {expected - actual} video"
                msg_lines.append(f"- {ed}: {actual}/{expected} ({status})")
            else:
                msg_lines.append(f"- {ed}: {actual} video (Chưa có lịch phân công)")
    else:
        msg_lines.append("⚠️ Không có dữ liệu đối chiếu.")
    msg_lines.append("")

    # 📦 Bước 4: Báo cáo tồn kho video
    msg_lines.append("<b>4. Cập nhật tồn kho sản phẩm:</b>")
    if RUN_REPORT["updated_products"]:
        for prod_name, info in RUN_REPORT["updated_products"].items():
            msg_lines.append(f"- {prod_name}: +{info['added']} (Tồn hiện tại: {info['total']})")
    else:
        msg_lines.append("ℹ️ Không có sản phẩm nào được cập nhật tồn kho.")
    msg_lines.append("")

    # 📝 Bước 5: Báo cáo phân công edit video hôm nay
    msg_lines.append("<b>5. Phân công edit video ngày hôm nay:</b>")
    if RUN_REPORT["today_assignments"]:
        for ed, vids in RUN_REPORT["today_assignments"].items():
            vids_str = ", ".join(vids)
            msg_lines.append(f"- <b>{ed}</b>: {vids_str}")
    else:
        msg_lines.append("ℹ️ Chưa có lịch phân công ngày hôm nay trên website.")
    
    # Báo cáo file đặt sai tên sản phẩm (nếu có) ở cuối cùng
    if RUN_REPORT["unmatched_files"]:
        msg_lines.append("\n⚠️ <b>File đặt sai tên sản phẩm trên Drive:</b>")
        for name, count in RUN_REPORT["unmatched_files"]:
            msg_lines.append(f"- <code>{name}</code> ({count} video)")
        msg_lines.append("👉 Vui lòng sửa tên file trên Drive cho đúng tên SP rồi chạy lại.")

    msg = "\n".join(msg_lines)
    send_telegram_message(msg)


def date_to_vi_name(date: datetime) -> str:
    """2026-06-03 → '3 tháng 6'"""
    return f"{date.day} tháng {date.month}"


def vi_name_to_date(name: str, year: int = None) -> datetime | None:
    """'3 tháng 6' → datetime(2026, 6, 3)"""
    try:
        parts = name.split(" tháng ")
        day, month = int(parts[0].strip()), int(parts[1].strip())
        y = year or datetime.today().year
        return datetime(y, month, day)
    except Exception:
        return None


# ============================================================
# GOOGLE DRIVE API (tạo/xóa folder)
# ============================================================
def get_drive_service():
    """Khởi tạo Google Drive API client (Ưu tiên Service Account, fallback OAuth2)"""
    try:
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("❌ Thiếu thư viện Google API. Chạy:")
        print("   pip3 install google-api-python-client google-auth-oauthlib --break-system-packages")
        sys.exit(1)

    SCOPES = ["https://www.googleapis.com/auth/drive"]
    
    # 1. Thử dùng Google Service Account từ biến môi trường (phù hợp chạy trên GitHub Actions)
    sa_json_str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json_str:
        try:
            info = json.loads(sa_json_str)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            print("   🔑 Đã kết nối bằng Google Service Account (Biến môi trường)")
            return build("drive", "v3", credentials=creds)
        except Exception as e:
            print(f"   ⚠️ Thử kết nối Service Account từ env thất bại: {e}")

    # 2. Thử dùng file service_account.json local nếu có
    sa_file_path = SCRIPT_DIR / "service_account.json"
    if sa_file_path.exists():
        try:
            creds = service_account.Credentials.from_service_account_file(str(sa_file_path), scopes=SCOPES)
            print("   🔑 Đã kết nối bằng Google Service Account (File JSON)")
            return build("drive", "v3", credentials=creds)
        except Exception as e:
            print(f"   ⚠️ Thử kết nối Service Account từ file thất bại: {e}")

    # 3. Fallback: OAuth2 (Đăng nhập bằng trình duyệt cá nhân)
    token_path = SCRIPT_DIR / "token.json"
    creds_path = SCRIPT_DIR / "credentials.json"

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                refreshed = True
            except Exception as e:
                print(f"   ⚠️  Token hết hạn hoặc bị thu hồi. Xóa token cũ để đăng nhập lại...")
                try:
                    token_path.unlink()
                except Exception:
                    pass
                creds = None
        if not refreshed and (not creds or not creds.valid):
            if not creds_path.exists():
                print("❌ Không tìm thấy credentials.json hay service_account.json để xác thực!")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    print("   🔑 Đã kết nối bằng Google OAuth2 (Token cá nhân)")
    return build("drive", "v3", credentials=creds)



def create_drive_folder(service, name: str, parent_id: str) -> str:
    """Tạo folder trong Drive, trả về folder ID"""
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def folder_exists(service, name: str, parent_id: str) -> str | None:
    """Kiểm tra folder đã tồn tại chưa. Trả về ID nếu có, None nếu chưa."""
    result = service.files().list(
        q=f"name='{name}' and '{parent_id}' in parents "
          f"and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
    ).execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def list_date_folders(service) -> list[dict]:
    """Liệt kê tất cả folder ngày trong ROOT, sắp xếp từ mới → cũ"""
    result = service.files().list(
        q=f"'{ROOT_FOLDER_ID}' in parents "
          f"and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name, createdTime)",
        orderBy="createdTime desc",
    ).execute()

    folders = []
    for f in result.get("files", []):
        d = vi_name_to_date(f["name"])
        if d:
            folders.append({"id": f["id"], "name": f["name"], "date": d})

    folders.sort(key=lambda x: x["date"], reverse=True)
    return folders


# ============================================================
# BƯỚC 1: TẠO FOLDER NGÀY MAI
# ============================================================
def create_tomorrow_folder(service) -> str | None:
    tomorrow = datetime.today() + timedelta(days=1)
    folder_name = date_to_vi_name(tomorrow)

    print(f"\n📁 [1/3] Tạo folder Drive: '{folder_name}'")

    existing_id = folder_exists(service, folder_name, ROOT_FOLDER_ID)
    if existing_id:
        print(f"   ✅ Đã tồn tại (ID: {existing_id})")
        return existing_id

    # Tạo folder ngày
    folder_id = create_drive_folder(service, folder_name, ROOT_FOLDER_ID)
    print(f"   ✅ Tạo '{folder_name}' → {folder_id}")

    # Tạo 8 subfolder editor
    for editor in EDITORS:
        editor_id = create_drive_folder(service, editor, folder_id)
        print(f"      📂 {editor} → {editor_id}")

    # Lưu vào cache
    date_str = tomorrow.strftime("%Y-%m-%d")
    cache = load_json(FOLDER_CACHE)
    cache[date_str] = folder_id
    save_json(FOLDER_CACHE, cache)

    print(f"   ✅ Tạo xong {len(EDITORS)} subfolder")
    return folder_id


# ============================================================
# BƯỚC 2: XÓA FOLDER CŨ (> 7 NGÀY)
# ============================================================
def cleanup_old_folders(service):
    print(f"\n🗑️  [2/3] Dọn folder cũ (giữ {KEEP_DAYS} ngày gần nhất)...")

    folders = list_date_folders(service)
    if len(folders) <= KEEP_DAYS:
        print(f"   ✅ Có {len(folders)} folder, chưa cần xóa")
        return

    to_delete = folders[KEEP_DAYS:]
    for f in to_delete:
        try:
            service.files().delete(fileId=f["id"]).execute()
            print(f"   🗑️  Đã xóa: '{f['name']}' ({f['date'].strftime('%d/%m/%Y')})")
        except Exception as e:
            print(f"   ⚠️  Không xóa được '{f['name']}': {e}")


# ============================================================
# BƯỚC 3: DOWNLOAD VIDEO NGÀY HÔM QUA
# ============================================================
def get_yesterday_folder_id(service, target_date: datetime) -> str | None:
    """Tìm folder ID cho ngày target. Ưu tiên cache, fallback Drive API."""
    date_str = target_date.strftime("%Y-%m-%d")

    # Thử cache
    cache = load_json(FOLDER_CACHE)
    if date_str in cache:
        print(f"   💾 Dùng cached ID: {cache[date_str]}")
        return cache[date_str]

    # Thử Drive API
    if service:
        vi_name = date_to_vi_name(target_date)
        folder_id = folder_exists(service, vi_name, ROOT_FOLDER_ID)
        if folder_id:
            cache[date_str] = folder_id
            save_json(FOLDER_CACHE, cache)
            print(f"   🔍 Tìm thấy trên Drive: {folder_id}")
            return folder_id

    return None


def list_all_videos_in_folder(service, folder_id: str) -> list[dict]:
    """Liệt kê đệ quy tất cả video trong folder và subfolders"""
    from googleapiclient.errors import HttpError
    video_mime = {"video/mp4", "video/quicktime", "video/x-msvideo",
                  "video/x-matroska", "video/x-m4v", "video/"}
    results = []

    def _recurse(fid: str, path_prefix: str):
        try:
            resp = service.files().list(
                q=f"'{fid}' in parents and trashed=false",
                fields="files(id, name, mimeType)",
                pageSize=200,
            ).execute()
        except HttpError as e:
            print(f"   ⚠️  Lỗi list folder {fid}: {e}")
            return

        for f in resp.get("files", []):
            if f["mimeType"] == "application/vnd.google-apps.folder":
                _recurse(f["id"], f"{path_prefix}/{f['name']}")
            elif any(f["mimeType"].startswith(m) for m in video_mime) or \
                 Path(f["name"]).suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".m4v"}:
                results.append({
                    "id": f["id"],
                    "name": f["name"],
                    "subpath": path_prefix,
                })

    _recurse(folder_id, "")
    return results


def dedup_drive_folder(service, folder_id: str):
    """
    Detect và rename file trùng tên trong cùng subfolder trên Drive.
    VD: 3 file cùng tên 'X - Duyên.mp4' → đổi thành 'X - Duyên.mp4', 'X - Duyên 2.mp4', 'X - Duyên 3.mp4'
    Chạy trước rclone để đảm bảo download đủ file.
    """
    from googleapiclient.errors import HttpError

    print("\n🔍 Kiểm tra file trùng tên trên Drive...")
    renamed_count = 0

    def _process_folder(fid: str, folder_name: str):
        nonlocal renamed_count
        try:
            resp = service.files().list(
                q=f"'{fid}' in parents and trashed=false",
                fields="files(id, name, mimeType)",
                pageSize=200,
            ).execute()
        except HttpError as e:
            print(f"   ⚠️  Lỗi list folder {fid}: {e}")
            return

        # Group files by name
        name_groups: dict[str, list[str]] = {}
        for f in resp.get("files", []):
            if f["mimeType"] == "application/vnd.google-apps.folder":
                _process_folder(f["id"], f["name"])
            else:
                name_groups.setdefault(f["name"], []).append(f["id"])

        # Rename duplicates
        for name, ids in name_groups.items():
            if len(ids) <= 1:
                continue
            stem = Path(name).stem
            ext = Path(name).suffix
            print(f"   ⚠️  Trùng tên trong '{folder_name}': '{name}' ({len(ids)} file)")
            for i, file_id in enumerate(ids[1:], start=2):
                new_name = f"{stem} {i}{ext}"
                try:
                    service.files().update(fileId=file_id, body={"name": new_name}).execute()
                    print(f"      → Đổi tên thành: '{new_name}'")
                    renamed_count += 1
                except HttpError as e:
                    print(f"      ⚠️  Không đổi tên được: {e}")

    _process_folder(folder_id, "root")

    if renamed_count == 0:
        print("   ✅ Không có file trùng tên")
    else:
        print(f"   ✅ Đã đổi tên {renamed_count} file trùng")


def flatten_into_one_folder(folder: Path, exts: set):
    """Di chuyển tất cả video trong các subfolder lên thư mục gốc, rồi xóa subfolder."""
    moved = 0
    for f in list(folder.rglob("*")):
        if f.is_file() and f.suffix.lower() in exts and f.parent != folder:
            dest = folder / f.name
            if dest.exists():
                stem, ext, i = f.stem, f.suffix, 2
                while (folder / f"{stem} {i}{ext}").exists():
                    i += 1
                dest = folder / f"{stem} {i}{ext}"
            shutil.move(str(f), str(dest))
            moved += 1
    # Xóa các thư mục con còn lại (từ sâu nhất lên trên)
    subdirs = sorted([p for p in folder.rglob("*") if p.is_dir()],
                     key=lambda p: len(p.parts), reverse=True)
    removed = 0
    for d in subdirs:
        try:
            shutil.rmtree(d)
            removed += 1
        except Exception as e:
            print(f"   ⚠️  Không xóa được thư mục '{d.name}': {e}")
    print(f"   📦 Gom {moved} video vào 1 thư mục, xóa {removed} thư mục con")


def check_video_corrupt(file_path: Path) -> bool:
    """Kiểm tra video có bị lỗi/hỏng không bằng ffprobe"""
    import subprocess
    if file_path.stat().st_size == 0:
        return True
        
    ffprobe_bins = ["ffprobe", "/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe"]
    for bin_path in ffprobe_bins:
        try:
            cmd = [
                bin_path, "-v", "error", 
                "-show_entries", "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                str(file_path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return False  # Video hợp lệ
            else:
                return True   # Bị lỗi
        except FileNotFoundError:
            continue
        except Exception:
            return True
    return False


def download_videos(target_date: datetime, folder_id: str) -> Path | None:
    """Download video bằng rclone (16 luồng song song) từ folder ID cụ thể"""
    date_str = target_date.strftime("%Y-%m-%d")
    output_dir = DOWNLOAD_BASE / f"tiktok_{date_str}"
    if output_dir.exists():
        print(f"   🧹 Thư mục cũ tồn tại, đang dọn dẹp sạch sẽ trước khi tải lại...")
        try:
            shutil.rmtree(output_dir)
        except Exception as e:
            print(f"   ⚠️ Không dọn dẹp được thư mục cũ: {e}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"   📁 → {output_dir}")
    print(f"   ⬇️  rclone từ folder ID: {folder_id}")

    # Dùng --drive-root-folder-id để download đúng folder bất kể path
    cmd = [
        "rclone", "copy", "gdrive:", str(output_dir),
        f"--drive-root-folder-id={folder_id}",
        "--transfers=16", "--progress"
    ]
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"   ❌ rclone thất bại (code {result.returncode})")
        RUN_REPORT["errors"].append(f"rclone copy thất bại cho ngày {date_str} (code {result.returncode})")
        RUN_REPORT["success"] = False
        return None

    _exts = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
    count = len([f for f in output_dir.rglob("*") if f.suffix.lower() in _exts])
    if count == 0:
        print(f"   ⚠️  Không tìm thấy video nào trong folder! Ghi nhận ngày rỗng.")
        return output_dir

    print(f"   ✅ Download xong: {count} video")
    RUN_REPORT["downloaded_dates"][date_str] = count

    # 1. Đếm số video thực tế của từng editor dựa trên thư mục con trước khi flatten
    editor_actual = {}
    corrupt_files = []
    
    for f in list(output_dir.rglob("*")):
        if f.is_file() and f.suffix.lower() in _exts:
            editor_name = f.parent.name
            if editor_name in EDITORS:
                editor_actual[editor_name] = editor_actual.get(editor_name, 0) + 1
            if check_video_corrupt(f):
                corrupt_files.append(f.name)
                
    RUN_REPORT["corrupt_files"].extend(corrupt_files)

    # 2. Lấy phân công trong history.json từ GitHub để đối chiếu số lượng yêu cầu
    history = _github_get_history()
    expected_data = None
    if history:
        day_data = history.get(date_str)
        if day_data and "assignments" in day_data:
            expected_data = {}
            for ed, assign_info in day_data["assignments"].items():
                vids = assign_info.get("videos", [])
                total_expected = 0
                for v in vids:
                    if isinstance(v, dict):
                        total_expected += v.get("count", 1)
                    else:
                        total_expected += 1
                expected_data[ed] = total_expected
                
    # 3. Gom kết quả đối chiếu vào RUN_REPORT
    for ed in EDITORS:
        actual_cnt = editor_actual.get(ed, 0)
        expected_cnt = expected_data.get(ed, 0) if (expected_data is not None) else 0
        RUN_REPORT["submission_check"][ed] = {
            "actual": actual_cnt,
            "expected": expected_cnt,
            "has_expected": (expected_data is not None and ed in expected_data)
        }

    # Gom tất cả video vào 1 thư mục chung, xóa các thư mục con
    flatten_into_one_folder(output_dir, _exts)

    return output_dir


# ============================================================
# CẬP NHẬT TỒN KHO (products.json)
# ============================================================
def _norm_name(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower().strip()


def extract_product_name(filename: str) -> str:
    """'TORRAS - Kính cường lực - Dung 1.mp4' → 'TORRAS - Kính cường lực'
    Tên file: '[TÊN SP] - [Người] [Số]'. Bỏ phần cuối (người + số)."""
    stem = Path(filename).stem
    parts = stem.split(" - ")
    if len(parts) >= 2:
        return " - ".join(parts[:-1]).strip()
    return stem.strip()


def count_delivered_per_product(video_dir: Path) -> dict:
    """Đếm số video edit mới tải về theo từng SP (dựa vào tên file)."""
    exts = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
    counts = {}
    for f in video_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in exts:
            name = extract_product_name(f.name)
            counts[name] = counts.get(name, 0) + 1
    return counts


def db_read_products() -> list[dict]:
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot connect to Supabase database!")
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name, videos_per_assign, so_video_ngay, status, ton_video, ton_date, giao_hom_nay, last_assigned, voice_total, voice_counter FROM products_inventory")
        rows = cursor.fetchall()
        products = []
        for r in rows:
            products.append({
                "name": r[0],
                "videos_per_assign": r[1],
                "so_video_ngay": r[2],
                "status": r[3],
                "ton_video": r[4],
                "ton_date": r[5],
                "giao_hom_nay": r[6],
                "last_assigned": r[7],
                "voice_total": r[8],
                "voice_counter": r[9]
            })
        print(f"   ✅ Đọc products_inventory từ Supabase ({len(products)} SP)")
        return products
    except Exception as e:
        print(f"   ❌ Không đọc được products_inventory từ Supabase: {e}")
        return None
    finally:
        conn.close()


def db_update_products(products: list[dict]) -> bool:
    print("\n📤 Đang cập nhật tồn kho lên Supabase Cloud...")
    conn = get_db_connection()
    if not conn:
        print("     ❌ Kết nối Supabase thất bại khi cập nhật tồn kho!")
        RUN_REPORT["errors"].append("Kết nối Supabase thất bại khi cập nhật tồn kho")
        RUN_REPORT["success"] = False
        return False
    cursor = conn.cursor()
    try:
        for p in products:
            name = p.get("name")
            ton_video = p.get("ton_video", 0)
            ton_date = p.get("ton_date")
            cursor.execute(
                "UPDATE products_inventory SET ton_video = %s, ton_date = %s WHERE name = %s",
                (ton_video, ton_date, name)
            )
        conn.commit()
        print("   ✅ Cập nhật Supabase thành công!")
        return True
    except Exception as e:
        conn.rollback()
        print(f"   ⚠️  Cập nhật Supabase thất bại: {e}")
        RUN_REPORT["errors"].append(f"Cập nhật Supabase thất bại: {e}")
        RUN_REPORT["success"] = False
        return False
    finally:
        conn.close()


def update_inventory(delivered: dict, target_date: datetime) -> bool:
    """
    Cập nhật tồn kho trong products_inventory trên Supabase:
      - TRỪ phần đã đăng theo nhịp (so_video_ngay) đối với các sản phẩm active, tính từ ton_date gần nhất đến target_date.
      - CỘNG số video edit mới tải về cho mỗi SP (nếu có).
      - Đặt ton_date = target_date.
    """
    products = db_read_products()
    if products is None:
        print("❌ Không lấy được products từ Supabase — bỏ qua cập nhật tồn kho")
        RUN_REPORT["errors"].append("Không lấy được products từ Supabase")
        RUN_REPORT["success"] = False
        return False

    def _clean_quotes(s: str) -> str:
        for char in ['"', "'", "“", "”", "‘", "’"]:
            s = s.replace(char, "")
        return s

    norm_map = {_clean_quotes(_norm_name(p.get("name", ""))): p for p in products}
    # map bỏ hết dấu cách và dấu ngoặc
    squash_map = {_clean_quotes(_norm_name(p.get("name", "")).replace(" ", "")): p for p in products}
    
    # Lấy ngày đang được xử lý làm mốc
    today = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today.strftime("%Y-%m-%d")

    def _match(raw):
        key = _clean_quotes(_norm_name(raw))
        for short, full in NAME_ALIASES.items():   # tên viết tắt → tên đầy đủ
            short_clean = _clean_quotes(short)
            if key.startswith(short_clean):
                key = _clean_quotes(full) + key[len(short_clean):]
                break
        p = norm_map.get(key)
        if p is not None:
            return p
        sk = key.replace(" ", "")                   # bỏ dấu cách
        if sk in squash_map:
            return squash_map[sk]
        for nk, cand in squash_map.items():
            if sk and (sk in nk or nk in sk):
                return cand
        return None

    unmatched = []
    per_product = {}
    
    # 1) Gom tổng số video theo từng SP (gộp các biến thể tên file về cùng 1 SP → 1 dòng)
    if delivered:
        for raw_name, count in delivered.items():
            p = _match(raw_name)
            if p is None:
                unmatched.append((raw_name, count))
                continue
            rec = per_product.setdefault(id(p), [p, 0])
            rec[1] += count

        # 2) Nếu CÒN file không khớp tên SP (kể cả sau alias/bỏ dấu cách) → DỪNG.
        #    Không cập nhật gì, báo Nam (popup + log) để sửa tên trên Drive rồi chạy lại.
        if unmatched:
            print("\n🚫 CÓ FILE KHÔNG KHỚP TÊN SP — DỪNG, CHƯA CẬP NHẬT TỒN KHO:")
            for name, c in unmatched:
                print(f"      → '{name}' ({c} video)")
            print("\n👉 Sửa tên file trên Drive cho đúng tên SP rồi chạy lại.")
            print("   Tồn kho chưa được cập nhật.")
            _notify("⚠️ Có file sai tên SP — tồn kho chưa cập nhật",
                    f"{len(unmatched)} file chưa khớp. Sửa tên trên Drive rồi chạy lại. Xem log tu_chay_6h.log")
            RUN_REPORT["unmatched_files"].extend(unmatched)
            RUN_REPORT["success"] = False
            return False

    # 3) Áp dụng cho TẤT CẢ các sản phẩm trong products.json: trừ đăng cũ, cộng nộp mới
    updated = []
    for p in products:
        # Trừ phần đã đăng theo nhịp của các SP active
        rate = p.get("so_video_ngay", 1) if p.get("status", "active") == "active" else 0
        if rate is None:
            rate = 1
        ton = p.get("ton_video")
        
        days = 0
        if p.get("ton_date"):
            try:
                last = datetime.strptime(p["ton_date"], "%Y-%m-%d")
                days = max(0, (today - last).days)
            except Exception:
                days = 0
                
        if ton is None:
            cur = 0
        else:
            cur = max(0, ton - rate * days)   # trừ phần đã đăng kể từ ton_date
            
        # Cộng video mới (nếu có)
        added = 0
        if id(p) in per_product:
            added = per_product[id(p)][1]
            
        p["ton_video"] = cur + added
        p["ton_date"] = today_str
        
        # Chỉ ghi log những sản phẩm có thay đổi (có video mới hoặc có trôi qua ngày đăng)
        if added > 0 or (days > 0 and rate > 0):
            updated.append((p["name"], rate * days, added, p["ton_video"], days, rate))
        
        # Ghi nhận vào RUN_REPORT
        if added > 0:
            prod_name = p["name"]
            if prod_name in RUN_REPORT["updated_products"]:
                RUN_REPORT["updated_products"][prod_name]["added"] += added
                RUN_REPORT["updated_products"][prod_name]["total"] = p["ton_video"]
            else:
                RUN_REPORT["updated_products"][prod_name] = {"added": added, "total": p["ton_video"]}

    print("\n📊 Cập nhật tồn kho:")
    for name, minus_registered, added, total, days, rate in updated:
        change_str = f"đã đăng -{minus_registered}" if (days > 0 and rate > 0) else ""
        add_str = f"nộp mới +{added}" if added > 0 else ""
        parts = [prt for prt in [change_str, add_str] if prt]
        print(f"   {name}: tồn {total} ({', '.join(parts)})")

    # Lưu lên Supabase
    return db_update_products(products)


# ============================================================
# MAIN
# ============================================================
def print_setup_guide():
    print("""
╔══════════════════════════════════════════════════════╗
║         HƯỚNG DẪN SETUP GOOGLE API (1 LẦN)          ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  1. Mở: https://console.cloud.google.com/            ║
║  2. Tạo project mới (tên tùy ý)                      ║
║  3. APIs & Services → Enable APIs                    ║
║     → Tìm "Google Drive API" → Enable                ║
║  4. APIs & Services → Credentials                    ║
║     → Create Credentials → OAuth client ID           ║
║     → Application type: Desktop app                  ║
║     → Download JSON → đổi tên thành credentials.json ║
║  5. Copy credentials.json vào:                       ║
║     BUILD TOOLS/tiktok_auto/credentials.json         ║
║  6. Chạy lại script — trình duyệt sẽ mở để đăng nhập║
║                                                      ║
╚══════════════════════════════════════════════════════╝
""")


# ============================================================
# CATCH-UP: THEO DÕI NGÀY ĐÃ XỬ LÝ
# ============================================================
PROCESSED_KEY = "__processed_dates__"


def get_processed_dates() -> set:
    """Đọc danh sách ngày đã xử lý thành công từ cache."""
    cache = load_json(FOLDER_CACHE)
    return set(cache.get(PROCESSED_KEY, []))


def mark_date_processed(date_str: str):
    """Ghi nhận ngày đã xử lý thành công vào cache."""
    cache = load_json(FOLDER_CACHE)
    processed = set(cache.get(PROCESSED_KEY, []))
    processed.add(date_str)
    # Giữ tối đa 30 ngày gần nhất để tránh file phình to
    sorted_dates = sorted(processed, reverse=True)[:30]
    cache[PROCESSED_KEY] = sorted_dates
    save_json(FOLDER_CACHE, cache)


def get_missing_dates() -> list[datetime]:
    """Trả về danh sách ngày chưa xử lý trong vòng 3 ngày gần nhất (tính đến hôm qua)."""
    cache = load_json(FOLDER_CACHE)
    processed = set(cache.get(PROCESSED_KEY, []))

    yesterday = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    earliest = yesterday - timedelta(days=2)  # Quét tối đa 3 ngày gần nhất

    missing = []
    current = earliest
    while current <= yesterday:
        date_str = current.strftime("%Y-%m-%d")
        if date_str not in processed:
            missing.append(current)
        current += timedelta(days=1)

    return missing


def process_one_date(service, target_date: datetime, only_download: bool = False) -> bool:
    """Xử lý đầy đủ 1 ngày: download + cập nhật tồn kho. Trả về True nếu thành công."""
    import os
    date_str = target_date.strftime("%Y-%m-%d")
    vi_name = date_to_vi_name(target_date)

    print(f"\n🔍 Tìm folder Drive: {vi_name} ({date_str})")
    target_folder_id = get_yesterday_folder_id(service, target_date)
    if not target_folder_id:
        print(f"   ❌ Không tìm thấy folder '{vi_name}' trong Drive — bỏ qua.")
        return False

    dedup_drive_folder(service, target_folder_id)

    is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"

    if only_download:
        print(f"\n⬇️  Chế độ: Chỉ tải video ({vi_name}) về máy...")
        video_dir = download_videos(target_date, target_folder_id)
        return video_dir is not None

    if is_github_actions:
        print("\n☁️  Đang chạy trên GitHub Actions. Đếm video trực tiếp qua Drive API...")
        video_list = list_all_videos_in_folder(service, target_folder_id)
        delivered = {}
        for f in video_list:
            name = extract_product_name(f["name"])
            delivered[name] = delivered.get(name, 0) + 1
        print(f"   ✅ Đã quét {len(video_list)} video từ Drive API")
        
        # Ghi nhận vào RUN_REPORT downloaded dates
        RUN_REPORT["downloaded_dates"][date_str] = len(video_list)
        
        return update_inventory(delivered, target_date)
    else:
        print(f"\n⬇️  Download video: {vi_name}")
        video_dir = download_videos(target_date, target_folder_id)
        if not video_dir:
            print(f"   ❌ Download thất bại cho {vi_name}!")
            return False

        delivered = count_delivered_per_product(video_dir)
        return update_inventory(delivered, target_date)


def main():
    parser = argparse.ArgumentParser(description="TikTok Daily Workflow")
    parser.add_argument("--date", help="Ngày cần xử lý (YYYY-MM-DD), mặc định = hôm qua (tắt catch-up)")
    parser.add_argument("--skip-drive", action="store_true", help="Bỏ qua quản lý Drive")
    parser.add_argument("--no-catchup", action="store_true", help="Tắt catch-up, chỉ xử lý hôm qua")
    parser.add_argument("--setup", action="store_true", help="Xem hướng dẫn setup credentials")
    parser.add_argument("--only-download", action="store_true", help="Chỉ download video về máy, không cập nhật tồn kho hay tạo folder")
    args = parser.parse_args()

    if args.setup:
        print_setup_guide()
        return

    print("=" * 55)
    print("🚀  TikTok Daily Workflow")
    print(f"📅  {datetime.today().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)

    try:
        # Khởi tạo Drive service
        print("\n🔐 Kết nối Google Drive API...")
        try:
            service = get_drive_service()
            print("   ✅ Kết nối thành công")
        except SystemExit:
            raise
        except Exception as e:
            print(f"   ⚠️  Lỗi kết nối Drive: {e}")
            RUN_REPORT["errors"].append(f"Không kết nối được Google Drive API: {e}")
            RUN_REPORT["success"] = False
            sys.exit(1)

        # BƯỚC 1: Tạo folder ngày mai + dọn folder cũ
        if not args.skip_drive and not args.only_download:
            create_tomorrow_folder(service)
            cleanup_old_folders(service)
        else:
            if args.only_download:
                print("\n⏭️  Bỏ qua quản lý Drive (Chỉ tải video)")
            else:
                print("\n⏭️  Bỏ qua quản lý Drive (--skip-drive)")

        # BƯỚC 2: Xác định danh sách ngày cần xử lý
        if args.date:
            # Chỉ định ngày cụ thể → xử lý đúng ngày đó, KHÔNG catch-up
            target_dates = [datetime.strptime(args.date, "%Y-%m-%d")]
            print(f"\n📥  Chế độ: Chỉ định ngày ({args.date})")
        elif args.no_catchup:
            # Tắt catch-up → chỉ xử lý hôm qua
            target_dates = [datetime.today() - timedelta(days=1)]
            print("\n📥  Chế độ: Chỉ hôm qua (--no-catchup)")
        else:
            # Chế độ mặc định: catch-up + hôm qua
            yesterday = datetime.today() - timedelta(days=1)
            yesterday_str = yesterday.strftime("%Y-%m-%d")
            processed = get_processed_dates()

            missing = get_missing_dates()
            # Đảm bảo hôm qua luôn có trong danh sách
            if yesterday not in missing and yesterday_str not in processed:
                missing.append(yesterday)
            # Sắp xếp từ cũ đến mới
            target_dates = sorted(set(missing), key=lambda d: d)

            if len(target_dates) == 1:
                print(f"\n📥  Chế độ: Tự động (hôm qua = {yesterday_str})")
            else:
                skipped = [d for d in target_dates if d != yesterday]
                print(f"\n📥  Chế độ: Tự động + Catch-up {len(skipped)} ngày bị lỡ")
                for d in skipped:
                    print(f"   📅 Tải bù: {date_to_vi_name(d)} ({d.strftime('%Y-%m-%d')})")

        if not target_dates:
            print("\n✅ Không có ngày nào cần xử lý.")
            return

        # BƯỚC 3: Xử lý từng ngày theo thứ tự
        success_count = 0
        for target_date in target_dates:
            date_str = target_date.strftime("%Y-%m-%d")
            processed = get_processed_dates()

            # Bảo vệ chống cộng đôi: bỏ qua nếu ngày đã được xử lý thành công
            if date_str in processed and not args.date and not args.only_download:
                print(f"\n⏭️  {date_to_vi_name(target_date)} ({date_str}) đã xử lý rồi — bỏ qua.")
                continue

            print(f"\n{'='*55}")
            print(f"📥  Xử lý: {date_to_vi_name(target_date)} ({date_str})")
            print(f"{'='*55}")

            ok = process_one_date(service, target_date, only_download=args.only_download)
            if ok:
                if not args.only_download:
                    mark_date_processed(date_str)
                success_count += 1
                print(f"   ✅ Hoàn tất {date_to_vi_name(target_date)}")
            else:
                print(f"   ⚠️  Thất bại {date_to_vi_name(target_date)} — sẽ thử lại lần chạy sau")
                if not RUN_REPORT["errors"] and not RUN_REPORT["unmatched_files"]:
                    RUN_REPORT["errors"].append(f"Xử lý thất bại ngày {date_to_vi_name(target_date)} ({date_str})")
                RUN_REPORT["success"] = False

        print("\n" + "=" * 55)
        print(f"✅ Hoàn tất! Đã xử lý {success_count}/{len(target_dates)} ngày.")
        if success_count > 0:
            last_dir = DOWNLOAD_BASE / f"tiktok_{target_dates[-1].strftime('%Y-%m-%d')}"
            print(f"   📂 Thư mục mới nhất: {last_dir}")
            
            # Tự động đồng bộ và deploy lên Cloudflare Pages
            deploy_to_cloudflare_landing()
        print("=" * 55)

    except SystemExit as e:
        if e.code != 0:
            RUN_REPORT["success"] = False
            if not RUN_REPORT["errors"]:
                RUN_REPORT["errors"].append(f"Script dừng đột ngột với mã lỗi {e.code}")
        raise
    except Exception as e:
        import traceback
        err_msg = f"Lỗi runtime script: {e}\n{traceback.format_exc()}"
        print(f"   ❌ {err_msg}")
        RUN_REPORT["errors"].append(f"Lỗi runtime: {e}")
        RUN_REPORT["success"] = False
        raise
    finally:
        send_run_report()


def deploy_to_cloudflare_landing():
    """Tự động đồng bộ và deploy lên Cloudflare Pages nếu thư mục namoinam-landing tồn tại."""
    import shutil
    import subprocess
    from pathlib import Path
    import urllib.request
    import base64 as _b64
    
    # SCRIPT_DIR được định nghĩa ở config
    landing_dir = Path("/Users/nambui/.gemini/antigravity/scratch/namoinam-landing")
    if not landing_dir.exists():
        return
        
    print("\n🔄 Phát hiện thư mục namoinam-landing local. Đang đồng bộ và deploy lên Cloudflare Pages...")
    try:
        # Fetch history.json and products.json from GitHub directly and write to landing_dir
        for filename in ["history.json", "products.json"]:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
            req = urllib.request.Request(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                content_bytes = _b64.b64decode(data["content"].replace("\n", ""))
                (landing_dir / filename).write_bytes(content_bytes)
                print(f"   ✅ Đã tải và đồng bộ {filename} từ GitHub sang thư mục landing")
            except Exception as fe:
                print(f"   ⚠️  Không tải được {filename} từ GitHub: {fe}")
                # Fallback to local copy if available
                if (SCRIPT_DIR / filename).exists():
                    shutil.copy(SCRIPT_DIR / filename, landing_dir / filename)
                    print(f"   ✅ Đồng bộ {filename} từ file local sang thư mục landing (fallback)")
                else:
                    raise FileNotFoundError(f"Không có file local {filename} và không fetch được từ GitHub.")
        
        # Chạy lệnh deploy
        cmd = ["npx", "wrangler", "pages", "deploy", ".", "--project-name=namoinam", "--branch=production"]
        result = subprocess.run(cmd, cwd=str(landing_dir), capture_output=True, text=True)
        if result.returncode == 0:
            print("   ✅ Deploy Cloudflare Pages thành công!")
        else:
            print(f"   ⚠️  Deploy Cloudflare Pages thất bại: {result.stderr}")
    except Exception as e:
        print(f"   ⚠️  Lỗi đồng bộ/deploy: {e}")


if __name__ == "__main__":
    main()
