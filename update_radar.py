import os
import time
import math
import json
import re
import concurrent.futures
import yfinance as yf
from bs4 import BeautifulSoup

# ==========================================
# 參數與設定
# ==========================================
HTML_FILE = "index.html"
OUTPUT_FILE = "index.html"
CACHE_FILE = "ticker_cache.json"
MARKET_TXT = "台股清單.txt"


def load_market_map(txt_path=MARKET_TXT):
    """
    解析台股清單.txt，建立台股代碼到上市/上櫃 (.TW/.TWO) 的精確對照字典。
    """
    market_map = {}
    if not os.path.exists(txt_path):
        print(f"[WARNING] 找不到台股清單檔案: {txt_path}，將預設為上市 (.TW)")
        return market_map

    pattern = re.compile(r"'\s*(\d{4,})\s*'\s*:\s*'.*?'\s*,\s*#\s*\[(上市|上櫃)\]")
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        matches = pattern.findall(content)
        for code, market in matches:
            market_map[code] = f"{code}.TW" if market == "上市" else f"{code}.TWO"
        print(f"成功解析 {len(market_map)} 檔台股上市櫃對照表。")
    except Exception as e:
        print(f"[WARNING] 解析台股清單時出錯: {e}")
    return market_map


def parse_html_for_dividends(soup, market_map, cache_path=CACHE_FILE):
    """
    從現有的 HTML 網頁中解析 quant-data 標籤，提取已有的殖利率與股價，
    並計算出每股配息金額 (dividend_rate) 寫入本地快取。
    """
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception:
            pass

    a_tags = soup.find_all('a', class_=lambda c: c and 'ticker' in c.split())
    span_pattern = re.compile(r"\[\$?([\d\.]+)\s*\|\s*([▲▼\-]?\s*[\d\.]+)%\s*\|\s*殖\s*([\d\.]+)%\]")
    
    updated_cache = False
    for tag in a_tags:
        href = tag.get('href', '')
        resolved_ticker = None
        
        if 'statementdog.com/analysis/' in href:
            code = href.rstrip('/').split('/')[-1]
            resolved_ticker = market_map.get(code, f"{code}.TW")
        elif 'finance.yahoo.com/quote/' in href:
            resolved_ticker = href.rstrip('/').split('/')[-1]

        if not resolved_ticker:
            continue

        # 若 cache 中此 ticker 的格式不是 dict，則將其重置
        ticker_entry = cache.get(resolved_ticker)
        if not isinstance(ticker_entry, dict):
            ticker_entry = {}
            cache[resolved_ticker] = ticker_entry

        # 若 cache 中還沒有此 ticker 的股息資訊，則從 HTML 解析
        if ticker_entry.get('dividend_rate') is None:
            span = tag.find_next_sibling('span', class_='quant-data')
            if span:
                match = span_pattern.search(span.text)
                if match:
                    try:
                        price = float(match.group(1))
                        yield_pct = float(match.group(3))
                        # 股息 = 股價 * 殖利率 / 100
                        div_rate = round((price * yield_pct / 100.0), 4)
                        cache[resolved_ticker] = {
                            "dividend_rate": div_rate,
                            "last_price": price,
                            "yield_pct": yield_pct
                        }
                        updated_cache = True
                    except Exception:
                        pass

    if updated_cache:
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            print(f"已從 HTML 提取股息資訊並儲存至 {cache_path}。")
        except Exception as e:
            print(f"[WARNING] 寫入快取檔案失敗: {e}")
            
    return cache


def get_new_ticker_dividend(ticker, cache, cache_path=CACHE_FILE):
    """
    針對全新加入且無快取的個股，發送一次線上 Ticker.info 請求獲取股息，並寫入快取中。
    為了避免被封鎖，每次請求後會延遲 1 秒。
    """
    ticker_entry = cache.get(ticker)
    if isinstance(ticker_entry, dict) and ticker_entry.get('dividend_rate') is not None:
        return ticker_entry['dividend_rate']

    try:
        print(f"-> 線上獲取新個股 {ticker} 股息資訊中...")
        stock = yf.Ticker(ticker)
        info = stock.info
        yield_val = info.get('trailingAnnualDividendYield', 0.0)
        if not yield_val:
            yield_val = info.get('dividendYield', 0.0)
            
        price = info.get('previousClose') or info.get('regularMarketPreviousClose') or 1.0
        div_rate = round(yield_val * price, 4) if yield_val else 0.0
        
        cache[ticker] = {
            "dividend_rate": div_rate,
            "last_price": price,
            "yield_pct": round(yield_val * 100, 2)
        }
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
            
        time.sleep(1.0)  # 安全間隔
        return div_rate
    except Exception as e:
        print(f"[WARNING] 線上獲取 {ticker} 股息失敗 (設為 0.0): {e}")
        return 0.0


def download_single_ticker_fallback(ticker):
    """
    當 yf.download 批次下載失敗或缺失時的安全單一補抓回退函數。
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2d")
        if len(hist) >= 2:
            prev_close = hist['Close'].iloc[-2]
            curr_price = hist['Close'].iloc[-1]
            return ticker, prev_close, curr_price
        elif len(hist) == 1:
            curr_price = hist['Close'].iloc[0]
            return ticker, curr_price, curr_price
    except Exception:
        pass
    return ticker, None, None


def generate_span_tag(price, pct_change, yield_pct):
    """
    依據漲跌幅強度生成「決策標籤」注入 HTML。
    """
    if pct_change is None or price is None:
        return ""

    # 訊號強度標籤
    signal_label = ""
    if pct_change >= 5.0:
        signal_label = " 🔥 HOT"
    elif pct_change <= -3.0:
        signal_label = " ⚠️ RISK"

    # 動能方向顏色與符號
    color = "#e74c3c" if pct_change > 0 else "#2ecc71" if pct_change < 0 else "#7f8c8d"
    sign = "▲" if pct_change > 0 else "▼" if pct_change < 0 else "-"

    return (
        f"<span class='quant-data' style='font-size: 11px; color: {color}; "
        f"margin-left: 4px; font-weight: bold;'>"
        f"[${price} | {sign} {abs(pct_change)}% | 殖 {yield_pct}%]{signal_label}"
        f"</span>"
    )


def main():
    start_time = time.time()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始更新 AI 量化總表...")

    if not os.path.exists(HTML_FILE):
        print(f"[ERROR] 找不到 HTML 檔案: {HTML_FILE}")
        return

    with open(HTML_FILE, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file.read(), 'html.parser')

    # 1. 載入台股清單對照字典
    market_map = load_market_map(MARKET_TXT)

    # 2. 從 HTML 解析已有股息資訊並建立快取
    dividend_cache = parse_html_for_dividends(soup, market_map, CACHE_FILE)

    # 3. 收集所有 Ticker，並建立 Ticker 與 a 標籤的映射
    a_tags = soup.find_all('a', class_=lambda c: c and 'ticker' in c.split())
    ticker_to_tags = {}
    all_tickers = set()

    for tag in a_tags:
        href = tag.get('href', '')
        resolved_ticker = None
        if 'statementdog.com/analysis/' in href:
            code = href.rstrip('/').split('/')[-1]
            resolved_ticker = market_map.get(code, f"{code}.TW")
        elif 'finance.yahoo.com/quote/' in href:
            resolved_ticker = href.rstrip('/').split('/')[-1]

        if resolved_ticker:
            all_tickers.add(resolved_ticker)
            if resolved_ticker not in ticker_to_tags:
                ticker_to_tags[resolved_ticker] = []
            ticker_to_tags[resolved_ticker].append(tag)

    all_tickers_list = list(all_tickers)
    print(f"共解析出 {len(all_tickers_list)} 檔不重複個股標籤。")

    # 4. 批次下載價格數據 (單一請求)
    print("正在透過單一批次請求下載所有價格數據...")
    price_data = {}
    try:
        # 使用 group_by='ticker' 來一次下載所有 Tickers
        batch_df = yf.download(all_tickers_list, period="2d", group_by='ticker', progress=False)
        
        # 提取資料
        for ticker in all_tickers_list:
            try:
                # 判斷是單一 Ticker 還是 MultiIndex DataFrame
                if len(all_tickers_list) == 1:
                    df = batch_df
                else:
                    df = batch_df[ticker]
                
                df = df.dropna(subset=['Close'])
                if len(df) >= 2:
                    prev_close = df['Close'].iloc[-2]
                    curr_price = df['Close'].iloc[-1]
                    price_data[ticker] = (prev_close, curr_price)
                elif len(df) == 1:
                    curr_price = df['Close'].iloc[0]
                    price_data[ticker] = (curr_price, curr_price)
            except Exception:
                pass
    except Exception as e:
        print(f"[WARNING] 批次下載出錯，將啟動 Fallback 回退機制: {e}")

    # 5. 針對下載失敗或缺失的個股，啟動 Fallback 單一補抓重試
    missing_tickers = [t for t in all_tickers_list if t not in price_data]
    if missing_tickers:
        print(f"共有 {len(missing_tickers)} 檔個股價格缺失，啟動低頻率安全回退重試...")
        # 限制 concurrent 數為 3，並且帶有 delay，絕對不觸發 Rate Limit
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(download_single_ticker_fallback, t): t for t in missing_tickers}
            for future in concurrent.futures.as_completed(futures):
                ticker = futures[future]
                try:
                    t, prev_close, curr_price = future.result()
                    if curr_price is not None:
                        price_data[t] = (prev_close, curr_price)
                        print(f"  [RETRY SUCCESS] {t}")
                    else:
                        print(f"  [RETRY FAILED] {t}")
                except Exception as e:
                    print(f"  [RETRY ERROR] {ticker}: {e}")
                time.sleep(0.5)  # 每次補抓間隔 0.5 秒

    # 6. 計算與更新 HTML 標籤
    up_count = 0
    down_count = 0
    strong_count = 0
    success_count = 0

    for ticker, (prev_close, curr_price) in price_data.items():
        if curr_price is None or math.isnan(curr_price):
            continue

        # 計算漲跌幅
        if prev_close is not None and not math.isnan(prev_close) and prev_close != 0:
            pct_change = round(((curr_price - prev_close) / prev_close) * 100, 2)
        else:
            pct_change = 0.0

        # 獲取或更新該個股股利資訊 (Lazy-load 快取)
        div_rate = get_new_ticker_dividend(ticker, dividend_cache, CACHE_FILE)
        
        # 計算殖利率 = 股利 / 最新股價 * 100
        yield_pct = round((div_rate / curr_price) * 100, 2) if div_rate else 0.0

        success_count += 1
        if pct_change > 0:
            up_count += 1
            if pct_change >= 5.0:
                strong_count += 1
        elif pct_change < 0:
            down_count += 1

        # 產生並注入新 span
        price_val = round(curr_price, 2)
        new_span_html = generate_span_tag(price_val, pct_change, yield_pct)

        for tag in ticker_to_tags[ticker]:
            new_span_soup = BeautifulSoup(new_span_html, 'html.parser').span
            if new_span_soup:
                next_sibling = tag.find_next_sibling()
                if next_sibling and next_sibling.name == 'span' and \
                   'quant-data' in next_sibling.get('class', []):
                    next_sibling.replace_with(new_span_soup)
                else:
                    tag.insert_after(new_span_soup)

    # 7. 更新 Hero 數據面板
    neutral_count = success_count - up_count - down_count
    hero_html = f"""
  <div class="hero-stats">
    <div class="hero-stat-item hero-stat-total">
      <span>📡 監測雷達</span>
      <span class="stat-num">{success_count}</span>
      <span>檔</span>
    </div>
    <div class="hero-stat-item hero-stat-up">
      <span>🔥 上漲</span>
      <span class="stat-num">{up_count}</span>
      <span>家 &nbsp;|&nbsp; 強勢 &gt;5%</span>
      <span class="stat-num">{strong_count}</span>
      <span>家</span>
    </div>
    <div class="hero-stat-item hero-stat-down">
      <span>🧊 下跌</span>
      <span class="stat-num">{down_count}</span>
      <span>家</span>
    </div>
    <div class="hero-stat-item hero-stat-time">
      <span>⏱ 更新</span>
      <span class="stat-num">{time.strftime('%Y-%m-%d %H:%M')}</span>
    </div>
  </div>
    """
    hero_soup = BeautifulSoup(hero_html, 'html.parser')
    existing_hero = soup.find('div', class_='hero-stats')

    if existing_hero:
        existing_hero.replace_with(hero_soup)
    else:
        title_div = soup.find('div', class_='dashboard-title')
        if title_div:
            title_div.insert_after(hero_soup)

    # 8. 寫回檔案
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
        file.write(str(soup))

    elapsed_time = round(time.time() - start_time, 2)
    print(f"\n{'='*50}")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 更新完畢！總耗時: {elapsed_time} 秒")
    print(f"  總個股: {len(all_tickers_list)} 檔 | 成功: {success_count} | 失敗: {len(all_tickers_list) - success_count}")
    print(f"  今日上漲: {up_count} | 今日下跌: {down_count} | 平盤: {neutral_count}")
    print(f"  強勢 (>=5%): {strong_count} 檔")
    print(f"  數據已成功更新並寫入 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
