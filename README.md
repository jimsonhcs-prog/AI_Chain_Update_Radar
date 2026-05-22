# AI 產業大聯盟與小聯盟量化數據總表系統

本專案為 2026 全球 AI 產業生態系十二大族群與大小聯盟數據總表的自動化量化更新系統。透過 Python 腳本動態解析網頁中的個股標籤，並結合 Yahoo Finance 進行價格與殖利率數據的即時更新。

## 檔案結構

*   `index.html`：系統展示網頁。包含十二大族群與大小聯盟個股的排版，以及用於搜尋、快篩（強勢股/風險股/大聯盟）與回到頂部功能的 JavaScript 互動邏輯。
*   `AI大聯盟II.py`：量化數據更新程式。負責解析網頁、下載最新價格、獲取股息資訊並將數據注入回網頁。
*   `台股清單.txt`：台股代碼對照表。用於判定個股為上市（.TW）或上櫃（.TWO）。
*   `ticker_cache.json`：股息與價格快取檔案。避免重複向 API 發送請求以防止觸發 Rate Limit 限制。

## 運作原理

1.  **載入上市櫃對照表**：讀取 `台股清單.txt`，建立台股代碼至交易市場後綴的對照字典。
2.  **解析現有 HTML 標籤**：讀取 `index.html`，尋找所有 class 包含 `ticker` 的 a 標籤。
3.  **批次下載最新股價**：將所有個股代號彙整後，使用 `yfinance` 進行單一批次請求，獲取前一日收盤價與最新價格，並計算漲跌幅。
4.  **安全回退機制 (Fallback)**：針對批次下載失敗的個股，自動啟動低頻率的單一補抓重試機制。
5.  **Lazy-load 股息更新**：
    *   優先自 `index.html` 內解析已存在的股息資訊並寫入本地快取 `ticker_cache.json`。
    *   若為全新加入的個股，則線上發送 `yf.Ticker` 請求取得股息，並更新快取。
6.  **動態注入數據**：計算最新殖利率後，生成包含價格、漲跌幅與殖利率的 `span.quant-data` 標籤，自動插入至對應 a 標籤的後方。
7.  **更新統計面板**：計算今日上漲、下跌、平盤以及強勢股（漲幅 >= 5%）的家數，並將統計結果與更新時間寫入網頁頂部的 Hero 面板。

## 環境安裝

本系統需要 Python 3.x 環境。請先安裝以下依賴套件：

```bash
pip install beautifulsoup4 yfinance bs4
```

## 執行更新

在專案目錄下執行以下指令即可自動更新 `index.html` 內的數據：

```bash
python AI大聯盟II.py
```

## 個股管理說明

### 1. 新增股票
若要在網頁中新增個股，僅需編輯 `index.html`，在對應族群大聯盟或小聯盟的 `<div class="tickers-wrap">` 或 `<div class="league-block">` 內插入 a 標籤。格式如下：

*   **台股格式**：
    ```html
    <a class="ticker" href="https://statementdog.com/analysis/個股代號" target="_blank">個股名稱 (個股代號)</a>
    ```
*   **美股/日股格式**：
    ```html
    <a class="global-ticker" href="https://finance.yahoo.com/quote/Ticker代號" target="_blank">個股名稱 (Ticker代號)</a>
    ```

*註：新增後不需手動填寫股價或殖利率數據。直接執行 `AI大聯盟II.py` 程式，系統將會自動抓取並在 a 標籤後方補齊數據標籤。*

### 2. 移除股票
若要移除個股，請將對應的 a 標籤及其後方的 `<span class="quant-data">` 標籤一併刪除，然後執行更新程式以重新計算頂部統計數據。
