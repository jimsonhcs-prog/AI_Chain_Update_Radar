import os
import time
import math
import concurrent.futures
import yfinance as yf
from bs4 import BeautifulSoup

# ==========================================
# 參數與設定
# ==========================================
HTML_FILE = "AI大聯盟II.html"
OUTPUT_FILE = "AI大聯盟II.html"
MAX_WORKERS = 30  # 並行線程數，30 個 Thread 能在 10-15 秒內完成 235 檔個股抓取


def get_quant_data(ticker_symbol):
    """
    抓取單一股票的當日漲跌幅、近 12 個月殖利率與當前股價。
    回傳: (pct_change, yield_pct, price) 或 (None, None, None)
    """
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="2d")

        if len(hist) < 2:
            # 有可能只有 1 筆數據（例如剛開盤或剛上市），此時試圖取最後一筆
            if len(hist) == 1:
                curr_price = hist['Close'].iloc[0]
                if not math.isnan(curr_price):
                    info = stock.info
                    yield_val = info.get('trailingAnnualDividendYield', 0)
                    yield_pct = (yield_val * 100) if yield_val else 0.0
                    return 0.0, round(yield_pct, 2), round(curr_price, 2)
            return None, None, None

        prev_close = hist['Close'].iloc[-2]
        curr_price = hist['Close'].iloc[-1]

        if math.isnan(prev_close) or prev_close == 0 or math.isnan(curr_price):
            return None, None, None

        pct_change = ((curr_price - prev_close) / prev_close) * 100

        try:
            info = stock.info
            yield_val = info.get('trailingAnnualDividendYield', 0)
            yield_pct = (yield_val * 100) if yield_val else 0.0
        except Exception:
            yield_pct = 0.0

        return round(pct_change, 2), round(yield_pct, 2), round(curr_price, 2)

    except Exception:
        return None, None, None


def process_single_tag(a_tag):
    """
    處理單一 <a> 標籤，進行數據抓取與解析。
    回傳: (a_tag, pct, yld, price)
    """
    href = a_tag.get('href', '')
    pct, yld, price = None, None, None
    resolved_ticker = None

    if 'statementdog.com/analysis/' in href:
        code = href.rstrip('/').split('/')[-1]
        resolved_ticker = f"{code}.TW"
        # 1. 先嘗試上市 (.TW)
        pct, yld, price = get_quant_data(resolved_ticker)

        # 2. Fallback：自動嘗試上櫃 (.TWO)
        if pct is None:
            resolved_ticker = f"{code}.TWO"
            pct, yld, price = get_quant_data(resolved_ticker)

    elif 'finance.yahoo.com/quote/' in href:
        code = href.rstrip('/').split('/')[-1]
        resolved_ticker = code
        pct, yld, price = get_quant_data(resolved_ticker)

    return a_tag, pct, yld, price


def generate_span_tag(pct_change, yield_pct, price):
    """
    依據漲跌幅強度生成「決策標籤」注入 HTML。
    """
    if pct_change is None:
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

    price_str = f"${price} | " if price is not None else ""

    return (
        f"<span class='quant-data' style='font-size: 11px; color: {color}; "
        f"margin-left: 4px; font-weight: bold;'>"
        f"[{price_str}{sign} {abs(pct_change)}% | 殖 {yield_pct}%]{signal_label}"
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

    a_tags = soup.find_all('a', class_=lambda c: c and 'ticker' in c.split())
    total_count = len(a_tags)
    print(f"共找到 {total_count} 檔個股標籤，準備並行下載數據...")

    up_count = 0
    down_count = 0
    strong_count = 0
    success_count = 0

    # 使用 ThreadPoolExecutor 並行下載所有標籤數據
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_tag, tag): tag for tag in a_tags}
        for future in concurrent.futures.as_completed(futures):
            tag = futures[future]
            try:
                a_tag, pct, yld, price = future.result()
                results.append((a_tag, pct, yld, price))
                if pct is not None:
                    success_count += 1
                    ticker_text = a_tag.text.strip()
                    print(f"成功 [{ticker_text}] 漲幅:{pct:+.2f}% 殖:{yld:.2f}% 價:{price}")
                else:
                    print(f"失敗 [{a_tag.text.strip()}] (代碼錯誤或無數據)")
            except Exception as e:
                print(f"[ERROR] 處理標籤 {tag.text.strip()} 時出錯: {e}")

    # 將結果寫回 BeautifulSoup
    for a_tag, pct, yld, price in results:
        if pct is not None:
            if pct > 0:
                up_count += 1
                if pct >= 5.0:
                    strong_count += 1
            elif pct < 0:
                down_count += 1

            new_span_html = generate_span_tag(pct, yld, price)
            new_span_soup = BeautifulSoup(new_span_html, 'html.parser').span

            next_sibling = a_tag.find_next_sibling()
            if next_sibling and next_sibling.name == 'span' and \
               'quant-data' in next_sibling.get('class', []):
                next_sibling.replace_with(new_span_soup)
            else:
                a_tag.insert_after(new_span_soup)

    # ==========================================
    # 動態注入 Hero 數據儀表板
    # ==========================================
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

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as file:
        file.write(str(soup))

    elapsed_time = round(time.time() - start_time, 2)
    # 避免 Windows cp950 編碼問題，不使用 '≥' 字符
    print(f"\n{'='*50}")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 更新完畢！總耗時: {elapsed_time} 秒")
    print(f"  總監測: {total_count} 檔 | 成功: {success_count} | 失敗: {total_count - success_count}")
    print(f"  今日上漲: {up_count} | 今日下跌: {down_count} | 平盤: {neutral_count}")
    print(f"  強勢 (>=5%): {strong_count} 檔")
    print(f"  已覆寫至 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
