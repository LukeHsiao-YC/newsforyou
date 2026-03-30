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
    
    # 如果系統要求必須抓取台灣媒體，就切換為繁體中文搜尋模式
    if require_taiwan:
        preferred_media = taiwan_media_names
        hl, gl, ceid = "zh-TW", "TW", "TW:zh-Hant"
        search_query = f"{region} 國際 新聞" if region != "全球" else "國際 重大 新聞"
    # 根據不同區域，給予專屬的國際外媒名單
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
        # 順便把台灣媒體放進白名單，如果有英文版剛好被搜到也能用
        preferred_media.extend(taiwan_media_names)
        hl, gl, ceid = "en-US", "US", "US:en"
        search_query = query
    
    # 過濾掉歐美常見的八卦小報或內容農場
    blocked_query = " -\"Daily Mail\" -\"The Sun\" -\"New York Post\" -\"Fox News\" -大紀元 -新唐人 -香港 -星島 -文匯 -中評 -搜狐 -網易 -每日頭條"
    blocked_media = ["Daily Mail", "The Sun", "New York Post", "Fox News", "Breitbart", "大紀元", "新唐人", "香港", "星島", "文匯", "中評", "搜狐", "網易", "每日頭條"]
    
    # 漸進式撒網：先找最近 2 天，沒有再找 5 天，最後找 14 天
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
                
                # 碰到黑名單直接跳過
                if any(blocked in source_name for blocked in blocked_media):
                    continue
                
                # 收集符合白名單的國際新聞
                if any(pref in source_name for pref in preferred_media):
                    title = item.find('title').text
                    link = item.find('link').text
                    valid_news.append({"title": title, "link": link, "source": source_name})
            
            if valid_news:
                # 優先挑選今天「還沒出場過」的媒體，確保多樣性
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
    1. 聚焦新聞本體：文章請將 80% 以上的篇幅放在「這則新聞到底發生了什麼事」，詳細把事件的起因、經過、結果說清楚，讓孩子能完整吸收客觀資訊。
    2. 刪除說教結語：絕對不要在文章最後寫出「我們應該要怎麼做」、「這告訴我們什麼道理」等呼籲或反思結語。請保持客觀，把思考的空間留給額外的提問即可。
    3. 理解世界：在敘述新聞時，遇到艱澀概念可以用生活化的比喻，清晰解釋這件國際大事為何發生。
    4. 連結與影響：平鋪直敘地客觀說明這件事對未來社會可能造成的影響，或是與台灣的關聯。

    【寫作風格與語氣】
    1. 真實忠誠：請盡量忠實呈現外媒報導的事件，不做過度誇飾，僅在語氣上進行改寫。
    2. 自然溫暖：溝通風格要自然、有個性，像個有智慧的大哥哥大姊姊在分享故事，讓他們感覺像在閱讀優質雜誌。
    3. 拒絕流行語：絕對不要使用令人感到尷尬的時下流行用語（例如：高大上、yyds、絕絕子 等）。
    4. 封殺機器詞彙：絕對禁止使用機器感重詞彙，包含但不限於：深入探討、值得注意的是、賦能、一站式、全方位 等。
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
      "zhContent": "<p>第一段：用吸引人的方式帶出新聞事件的主題...</p><p>第二段：詳細描述新聞事件的經過與細節...</p><p>第三段：補充事件背後的原因或相關背景知識...</p><p>第四段：客觀說明這個事件目前的結果或對未來的實際影響（切勿說教）...</p>",
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

def test_single_ai_generation():
    """單篇 AI 寫作測試模式：只抓一篇新聞讓 AI 寫，印出結果不存檔，用來測試寫作風格"""
    print(f"[{get_now()}] >>> 啟動單篇 AI 寫作測試模式 <<<")
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    used_media = set()
    
    # 隨機挑一個頻道來測試，這裡我讓它挑全球政治經濟或隨機一個
    channel = random.choice(CHANNELS)
    print(f"[{get_now()}] 準備測試的頻道: [{channel['region']}] [{channel['category']}]")
    
    real_news = fetch_real_news_from_rss(channel, used_media, require_taiwan=False)
    if not real_news:
        print(f"[{get_now()}] 找不到新聞可以測試，請稍後再試。")
        return
        
    print(f"[{get_now()}] 已經鎖定新聞，交給專欄作家 AI 中...")
    article = generate_article_with_ai(channel, real_news, today_str)
    
    if article:
        print(f"\n{'='*50}")
        print(f"[{get_now()}] 寫作完成！以下是 AI 產出的排版結果：")
        print(f"{'='*50}\n")
        # 把寫出來的 JSON 排版印出來給你看
        print(json.dumps(article, ensure_ascii=False, indent=2))
        print(f"\n{'='*50}")
        print(f"[{get_now()}] 測試結束。請檢查上方內容是否符合你要的風格。")
    else:
        print(f"[{get_now()}] AI 寫作過程發生錯誤。")

def test_rss_search():
    """只抓取 RSS 不呼叫 AI 的測試模式"""
    print(f"[{get_now()}] >>> 啟動外媒 RSS 抓取測試模式（不呼叫 AI） <<<")
    success_count = 0
    used_media = set()
    has_taiwan_media = False
    taiwan_media_names = ["中央社", "公視", "報導者", "少年報導者", "天下雜誌", "轉角國際", "敏迪", "Taipei Times"]
    
    for idx, channel in enumerate(CHANNELS):
        print(f"\n[{get_now()}] --- 測試頻道 {idx+1}/13: [{channel['region']}] [{channel['category']}] ---")
        
        require_taiwan = not has_taiwan_media
        real_news = fetch_real_news_from_rss(channel, used_media, require_taiwan)
        
        if real_news:
            success_count += 1
            used_media.add(real_news['source'])
            if any(tw_m in real_news['source'] for tw_m in taiwan_media_names):
                has_taiwan_media = True
                
            print(f"  ✅ 成功找到新聞：{real_news['title']}")
            print(f"  來源：{real_news['source']}")
            print(f"  連結：{real_news['link']}")
        else:
            print(f"  ❌ 找不到符合條件的新聞。")
        time.sleep(2) 
    
    print(f"\n[{get_now()}] 測試結束。共設定 {len(CHANNELS)} 個頻道，成功找到 {success_count} 篇新聞。")

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
        
        # 只要還沒抓到台灣媒體，就強迫去抓
        require_taiwan = not has_taiwan_media
        
        real_news = fetch_real_news_from_rss(channel, used_media, require_taiwan)
        if not real_news: continue
        
        article = generate_article_with_ai(channel, real_news, today_str)
        if article:
            final_news_list.append(article)
            consecutive_fails = 0
            
            # 紀錄出場過的媒體與確認是否抓到台灣視角
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
    # 透過指令決定要執行哪一種模式
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            test_rss_search()
        elif sys.argv[1] == 'test_ai':
            test_single_ai_generation()
        else:
            update_daily_news()
    else:
        update_daily_news()
