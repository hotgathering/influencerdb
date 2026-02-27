import gspread
from oauth2client.service_account import ServiceAccountCredentials
import instaloader
import time
import random
import datetime
import os

# ==========================================
# [설정] 열 번호 매칭 (1~17열 완벽 매칭)
# ==========================================
SPREADSHEET_KEY = "1hQ1CKUWOlAZNQB3JK74hSZ3hI-QPbEpVGrn5q0PUGlg" 
TAB_NAME = "인플루언서_DB"

COL_ID = 1            # A열
COL_INSTA_ID = 2      # B열
COL_CHANNEL_NAME = 3  # C열
COL_LINK = 4          # D열
COL_PROFILE_PIC = 5   # E열
COL_FOLLOWERS = 6     # F열
COL_SCORE = 7         # G열
COL_AVG_VIEWS = 8     # H열
COL_BIO = 9           # I열
COL_UPDATE_DATE = 17  # Q열

MAX_PROCESS_PER_RUN = 5 # 전체 실행 시 최대 5명만 처리
# ==========================================

def connect_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("key.json", scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_KEY).worksheet(TAB_NAME)

def get_instagram_data(username):
    L = instaloader.Instaloader(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        
        posts = profile.get_posts()
        count, total_likes, total_comments, total_views = 0, 0, 0, 0
        
        for post in posts:
            if count >= 5: break
            total_likes += post.likes
            total_comments += post.comments
            if post.is_video: total_views += post.video_view_count
            count += 1
            time.sleep(random.uniform(2, 4))

        score = total_likes + (total_comments * 3) + (total_views * 0.1)
        avg_views = int(total_views / count) if count > 0 else 0

        return {
            "full_name": profile.full_name, "followers": profile.followers,
            "profile_pic": profile.profile_pic_url, "score": int(score), 
            "bio": profile.biography, "avg_views": avg_views
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 에러 발생 ({username}): {error_msg}")
        if "429" in error_msg or "Too Many Requests" in error_msg:
            return "STOP_429"
        return None

def main():
    print("🚀 크롤링 봇 실행됨!")
    sheet = connect_google_sheets()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    target_id = os.environ.get('TARGET_ID', '').strip()

    col_ids = sheet.col_values(COL_ID)
    col_insta_ids = sheet.col_values(COL_INSTA_ID)
    col_dates = sheet.col_values(COL_UPDATE_DATE)
    col_bios = sheet.col_values(COL_BIO)

    target_rows = []

    # 단건 실행 모드
    if target_id:
        print(f"🎯 [단건 실행 모드] 타겟 아이디: {target_id}")
        for i, insta_id in enumerate(col_insta_ids[1:], start=2):
            if target_id == insta_id:
                target_rows.append(i)
                break
    # 대량 실행 모드 (빈칸 우선 정렬)
    else:
        print(f"📊 [대량 실행 모드] 전체 리스트 훑기 시작...")
        empty_bio_rows = []
        filled_bio_rows = []
        for i, insta_id in enumerate(col_insta_ids[1:], start=2):
            if not insta_id: continue
            last_update = col_dates[i-1] if len(col_dates) > i-1 else ""
            if last_update == today: continue # 오늘 이미 했으면 패스

            bio_val = col_bios[i-1].strip() if len(col_bios) > i-1 else ""
            if not bio_val:
                empty_bio_rows.append(i)
            else:
                filled_bio_rows.append(i)
        target_rows = empty_bio_rows + filled_bio_rows

    processed_count = 0

    for i in target_rows:
        insta_id = col_insta_ids[i-1]
        
        if processed_count >= MAX_PROCESS_PER_RUN and not target_id:
            print(f"🛑 차단 방지: 오늘 목표치({MAX_PROCESS_PER_RUN}명) 완료.")
            break

        print(f"🔎 크롤링 시작: {insta_id} (Row {i})")
        data = get_instagram_data(insta_id)
        
        if data == "STOP_429":
            print("🚨 429 에러 감지! 봇을 즉시 종료합니다.")
            break

        if data:
            current_id = col_ids[i-1] if len(col_ids) > i-1 else ""
            if not current_id:
                sheet.update_cell(i, COL_ID, f"INF_{i:03d}")
            
            sheet.update_cell(i, COL_CHANNEL_NAME, data['full_name'])
            sheet.update_cell(i, COL_LINK, f"https://www.instagram.com/{insta_id}/")
            sheet.update_cell(i, COL_PROFILE_PIC, data['profile_pic'])
            sheet.update_cell(i, COL_FOLLOWERS, data['followers'])
            sheet.update_cell(i, COL_SCORE, data['score'])
            sheet.update_cell(i, COL_AVG_VIEWS, data['avg_views'])
            sheet.update_cell(i, COL_BIO, data['bio'])
            sheet.update_cell(i, COL_UPDATE_DATE, today)
            
            print(f"   ✅ {insta_id} 저장 완료!")
            processed_count += 1

        if target_id: 
            break # 단건이면 1명 하고 바로 끝
        else:
            time.sleep(random.uniform(20, 30)) # 대량일 때만 휴식

if __name__ == "__main__":
    main()
