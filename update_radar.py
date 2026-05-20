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
    
    return (
        f"<span class='quant-data' style='font-size: 11px; color: {color}; margin-left: 4px; font-weight: bold;'>"
        f"[{sign} {abs(pct_change)}% | 殖 {yield_pct}%]"
        f"</span>"
    )

def main():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始更新 AI 量化總表...")
    
    with open(HTML_FILE, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file.read(), 'html.parser')
        
    a_tags = soup.find_all('a', class_=lambda c: c and 'ticker' in c.split())
    print(f"共找到 {len(a_tags)} 檔個股標籤，準備進行資料抓取與注入...")
    
    for idx, a_tag in enumerate(a_tags, 1):
        href = a_tag.get('href', '')
        
        print(f"處理中 ({idx}/{len(a_tags)})...", end=" ")
        pct, yld = None, None
        
        # Rule 3 & 12: 依賴 URL 動態解析並加入 Fallback 容錯機制
        if 'statementdog.com/analysis/' in href:
            code = href.split('/')[-1]
            
            # 1. 先嘗試上市 (.TW)
            pct, yld = get_quant_data(f"{code}.TW")
            
            # 2. 如果失敗，自動嘗試上櫃 (.TWO)
            if pct is None:
                pct, yld = get_quant_data(f"{code}.TWO")
                
        elif 'finance.yahoo.com/quote/' in href:
            code = href.split('/')[-1]
            pct, yld = get_quant_data(code)
            
        if pct is not None:
            new_span_soup = BeautifulSoup(generate_span_tag(pct, yld), 'html.parser').span
            next_sibling = a_tag.find_next_sibling()
            
            if next_sibling and next_sibling.name == 'span' and 'quant-data' in next_sibling.get('class', []):
                next_sibling.replace_with(new_span_soup)
            else:
                a_tag.insert_after(new_span_soup)
                
            print(f"成功 [漲幅: {pct}%, 殖利率: {yld}%]")
        else:
            print(f"失敗 (請檢查代碼是否正確或下市)。")
            
        time.sleep(0.5)
        
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
        file.write(str(soup))
        
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 更新完畢，已覆寫至 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
