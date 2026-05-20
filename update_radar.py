import yfinance as yf
from bs4 import BeautifulSoup
import time
import math

# ==========================================
# 參數與設定 (Simplicity First - Rule 2)
# ==========================================
HTML_FILE = "index.html"  # 您存放的 GitHub HTML 檔案名稱
OUTPUT_FILE = "index.html" # 覆寫回原檔案以供 GitHub Pages 渲染

def get_quant_data(ticker_symbol):
    """
    抓取單一股票的當日漲跌幅與近12個月殖利率 (Trailing Annual Dividend Yield)。
    """
    try:
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
            
        return round(pct_change, 2), round(yield_pct, 2)
        
    except Exception as e:
        return None, None

def generate_span_tag(pct_change, yield_pct):
    """
    根據漲跌幅與殖利率生成帶有熱力色塊的 HTML 標籤。
    """
    if pct_change is None:
        return ""
        
    # 動能熱力顏色邏輯 (漲 > 0 為紅色，跌 < 0 為綠色)
    color = "#e74c3c" if pct_change > 0 else "#2ecc71" if pct_change < 0 else "#7f8c8d"
    sign = "▲" if pct_change > 0 else "▼" if pct_change < 0 else "-"
    
    # 賦予 quant-data class，確保下次更新時可以定位替換
    return (
        f"<span class='quant-data' style='font-size: 11px; color: {color}; margin-left: 4px; font-weight: bold;'>"
        f"[{sign} {abs(pct_change)}% | 殖 {yield_pct}%]"
        f"</span>"
    )

def main():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始更新 AI 量化總表...")
    
    with open(HTML_FILE, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file.read(), 'html.parser')
        
    # 找出所有帶有 'ticker' class 的 <a> 標籤 (Rule 3: 依賴現有慣例)
    a_tags = soup.find_all('a', class_=lambda c: c and 'ticker' in c.split())
    print(f"共找到 {len(a_tags)} 檔個股標籤，準備進行資料抓取與注入...")
    
    for idx, a_tag in enumerate(a_tags, 1):
        href = a_tag.get('href', '')
        ticker = None
        
        # Rule 11: 依賴既有的 URL 結構動態解析代碼，不須修改 HTML
        if 'statementdog.com/analysis/' in href:
            code = href.split('/')[-1]
            ticker = f"{code}.TW"  # yfinance 台股需要加上 .TW
        elif 'finance.yahoo.com/quote/' in href:
            ticker = href.split('/')[-1]
            
        if not ticker:
            continue
            
        print(f"處理中 ({idx}/{len(a_tags)}): {ticker}...", end=" ")
        
        # 抓取資料
        pct, yld = get_quant_data(ticker)
        
        if pct is not None:
            # 生成新的 BeautifulSoup 標籤物件
            new_span_soup = BeautifulSoup(generate_span_tag(pct, yld), 'html.parser').span
            
            # 檢查 <a> 標籤的下一個相鄰節點是不是已經有 quant-data 了
            next_sibling = a_tag.find_next_sibling()
            if next_sibling and next_sibling.name == 'span' and 'quant-data' in next_sibling.get('class', []):
                # 已經有了就覆寫 (避免重複執行導致無限增長)
                next_sibling.replace_with(new_span_soup)
            else:
                # 第一次執行，安插在 <a> 的正後方
                a_tag.insert_after(new_span_soup)
                
            print(f"完成 [漲幅: {pct}%, 殖利率: {yld}%]")
        else:
            print("資料獲取失敗，跳過。")
            
        # 禮貌性延遲，避免遭 Yahoo API 阻擋
        time.sleep(0.5)
        
    # 寫回檔案
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
        file.write(str(soup))
        
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 更新完畢，已覆寫至 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
