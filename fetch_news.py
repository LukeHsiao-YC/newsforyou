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

# 強制 Python 立刻印出文字，解決 GitHub Actions 畫面憋著不跳動的問題
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
        print(f"[{get_now()}] 抓取 RSS 失敗: {e}")
    return None

def generate_article_with_ai(channel_info, real_news, today_date):
    prompt = f"""
    你現在是一位青少年報紙總編輯。
    請根據這則新聞：{real_news['title']}，為 10-15 歲的孩子撰寫深度報導。
    
    【核心任務：內容長度與單字正確性】
    1. 中文內容 (zhContent)：字數絕對必須超過 550 個中文字。分成 4 個 <p> 段落，語氣要自然溫暖。
    2. 重點單字 (vocabulary)：請挑選 2 個最重要的單字。
       - "word" 欄位：**必須填寫該單字的英文名稱** (例如: Semiconductor)。禁止填寫中文。
       - "zh" 欄位：填寫該單字的中文翻譯與詳細解釋。
    3. 引導提示 (scaffold)：提供 3 個層次的引導提示（觀察、連結、提案），旨在引發孩子好奇，不要給答案。
    4. 英文摘要 (enContent)：basic, intermediate, advanced 三種難度。
    5. 圖片關鍵字 (imageKeyword)：一個具體的英文名詞，如 'telescope', 'glacier'。

    請只回傳 JSON 格式（不要 Markdown 標記）：
    {{
      "zhTitle": "吸引人的標題",
      "zhSummary": "重點摘錄",
      "zhContent": "<p>...</p><p>...</p>",
      "scaffold": ["提示一", "提示二", "提示三"],
      "enTitle": "English Title",
      "enContent": {{ "basic": "...", "intermediate": "...", "advanced": "..." }},
      "vocabulary": [ 
          {{ "word": "EnglishWord", "zh": "中文解釋" }}, 
          {{ "word": "EnglishWord", "zh": "中文解釋" }} 
      ],
      "imageKeyword": "keyword"
    }}
    """
    payload = { "contents": [{"parts": [{"text": prompt}]}], "generationConfig": { "responseMimeType": "application/json" } }
    headers = { "Content-Type": "application/json" }
    
    for attempt in range(3):
        try:
            print(f"[{get_now()}] 正在呼叫 API (嘗試 {attempt+1}/3)...")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            if response.status_code == 429:
                print(f"[{get_now()}] 頻率限制中，休息 45 秒...")
                time.sleep(45); continue
            response.raise_for_status()
            article_data = json.loads(response.json()['candidates'][0]['content']['parts'][0]['text'].strip())
            
            zh_length = len(article_data.get("zhContent", ""))
            print(f"[{get_now()}] AI 撰稿完成！[內容長度：{zh_length} 字]")

            article_data.update({
                "id": channel_info["id"], "type": channel_info["type"], "category": channel_info["category"],
                "tagClass": channel_info["tagClass"], "region": channel_info["region"], "date": today_date,
                "sourceName": real_news["source"], "sourceLink": real_news["link"], "isFeatured": False 
            })
            
            keyword = article_data.get("imageKeyword", "news")
            random_seed = random.randint(1, 99999)
            article_data["imageUrl"] = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(keyword)}?width=800&height=500&nologo=true&seed={random_seed}"
            return article_data
        except Exception as e:
            print(f"[{get_now()}] 生成失敗: {e}"); time.sleep(15)
    return None

def update_daily_news():
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    final_news_list = []
    consecutive_fails = 0  
    
    print(f"[{get_now()}] >>> 編輯室啟動任務 <<<")
    for idx, channel in enumerate(CHANNELS):
        print(f"\n[{get_now()}] --- 處理進度 {idx+1}/12: [{channel['region']}] ---")
        real_news = fetch_real_news_from_rss(channel["query"])
        if not real_news: continue
        article = generate_article_with_ai(channel, real_news, today_str)
        if article:
            final_news_list.append(article)
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            if consecutive_fails >= 2:
                print(f"[{get_now()}] 🚨 連續兩次失敗，停止今日任務以節省額度。")
                break
        print(f"[{get_now()}] 冷卻 25 秒確保 API 穩定...")
        time.sleep(25)
        
    if not final_news_list: return

    existing_news = []
    if os.path.exists('news.json'):
        with open('news.json', 'r', encoding='utf-8') as f:
            try: 
                existing_news = json.load(f)
                print(f"[{get_now()}] 讀取到 {len(existing_news)} 筆歷史資料")
            except: pass

    # 合併並保留 30 天內資料，並挑選今日第一篇為精選
    for news in final_news_list:
        if news["type"] == "thematic": news["isFeatured"] = True; break

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
                filtered_news.append(news); seen_ids.add(unique_id)
        except: pass

    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(filtered_news, f, ensure_ascii=False, indent=2)
    print(f"[{get_now()}] 任務大功告成！共存檔 {len(final_news_list)} 篇今日新報導。")

if __name__ == "__main__":
    update_daily_news()
