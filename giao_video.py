#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
giao_video.py — Phân công video edit hàng ngày
================================================
Cách dùng:
  python3 giao_video.py                         # nhập danh sách tay
  python3 giao_video.py --absent Thư,Sơn        # editor vắng
  python3 giao_video.py --push                  # push sau khi xem plan
  python3 giao_video.py --date 2026-06-08       # giao cho ngày cụ thể
  python3 giao_video.py --file danh_sach.txt    # đọc từ file

Format danh sách SP (mỗi dòng):
  15 TORRAS - Kính cường lực
  10 MENCANON - Rèm che nắng ô tô
  20 DEERMA - Máy xay gia vị
"""

import sys
import json
import math
import argparse
import unicodedata
import urllib.request
import urllib.error
import base64
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================
SCRIPT_DIR      = Path(__file__).parent
import os
token_file = SCRIPT_DIR / "github_token.txt"
if token_file.exists():
    GITHUB_TOKEN = token_file.read_text(encoding="utf-8").strip()
else:
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO     = "namoinam/phan-cong-edit-video"
GITHUB_HISTORY  = "history.json"
GITHUB_PRODUCTS = "products.json"

# Root folder Drive chứa folder SP (mỗi SP có subfolder VOICE)
# Folder FINAL — cùng root với date folders
SP_SEARCH_FOLDER_ID = "15QkvfBt8GHorxBIbNsRzy_5r7ZdOsddU"  # TÀI NGUYÊN EDIT VIDEO

# Editors & capacity
EDITORS_ALL = ["Thư", "Dung", "Duyên", "Hiếu", "Thắm", "Trân", "Sơn", "Tuyên"]
CAPACITY_DEFAULT = {
    "Thư": 20,
    "Dung": 15, "Duyên": 15, "Hiếu": 15,
    "Thắm": 15, "Trân": 15, "Sơn": 15, "Tuyên": 10,
}
# Thứ tự ưu tiên chia phần dư + chia voice
PRIORITY_ORDER = ["Thư", "Dung", "Duyên", "Hiếu", "Thắm", "Trân", "Sơn", "Tuyên"]

HISTORY_KEEP_DAYS = 7

# Alias tên SP: tên hay sai → tên đúng trong products.json (chữ thường)
NAME_ALIASES = {
    "tmt store": "tieu man thau store",
    "hapas - quà tặng set thân thương": 'hapas - quà tặng set "thân thương"',
    "ulucky - chườm ấm bụng": "ulucky - đai chườm ấm bụng",
    "luck - đai chường ấm bụng": "ulucky - đai chườm ấm bụng",
    "luck - đai chườm ấm bụng": "ulucky - đai chườm ấm bụng",
    "vua nem official - nệm lò xo goodnight sleep": "vua nệm - nệm lò xo",
    "vua nem - nệm lò xo": "vua nệm - nệm lò xo",
    "jetzt - máy hút bụi x9": "jetz - máy hút bụi x9",
    "torras - kính cường lực không viền": "torras - kính cường lực",
    "torras - kính cường lực khong vien": "torras - kính cường lực",
    # ONECHI — sửa lỗi chính tả và rút gọn tên file
    "onechi - dây dán velcro quản chống rối": "onechi - dây dán velcro quấn chống rối",
    "dây dán velcro quản chống rối": "onechi - dây dán velcro quấn chống rối",
    # Mới bổ sung để khớp folder Google Drive
    "hapas - quà tặng set \"chân thành\"": "hapas - quà tặng hapas set \"chân thành\"",
    "luck - bình đựng dầu ăn đa năng": "luck - bình đựng dầu ăn thủy tinh",
    "royal - khăn tắm cotton": "royal towel - khăn tắm",
    "thinshop88 - cây đấm lưng ngải cứu": "thinshop88 - cây đâm lưng ngải cứu",
    "ajido - cân điện tử thông minh": "ajido - cân điện tử ajido s5 pro",
    "edc vn - đèn pin led zoom f35": "edc vn - đèn pin led f35 vs f37",
    "tosudo - móc treo đồ": "tosudo - móc kẹp, treo đồ",
    "deli - ổ điện chữ t": "deli - ổ cắm điện chữ t",
    # Mới bổ sung cho phân công hôm nay
    "perysmith - máy hút bụi cầm tay xs1pro": "perysmith - máy hút bụi cầm tay xs1 pro",
    "jisulife - quạt đeo cổ life 5": "jisulife - quạt đeo cổ jisulife life 5",
    "arzopa - màn hình di động z1fc": "arzopa - màn hình di động",
    "hapas - phụ nữ việt nam 20.10 (2026)": "hapas - quà tặng phụ nữ việt nam 20.10 (2026)",
    "hapas - valentine 14.2 (2026)": "hapas - quà tặng valentine 14.2 (2026)",
    "dominic - máy cắt tỉa lông mũi": "dominic - máy tỉa lông mũi",
    "boxerman - quần boxer nam profit": "boxerman - quần sịp nam",
    "deerma - vòi sen tăng áp 2in1": "deerma - vòi sen tăng áp",
}



# ============================================================
# TEXT HELPERS
# ============================================================
def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower().strip()


def resolve_alias(name_lower: str) -> str:
    return NAME_ALIASES.get(name_lower, name_lower)


def match_product(input_name: str, products: list[dict]) -> dict | None:
    """Tìm SP trong products.json theo tên (dùng alias nếu cần)."""
    target = resolve_alias(norm(input_name))
    for p in products:
        if norm(p["name"]) == target:
            return p
        if resolve_alias(norm(p["name"])) == target:
            return p
        # Partial brand match fallback
        if target in norm(p["name"]) or norm(p["name"]) in target:
            return p
    return None


# ============================================================
# GITHUB API
# ============================================================
def _gh_request(url: str, method: str = "GET", body: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def gh_read_json(path: str) -> tuple[dict | list, str]:
    """Đọc file JSON từ GitHub. Trả về (parsed_data, sha)."""
    data = _gh_request(f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}")
    content = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(content), data["sha"]


def gh_push_json(path: str, sha: str, content: dict | list, message: str) -> str:
    """Push file JSON lên GitHub. Trả về commit sha mới."""
    body = json.dumps({
        "message": message,
        "content": base64.b64encode(
            json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("ascii"),
        "sha": sha,
    }).encode("utf-8")
    result = _gh_request(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}",
        method="PUT", body=body,
    )
    return result["commit"]["sha"]


# ============================================================
# GOOGLE DRIVE HELPERS
# ============================================================
def get_drive_service():
    """Lấy Drive service dùng cùng credentials với fetch_drive.py."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import pickle

        SCOPES = ["https://www.googleapis.com/auth/drive"]
        token_path = SCRIPT_DIR / "token.pickle"
        creds_path = SCRIPT_DIR / "credentials.json"

        creds = None
        if token_path.exists():
            with open(token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)

        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"   ⚠️  Drive không khả dụng: {e}")
        return None


def list_folders_in(service, parent_id: str) -> list[dict]:
    """Liệt kê tất cả subfolder trong một folder."""
    results = []
    page_token = None
    while True:
        q_args = dict(
            q=f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="nextPageToken, files(id, name, webViewLink)",
            pageSize=200,
        )
        if page_token:
            q_args["pageToken"] = page_token
        r = service.files().list(**q_args).execute()
        results.extend(r.get("files", []))
        page_token = r.get("nextPageToken")
        if not page_token:
            break
    return results


def find_sp_folder(service, sp_name: str) -> tuple[str | None, str | None]:
    """
    Tìm folder SP trong SP_SEARCH_FOLDER_ID.
    Trả về (folder_id, webViewLink) hoặc (None, None).
    """
    if not service:
        return None, None
    try:
        folders = list_folders_in(service, SP_SEARCH_FOLDER_ID)
        target = resolve_alias(norm(sp_name))
        for f in folders:
            if resolve_alias(norm(f["name"])) == target:
                return f["id"], f["webViewLink"]
        return None, None
    except Exception as e:
        print(f"   ⚠️  Lỗi tìm folder Drive: {e}")
        return None, None


def count_voice_files(service, sp_folder_id: str) -> int:
    """Đếm số file trong subfolder VOICE của SP (đệ quy, ưu tiên Voice Daily nếu có subfolders)."""
    if not service or not sp_folder_id:
        return 0
    try:
        # Tìm subfolder có tên chứa "VOICE" (vd: "5. VOICE", "5. VOICE (update 3.2)")
        r = service.files().list(
            q=f"'{sp_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false and name contains 'VOICE'",
            fields="files(id,name)",
        ).execute()
        folders = r.get("files", [])
        if not folders:
            return 0

        voice_id = folders[0]["id"]
        
        # Kiểm tra xem bên trong folder VOICE này có chứa subfolders nào không
        r_sub = service.files().list(
            q=f"'{voice_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id,name)",
        ).execute()
        subfolders = r_sub.get("files", [])
        
        # Nếu có subfolders, tìm xem có folder nào tên chứa "daily" không
        if subfolders:
            daily_folders = [sf for sf in subfolders if "daily" in sf["name"].lower()]
            if daily_folders:
                # Nếu có folder chứa "daily", ta chỉ đếm trong folder daily này thôi!
                voice_id = daily_folders[0]["id"]
        
        def _count_recursive(fid: str) -> int:
            total_count = 0
            page_token = None
            while True:
                q_args = dict(
                    q=f"'{fid}' in parents and trashed=false",
                    fields="nextPageToken, files(id, mimeType)",
                    pageSize=1000,
                )
                if page_token:
                    q_args["pageToken"] = page_token
                res = service.files().list(**q_args).execute()
                for f in res.get("files", []):
                    if f["mimeType"] == "application/vnd.google-apps.folder":
                        total_count += _count_recursive(f["id"])
                    else:
                        total_count += 1
                page_token = res.get("nextPageToken")
                if not page_token:
                    break
            return total_count

        return _count_recursive(voice_id)
    except Exception as e:
        print(f"   ⚠️  Lỗi đếm VOICE: {e}")
        return 0




# ============================================================
# INPUT PARSING
# ============================================================
def parse_product_list(text: str) -> list[tuple[int, str]]:
    """Parse danh sách SP từ text. Mỗi dòng: 'N tên_SP'."""
    result = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        try:
            count = int(parts[0])
            name = parts[1].strip()
            result.append((count, name))
        except ValueError:
            continue
    return result


# ============================================================
# VIDEO DISTRIBUTION (theo tỉ lệ capacity + phần dư xoay vòng)
# ============================================================
def distribute_videos(
    n_videos: int,
    active_editors: list[str],
    capacity: dict[str, int],
    remainder_ptr: int,  # con trỏ toàn cục xoay qua các SP
) -> tuple[dict[str, int], int]:
    """
    Chia n_videos cho active_editors theo capacity.
    Phần dư chia theo thứ tự PRIORITY_ORDER, con trỏ tiếp tục qua SP tiếp theo.
    Trả về (shares_dict, new_remainder_ptr).
    """
    active_ordered = [e for e in PRIORITY_ORDER if e in active_editors]
    total_cap = sum(capacity[e] for e in active_editors)

    # Bước 1: Floor theo tỉ lệ
    shares = {e: math.floor(n_videos * capacity[e] / total_cap) for e in active_editors}

    # Bước 2: Chia phần dư
    remainder = n_videos - sum(shares.values())
    ptr = remainder_ptr % len(active_ordered)
    for _ in range(remainder):
        shares[active_ordered[ptr]] += 1
        ptr = (ptr + 1) % len(active_ordered)

    return shares, ptr


# ============================================================
# VOICE DISTRIBUTION (counter toàn cục xoay vòng, không reset)
# ============================================================
def distribute_voice(
    sp_name: str,
    editor_videos: dict[str, int],   # editor → số video SP này
    voice_state: dict,               # !voice_state (sẽ được cập nhật in-place)
    voice_total_drive: int,          # số file trong VOICE folder
) -> dict[str, list[int]]:
    """
    Gán số voice cho từng editor, theo counter toàn cục xoay vòng.
    voice_state được cập nhật trực tiếp.
    Trả về {editor: [voice_nums]}.
    """
    state = voice_state.get(sp_name, {"total": voice_total_drive, "counter": 0})

    # Cập nhật total nếu Drive có số khác (folder VOICE thay đổi)
    if voice_total_drive > 0:
        state["total"] = voice_total_drive

    total = state["total"]
    counter = state["counter"]
    result = {}

    if total == 0:
        voice_state[sp_name] = state
        return result  # Không có voice

    # SPECIAL OVERRIDE FOR STARFISH 2 (Only voices 22-32)
    is_starfish2 = "starfish 2" in norm(sp_name)

    for editor in PRIORITY_ORDER:
        n = editor_videos.get(editor, 0)
        if n == 0:
            continue
        voices = []
        for _ in range(n):
            if is_starfish2:
                # Chỉ phân phối từ voice 22 đến 32 (tổng cộng 11 files)
                voices.append(22 + (counter % 11))
            else:
                voices.append((counter % total) + 1)
            counter += 1
        result[editor] = voices

    state["counter"] = counter
    voice_state[sp_name] = state
    return result


# ============================================================
# HISTORY HELPERS
# ============================================================
def cleanup_history(history: dict, today: datetime) -> dict:
    """Xóa entry cũ > HISTORY_KEEP_DAYS ngày. Không bao giờ xóa key bắt đầu bằng '!'."""
    cutoff = today - timedelta(days=HISTORY_KEEP_DAYS)
    to_del = [
        k for k in history
        if not k.startswith("!")
        and len(k) == 10
        and datetime.strptime(k, "%Y-%m-%d") < cutoff
    ]
    for k in to_del:
        del history[k]
    return history


# ============================================================
# DISPLAY
# ============================================================
def display_plan(
    today: datetime,
    active_editors: list[str],
    capacity: dict[str, int],
    sp_plans: list[dict],
) -> bool:
    """Hiển thị kế hoạch. Trả về True nếu ổn (tổng khớp, không lỗi cứng)."""
    total_videos = sum(p["n_videos"] for p in sp_plans)
    total_cap = sum(capacity[e] for e in active_editors)

    # Tổng từng editor
    editor_total: dict[str, int] = {e: 0 for e in active_editors}
    for p in sp_plans:
        for e, n in p["shares"].items():
            editor_total[e] = editor_total.get(e, 0) + n

    print("\n" + "═" * 62)
    print(f"  📋 KẾ HOẠCH GIAO VIDEO — {today.strftime('%d/%m/%Y')}")
    print("═" * 62)

    ok = True

    # Kiểm tra tổng
    if total_videos != total_cap:
        print(f"\n  ❌ TỔNG KHÔNG KHỚP: {total_videos} video ≠ {total_cap} capacity")
        print("     Điều chỉnh danh sách rồi chạy lại!\n")
        ok = False
    else:
        print(f"\n  ✅ Tổng: {total_videos} video  |  {len(active_editors)} editor  |  {len(sp_plans)} SP")

    # Nhân sự
    print("\n  👥 Nhân sự & capacity:")
    parts = [f"{e} {editor_total[e]}" for e in PRIORITY_ORDER if e in active_editors]
    print("     " + " · ".join(parts))

    absent = [e for e in PRIORITY_ORDER if e not in active_editors]
    if absent:
        print(f"     🚫 Vắng: {', '.join(absent)}")

    # Chi tiết từng SP
    print(f"\n  📦 Chi tiết {len(sp_plans)} sản phẩm:")
    for p in sp_plans:
        has_warn = bool(p["warnings"])
        icon = "⚠️ " if has_warn else "  "
        print(f"\n  {icon}【{p['name']}】 — {p['n_videos']} video")

        for w in p["warnings"]:
            print(f"      ⚠️  {w}")
            if "KHÔNG TÌM THẤY" in w:
                ok = False  # lỗi cứng: không có folder Drive

        link_str = p.get("drive_link") or "❌ chưa tìm thấy"
        print(f"      🔗 {link_str}")

        # Video
        vid_parts = [
            f"{e}:{p['shares'][e]}"
            for e in PRIORITY_ORDER
            if e in active_editors and p["shares"].get(e, 0) > 0
        ]
        print(f"      📹 {' | '.join(vid_parts)}")

        # Voice
        vt = p.get("voice_total", 0)
        if vt > 0:
            voice_parts = [
                f"{e}:[{','.join(str(v) for v in p['voice_assignments'].get(e, []))}]"
                for e in PRIORITY_ORDER
                if e in active_editors and p["voice_assignments"].get(e)
            ]
            print(f"      🎙️  {' | '.join(voice_parts)}")
        else:
            print(f"      🎙️  Không có voice")

    # Verify tổng từng editor
    print("\n  ✅ Verify từng editor:")
    all_match = True
    for e in PRIORITY_ORDER:
        if e not in active_editors:
            continue
        total = editor_total.get(e, 0)
        expected = capacity[e]
        if total == expected:
            print(f"      {e}: {total} ✓")
        else:
            print(f"      {e}: {total} ❌ (cần {expected})")
            all_match = False

    if not all_match:
        ok = False

    print("\n" + "═" * 62)
    if ok:
        print("  ✅ Kế hoạch ổn! Chạy lại với --push để push lên GitHub.")
    else:
        print("  ❌ Có lỗi — xem cảnh báo ở trên, sửa rồi chạy lại.")
    print("═" * 62)

    return ok


# ============================================================
# BUILD HISTORY ENTRY
# ============================================================
def build_history_entry(
    active_editors: list[str],
    sp_plans: list[dict],
) -> tuple[dict, list]:
    """Build assignments dict và links list theo format history.json thực tế."""
    assignments: dict[str, dict] = {}
    links: list[dict] = []

    for p in sp_plans:
        # links list
        links.append({
            "full_name": p["name"],
            "url": p.get("drive_link") or "",
        })

        for editor in PRIORITY_ORDER:
            if editor not in active_editors:
                continue
            n_vid = p["shares"].get(editor, 0)
            if n_vid == 0:
                continue

            if editor not in assignments:
                assignments[editor] = {"videos": [], "voices": []}

            assignments[editor]["videos"].append({
                "name": p["name"],
                "count": n_vid,
            })

            voice_nums = p["voice_assignments"].get(editor, [])
            if voice_nums:
                assignments[editor]["voices"].append({
                    "name": p["name"],
                    "count": ", ".join(str(v) for v in voice_nums),
                })

    return assignments, links


def deploy_to_cloudflare_landing():
    """Tự động đồng bộ và deploy lên Cloudflare Pages nếu thư mục namoinam-landing tồn tại."""
    import shutil
    import subprocess
    from pathlib import Path
    import urllib.request
    import base64 as _b64
    import json
    
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
        try:
            result = subprocess.run(cmd, cwd=str(landing_dir), capture_output=True, text=True, timeout=25)
            if result.returncode == 0:
                print("   ✅ Deploy Cloudflare Pages thành công!")
            else:
                print(f"   ⚠️  Deploy Cloudflare Pages thất bại: {result.stderr}")
        except subprocess.TimeoutExpired as te:
            stdout = te.stdout or b""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="ignore")
            if "Deployment complete!" in stdout or "Success!" in stdout:
                print("   ✅ Deploy Cloudflare Pages thành công! (Tiến trình kết thúc chậm)")
            else:
                print(f"   ⚠️  Deploy Cloudflare Pages quá thời gian chờ (timeout): {te}")
    except Exception as e:
        print(f"   ⚠️  Lỗi đồng bộ/deploy: {e}")


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Phân công video edit hàng ngày")
    parser.add_argument("--absent", help="Editor vắng, cách nhau bằng dấu phẩy (vd: Thư,Sơn)")
    parser.add_argument("--push", action="store_true", help="Push kết quả lên GitHub")
    parser.add_argument("--date", help="Ngày giao (YYYY-MM-DD), mặc định = hôm nay")
    parser.add_argument("--file", help="File danh sách SP (mỗi dòng: 'N tên_SP')")
    parser.add_argument("--no-drive", action="store_true", help="Bỏ qua kết nối Drive")
    args = parser.parse_args()

    # Ngày giao
    today = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.today()
    today_str = today.strftime("%Y-%m-%d")

    print("\n" + "═" * 62)
    print("  🎬 GIAO VIDEO EDIT HÀNG NGÀY")
    print(f"  📅 {today.strftime('%d/%m/%Y (%A)')}")
    print("═" * 62)

    # Editor vắng
    absent = [a.strip() for a in args.absent.split(",")] if args.absent else []
    if absent:
        print(f"\n  🚫 Editor vắng: {', '.join(absent)}")

    active_editors = [e for e in EDITORS_ALL if e not in absent]
    capacity = {e: CAPACITY_DEFAULT[e] for e in active_editors}
    total_cap = sum(capacity.values())
    print(f"  👥 {len(active_editors)} editor · Capacity: {total_cap} video")

    # Đọc danh sách SP
    if args.file:
        sp_text = Path(args.file).read_text(encoding="utf-8")
    else:
        print("\n  📋 Paste danh sách SP (format: 'N tên_SP'), Enter 2 lần khi xong:")
        lines = []
        while True:
            try:
                line = input()
                if line == "" and lines:
                    break
                elif line:
                    lines.append(line)
            except EOFError:
                break
        sp_text = "\n".join(lines)

    sp_list = parse_product_list(sp_text)
    if not sp_list:
        print("\n  ❌ Không parse được danh sách SP. Format: 'N tên_SP' mỗi dòng.")
        sys.exit(1)

    total_videos = sum(n for n, _ in sp_list)
    print(f"\n  📦 Đọc được {len(sp_list)} SP · {total_videos} video")

    # Kiểm tra tổng
    if total_videos != total_cap:
        print(f"\n  ❌ TỔNG KHÔNG KHỚP: {total_videos} video ≠ {total_cap} capacity")
        print(f"     Cần {'thêm' if total_videos < total_cap else 'bớt'} "
              f"{abs(total_videos - total_cap)} video. Script DỪNG.")
        print("\n  Danh sách đã đọc:")
        for n, name in sp_list:
            print(f"  {n:4d}  {name}")
        sys.exit(1)

    # Đọc GitHub data
    print("\n  🔗 Đọc dữ liệu GitHub...")
    try:
        products_raw, _ = gh_read_json(GITHUB_PRODUCTS)
        print(f"     ✅ products.json — {len(products_raw)} SP")
    except Exception as e:
        print(f"     ❌ Lỗi đọc products.json: {e}")
        sys.exit(1)

    try:
        history, history_sha = gh_read_json(GITHUB_HISTORY)
        day_count = len([k for k in history if not k.startswith("!")])
        print(f"     ✅ history.json — {day_count} ngày")
    except Exception as e:
        print(f"     ❌ Lỗi đọc history.json: {e}")
        sys.exit(1)

    # Lấy voice_state (KHÔNG BAO GIỜ xóa key này)
    voice_state: dict = history.get("!voice_state", {})

    # Kết nối Drive
    service = None
    if not args.no_drive:
        print("\n  🔐 Kết nối Google Drive...")
        service = get_drive_service()
        if service:
            print("     ✅ Kết nối thành công")
        else:
            print("     ⚠️  Không kết nối được — link Drive sẽ bỏ trống")

    # Xử lý từng SP
    print(f"\n  🔄 Tính toán phân công {len(sp_list)} SP...")
    sp_plans = []
    remainder_ptr = 0  # con trỏ toàn cục qua các SP
    remaining_capacity = dict(capacity)  # tracking để đảm bảo tổng chính xác

    for n_videos, sp_name_input in sp_list:
        warnings = []

        # Tìm SP trong products.json
        matched = match_product(sp_name_input, products_raw)
        if matched:
            sp_name = matched["name"]
            if matched.get("status", "active") != "active":
                warnings.append(f"SP đang '{matched.get('status')}' — nên kiểm tra lại!")
        else:
            sp_name = sp_name_input
            warnings.append(f"Tên '{sp_name_input}' không khớp chính xác products.json")

        # Tìm folder Drive
        drive_link = None
        voice_total = 0

        if service:
            folder_id, folder_link = find_sp_folder(service, sp_name_input)
            if folder_id:
                drive_link = folder_link
                voice_total_drive = count_voice_files(service, folder_id)
                if voice_total_drive > 0:
                    voice_total = voice_total_drive
                    # Nếu total thay đổi → ghi nhận
                    if sp_name in voice_state and voice_state[sp_name]["total"] != voice_total:
                        warnings.append(
                            f"Voice total cập nhật: {voice_state[sp_name]['total']} → {voice_total}"
                        )
                else:
                    voice_total = voice_state.get(sp_name, {}).get("total", 0)
            else:
                warnings.append(f"❌ KHÔNG TÌM THẤY folder Drive cho '{sp_name_input}' — DỪNG, cần kiểm tra!")
                voice_total = voice_state.get(sp_name, {}).get("total", 0)
        else:
            # Không có Drive → dùng total đã lưu trong voice_state
            voice_total = voice_state.get(sp_name, {}).get("total", 0)
            warnings.append("Không có Drive — dùng voice total từ lần trước")

        # Phân chia video — dùng remaining_capacity để đảm bảo tổng chính xác
        shares, remainder_ptr = distribute_videos(n_videos, active_editors, remaining_capacity, remainder_ptr)
        for e in active_editors:
            remaining_capacity[e] -= shares.get(e, 0)

        # Phân chia voice
        editor_videos_sp = {e: shares[e] for e in active_editors if shares.get(e, 0) > 0}
        voice_assignments = distribute_voice(sp_name, editor_videos_sp, voice_state, voice_total)

        sp_plans.append({
            "name": sp_name,
            "input_name": sp_name_input,
            "n_videos": n_videos,
            "shares": shares,
            "voice_assignments": voice_assignments,
            "drive_link": drive_link,
            "voice_total": voice_total,
            "warnings": warnings,
        })

        status = "⚠️ " if warnings else "✅"
        print(f"     {status} {sp_name} ({n_videos}v, voice total={voice_total})")

    # Hiển thị kế hoạch
    plan_ok = display_plan(today, active_editors, capacity, sp_plans)

    if not args.push:
        return

    # ─── PUSH ────────────────────────────────────────────────
    if not plan_ok:
        print("\n  ❌ Plan chưa ổn — KHÔNG push. Sửa lại rồi chạy với --push.")
        sys.exit(1)

    # Cảnh báo nếu có warnings nhưng không cứng
    hard_warnings = [
        w for p in sp_plans for w in p["warnings"]
        if "KHÔNG TÌM THẤY" in w
    ]
    if hard_warnings:
        print("\n  ❌ Còn lỗi cứng (folder Drive không tìm thấy) — KHÔNG push!")
        sys.exit(1)

    print("\n  📤 Push history.json lên GitHub...")

    # Build history entry
    assignments, links = build_history_entry(active_editors, sp_plans)

    # Cập nhật history (KHÔNG bao giờ xóa !voice_state)
    history[today_str] = {
        "assignments": assignments,
        "links": links,
    }
    history["!voice_state"] = voice_state

    # Dọn entry cũ (trừ key bắt đầu bằng !)
    history = cleanup_history(history, today)

    # Push
    try:
        new_sha = gh_push_json(
            GITHUB_HISTORY,
            history_sha,
            history,
            f"giao video {today_str}: {len(sp_plans)} SP, {total_videos} video, {len(active_editors)} editor",
        )
        print(f"     ✅ Push thành công! Commit: {new_sha[:7]}")
        print(f"\n  🔗 https://namoinam.com/phan-cong-edit-video/ — live ~1 phút")
        print(f"  👥 {len(active_editors)} editor · {len(sp_plans)} SP · {total_videos} video\n")
        
        # Tự động đồng bộ và deploy lên Cloudflare Pages
        deploy_to_cloudflare_landing()
    except Exception as e:
        print(f"     ❌ Push thất bại: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
