import gspread
from oauth2client.service_account import ServiceAccountCredentials
import instaloader
import time
import random
import datetime

# ==========================================
# [설정]
SPREADSHEET_KEY = "1hQ1CKUWOlAZNQB3JK74hSZ3hI-QPbEpVGrn5q0PUGlg" 
TAB_NAME = "인플루언서_DB"
# ==========================================

def connect_google_sheets():
    print("📋 구글 시트에 연결 중...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("key.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_KEY).worksheet(TAB_NAME)
    return sheet

def get_instagram_data(username):
    L = instaloader.Instaloader()
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        
        # 1. 기본 정보
        followers = profile.followers
        full_name = profile.full_name
        biography = profile.biography
        profile_pic = profile.profile_pic_url
        
        # 2. 화력 분석 (최근 10개)
        posts = profile.get_posts()
        count = 0
        total_likes = 0
        total_comments = 0
        total_views = 0 
        
        for post in posts:
            if count >= 10: break
            
            total_likes += post.likes
            total_comments += post.comments
            
            # [사장님 질문 확인] 파이썬에서는 video_view_count가 맞습니다!
            if post.is_video:
                total_views += post.video_view_count
            
            count += 1
            time.sleep(random.uniform(1, 2))

        # 3. 점수 계산 (좋아요 + 댓글x3 + 조회수x0.1)
        score = 0
        avg_views = 0
        if count > 0:
            score = total_likes + (total_comments * 3) + (total_views * 0.1)
            avg_views = int(total_views / count)

        return {
            "username": profile.username, # 인스타 ID
            "full_name": full_name,
            "followers": followers,
            "profile_pic": profile_pic,
            "score": int(score),
            "bio": biography,
            "avg_views": avg_views
        }

    except Exception as e:
        print(f"❌ 에러 발생 ({username}): {e}")
        return None

def main():
    sheet = connect_google_sheets()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # [수정됨] 링크가 D열(4번째)로 옮겨졌습니다.
    urls = sheet.col_values(4) 
    
    for i, url in enumerate(urls[1:], start=2):
        if not url or "instagram.com" not in url: continue

        # Q열(17번째) 날짜 확인 (이미 오늘 했으면 패스)
        last_update = sheet.cell(i, 17).value 
        if last_update == today:
            print(f"PASS: {url} (오늘 이미 완료)")
            continue

        try:
            username = url.strip().split("instagram.com/")[-1].replace("/", "").split("?")[0]
        except:
            continue
        
        print(f"🔄 {username} 분석 중...")
        data = get_instagram_data(username)
        
        if data:
            # A열: ID (없으면 생성)
            current_id = sheet.cell(i, 1).value
            if not current_id:
                sheet.update_cell(i, 1, f"INF_{i:03d}") 
            
            # B열: 인스타ID (NEW)
            sheet.update_cell(i, 2, data['username'])
            
            # C열: 채널명
            sheet.update_cell(i, 3, data['full_name'])
            
            # D열은 링크니까 건너뜀
            
            # E열: 프로필사진
            sheet.update_cell(i, 5, data['profile_pic'])
            
            # F열: 팔로워
            sheet.update_cell(i, 6, data['followers'])
            
            # G열: 화력점수
            sheet.update_cell(i, 7, data['score'])
            
            # H열: 평균조회수
            sheet.update_cell(i, 8, data['avg_views'])
            
            # I열: 소개글
            sheet.update_cell(i, 9, data['bio'])
            
            # Q열: 업데이트일
            sheet.update_cell(i, 17, today)
            
            print(f"   ✅ 저장 완료! (ID: {data['username']}, 점수: {data['score']})")
        
        time.sleep(5)

if __name__ == "__main__":
    main()
