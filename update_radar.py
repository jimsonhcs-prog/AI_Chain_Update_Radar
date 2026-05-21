import yfinance as yf
from bs4 import BeautifulSoup
import time
import math

# ==========================================
# 參數與設定 (Simplicity First - Rule 2)
# ==========================================
HTML_FILE = "index.html"
OUTPUT_FILE = "index.html"

def get_quant_data(ticker_symbol):
    """
    抓取單一股票的當日漲跌幅與近12個月殖利率 (Trailing Annual Dividend Yield)。
    """
    try:
        # yfinance 內部若遇到 404 會自動印出警告，這是正常現象
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="2d")
        
        if len(hist) < 2:
            return None, None
            
        prev_close = hist['Close'].iloc[0]
        curr_price = hist['Close'].iloc[1]
        
        if math.isnan(prev_close) or prev_close == 0:
            return None, None
            
        pct_change = ((curr_price - prev_close) / prev_close) * 100
        
        info = stock.info
        yield_pct = info.get('trailingAnnualDividendYield', 0)
        yield_pct = yield_pct * 100 if yield_pct else 0
            
        return round(pct_change, 2), round(yield_pct, 2), round(curr_price, 2)
        
    except Exception as e:
        return None, None

def generate_span_tag(pct_change, yield_pct):
    """
    依據漲跌幅強度生成「決策標籤」注入 HTML。
    """
    if pct_change is None:
        return ""
        
    # 定義訊號強度標籤
    signal_label = ""
    if pct_change >= 5.0:
        signal_label = "🔥 HOT"
    elif pct_change <= -3.0:
        signal_label = "⚠️ RISK"
    
    # 動能熱力顏色邏輯
    color = "#e74c3c" if pct_change > 0 else "#2ecc71" if pct_change < 0 else "#7f8c8d"
    sign = "▲" if pct_change > 0 else "▼" if pct_change < 0 else "-"
    
    # 加入 signal_label 的 HTML 注入
    return (
        f"<span class='quant-data' style='font-size: 11px; color: {color}; margin-left: 4px; font-weight: bold;'>"
        f"[{price} | {sign} {abs(pct_change)}% | 殖 {yield_pct}%]"
        f"</span>"
    )
	
def main():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始更新 AI 量化總表...")
    
    with open(HTML_FILE, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file.read(), 'html.parser')
        
    a_tags = soup.find_all('a', class_=lambda c: c and 'ticker' in c.split())
    print(f"共找到 {len(a_tags)} 檔個股標籤，準備進行資料抓取與注入...")
    
    # --- 新增：Hero 統計數據計數器 ---
    total_count = len(a_tags)
    up_count = 0
    down_count = 0
    strong_count = 0
    # -------------------------------

    for idx, a_tag in enumerate(a_tags, 1):
        href = a_tag.get('href', '')
        
        print(f"處理中 ({idx}/{len(a_tags)})...", end=" ")
        pct, yld, price = None, None, None
        
        # Rule 3 & 12: 依賴 URL 動態解析並加入 Fallback 容錯機制
        if 'statementdog.com/analysis/' in href:
            code = href.split('/')[-1]
            
            # 1. 先嘗試上市 (.TW)
            pct, yld, price = get_quant_data(f"{code}.TW")
            
            # 2. 如果失敗，自動嘗試上櫃 (.TWO)
            if pct is None:
                pct, yld = get_quant_data(f"{code}.TWO")
                
        elif 'finance.yahoo.com/quote/' in href:
            code = href.split('/')[-1]
            pct, yld = get_quant_data(code)
            
        if pct is not None:
            # --- 新增：更新計數器 ---
            if pct > 0:
                up_count += 1
                if pct >= 5.0:  # 漲幅大於 5% 視為強勢動能
                    strong_count += 1
            elif pct < 0:
                down_count += 1
            # ------------------------

            new_span_soup = BeautifulSoup(generate_span_tag(pct, yld, price), 'html.parser').span
            next_sibling = a_tag.find_next_sibling()
            
            if next_sibling and next_sibling.name == 'span' and 'quant-data' in next_sibling.get('class', []):
                next_sibling.replace_with(new_span_soup)
            else:
                a_tag.insert_after(new_span_soup)
                
            print(f"成功 [漲幅: {pct}%, 殖利率: {yld}%]")
        else:
            print(f"失敗 (請檢查代碼是否正確或下市)。")
            
        time.sleep(0.5)
        
    # ==========================================
    # 新增：動態注入 Hero 數據儀表板 (Rule 4)
    # ==========================================
    hero_html = f"""
    <div class="hero-stats" style="display: flex; gap: 16px; margin-top: 16px; margin-bottom: 16px; font-size: 14px; font-weight: 600; flex-wrap: wrap;">
        <span style="background: #334155; padding: 6px 12px; border-radius: 6px; color: #f8fafc; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">📡 監測雷達: {total_count} 檔</span>
        <span style="background: #fee2e2; padding: 6px 12px; border-radius: 6px; color: #991b1b; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">🔥 今日上漲: {up_count} 家 (強勢 >5%: {strong_count} 家)</span>
        <span style="background: #dcfce7; padding: 6px 12px; border-radius: 6px; color: #166534; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">🧊 今日下跌: {down_count} 家</span>
        <span style="background: #f1f5f9; padding: 6px 12px; border-radius: 6px; color: #475569; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">⏱ 更新時間: {time.strftime('%Y-%m-%d %H:%M')}</span>
    </div>
    """
    hero_soup = BeautifulSoup(hero_html, 'html.parser')
    existing_hero = soup.find('div', class_='hero-stats')
    
    # 尋找插入點 (替換舊的或插入標題後方)
    if existing_hero:
        existing_hero.replace_with(hero_soup)
    else:
        title_div = soup.find('div', class_='dashboard-title')
        if title_div:
            title_div.insert_after(hero_soup)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
        file.write(str(soup))
        
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 更新完畢，已覆寫至 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
