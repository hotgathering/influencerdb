import gspread
from oauth2client.service_account import ServiceAccountCredentials
import instaloader
import time
import random
import datetime

# ==========================================
# [설정] 구글 시트 ID 및 탭 이름
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
            if post.is_video:
                total_views += post.video_view_count
            
            count += 1
            time.sleep(random.uniform(1, 2))

        # 3. 점수 계산
        score = 0
        avg_views = 0
        if count > 0:
            score = total_likes + (total_comments * 3) + (total_views * 0.1)
            avg_views = int(total_views / count)

        return {
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
    
    # 오늘 날짜
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # C열(링크) 데이터 가져오기 (3번째 열)
    urls = sheet.col_values(3) 
    
    # 2번째 줄부터 시작 (헤더 제외)
    for i, url in enumerate(urls[1:], start=2):
        
        # 1. 링크 없으면 패스
        if not url or "instagram.com" not in url:
            continue

        # 2. 오늘 이미 업데이트했으면 패스 (P열 확인)
        # (매일 새벽에 돌릴 때 중복 방지용)
        last_update = sheet.cell(i, 16).value 
        if last_update == today:
            print(f"PASS: {url} (이미 오늘 함)")
            continue

        # 3. URL에서 아이디 추출
        try:
            username = url.strip().split("instagram.com/")[-1].replace("/", "").split("?")[0]
        except:
            continue
        
        print(f"🔄 {username} 분석 중...")
        data = get_instagram_data(username)
        
        if data:
            # ---------------------------------------------------------
            # [로봇 영역] A~H열, P열만 건드립니다. (I~O열은 절대 안 건드림)
            # ---------------------------------------------------------
            
            # A열: ID 생성 (없을 때만)
            current_id = sheet.cell(i, 1).value
            if not current_id:
                sheet.update_cell(i, 1, f"INF_{i:03d}") 
            
            # B열: 채널명
            sheet.update_cell(i, 2, data['full_name'])
            
            # D열: 프로필사진 URL
            sheet.update_cell(i, 4, data['profile_pic'])
            
            # E열: 팔로워
            sheet.update_cell(i, 5, data['followers'])
            
            # F열: 화력점수
            sheet.update_cell(i, 6, data['score'])
            
            # G열: 평균조회수
            sheet.update_cell(i, 7, data['avg_views'])
            
            # H열: 소개글(Bio)
            sheet.update_cell(i, 8, data['bio'])
            
            # P열: 업데이트 날짜
            sheet.update_cell(i, 16, today)
            
            print(f"   ✅ 저장 완료! (팔로워: {data['followers']}, 조회수: {data['avg_views']})")
        
        # 5초 대기
        time.sleep(5)

if __name__ == "__main__":
    main()
