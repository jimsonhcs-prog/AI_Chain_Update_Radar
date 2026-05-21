import yfinance as yf
from bs4 import BeautifulSoup
import time
import math

# ==========================================
# 參數與設定
# ==========================================
HTML_FILE = "index.html"
OUTPUT_FILE = "index.html"


def get_quant_data(ticker_symbol):
    """
    抓取單一股票的當日漲跌幅、近12個月殖利率與當前股價。
    回傳: (pct_change, yield_pct, price) 或 (None, None, None)
    """
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="2d")

        if len(hist) < 2:
            return None, None, None

        prev_close = hist['Close'].iloc[0]
        curr_price = hist['Close'].iloc[1]

        if math.isnan(prev_close) or prev_close == 0:
            return None, None, None

        pct_change = ((curr_price - prev_close) / prev_close) * 100

        info = stock.info
        yield_val = info.get('trailingAnnualDividendYield', 0)
        yield_pct = (yield_val * 100) if yield_val else 0

        return round(pct_change, 2), round(yield_pct, 2), round(curr_price, 2)

    except Exception as e:
        print(f"[ERROR] {ticker_symbol}: {e}")
        return None, None, None


def generate_span_tag(pct_change, yield_pct, price):
    """
    依據漲跌幅強度生成「決策標籤」注入 HTML。
    修正：price 現在正確作為參數傳入；signal_label 也正確顯示。
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
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始更新 AI 量化總表...")

    with open(HTML_FILE, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file.read(), 'html.parser')

    a_tags = soup.find_all('a', class_=lambda c: c and 'ticker' in c.split())
    print(f"共找到 {len(a_tags)} 檔個股標籤，準備進行資料抓取與注入...")

    total_count = len(a_tags)
    up_count = 0
    down_count = 0
    strong_count = 0

    for idx, a_tag in enumerate(a_tags, 1):
        href = a_tag.get('href', '')

        print(f"處理中 ({idx}/{len(a_tags)})...", end=" ")
        pct, yld, price = None, None, None

        if 'statementdog.com/analysis/' in href:
            code = href.rstrip('/').split('/')[-1]

            # 1. 先嘗試上市 (.TW)
            pct, yld, price = get_quant_data(f"{code}.TW")

            # 2. Fallback：自動嘗試上櫃 (.TWO)
            # 修正：fallback 也要解包三個值
            if pct is None:
                pct, yld, price = get_quant_data(f"{code}.TWO")

        elif 'finance.yahoo.com/quote/' in href:
            code = href.rstrip('/').split('/')[-1]
            pct, yld, price = get_quant_data(code)

        if pct is not None:
            if pct > 0:
                up_count += 1
                if pct >= 5.0:
                    strong_count += 1
            elif pct < 0:
                down_count += 1

            # 修正：正確傳入三個參數
            new_span_html = generate_span_tag(pct, yld, price)
            new_span_soup = BeautifulSoup(new_span_html, 'html.parser').span

            next_sibling = a_tag.find_next_sibling()
            if next_sibling and next_sibling.name == 'span' and \
               'quant-data' in next_sibling.get('class', []):
                next_sibling.replace_with(new_span_soup)
            else:
                a_tag.insert_after(new_span_soup)

            print(f"成功 [{a_tag.text.strip()}] 漲幅:{pct:+.2f}% 殖:{yld:.2f}% 價:{price}")
        else:
            print(f"失敗 [{a_tag.text.strip()}] (代碼錯誤或已下市)")

        time.sleep(0.5)

    # ==========================================
    # 動態注入 Hero 數據儀表板
    # ==========================================
    neutral_count = total_count - up_count - down_count
    hero_html = f"""
    <div class="hero-stats" style="display: flex; gap: 16px; margin-top: 16px; margin-bottom: 16px; font-size: 14px; font-weight: 600; flex-wrap: wrap;">
        <span style="background: #334155; padding: 6px 12px; border-radius: 6px; color: #f8fafc; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">📡 監測雷達: {total_count} 檔</span>
        <span style="background: #fee2e2; padding: 6px 12px; border-radius: 6px; color: #991b1b; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">🔥 今日上漲: {up_count} 家 (強勢 &gt;5%: {strong_count} 家)</span>
        <span style="background: #dcfce7; padding: 6px 12px; border-radius: 6px; color: #166534; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">🧊 今日下跌: {down_count} 家</span>
        <span style="background: #f1f5f9; padding: 6px 12px; border-radius: 6px; color: #475569; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">⏱ 更新時間: {time.strftime('%Y-%m-%d %H:%M')}</span>
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

    print(f"\n{'='*50}")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 更新完畢！")
    print(f"  總監測: {total_count} 檔 | 上漲: {up_count} | 下跌: {down_count} | 平盤: {neutral_count}")
    print(f"  強勢 (≥5%): {strong_count} 檔 | 風險 (≤-3%): {total_count - up_count - down_count} 檔")
    print(f"  已覆寫至 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
