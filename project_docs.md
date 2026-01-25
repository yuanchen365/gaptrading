# 台股跳空強勢股即時監控系統 - 專案規格書 (v2.0)

## 1. 需求定義文件 (PRD - Product Requirement Document)

### 1.1 核心願景 (Vision)
建立一套自動化的台股即時監控系統，旨在幫助量化交易者在盤中即時捕捉「底部起漲」且「型態強勢」的標的。系統結合盤前數據分析與盤中即時行情，解決人工盯盤效率低落與無法覆蓋全市場的問題，並透過 LINE 即時推播確保不漏接訊號。

### 1.2 目標受眾
具備 Python 基礎的量化交易者，追求高勝率突破策略（S6 區間突破 + 低基期）。

### 1.3 核心功能需求
12: 1.  **盤前低基期篩選**：利用 FinLab 數據，鎖定全市場乖離率最低的後 60% 股票，確保進場點位於相對低檔 (安全邊際)。
2.  **盤中即時強勢跳空監控**：利用 Shioaji API 每 60 秒掃描一次，捕捉符合「嚴格缺口」定義的股票。
3.  **動態分區監控 UI**：
    *   **🔥 目前強勢區 (Active)**：即時顯示當下符合所有條件的標的。
    *   **👀 轉弱觀察區 (Watchlist)**：顯示曾經符合但目前暫時轉弱的標的，持續更新報價以便觀察反轉。
4.  **多因子特徵標記**：自動標記 P-Loc 特徵 (如 🔥S6_極強勢) 與乖離率數值。
5.  **即時通知**：透過 LINE Messaging API 推播訊號，單一標的當日僅通知一次，避免訊息轟炸。

---

## 2. 技術規劃文件 (TDD - Technical Design Document)

### 2.1 系統架構 (Architecture)
系統採用 **ETL (Extract, Transform, Load)** 與 **Real-time Event Loop** 混合架構。

*   **資料層 (Data Layer)**：
    *   **FinLab**: 負責歷史數據 (Open, High, Low, Close, MA60) 的抓取與計算。
    *   **Shioaji (Sinopac)**: 負責盤中即時 Snapshot (Snapshots) 的抓取。
    *   **CSV Storage**: `data/candidate_list.csv` 儲存盤前篩選結果 (含 `stock_code`, `bias`, `prev_high`)。

*   **應用層 (Application Layer)**：
    *   **Pre-processor (`pre_process.py`)**: 每日盤前執行，產出監控清單。
    *   **Streamlit App (`app.py`)**: 核心主程式 (Stateful)，維護 `triggered_history` 集合與 `Active/Watchlist` 雙表格邏輯。
    *   **Notification Service (`line_notifier.py`)**: 封裝 LINE Messaging API。

### 2.2 資料流 (Data Flow) - 盤中迴圈
1.  **Iterative Fetching (Chunking)**:
    *   系統將 1200+ 檔監控名單拆分為小批次 (每批 15 檔)。
    *   針對每批次呼叫 `api.snapshots`，若遇錯誤自動重試 (最多 3 次)。

2.  **Open-Gap Filter (開盤過濾) [✨核心機制]**:
    *   **檢查量能**: 若 `Volume > 0` (已開盤交易)。
    *   **檢查跳空**: 判斷 `Open > PrevHigh * 1.01`。
        *   **❌無跳空**: 立即從當日監控名單中**永久剔除**，不再查詢 (此機制能隨時間推進大幅降低系統負載)。
        *   **🟢有跳空**: 保留在名單中，進入下一步分析。
    *   **未開盤**: 若 `Volume == 0`，暫時保留等待開盤。

3.  **Active Check (強勢篩選)**: 針對保留下來的跳空股，進一步檢查：
    *   **P-Loc > 0.5**: 股價是否維持在當日強勢區間。
    *   **Gap Condition**: 確認低點是否守住缺口 (Low >= PrevHigh)。

4.  **Classify (分類與通知)**:
    *   **🔥Pass**: 加入 `Active List`。若為今日首次觸發，發送 LINE 通知並加入 `triggered_history`。
    *   **👀Watchlist**: 檢查是否在 `triggered_history` 中。若是，加入 `Watchlist`，標示為轉弱觀察。
    *   **Fail**: 檢查是否在 `triggered_history` 中。若是，加入 `Watchlist`，標示為轉弱觀察。
4.  **Display**: 更新 Streamlit 介面的上下兩個 DataFrame (Active / Watchlist)。
5.  **Loop**: 休眠短暫時間後 (如 60 秒) 重新開始下一輪掃描。

---

## 3. 規格驅動開發說明 (SDD - Specification Driven Development)

### 3.1 數學模型與參數

#### A. 基期篩選 (Bias Ranking)
*   **公式**: $Bias_{60} = \frac{Price_{close} - MA_{60}}{MA_{60}}$
*   **邏輯**: 取 $Bias$ 最小值 (最負) 的前 60% 股票。

#### B. 嚴格跳空 (Strict Gap)
*   **公式**: $(Low_{today} \ge High_{yesterday}) \land (Open_{today} > High_{yesterday} \times 1.01)$
*   **數據源**: $High_{yesterday}$ 來自盤前預算之 CSV，$Low_{today}, Open_{today}$ 來自即時行情。

#### C. 相對位置 (P-Loc) & 特徵標籤
*   **公式**: $P\text{-}Loc = \frac{Close_{current} - Low_{today}}{High_{today} - Low_{today} + \epsilon}$
*   **篩選門檻**: $P\text{-}Loc > 0.5$ (基礎過濾)
*   **特徵定義**:
    *   **🔥S6_極強勢**: $P\text{-}Loc \ge 0.95$ (收最高，極高勝率特徵)。
    *   **S6_區間突破**: $0.8 \le P\text{-}Loc < 0.95$。

### 3.2 介面規格 (UI Specs)

#### 主畫面佈局
*   **Header**: 系統狀態 (監控中/停止)、最後更新時間。
*   **Section 1: 🔥 目前強勢區 (Active Matches)**
    *   只顯示當下 `is_active = True` 的股票。
    *   欄位：`代碼`, `名稱`, `現價`, `跳空%`, `P-Loc`, `乖離率`, `量能`, `特徵`。
    *   特徵欄位以 🔥 前綴強調。
*   **Section 2: 👀 轉弱觀察區 (Watchlist)**
    *   顯示今日曾觸發但目前 `is_active = False` 的股票。
    *   欄位同上，但數據即時更新以反映最新轉弱狀態。

### 3.3 通知規格
*   **LINE 推播內容**:
    ```text
    🚨 強勢標的觸發
    股票：6674 鋐寶科技
    現價：22.15 (跳空 +2.73%)
    P-Loc：1.00
    量能：733張
    ```
*   **去重機制**: 使用 `line_notifier.py` 內部的 `sent_cache` 確保當日不重複發送。
