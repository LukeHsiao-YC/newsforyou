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

# 定義 13 個新聞頻道，全面改用「英文關鍵字」，準備跨國撈新聞
CHANNELS = [
    {"id": "t-1", "type": "thematic", "category": "政治經濟", "tagClass": "tag-polecon", "region": "全球", "query": "World (Politics OR Economy OR Policy)"},
    {"id": "t-2", "type": "thematic", "category": "自然生態", "tagClass": "tag-nature", "region": "全球", "query": "(Climate OR Environment OR Ecology OR Global Warming)"},
    {"id": "t-3", "type": "thematic", "category": "人文流行", "tagClass": "tag-human", "region": "全球", "query": "(Culture OR Art OR Society OR Education)"},
    {"id": "t-4", "type": "thematic", "category": "科技探索", "tagClass": "tag-tech", "region": "全球", "query": "(Technology OR AI OR Space OR Science OR Semiconductor)"},
    {"id": "t-5", "type": "thematic", "category": "趣味溫馨", "tagClass": "tag-fun", "region": "全球", "query": "(Heartwarming OR Rescue OR Inspiring OR Fun facts)"},
    {"id": "r-1", "type": "regional", "region": "北美洲", "category": "政治經濟", "tagClass": "tag-polecon", "query": "(US OR Canada OR Mexico) (Politics OR Society OR Economy)"},
    {"id": "r-2", "type": "regional", "region": "南美洲", "category": "自然生態", "tagClass": "tag-nature", "query": "(Brazil OR Argentina OR Chile OR Peru OR South America)"},
    {"id": "r-3", "type": "regional", "region": "歐洲", "category": "人文流行", "tagClass": "tag-human", "query": "(UK OR France OR Germany OR EU OR Europe)"},
    {"id": "r-4", "type": "regional", "region": "非洲", "category": "自然生態", "tagClass": "tag-nature", "query": "(South Africa OR Egypt OR Kenya OR Nigeria OR Africa)"},
    {"id": "r-5", "type": "regional", "region": "中東與中亞", "category": "政治經濟", "tagClass": "tag-polecon", "query": "(Middle East OR Israel OR Iran OR Saudi Arabia OR Kazakhstan OR Central Asia)"},
    {"id": "r-6", "type": "regional", "region": "東北亞", "category": "科技探索", "tagClass": "tag-tech", "query": "(Japan OR South Korea OR East Asia) Technology"},
    {"id": "r-7", "type": "regional", "region": "東南亞", "category": "政治經濟", "tagClass": "tag-polecon", "query": "(Indonesia OR Thailand OR Vietnam OR Singapore OR Philippines OR Southeast Asia)"},
    {"id": "r-8", "type": "regional", "region": "大洋洲", "category": "自然生態", "tagClass": "tag-nature", "query": "(Australia OR New Zealand OR Pacific Islands OR Oceania)"}
]

def get_now():
    return datetime.datetime.now().strftime('%H:%M:%S')

def fetch_real_news_from_rss(channel, used_media, require_taiwan=False):
    region = channel.get("region", "")
    query = channel.get("query", "")
    
    taiwan_media_names = ["中央社", "公視", "報導者", "少年報導者", "天下雜誌", "轉角國際", "敏迪", "Taipei Times"]
    
    if require_taiwan:
        preferred_media = taiwan_media_names
        hl, gl, ceid = "zh-TW", "TW", "TW:zh-Hant"
        search_query = f"{region} 國際 新聞" if region != "全球" else "國際 重大 新聞"
    elif region == "大洋洲":
        preferred_media = ["ABC News", "RNZ", "Radio New Zealand", "BBC", "Reuters", "Associated Press", "The Guardian", "Taipei Times"]
        hl, gl, ceid = "en-US", "US", "US:en"
        search_query = query
    elif region == "中東與中亞":
        preferred_media = ["Al Jazeera", "BBC", "Reuters", "DW", "Associated Press", "NPR", "France 24", "Taipei Times"]
        hl, gl, ceid = "en-US", "US", "US:en"
        search_query = query
    else:
        preferred_media = ["BBC", "Reuters", "Associated Press", "AP", "DW", "Al Jazeera", "CNBC", "NHK WORLD", "The Economist", "NPR", "The Guardian", "TIME", "Taipei Times"]
        preferred_media.extend(taiwan_media_names)
        hl, gl, ceid = "en-US", "US", "US:en"
        search_query = query
    
    blocked_query = " -\"Daily Mail\" -\"The Sun\" -\"New York Post\" -\"Fox News\" -大紀元 -新唐人 -香港 -星島 -文匯 -中評 -搜狐 -網易 -每日頭條"
    blocked_media = ["Daily Mail", "The Sun", "New York Post", "Fox News", "Breitbart", "大紀元", "新唐人", "香港", "星島", "文匯", "中評", "搜狐", "網易", "每日頭條"]
    
    time_windows = ['2d', '5d', '14d']
    
    for window in time_windows:
        encoded_query = urllib.parse.quote(f"{search_query}{blocked_query} when:{window}")
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={ceid}"
        print(f"[{get_now()}] 正在搜尋 RSS (時間範圍: 最近 {window}) -> {region} (強制尋找台媒: {require_taiwan})")
        
        try:
            response = requests.get(rss_url, timeout=10)
            xml_content = response.content.decode('utf-8', errors='ignore')
            xml_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', xml_content)
            root = ET.fromstring(xml_content)
            items = root.findall('.//channel/item')
            
            valid_news = []
            
            for item in items:
                source_elem = item.find('source')
                source_name = source_elem.text if source_elem is not None else ""
                
                if any(blocked in source_name for blocked in blocked_media):
                    continue
                
                if any(pref in source_name for pref in preferred_media):
                    title = item.find('title').text
                    link = item.find('link').text
                    valid_news.append({"title": title, "link": link, "source": source_name})
            
            if valid_news:
                unused_news = [n for n in valid_news if n["source"] not in used_media]
                
                if unused_news:
                    selected_item = random.choice(unused_news)
                    print(f"[{get_now()}] 成功鎖定全新媒體: {selected_item['title']} ({selected_item['source']})")
                else:
                    selected_item = random.choice(valid_news)
                    print(f"[{get_now()}] 所有候選媒體皆已出場，勉強重複鎖定: {selected_item['title']} ({selected_item['source']})")
                    
                return selected_item
                    
        except Exception as e:
            print(f"[{get_now()}] 抓取 RSS 發生錯誤: {e}")
            
    print(f"[{get_now()}] 擴大搜尋範圍至 14 天後，仍找不到外媒白名單的新聞。")
    return None

def generate_article_with_ai(channel_info, real_news, today_date):
    prompt = f"""
    你現在是一位青少年雜誌的真人專欄作家。
    我們從外國媒體找來了這則新聞：{real_news['title']} (來源：{real_news['source']})。
    請你閱讀標題與來源判斷背後的新聞事件，用「繁體中文」撰寫一篇適合 10-15 歲青少年的報導。
    
    【文章內容與架構重點】
    1. 100% 聚焦新聞本體：文章必須百分之百根據原文報導的客觀事實進行改寫。詳細交代事件的起因、經過、細節與官方結果。
    2. 絕對禁止說教與反思：這點非常重要！新聞講到哪裡就停在哪裡。絕對不准在文章最後加上「這提醒了我們社會...」、「讓我們有機會去思考...」、「我們應該要...」等任何形式的反思或呼籲結語。
    3. 不硬扯台灣或未來：除非原始新聞本身就有提到台灣或未來影響，否則絕對不准自行腦補或硬把話題拉回台灣。
    4. 留白思考：請保持絕對的客觀陳述，把思考的空間完全留給文章底下的提問區就好。

    【寫作風格與語氣】
    1. 真實忠誠：請忠實呈現外媒報導的事件，不做過度誇飾，僅把艱澀的用詞改寫成青少年能懂的白話文。
    2. 自然流暢：溝通風格要自然、有個性，像個真正的人類記者在陳述客觀事實。
    3. 拒絕流行語：絕對不要使用令人感到尷尬的時下流行用語。
    4. 封殺機器詞彙：絕對禁止使用機器感重的詞彙，包含但不限於：賦能、一站式、全方位、值得注意的是、深入探討 等。
    5. 格式限制：寫作前請先在腦中掃描，絕對禁止使用全形破折號以及濫用 Emoji。
    6. 最後檢查：請自己問自己：「一個客觀的真實人類作家會加上這些多餘的結語嗎？」

    【重要：字數與單字規定】
    1. 中文報導 (zhContent)：字數請嚴格控制在 500 到 800 個中文字之間。分成 4 個 <p> 段落。
    2. 英文單字 (vocabulary)：請挑選 2 個。
       - "word" 欄位：必須、絕對、只能填寫『英文單字』。
       - "zh" 欄位：填寫該單字的中文翻譯與適合孩子理解的解釋。

    【JSON 格式要求】
    回傳標準 JSON 物件，不要帶 Markdown 標記，也不需要提供圖片提示：
    {{
      "zhTitle": "吸引人的大標題",
      "zhSummary": "簡單摘要這則新聞的重點",
      "zhContent": "<p>第一段：破題，清楚點出這個新聞事件的核心焦點...</p><p>第二段：詳細描述新聞事件的經過、具體規定或發生細節...</p><p>第三段：補充事件背後的客觀原因或各方實際說法...</p><p>第四段：直接說明這個事件目前的最終結果或後續進度（直接俐落收尾，絕對不准寫任何反思或心得）...</p>",
      "scaffold": ["觀察與識讀：這則新聞中...？", "生活與未來：你覺得這個改變會對相關的人造成什麼實際影響？", "獨立思考提案：針對這個規定，你覺得還可以怎麼做會更好？"],
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
            print(f"[{get_now()}] 正在跨國翻譯與寫作 (嘗試 {attempt+1}/3)...")
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
    
    used_media = set()
    has_taiwan_media = False
    taiwan_media_names = ["中央社", "公視", "報導者", "少年報導者", "天下雜誌", "轉角國際", "敏迪", "Taipei Times"]
    
    print(f"[{get_now()}] >>> 自動報社開始上班 <<<")
    for idx, channel in enumerate(CHANNELS):
        print(f"\n[{get_now()}] --- 處理進度 {idx+1}/13: [{channel['region']}] [{channel['category']}] ---")
        
        require_taiwan = not has_taiwan_media
        
        real_news = fetch_real_news_from_rss(channel, used_media, require_taiwan)
        if not real_news: continue
        
        article = generate_article_with_ai(channel, real_news, today_str)
        if article:
            final_news_list.append(article)
            consecutive_fails = 0
            
            used_media.add(real_news['source'])
            if any(tw_m in real_news['source'] for tw_m in taiwan_media_names):
                has_taiwan_media = True
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
