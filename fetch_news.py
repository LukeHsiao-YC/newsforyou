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

# 定義 13 個新聞頻道 (新增趣味溫馨)
CHANNELS = [
    {"id": "t-1", "type": "thematic", "category": "政治經濟", "tagClass": "tag-polecon", "region": "全球", "query": "國際 政治 經濟"},
    {"id": "t-2", "type": "thematic", "category": "自然生態", "tagClass": "tag-nature", "region": "全球", "query": "國際 自然 環境 生態"},
    {"id": "t-3", "type": "thematic", "category": "人文流行", "tagClass": "tag-human", "region": "全球", "query": "國際 文化 藝術 流行"},
    {"id": "t-4", "type": "thematic", "category": "科技探索", "tagClass": "tag-tech", "region": "全球", "query": "國際 科技 AI 太空"},
    {"id": "t-5", "type": "thematic", "category": "趣味溫馨", "tagClass": "tag-fun", "region": "全球", "query": "國際 趣味 溫馨 奇聞 感人"},
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
    # 強制將我們信賴的媒體加入搜尋條件，提高命中率
    media_query = " (中央社 OR 公視 OR 報導者 OR 天下雜誌 OR 轉角國際 OR 敏迪 OR BBC OR 路透 OR 德國之聲 OR NHK)"
    encoded_query = urllib.parse.quote(f"{query}{media_query} when:7d")
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    print(f"[{get_now()}] 準備抓取 RSS: {query}")
    try:
        response = requests.get(rss_url, timeout=10)
        xml_content = response.content.decode('utf-8', errors='ignore')
        xml_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', xml_content)
        root = ET.fromstring(xml_content)
        items = root.findall('.//channel/item')
        
        # 定義優質媒體白名單
        preferred_media = ["BBC", "路透", "美聯社", "德國之聲", "半島", "CNBC", "NHK", "經濟學人", "日經", "NPR", "Taipei Times", "報導者", "中央社", "公視", "轉角國際", "敏迪", "天下雜誌"]
        # 定義黑名單
        blocked_media = ["大紀元", "新唐人", "香港", "星島", "文匯", "中評", "搜狐", "網易"]
        
        selected_item = None
        
        # 1. 優先尋找白名單內的媒體
        for item in items:
            source_elem = item.find('source')
            source_name = source_elem.text if source_elem is not None else ""
            if any(blocked in source_name for blocked in blocked_media):
                continue
            if any(pref in source_name for pref in preferred_media):
                selected_item = item
                break
                
        # 2. 如果找不到白名單，就找任何一個非黑名單的媒體
        if not selected_item:
            for item in items:
                source_elem = item.find('source')
                source_name = source_elem.text if source_elem is not None else ""
                if not any(blocked in source_name for blocked in blocked_media):
                    selected_item = item
                    break

        if selected_item is not None:
            title = selected_item.find('title').text
            link = selected_item.find('link').text
            source = selected_item.find('source').text if selected_item.find('source') is not None else "國際媒體"
            print(f"[{get_now()}] 成功鎖定真實新聞: {title} ({source})")
            return {"title": title, "link": link, "source": source}
            
    except Exception as e:
        print(f"[{get_now()}] 抓取 RSS 失敗: {e}")
    return None

def generate_article_with_ai(channel_info, real_news, today_date):
    prompt = f"""
    你現在是一位青少年雜誌的真人專欄作家。
    請根據這則新聞：{real_news['title']}，撰寫一篇字數充實且具有教育意義的報導。
    
    【寫作風格與語氣】
    1. 真實忠誠：請盡量忠實呈現原文的新聞事件，不做過度誇飾，僅在語氣上進行改寫。
    2. 自然溫暖：溝通風格要自然、有個性，像個有智慧的真人專欄作家在對 10-15 歲的孩子說話，讓他們感覺像在閱讀優質雜誌。
    3. 拒絕流行語：絕對不要使用令人感到尷尬的時下流行用語（例如：高大上、yyds、絕絕子 等）。
    4. 封殺 AI 詞彙：絕對禁止使用 AI 慣用語，包含但不限於：「深入探討」、「值得注意的是」、「賦能」、「一站式」、「全方位」。
    5. 格式限制：寫作前請先在腦中掃描，絕對禁止使用 Em dash 以及濫用 Emoji。
    6. 最後檢查：請自己問自己：「一個真實的人類作家會這樣寫嗎？」

    【重要：字數與單字規定】
    1. 中文報導 (zhContent)：字數請嚴格控制在 500 到 800 個中文字之間。分成 4 到 5 個 <p> 段落。
    2. 英文單字 (vocabulary)：請挑選 2 個。
       - "word" 欄位：必須、絕對、只能填寫『英文單字』。
       - "zh" 欄位：填寫該單字的中文翻譯與適合孩子理解的解釋。
    3. 圖片指令 (imagePrompt)：請用英文寫一段這篇新聞的視覺描述（例如：'A futuristic solar farm in a lush tropical forest under a bright sun'）。

    【JSON 格式要求】
    回傳標準 JSON 物件，不要帶 Markdown 標記：
    {{
      "zhTitle": "吸引人的大標題",
      "zhSummary": "簡單摘要這則新聞的重點",
      "zhContent": "<p>第一段描述背景...</p><p>第二段深入解釋原理...</p><p>第三段對生活的影響...</p><p>第四段引導思考...</p>",
      "scaffold": ["觀察提示：這則新聞中...？", "生活提示：如果在台灣...？", "提案提示：我們可以用什麼小動作...？"],
      "enTitle": "English Title of the Story",
      "enContent": {{ "basic": "...", "intermediate": "...", "advanced": "..." }},
      "vocabulary": [ 
          {{ "word": "English_Word_1", "zh": "中文意思與簡單生活化的解釋" }}, 
          {{ "word": "English_Word_2", "zh": "中文意思與簡單生活化的解釋" }} 
      ],
      "imagePrompt": "A unique English descriptive sentence for AI image generation"
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
            
            raw_img_prompt = article_data.get("imagePrompt", "Global scenery")
            en_title = article_data.get("enTitle", "")
            unique_img_prompt = f"{raw_img_prompt} inspired by {en_title}"
            random_seed = random.randint(1, 999999)
            article_data["imageUrl"] = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(unique_img_prompt)}?width=800&height=500&nologo=true&seed={random_seed}"
            
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
                print(f"[{get_now()}] 🚨 連續兩篇失敗，可能額度用光，緊急煞車！")
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
