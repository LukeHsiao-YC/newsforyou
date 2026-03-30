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
    # 更強大的 Prompt：規定字數與結構
    prompt = f"""
    你現在是一位知識博大精深、充滿魅力的青少年報紙總編輯。
    請根據這則真實新聞標題：{real_news['title']}，為 10-15 歲的孩子撰寫一篇深度專題。
    
    【核心任務：內容長度與品質】
    1. 中文長度 (zhContent)：絕對必須超過 550 個中文字。
    2. 強制寫作結構（請按此順序分成 4 到 5 個 <p> 段落）：
       - 第一段【現場直擊】：用說故事的方式引人入勝，描述這件事發生的背景與最震撼的改變。
       - 第二段【為什麼會這樣】：詳細解釋事件背後的科學原理、歷史原因或政治動機。
       - 第三段【知識放大鏡】：提供一個與這則新聞相關的冷知識（例如：如果是太空新聞，就解釋軌道原理）。
       - 第四段【對未來的影響】：這件事會如何改變我們 10 年後的生活？或是這件事跟台灣的我們有什麼關聯？
    3. 禁用 AI 詞彙：嚴禁「深入探討、值得注意、賦能、全方位、一站式」。禁止使用任何破折號或 Em dash。語氣要像真人。

    【其他欄位要求】
    - scaffold：提供 3 個層次的引導提示，重點是引發孩子好奇，不要給答案。
    - enContent：basic, intermediate, advanced 三種難度。
    - vocabulary：2 個重點單字 + 中文解釋。
    - imageKeyword：1 個具體的英文名詞，如 'telescope', 'glacier', 'stadium'。

    請只回傳 JSON 格式（不要 Markdown 標記）：
    {{
      "zhTitle": "吸睛且有教育意義的標題",
      "zhSummary": "約 60 字的重點摘錄",
      "zhContent": "用 <p> 標籤包裹的 550 字以上詳細內容",
      "scaffold": ["觀察提示", "連結提示", "行動提示"],
      "enTitle": "English News Title",
      "enContent": {{ "basic": "...", "intermediate": "...", "advanced": "..." }},
      "vocabulary": [ {{ "word": "...", "zh": "..." }}, {{ "word": "...", "zh": "..." }} ],
      "imageKeyword": "keyword"
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
            print(f"[{get_now()}] 正在呼叫 API (第 {attempt+1} 次嘗試)...")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 429:
                print(f"[{get_now()}] API 頻率限制中，休息 45 秒...")
                time.sleep(45)
                continue
                
            response.raise_for_status()
            result = response.json()
            text_content = result['candidates'][0]['content']['parts'][0]['text']
            article_data = json.loads(text_content.strip())
            
            # 填入元數據
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
            print(f"[{get_now()}] AI 生成發生小問題: {e}")
            time.sleep(15)
            
    return None

def update_daily_news():
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    final_news_list = []
    consecutive_fails = 0  
    
    print(f"[{get_now()}] >>> 啟動地球日報專屬編輯任務 <<<")
    
    for idx, channel in enumerate(CHANNELS):
        print(f"\n[{get_now()}] --- 正在撰寫第 {idx+1}/12 篇: [{channel['region']}] ---")
        
        real_news = fetch_real_news_from_rss(channel["query"])
        if not real_news:
            print(f"[{get_now()}] 本頻道暫無新聞，跳過。")
            continue
            
        article = generate_article_with_ai(channel, real_news, today_str)
        if article:
            final_news_list.append(article)
            consecutive_fails = 0  
            print(f"[{get_now()}] 撰稿成功！目前已有 {len(final_news_list)} 篇報導。")
        else:
            consecutive_fails += 1
            if consecutive_fails >= 2:
                print(f"[{get_now()}] 🚨 連續兩次失敗，可能是 API 額度限制，緊急存檔並退出。")
                break
            
        print(f"[{get_now()}] 為了維持穩定，休息 30 秒...")
        time.sleep(30)
        
    if not final_news_list:
        print(f"[{get_now()}] 很抱歉，今日沒有產出任何報導。")
        return
        
    # 設定第一篇為精選
    for news in final_news_list:
        if news["type"] == "thematic":
            news["isFeatured"] = True
            break

    # 合併新舊資料
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
        # 唯一識別碼由日期和頻道 ID 組成
        unique_id = f"{news.get('date')}-{news.get('id')}"
        try:
            news_date = datetime.datetime.strptime(news.get('date', ''), '%Y-%m-%d').date()
            if unique_id not in seen_ids and news_date >= thirty_days_ago:
                filtered_news.append(news)
                seen_ids.add(unique_id)
        except: pass

    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(filtered_news, f, ensure_ascii=False, indent=2)
        
    print(f"[{get_now()}] 編輯室完成工作！今日產出 {len(final_news_list)} 篇深度報導，存檔成功。")

if __name__ == "__main__":
    update_daily_news()
