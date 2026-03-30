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

# 強制 Python 立刻印出文字，讓 GitHub Actions 即時顯示進度
sys.stdout.reconfigure(line_buffering=True)

# 設定 Gemini API
API_KEY = os.environ.get("GEMINI_API_KEY")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# 定義 13 個新聞頻道，加入 OR 邏輯讓搜尋更聰明，擴大命中率
CHANNELS = [
    {"id": "t-1", "type": "thematic", "category": "政治經濟", "tagClass": "tag-polecon", "region": "全球", "query": "國際 (政治 OR 經濟 OR 政策)"},
    {"id": "t-2", "type": "thematic", "category": "自然生態", "tagClass": "tag-nature", "region": "全球", "query": "(氣候 OR 環保 OR 生態 OR 暖化 OR 減碳)"},
    {"id": "t-3", "type": "thematic", "category": "人文流行", "tagClass": "tag-human", "region": "全球", "query": "(文化 OR 藝術 OR 流行 OR 社會 OR 教育)"},
    {"id": "t-4", "type": "thematic", "category": "科技探索", "tagClass": "tag-tech", "region": "全球", "query": "(科技 OR AI OR 太空 OR 科學 OR 晶片)"},
    {"id": "t-5", "type": "thematic", "category": "趣味溫馨", "tagClass": "tag-fun", "region": "全球", "query": "(奇聞 OR 溫馨 OR 趣味 OR 感人 OR 救援)"},
    {"id": "r-1", "type": "regional", "region": "北美洲", "category": "政治經濟", "tagClass": "tag-polecon", "query": "(美國 OR 加拿大 OR 墨西哥) (政治 OR 社會 OR 經濟)"},
    {"id": "r-2", "type": "regional", "region": "南美洲", "category": "自然生態", "tagClass": "tag-nature", "query": "(巴西 OR 阿根廷 OR 智利 OR 秘魯 OR 南美洲)"},
    {"id": "r-3", "type": "regional", "region": "歐洲", "category": "人文流行", "tagClass": "tag-human", "query": "(英國 OR 法國 OR 德國 OR 歐盟 OR 歐洲)"},
    {"id": "r-4", "type": "regional", "region": "非洲", "category": "自然生態", "tagClass": "tag-nature", "query": "(南非 OR 埃及 OR 肯亞 OR 奈及利亞 OR 非洲)"},
    {"id": "r-5", "type": "regional", "region": "中亞", "category": "政治經濟", "tagClass": "tag-polecon", "query": "(哈薩克 OR 烏茲別克 OR 塔吉克 OR 中亞)"},
    {"id": "r-6", "type": "regional", "region": "東北亞", "category": "科技探索", "tagClass": "tag-tech", "query": "(日本 OR 韓國 OR 東北亞) 科技"},
    {"id": "r-7", "type": "regional", "region": "東南亞", "category": "政治經濟", "tagClass": "tag-polecon", "query": "(印尼 OR 泰國 OR 越南 OR 新加坡 OR 菲律賓 OR 東南亞)"},
    {"id": "r-8", "type": "regional", "region": "大洋洲", "category": "自然生態", "tagClass": "tag-nature", "query": "(澳洲 OR 紐西蘭 OR 太平洋島國 OR 大洋洲)"}
]

def get_now():
    return datetime.datetime.now().strftime('%H:%M:%S')

def fetch_real_news_from_rss(query):
    # 限制優先搜尋這些關鍵字，加入「少年報導者」提高青少年合適度
    media_query = " (中央社 OR 公視 OR 報導者 OR 少年報導者 OR 天下雜誌 OR 轉角國際 OR 敏迪 OR BBC OR 路透 OR 德國之聲 OR NHK)"
    
    # 從源頭直接封鎖黑名單媒體
    blocked_query = " -大紀元 -新唐人 -香港 -星島 -文匯 -中評 -搜狐 -網易"
    
    # 定義優質媒體白名單與過濾黑名單 (作為雙重保險)
    preferred_media = ["BBC", "路透", "美聯社", "德國之聲", "半島", "CNBC", "NHK", "經濟學人", "日經", "NPR", "Taipei Times", "報導者", "少年報導者", "中央社", "公視", "轉角國際", "敏迪", "天下雜誌"]
    blocked_media = ["大紀元", "新唐人", "香港", "星島", "文匯", "中評", "搜狐", "網易"]
    
    # 漸進式撒網：先找最近 2 天，沒有再找 5 天，最後找 14 天
    time_windows = ['2d', '5d', '14d']
    
    for window in time_windows:
        # 把過濾條件組合進去 Google News 搜尋字串
        encoded_query = urllib.parse.quote(f"{query}{media_query}{blocked_query} when:{window}")
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        print(f"[{get_now()}] 正在搜尋 RSS (時間範圍: 最近 {window}) -> {query}")
        
        try:
            response = requests.get(rss_url, timeout=10)
            xml_content = response.content.decode('utf-8', errors='ignore')
            xml_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', xml_content)
            root = ET.fromstring(xml_content)
            items = root.findall('.//channel/item')
            
            for item in items:
                source_elem = item.find('source')
                source_name = source_elem.text if source_elem is not None else ""
                
                # 碰到黑名單直接跳過 (雙重保險)
                if any(blocked in source_name for blocked in blocked_media):
                    continue
                
                # 碰到白名單立刻鎖定回傳
                if any(pref in source_name for pref in preferred_media):
                    title = item.find('title').text
                    link = item.find('link').text
                    print(f"[{get_now()}] 成功鎖定優質新聞: {title} ({source_name})")
                    return {"title": title, "link": link, "source": source_name}
                    
        except Exception as e:
            print(f"[{get_now()}] 抓取 RSS 發生錯誤: {e}")
            
    print(f"[{get_now()}] 擴大搜尋範圍至 14 天後，仍找不到白名單媒體的新聞。")
    return None

def generate_article_with_ai(channel_info, real_news, today_date):
    prompt = f"""
    你現在是一位青少年雜誌的真人專欄作家。
    請根據這則新聞：{real_news['title']}，撰寫一篇適合 10-15 歲青少年的報導。
    
    【核心教育目標】
    寫作與設計提問時，請務必緊扣以下四大標準：
    1. 理解世界：用生活化的比喻，清晰解釋這件國際大事為何發生、有何重要性。
    2. 想像未來：這件事會如何影響未來的科技、環境、社會或人類生活？
    3. 獨立思考：不要只給單一標準答案，鼓勵孩子從不同角度看事情，培養批判性思維。
    4. 媒體識讀：適時引導孩子思考訊息的來源，學習分辨事實與觀點。

    【寫作風格與語氣】
    1. 真實忠誠：請盡量忠實呈現原文的新聞事件，不做過度誇飾，僅在語氣上進行改寫。
    2. 自然溫暖：溝通風格要自然、有個性，像個有智慧的大哥哥大姊姊在對孩子說話，讓他們感覺像在閱讀優質雜誌。
    3. 拒絕流行語：絕對不要使用令人感到尷尬的時下流行用語（例如：高大上、yyds、絕絕子 等）。
    4. 封殺 AI 詞彙：絕對禁止使用機器感重詞彙，例如：深入探討、值得注意的是、賦能、一站式、全方位 等。
    5. 格式限制：寫作前請先在腦中掃描，絕對禁止使用全形破折號以及濫用 Emoji。
    6. 最後檢查：請自己問自己：「一個真實的人類作家會這樣寫嗎？」

    【重要：字數與單字規定】
    1. 中文報導 (zhContent)：字數請嚴格控制在 500 到 800 個中文字之間。分成 4 到 5 個 <p> 段落。
    2. 英文單字 (vocabulary)：請挑選 2 個。
       - "word" 欄位：必須、絕對、只能填寫『英文單字』。
       - "zh" 欄位：填寫該單字的中文翻譯與適合孩子理解的解釋。

    【JSON 格式要求】
    回傳標準 JSON 物件，不要帶 Markdown 標記，也不需要提供圖片提示：
    {{
      "zhTitle": "吸引人的大標題",
      "zhSummary": "簡單摘要這則新聞的重點",
      "zhContent": "<p>第一段描述背景與事件...</p><p>第二段解釋原理或影響...</p><p>第三段對未來或台灣的連結...</p><p>第四段引導獨立思考...</p>",
      "scaffold": ["觀察與識讀：這則新聞中...？", "生活與未來：如果在台灣...未來會...？", "獨立思考提案：你覺得我們可以用什麼角度...？"],
      "enTitle": "English Title of the Story",
      "enContent": {{ "basic": "...", "intermediate": "...", "advanced": "..." }},
      "vocabulary": [ 
          {{ "word": "English_Word_1", "zh": "中文意思與簡單生活化的解釋" }}, 
          {{ "word": "English_Word_2", "zh": "中文意思與簡單生活化的解釋" }} 
      ]
    }}
    """
    payload = { "contents": [{"parts": [{"text": prompt}]}], "generationConfig": { "responseMimeType": "application/json" } }
    headers = { "Content-Type": "application/json" }
    
    for attempt in range(3):
        try:
            print(f"[{get_now()}] 正在寫作 (嘗試 {attempt+1}/3)...")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            if response.status_code == 429:
                print(f"[{get_now()}] API 頻率限制，休息 45 秒...")
                time.sleep(45); continue
            response.raise_for_status()
            article_data = json.loads(response.json()['candidates'][0]['content']['parts'][0]['text'].strip())
            
            zh_length = len(article_data.get("zhContent", ""))
            print(f"[{get_now()}] 撰寫完成！內容長度：{zh_length} 字。")

            article_data.update({
                "id": channel_info["id"], "type": channel_info["type"], "category": channel_info["category"],
                "tagClass": channel_info["tagClass"], "region": channel_info["region"], "date": today_date,
                "sourceName": real_news["source"], "sourceLink": real_news["link"], "isFeatured": False 
            })
            
            return article_data
        except Exception as e:
            print(f"[{get_now()}] 撰寫失敗: {e}"); time.sleep(15)
    return None

def update_daily_news():
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    final_news_list = []
    consecutive_fails = 0  
    
    print(f"[{get_now()}] >>> 自動報社開始上班 <<<")
    for idx, channel in enumerate(CHANNELS):
        print(f"\n[{get_now()}] --- 處理進度 {idx+1}/13: [{channel['region']}] [{channel['category']}] ---")
        real_news = fetch_real_news_from_rss(channel["query"])
        if not real_news: continue
        article = generate_article_with_ai(channel, real_news, today_str)
        if article:
            final_news_list.append(article)
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            if consecutive_fails >= 2:
                print(f"[{get_now()}] 連續兩篇失敗，可能額度用光，緊急煞車！")
                break
        print(f"[{get_now()}] 強制休息 25 秒維護 API 穩定...")
        time.sleep(25)
        
    if not final_news_list: return

    existing_news = []
    if os.path.exists('news.json'):
        with open('news.json', 'r', encoding='utf-8') as f:
            try: 
                existing_news = json.load(f)
                print(f"[{get_now()}] 成功載入 {len(existing_news)} 筆歷史資料")
            except: pass

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
            news_date_str = news.get('date', '')
            news_date = datetime.datetime.strptime(news_date_str, '%Y-%m-%d').date()
            if unique_id not in seen_ids and news_date >= thirty_days_ago:
                filtered_news.append(news); seen_ids.add(unique_id)
        except: pass

    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(filtered_news, f, ensure_ascii=False, indent=2)
    print(f"[{get_now()}] 存檔成功！今日新增 {len(final_news_list)} 篇報導。")

if __name__ == "__main__":
    update_daily_news()
