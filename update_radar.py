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
    為避免遭 Yahoo 封鎖，若大量請求可考慮加上 sleep 或改用進階套件。
    """
    try:
        stock = yf.Ticker(ticker_symbol)
        
        # 1. 抓取當日報價與前日收盤以計算漲跌幅
        hist = stock.history(period="2d")
        if len(hist) < 2:
            return None, None
            
        prev_close = hist['Close'].iloc[0]
        curr_price = hist['Close'].iloc[1]
        
        if math.isnan(prev_close) or prev_close == 0:
            return None, None
            
        pct_change = ((curr_price - prev_close) / prev_close) * 100
        
        # 2. 抓取殖利率 (Trailing Annual Dividend Yield)
        info = stock.info
        yield_pct = info.get('trailingAnnualDividendYield', 0)
        if yield_pct is None:
            yield_pct = 0
        else:
            yield_pct = yield_pct * 100
            
        return round(pct_change, 2), round(yield_pct, 2)
        
    except Exception as e:
        print(f"Error fetching data for {ticker_symbol}: {e}")
        return None, None

def generate_html_tag(pct_change, yield_pct):
    """
    根據漲跌幅與殖利率生成帶有熱力色塊的 HTML 標籤。
    """
    if pct_change is None:
        return ""
        
    # 動能熱力顏色邏輯 (台灣習慣：紅漲綠跌。若為美股習慣可反轉)
    # 這裡採用台股慣例：漲 > 0 為紅色，跌 < 0 為綠色
    color = "#e74c3c" if pct_change > 0 else "#2ecc71" if pct_change < 0 else "#7f8c8d"
    sign = "▲" if pct_change > 0 else "▼" if pct_change < 0 else "-"
    
    # 組合字串，例如：[▲ 1.2% | 殖 2.5%]
    html_content = (
        f"<span style='font-size: 11px; color: {color}; margin-left: 4px; font-weight: bold;'>"
        f"[{sign} {abs(pct_change)}% | 殖 {yield_pct}%]"
        f"</span>"
    )
    return html_content

def main():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始更新 AI 量化總表...")
    
    # 讀取現有 HTML
    with open(HTML_FILE, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file.read(), 'html.parser')
        
    # 找出所有標註了 data-ticker 的空 span 容器
    data_containers = soup.find_all('span', class_='quant-data')
    total_tickers = len(data_containers)
    print(f"共找到 {total_tickers} 檔需要更新的個股...")
    
    for idx, container in enumerate(data_containers, 1):
        ticker = container.get('data-ticker')
        if not ticker:
            continue
            
        print(f"處理中 ({idx}/{total_tickers}): {ticker}...", end=" ")
        
        # 抓取資料
        pct, yld = get_quant_data(ticker)
        
        if pct is not None:
            # 將產生的 HTML 直接塞入原有的空 span 內
            container.clear()
            container.append(BeautifulSoup(generate_html_tag(pct, yld), 'html.parser'))
            print(f"完成 [漲幅: {pct}%, 殖利率: {yld}%]")
        else:
            print("資料獲取失敗，跳過。")
            
        # 禮貌性延遲，避免被 Yahoo 擋下 (Rule 12 - 防禦性設計)
        time.sleep(0.5)
        
    # 將更新後的 DOM 寫回檔案
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
        file.write(str(soup))
        
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 更新完畢，已覆寫至 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
