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
COL_ID = 1            # 1: ID (A열)
COL_INSTA_ID = 2      # 2: 인스타ID (B열)
COL_CHANNEL_NAME = 3  # 3: 채널명 (C열)
COL_LINK = 4          # 4: 링크 (D열)
COL_PROFILE_PIC = 5   # 5: 프로필사진 (E열)
COL_FOLLOWERS = 6     # 6: 팔로워 (F열)
COL_SCORE = 7         # 7: 🔥화력점수 (G열)
COL_AVG_VIEWS = 8     # 8: 평균조회수 (H열)
COL_BIO = 9           # 9: 소개글(Bio) (I열)
COL_UPDATE_DATE = 17  # 17: 업데이트일 (Q열)

# ★ 핵심 안전장치: 한 번 실행할 때 최대 몇 명까지 분석할 것인가?
MAX_PROCESS_PER_RUN = 5 
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
            if count >= 5: break # 분석 게시물 수도 10개에서 5개로 줄여 속도와 안전성 확보
            total_likes += post.likes
            total_comments += post.comments
            if post.is_video: total_views += post.video_view_count
            count += 1
            time.sleep(random.uniform(2, 5)) # 게시물 사이의 휴식 시간도 늘림

        score = total_likes + (total_comments * 3) + (total_views * 0.1)
        avg_views = int(total_views / count) if count > 0 else 0

        return {
            "username": profile.username, "full_name": full_name, "followers": followers,
            "profile_pic": profile_pic, "score": int(score), "bio": biography, "avg_views": avg_views
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 에러 발생 ({username}): {error_msg}")
        # 429 에러 발생 시 완전히 중단하라는 신호 반환
        if "429" in error_msg or "Too Many Requests" in error_msg:
            return "STOP_429"
        return None

def main():
    sheet = connect_google_sheets()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    target_id = os.environ.get('TARGET_ID', '').strip()

    col_ids = sheet.col_values(COL_ID)
    col_insta_ids = sheet.col_values(COL_INSTA_ID)
    col_dates = sheet.col_values(COL_UPDATE_DATE)
    
    processed_count = 0 # 처리한 인원 수 카운트

    for i, insta_id in enumerate(col_insta_ids[1:], start=2):
        if not insta_id: continue
        
        # 목표 처리량에 도달하면 안전하게 종료
        if processed_count >= MAX_PROCESS_PER_RUN and not target_id:
            print(f"🛑 인스타그램 차단 방지를 위해 오늘치({MAX_PROCESS_PER_RUN}명) 작업을 완료하고 휴식합니다.")
            break
        
        if target_id and target_id != insta_id: continue
            
        last_update = col_dates[i-1] if len(col_dates) > i-1 else ""
        if not target_id and last_update == today: continue

        print(f"🔎 분석 시작: {insta_id} (Row {i})")
        generated_url = f"https://www.instagram.com/{insta_id}/"
        
        data = get_instagram_data(insta_id)
        
        # 429 에러를 감지하면 그 즉시 전체 루프 중단
        if data == "STOP_429":
            print("🚨 인스타그램이 봇을 감지했습니다! 6시간 타임아웃을 막기 위해 프로그램을 즉시 종료합니다.")
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

        # 다음 사람으로 넘어가기 전 충분한 휴식 (20~40초)
        wait_time = random.uniform(20, 40)
        print(f"   ⏳ {int(wait_time)}초 동안 숨 고르기...")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()
