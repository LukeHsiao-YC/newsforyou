import os
import json
import datetime
import requests
import re

# 設定 Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={AIzaSyAPe-KPHdH-bdICKi7kF6xJGcvcNscESWo}"

def generate_daily_news():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 給 AI 的指令，要求它扮演專業編輯並輸出 JSON
    prompt = f"""
    請身為一位專業的兒童新聞編輯，幫我撰寫 {today} 的 4 篇每日新聞。
    目標讀者：國小高年級到國中生（10-15歲）。
    
    新聞必須包含以下四個分類各一篇：
    1. 政治經濟 (tagClass: tag-polecon)
    2. 科技探索 (tagClass: tag-tech)
    3. 人文流行 (tagClass: tag-human)
    4. 自然生態 (tagClass: tag-nature)
    
    寫作要求：
    - 每篇中文新聞內容 (zhContent) 必須大於 500 字，分段落，以口語化、說故事的方式撰寫，並帶有啟發性。
    - 必須根據真實發生的近期國際或台灣重大新聞來改寫，絕不可捏造。
    - 每篇都要附上真實的來源媒體名稱 (sourceName) 與對應的真實網址 (sourceLink)。
    - 提供符合劍橋兒童英文 YLE Flyers 程度的英文標題 (enTitle) 和英文短文 (enContent)，約 50-80 字。
    - 提供一個簡短的英文關鍵字 (例如 space, desert, cat) 放在 imageKeyword 欄位，這會用來自動配圖。
    - 隨機挑選其中 1 篇設定為「每週精選」 (isFeatured: true)，其他 3 篇為 false。
    
    請務必只回傳合法的 JSON 陣列格式，不要包含任何 Markdown 標記或其他文字，格式如下：
    [
      {{
        "id": "{today}-1",
        "date": "{today}",
        "isFeatured": true,
        "category": "政治經濟",
        "tagClass": "tag-polecon",
        "imageKeyword": "oil",
        "zhTitle": "標題",
        "zhSummary": "50字摘要",
        "zhContent": "<p>段落一...</p><p>段落二...</p>",
        "enTitle": "English Title",
        "enContent": "English content...",
        "sourceName": "中央通訊社",
        "sourceLink": "https://www.cna.com.tw/..."
      }}
    ]
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # 抓取 AI 回傳的文字內容
        text_content = result['candidates'][0]['content']['parts'][0]['text']
        
        # 清理多餘的 Markdown 標籤以確保 JSON 格式正確
        text_content = re.sub(r'^```json', '', text_content, flags=re.MULTILINE)
        text_content = re.sub(r'^```', '', text_content, flags=re.MULTILINE)
        text_content = text_content.strip()
        
        news_data = json.loads(text_content)
        
        # 把 imageKeyword 轉換成免費的 AI 圖片生成網址
        for index, item in enumerate(news_data):
            # 使用 pollinations.ai 根據關鍵字自動生成不帶浮水印的圖片
            keyword = item.get("imageKeyword", "news")
            item["imageUrl"] = f"https://image.pollinations.ai/prompt/{keyword}?width=800&height=500&nologo=true"
            item["id"] = f"{today}-{index+1}"
            
        return news_data
        
    except Exception as e:
        print(f"生成新聞時發生錯誤: {e}")
        return []

def update_news_database():
    new_daily_news = generate_daily_news()
    if not new_daily_news:
        print("今天沒有產出新資料，提早結束程式。")
        return

    today_date = datetime.datetime.now().date()
    thirty_days_ago = today_date - datetime.timedelta(days=30)
    
    # 讀取現有的 news.json
    existing_news = []
    if os.path.exists('news.json'):
        with open('news.json', 'r', encoding='utf-8') as f:
            try:
                existing_news = json.load(f)
            except json.JSONDecodeError:
                pass

    # 將新新聞加到最前面
    all_news = new_daily_news + existing_news
    
    # 過濾機制：保留最近 30 天的資料，並剔除可能重複的今日資料
    filtered_news = []
    seen_ids = set()
    
    for news in all_news:
        news_id = news.get('id')
        news_date_str = news.get('date', '')
        
        # 避免重複 ID
        if news_id in seen_ids:
            continue
            
        try:
            news_date = datetime.datetime.strptime(news_date_str, '%Y-%m-%d').date()
            if news_date >= thirty_days_ago:
                filtered_news.append(news)
                seen_ids.add(news_id)
        except ValueError:
            pass

    # 將更新後的資料寫回 news.json
    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(filtered_news, f, ensure_ascii=False, indent=2)
        
    print(f"成功更新資料庫！共保留 {len(filtered_news)} 筆新聞。")

if __name__ == "__main__":
    update_news_database()
