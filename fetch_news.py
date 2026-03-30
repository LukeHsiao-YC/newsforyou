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

# 步驟一：先從 Google News 抓取真實的新聞標題與網址
def fetch_real_news_from_rss(query):
    encoded_query = urllib.parse.quote(f"{query} when:7d")
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    print(f"[{get_now()}] 準備抓取 RSS: {query}")
    try:
        response = requests.get(rss_url, timeout=10)
        # 過濾掉 XML 不允許的奇怪控制字元，避免解析崩潰
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

# 步驟二：請 AI 根據真實標題寫作
def generate_article_with_ai(channel_info, real_news, today_date):
    prompt = f"""
    你現在是一位充滿熱情、語氣溫暖的青少年新聞編輯。
    今天我們要介紹一則真實新聞給國小高年級到國中生（10-15歲）閱讀。
    
    真實新聞標題：{real_news['title']}
    新聞分類：{channel_info['region']}的{channel_info['category']}
    
    請你根據這個新聞標題，撰寫一篇完整的教育新聞，並嚴格遵守以下要求：
    1. 中文內容 (zhContent)：文章長度絕對必須超過 500 字！(非常重要)。如果字數不夠，請補充：這件事發生的背景原因、相關的科學或歷史知識、或是對未來世界的影響。分成數個段落，客觀描述發生了什麼事。
    2. 寫作風格：你是一個真實的人類寫作者，溝通風格自然、溫暖。請不要使用 AI 慣用語（例如：深入探討、值得注意的是、賦能、一站式、全方位），絕對禁止使用破折號或 Em dash，也不要濫用 Emoji。請自己問自己：「一個真人會這樣寫嗎？」
    3. 深度思考小站 (scaffold)：請不要直接給答案，而是提供 3 個層次的「引導提示」。這 3 個提示分別是：
       - 提示一（觀察事實）：這件事發生了什麼關鍵改變？（約30字）
       - 提示二（生活連結）：這件事跟台灣的學生或家庭有什麼關聯？（約40字）
       - 提示三（行動提案）：為了這個議題，學生現在在生活中可以做到的一件具體小事？（約40字）
    4. 英文內容 (enContent)：請提供 basic, intermediate, advanced 三種難度的簡短英文摘要，並符合劍橋兒童英文 YLE Flyers 程度。
    5. 重點單字 (vocabulary)：挑選 2 個符合該新聞主題的英文單字並附上中文。
    6. 圖片關鍵字 (imageKeyword)：給一個具體的英文單字名詞，例如 rocket, forest, city, train，用來自動配圖。
    
    回傳格式必須是 JSON 物件（不需要 markdown 標籤）：
    {{
      "zhTitle": "吸引人的標題",
      "zhSummary": "50字的客觀摘要",
      "zhContent": "<p>第一段...</p><p>第二段...</p><p>第三段...</p><p>第四段...</p>",
      "scaffold": ["提示一的內容", "提示二的內容", "提示三的內容"],
      "enTitle": "English Title",
      "enContent": {{
          "basic": "...",
          "intermediate": "...",
          "advanced": "..."
      }},
      "vocabulary": [
          {{"word": "apple", "zh": "蘋果"}},
          {{"word": "world", "zh": "世界"}}
      ],
      "imageKeyword": "word"
    }}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    headers = {"Content-Type": "application/json"}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"[{get_now()}] 正在向 Gemini API 發送請求 (嘗試 {attempt+1}/{max_retries})...")
            # timeout 設為 45 秒，避免無限期卡死
            response = requests.post(API_URL, headers=headers, json=payload, timeout=45)
            
            if response.status_code == 429:
                print(f"[{get_now()}] 被 Google 擋下來了 (429 Error)，休息 30 秒後重試...")
                time.sleep(30)
                continue
                
            response.raise_for_status()
            print(f"[{get_now()}] API 回應成功！正在解析內容...")
            result = response.json()
            
            text_content = result['candidates'][0]['content']['parts'][0]['text']
            article_data = json.loads(text_content.strip())
            
            # 組合資料
            article_data["id"] = channel_info["id"]
            article_data["type"] = channel_info["type"]
            article_data["category"] = channel_info["category"]
            article_data["tagClass"] = channel_info["tagClass"]
            article_data["region"] = channel_info["region"]
            article_data["date"] = today_date
            article_data["sourceName"] = real_news["source"]
            article_data["sourceLink"] = real_news["link"]
            article_data["isFeatured"] = False 
            
            # 產生圖片網址
            keyword = article_data.get("imageKeyword", "news")
            encoded_keyword = urllib.parse.quote(keyword)
            random_seed = random.randint(1, 99999)
            article_data["imageUrl"] = f"https://image.pollinations.ai/prompt/{encoded_keyword}?width=800&height=500&nologo=true&seed={random_seed}"
            
            return article_data
            
        except requests.exceptions.RequestException as e:
            if "429" in str(e):
                print(f"[{get_now()}] 遇到 429 錯誤，休息 30 秒後重試...")
                time.sleep(30)
                continue
            else:
                print(f"[{get_now()}] API 網路請求失敗: {e}")
                return None
        except Exception as e:
            print(f"[{get_now()}] AI 生成發生非預期錯誤: {e}")
            return None
            
    print(f"[{get_now()}] 重試 {max_retries} 次後仍然失敗，放棄此篇新聞。")
    return None

def update_daily_news():
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    final_news_list = []
    consecutive_fails = 0  
    
    print(f"[{get_now()}] ==========================================")
    print(f"[{get_now()}] 開始執行 {today_str} 的地球日報抓取任務")
    print(f"[{get_now()}] ==========================================")
    
    for idx, channel in enumerate(CHANNELS):
        print(f"\n[{get_now()}] ---> 開始處理第 {idx+1}/12 篇: [{channel['region']}] {channel['category']}")
        
        real_news = fetch_real_news_from_rss(channel["query"])
        if not real_news:
            print(f"[{get_now()}] 找不到適合的 RSS 新聞，跳過此頻道。")
            continue
            
        article = generate_article_with_ai(channel, real_news, today_str)
        if article:
            final_news_list.append(article)
            consecutive_fails = 0  
            print(f"[{get_now()}] 此篇 AI 撰寫完成！目前已累積 {len(final_news_list)} 篇成功文章。")
        else:
            consecutive_fails += 1
            print(f"[{get_now()}] 此篇生成失敗。目前累積連續失敗次數: {consecutive_fails}")
            
            if consecutive_fails >= 2:
                print(f"[{get_now()}] 🚨 連續失敗兩次，判斷 API 每日額度可能已耗盡，啟動緊急煞車，提早結束任務！")
                break
            
        print(f"[{get_now()}] 為了避免 API 限制，強制休息 20 秒...")
        time.sleep(20)
        
    print(f"\n[{get_now()}] ==========================================")
    if not final_news_list:
        print(f"[{get_now()}] 今天完全沒有產出任何資料，結束程式。")
        return
        
    for news in final_news_list:
        if news["type"] == "thematic":
            news["isFeatured"] = True
            break

    today_date = datetime.datetime.now().date()
    thirty_days_ago = today_date - datetime.timedelta(days=30)
    existing_news = []
    
    if os.path.exists('news.json'):
        with open('news.json', 'r', encoding='utf-8') as f:
            try:
                existing_news = json.load(f)
                print(f"[{get_now()}] 成功讀取現有的 news.json，共 {len(existing_news)} 筆舊資料。")
            except json.JSONDecodeError:
                print(f"[{get_now()}] 現有的 news.json 格式錯誤，將重新建立。")
                pass

    all_news = final_news_list + existing_news
    
    filtered_news = []
    seen_ids = set()
    
    for news in all_news:
        unique_id = f"{news.get('date')}-{news.get('id')}"
        news_date_str = news.get('date', '')
        
        if unique_id in seen_ids:
            continue
            
        try:
            news_date = datetime.datetime.strptime(news_date_str, '%Y-%m-%d').date()
            if news_date >= thirty_days_ago:
                filtered_news.append(news)
                seen_ids.add(unique_id)
        except ValueError:
            pass

    with open('news.json', 'w', encoding='utf-8') as f:
        json.dump(filtered_news, f, ensure_ascii=False, indent=2)
        
    print(f"[{get_now()}] 成功寫入資料庫！今日新增 {len(final_news_list)} 篇，共保留 {len(filtered_news)} 筆新聞。")
    print(f"[{get_now()}] 任務圓滿結束！")

if __name__ == "__main__":
    update_daily_news()
