import os
import sys
import json
import datetime
import requests
import re
import urllib.parse
import random
import time
import xml.etree.ElementTree as ET

# 強制 Python 立刻印出文字，解決 GitHub Actions 畫面沒有即時更新的問題
sys.stdout.reconfigure(line_buffering=True)

# 設定 Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# 定義 12 個新聞頻道 (4大主題 + 8大區域)
CHANNELS = [
    {"id": "t-1", "type": "thematic", "category": "政治經濟", "tagClass": "tag-polecon", "region": "全球", "query": "國際 政治 經濟"},
    {"id": "t-2", "type": "thematic", "category": "自然生態", "tagClass": "tag-nature", "region": "全球", "query": "國際 自然 環境 生態"},
    {"id": "t-3", "type": "thematic", "category": "人文流行", "tagClass": "tag-human", "region": "全球", "query": "國際 文化 藝術 流行"},
    {"id": "t-4", "type": "thematic", "category": "科技探索", "tagClass": "tag-tech", "region": "全球", "query": "國際 科技 AI 太空"},
    {"id": "r-1", "type": "regional", "region": "北美洲", "category": "政治經濟", "tagClass": "tag-polecon", "query": "美國 加拿大 社會 新聞"},
    {"id": "r-2", "type": "regional", "region": "南美洲", "category": "自然生態", "tagClass": "tag-nature", "query": "南美洲 巴西 阿根廷 新聞"},
    {"id": "r-3", "type": "regional", "region": "歐洲", "category": "人文流行", "tagClass": "tag-human", "query": "歐洲 英國 法國 德國 新聞"},
    {"id": "r-4", "type": "regional", "region": "非洲", "category": "自然生態", "tagClass": "tag-nature", "query": "非洲 新聞"},
    {"id": "r-5", "type": "regional", "region": "中亞", "category": "政治經濟", "tagClass": "tag-polecon", "query": "中亞 哈薩克 烏茲別克 新聞"},
    {"id": "r-6", "type": "regional", "region": "東北亞", "category": "科技探索", "tagClass": "tag-tech", "query": "日本 韓國 科技 新聞"},
    {"id": "r-7", "type": "regional", "region": "東南亞", "category": "政治經濟", "tagClass": "tag-polecon", "query": "東南亞 印尼 泰國 越南 新聞"},
    {"id": "r-8", "type": "regional", "region": "大洋洲", "category": "自然生態", "tagClass": "tag-nature", "query": "澳洲 紐西蘭 大洋洲 新聞"}
]

def get_now():
    return datetime.datetime.now().strftime('%H:%M:%S')

def fetch_real_news_from_rss(query):
    encoded_query = urllib.parse.quote(f"{query} when:7d")
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    print(f"[{get_now()}] 準備抓取 RSS: {query}")
    try:
        response = requests.get(rss_url, timeout=10)
        xml_content = response.content.decode('utf-8', errors='ignore')
        xml_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', xml_content)
        
        root = ET.fromstring(xml_content)
        item = root.find('.//channel/item')
        if item is not None:
            title = item.find('title').text
            link = item.find('link').text
            source = item.find('source').text if item.find('source') is not None else "國際媒體"
            print(f"[{get_now()}] 成功找到真實新聞: {title}")
            return {"title": title, "link": link, "source": source}
    except Exception as e:
        print(f"[{get_now()}] 抓取 RSS 失敗 ({query}): {e}")
    return None

def generate_article_with_ai(channel_info, real_news, today_date):
    # 升級版 Prompt：強迫輸出長文並豐富內容
    prompt = f"""
    你現在是一位充滿熱情、知識淵博的青少年新聞總編。
    目標讀者：國小高年級到國中生（10-15歲）。
    
    真實新聞標題：{real_news['title']}
    區域與類型：{channel_info['region']}的{channel_info['category']}
    
    請撰寫一篇富有教育意義的長篇報導，嚴格遵守：
    1. 中文長度 (zhContent)：絕對必須超過 500 字，甚至 700 字也沒關係。
       內容必須包含以下三個「隱藏段落」來支撐字數：
       - 第一部分：這件事發生的詳細經過與因果關係。
       - 第二部分：補充與此事件相關的一個「科學知識」或「歷史背景」。
       - 第三部分：這件事對人類社會或未來世界的長遠影響。
       語氣要自然溫暖，像是在跟孩子促膝長談，禁止 AI 慣用語。
       
    2. 深度思考提示 (scaffold)：請提供 3 個層次的引導文字（不要直接給答案）：
       - 提示一（觀察事實）：導引用戶去注意新聞中的某個關鍵變化。
       - 提示二（生活連結）：將這件事與用戶在台灣的日常經驗掛鉤。
       - 提示三（提案）：給予一個具體的方向，讓用戶思考自己能做出的微小改變。
       
    3. 英文分級 (enContent)：basic, intermediate, advanced 三個難度，每段約 3-5 句話。
    
    4. 英文單字 (vocabulary)：2 個重點單字 + 中文解釋。
    
    5. 圖片關鍵字 (imageKeyword)：給一個具體的英文名詞。

    回傳 JSON 格式（禁止 Markdown）：
    {{
      "zhTitle": "吸睛標題",
      "zhSummary": "約50字摘要",
      "zhContent": "使用HTML段落標籤包裹的500字以上內容",
      "scaffold": ["提示一", "提示二", "提示三"],
      "enTitle": "English Title",
      "enContent": {{ "basic": "...", "intermediate": "...", "advanced": "..." }},
      "vocabulary": [ {{ "word": "...", "zh": "..." }}, {{ "word": "...", "zh": "..." }} ],
      "imageKeyword": "one_word"
    }}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": { "responseMimeType": "application/json" }
    }
    headers = {"Content-Type": "application/json"}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"[{get_now()}] 正在呼叫 API (試行 {attempt+1}/{max_retries})...")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 429:
                print(f"[{get_now()}] 碰到頻率限制，休息 30 秒...")
                time.sleep(30)
                continue
                
            response.raise_for_status()
            result = response.json()
            text_content = result['candidates'][0]['content']['parts'][0]['text']
            article_data = json.loads(text_content.strip())
            
            # 填入後設資料
            article_data["id"] = channel_info["id"]
            article_data["type"] = channel_info["type"]
            article_data["category"] = channel_info["category"]
            article_data["tagClass"] = channel_info["tagClass"]
            article_data["region"] = channel_info["region"]
            article_data["date"] = today_date
            article_data["sourceName"] = real_news["source"]
            article_data["sourceLink"] = real_news["link"]
            article_data["isFeatured"] = False 
            
            keyword = article_data.get("imageKeyword", "world")
            encoded_keyword = urllib.parse.quote(keyword)
            random_seed = random.randint(1, 99999)
            article_data["imageUrl"] = f"https://image.pollinations.ai/prompt/{encoded_keyword}?width=800&height=500&nologo=true&seed={random_seed}"
            
            return article_data
            
        except Exception as e:
            print(f"[{get_now()}] 錯誤: {e}")
            time.sleep(10)
            
    return None

def update_daily_news():
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    final_news_list = []
    consecutive_fails = 0  
    
    print(f"[{get_now()}] >>> 開始執行地球日報任務 <<<")
    
    for idx, channel in enumerate(CHANNELS):
        print(f"\n[{get_now()}] --- 處理進度 {idx+1}/12: [{channel['region']}] ---")
        
        real_news = fetch_real_news_from_rss(channel["query"])
        if not real_news:
            print(f"[{get_now()}] RSS 空白，跳過。")
            continue
            
        article = generate_article_with_ai(channel, real_news, today_str)
        if article:
            final_news_list.append(article)
            consecutive_fails = 0  
            print(f"[{get_now()}] 寫作完成！")
        else:
            consecutive_fails += 1
            if consecutive_fails >= 2:
                print(f"[{get_now()}] 🚨 連續失敗，停止今日任務。")
                break
            
        print(f"[{get_now()}] 冷卻 25 秒...")
        time.sleep(25)
        
    if not final_news_list:
        print(f"[{get_now()}] 失敗。")
        return
        
    for news in final_news_list:
        if news["type"] == "thematic":
            news["isFeatured"] = True
            break

    # 讀取現有資料
    existing_news = []
    if os.path.exists('news.json'):
        with open('news.json', 'r', encoding='utf-8') as f:
            try:
                existing_news = json.load(f)
            except: pass

    all_news = final_news_list + existing_news
    today_date = datetime.datetime.now().date()
    thirty_days_ago = today_date - datetime.timedelta(days=30)
    
    filtered_news = []
    seen_ids = set()
    for news in all_news:
        unique_id = f"{news.get('date')}-{news.get('id')}"
        try:
            news_date = datetime.datetime.strptime(news.get('date', ''), '%Y-%m-%d').date()
            if unique_id not in seen_ids and news_date >= thirty_days_ago:
                filtered_news.append(news)
                seen_ids.add(unique_id)
        except: pass

    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(filtered_news, f, ensure_ascii=False, indent=2)
        
    print(f"[{get_now()}] 資料庫更新成功，今日產出 {len(final_news_list)} 篇報導。")

if __name__ == "__main__":
    update_daily_news()
