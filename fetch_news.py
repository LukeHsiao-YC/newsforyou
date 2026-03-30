import os
import json
import datetime
import requests
import re
import urllib.parse
import random

# 設定 Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

def generate_daily_news():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 給 AI 的指令，要求它扮演專業編輯並輸出 JSON
    prompt = f"""
    請身為一位專業的新聞編輯，幫我撰寫 {today} 的 8 篇每日新聞。
    目標讀者：國小高年級到國中生（10-15歲）。
    
    新聞必須涵蓋以下 8 個地區各一篇，主題請從「政治經濟、科技探索、人文流行、自然生態」中自行挑選最適合該地區的重大事件：
    1. 東北亞
    2. 東南亞
    3. 中亞
    4. 大洋洲
    5. 歐洲
    6. 非洲
    7. 北美洲
    8. 南美洲
    
    寫作要求：
    - 中文內容 (zhContent) 必須約 400 到 500 字，分段落。請客觀描述事實，語氣平易近人，不要有尷尬的大人說教感。
    - 訓練閱讀素養：內容要有清晰的因果關係，並且在文章最後，加上一小段「引導思考」的問題，激發好奇心。
    - 必須根據真實發生的近期國際重大新聞來改寫，絕不可捏造。
    - 每篇都要附上真實的具公信力媒體名稱 (sourceName) 與對應的真實網址 (sourceLink)。
    - 英文內容：請針對該新聞，提供三個不同閱讀難度 (basic, intermediate, advanced) 的短文。
    - 英文單字：從短文中挑選 2 個重點單字 (vocabulary)，並提供中文解釋。
    - 提供一個簡短、具體的英文名詞 (例如 space, desert, train) 放在 imageKeyword 欄位，這會用來自動配圖。
    - 隨機挑選其中 1 篇設定為「每週精選」 (isFeatured: true)，其他 7 篇為 false。
    
    請務必只回傳合法的 JSON 陣列格式，不要包含任何 Markdown 標記或其他文字，格式如下：
    [
      {{
        "id": "{today}-1",
        "date": "{today}",
        "isFeatured": true,
        "region": "東北亞",
        "category": "科技探索",
        "tagClass": "tag-tech",
        "imageKeyword": "robot",
        "zhTitle": "標題",
        "zhSummary": "50字客觀摘要",
        "zhContent": "<p>段落一...</p><p>段落二...</p><p>引導思考：...</p>",
        "enTitle": "English Title",
        "enContent": {{
            "basic": "Simple english...",
            "intermediate": "Normal english...",
            "advanced": "Harder english..."
        }},
        "vocabulary": [
            {{"word": "robot", "zh": "機器人"}},
            {{"word": "future", "zh": "未來"}}
        ],
        "sourceName": "BBC News",
        "sourceLink": "https://www.bbc.com/..."
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
        
        # 把 imageKeyword 轉換成免費的 AI 圖片生成網址，並加上 URL 編碼避免破圖
        for index, item in enumerate(news_data):
            keyword = item.get("imageKeyword", "news")
            encoded_keyword = urllib.parse.quote(keyword)
            # 加入隨機亂數避免瀏覽器快取到同一張圖片
            random_seed = random.randint(1, 10000)
            item["imageUrl"] = f"https://image.pollinations.ai/prompt/{encoded_keyword}?width=800&height=500&nologo=true&seed={random_seed}"
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
