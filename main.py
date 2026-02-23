import gspread
from oauth2client.service_account import ServiceAccountCredentials
import instaloader
import time
import random
import datetime
import os

# ==========================================
# [설정] 
# ==========================================
SPREADSHEET_KEY = "1hQ1CKUWOlAZNQB3JK74hSZ3hI-QPbEpVGrn5q0PUGlg" 
TAB_NAME = "인플루언서_DB"

# 열 번호 매칭 
COL_ID = 1            # A열
COL_INSTA_ID = 2      # B열
COL_CHANNEL_NAME = 3  # C열
COL_LINK = 4          # D열
COL_PROFILE_PIC = 5   # E열
COL_FOLLOWERS = 6     # F열
COL_SCORE = 7         # G열
COL_AVG_VIEWS = 8     # H열
COL_BIO = 9           # I열 (우선순위 판별 기준!)
COL_UPDATE_DATE = 17  # Q열

MAX_PROCESS_PER_RUN = 5 # 1회 최대 처리 인원
# ==========================================

def connect_google_sheets():
    print("📋 구글 시트에 연결 중...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("key.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(TAB_NAME)
    return sheet

def get_instagram_data(username):
    L = instaloader.Instaloader(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        
        followers = profile.followers
        full_name = profile.full_name
        biography = profile.biography
        profile_pic = profile.profile_pic_url
        
        posts = profile.get_posts()
        count, total_likes, total_comments, total_views = 0, 0, 0, 0
        
        for post in posts:
            if count >= 5: break
            total_likes += post.likes
            total_comments += post.comments
            if post.is_video: total_views += post.video_view_count
            count += 1
            time.sleep(random.uniform(2, 5))

        score = total_likes + (total_comments * 3) + (total_views * 0.1)
        avg_views = int(total_views / count) if count > 0 else 0

        return {
            "username": profile.username, "full_name": full_name, "followers": followers,
            "profile_pic": profile_pic, "score": int(score), "bio": biography, "avg_views": avg_views
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 에러 발생 ({username}): {error_msg}")
        if "429" in error_msg or "Too Many Requests" in error_msg:
            return "STOP_429"
        return None

def main():
    sheet = connect_google_sheets()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    target_id = os.environ.get('TARGET_ID', '').strip()

    # 데이터 읽어오기
    col_ids = sheet.col_values(COL_ID)
    col_insta_ids = sheet.col_values(COL_INSTA_ID)
    col_dates = sheet.col_values(COL_UPDATE_DATE)
    col_bios = sheet.col_values(COL_BIO) # ★ 소개글 데이터를 읽어옵니다.

    # ★ 1. 우선순위 분류 작업 (소개글 빈칸 vs 채워진 칸)
    empty_bio_rows = []
    filled_bio_rows = []

    for i, insta_id in enumerate(col_insta_ids[1:], start=2):
        if not insta_id: continue
        
        if target_id and target_id != insta_id: continue
            
        last_update = col_dates[i-1] if len(col_dates) > i-1 else ""
        if not target_id and last_update == today: continue

        # 소개글(Bio)이 비어있는지 확인
        bio_val = col_bios[i-1].strip() if len(col_bios) > i-1 else ""
        
        if not bio_val:
            empty_bio_rows.append(i) # 빈칸이면 1순위 그룹으로
        else:
            filled_bio_rows.append(i) # 채워져있으면 2순위 그룹으로

    # ★ 2. 빈칸 그룹을 먼저 훑고, 남은 자리에 채워진 그룹을 이어 붙임
    target_rows = empty_bio_rows + filled_bio_rows

    if not target_id:
        print(f"📊 타겟팅 완료: 소개글 빈칸 {len(empty_bio_rows)}명, 업데이트 대상 {len(filled_bio_rows)}명 대기 중")

    processed_count = 0

    # ★ 3. 분류된 순서대로 크롤링 실행
    for i in target_rows:
        insta_id = col_insta_ids[i-1]
        
        # 목표 처리량 도달 시 종료
        if processed_count >= MAX_PROCESS_PER_RUN and not target_id:
            print(f"🛑 차단 방지: 오늘 목표치({MAX_PROCESS_PER_RUN}명) 완료. 퇴근합니다!")
            break

        print(f"🔎 분석 시작: {insta_id} (Row {i})")
        generated_url = f"https://www.instagram.com/{insta_id}/"
        
        data = get_instagram_data(insta_id)
        
        if data == "STOP_429":
            print("🚨 429 에러 감지! 6시간 에러를 막기 위해 봇을 즉시 종료합니다.")
            break

        if data:
            current_id = col_ids[i-1] if len(col_ids) > i-1 else ""
            if not current_id:
                sheet.update_cell(i, COL_ID, f"INF_{i:03d}")
            
            sheet.update_cell(i, COL_CHANNEL_NAME, data['full_name'])
            sheet.update_cell(i, COL_LINK, generated_url)
            sheet.update_cell(i, COL_PROFILE_PIC, data['profile_pic'])
            sheet.update_cell(i, COL_FOLLOWERS, data['followers'])
            sheet.update_cell(i, COL_SCORE, data['score'])
            sheet.update_cell(i, COL_AVG_VIEWS, data['avg_views'])
            sheet.update_cell(i, COL_BIO, data['bio'])
            sheet.update_cell(i, COL_UPDATE_DATE, today)
            
            print(f"   ✅ {insta_id} 저장 완료!")
            processed_count += 1

        # 단건 실행이면 바로 끝내고, 대량 실행이면 휴식
        if target_id:
            break
        else:
            wait_time = random.uniform(20, 40)
            print(f"   ⏳ {int(wait_time)}초 동안 숨 고르기...")
            time.sleep(wait_time)

if __name__ == "__main__":
    main()
