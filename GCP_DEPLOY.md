# GapTrading 系統 GCP 部署指南

本指南將說明如何使用 **Cloud Run Jobs** 將您的自動化交易機器人部署到 Google Cloud Platform (GCP)。此方法可讓系統每天早晨自動喚醒，執行盤中監控，並在收盤 (13:30) 後自動關閉，以節省成本。

## 前置準備
1.  **GCP 帳號**: 擁有一個已啟用計費功能的 Google Cloud 專案。
2.  **Google Cloud SDK**: 已安裝在本地電腦，或直接使用瀏覽器中的 Cloud Shell。
3.  **啟用 API**: 請至 GCP 後台啟用 "Cloud Run Admin API"、"Artifact Registry API" 與 "Cloud Scheduler API"。

## 步驟 1: 準備環境變數 (Environment Variables)
您需要準備好以下數值，稍後設定時會用到：
*   `SHIOAJI_API_KEY`: 您的永豐金證券 API Key。
*   `SHIOAJI_SECRET_KEY`: 您的永豐金證券 Secret Key。
*   `FINLAB_TOKEN`: 您的 FinLab API Token。
*   `LINE_TOKEN`: 您的 LINE Messaging API Token。
*   `LINE_USER_ID`: 您的 LINE User ID (用於接收通知)。

## 步驟 2: 建置並上傳 Docker 映像檔

1.  **初始化 gcloud** (若使用 Cloud Shell 可跳過):
    ```bash
    gcloud auth login
    gcloud config set project [您的專案ID]
    ```

2.  **建立 Artifact Registry 倉庫** (若尚未建立):
    ```bash
    gcloud artifacts repositories create gaptrading-repo --repository-format=docker --location=asia-east1
    ```

3.  **建置並推送映像檔**:
    *請將 `[您的專案ID]` 替換為實際的 Project ID。*
    ```bash
    # 設定 Docker 使用 gcloud 憑證
    gcloud auth configure-docker asia-east1-docker.pkg.dev

    # 建置映像檔 (Build)
    docker build -t asia-east1-docker.pkg.dev/[您的專案ID]/gaptrading-repo/monitor:v1 .

    # 推送映像檔 (Push)
    docker push asia-east1-docker.pkg.dev/[您的專案ID]/gaptrading-repo/monitor:v1
    ```

## 步驟 3: 建立 Cloud Run Job (作業)

我們使用 **Job (作業)** 而非 Service (服務)，因為此程式只需執行一段時間 (直到 13:30) 就會結束。

1.  **建立作業**:
    ```bash
    gcloud run jobs create gaptrading-daily-job \
      --image asia-east1-docker.pkg.dev/[您的專案ID]/gaptrading-repo/monitor:v1 \
      --location asia-east1 \
      --task-timeout 5h \
      --cpu 1 \
      --memory 1Gi \
      --max-retries 0 \
      --set-env-vars SHIOAJI_API_KEY=[您的API_KEY],SHIOAJI_SECRET_KEY=[您的SECRET_KEY],FINLAB_TOKEN=[您的TOKEN],LINE_TOKEN=[您的LINE_TOKEN],LINE_USER_ID=[您的LINE_USER_ID]
    ```
    *   `--task-timeout 5h`: 確保作業能從 08:30 執行到 13:30，不會中途被強制停止。
    *   `--location asia-east1`: 選擇台灣 (彰化) 機房，連線延遲最低。

## 步驟 4: 設定排程 (Cloud Scheduler)

設定排程器，讓作業在每個交易日 (週一至週五) 的早上 08:50 自動啟動。

1.  **建立排程器觸發條件**:
    
    **推薦使用 GCP 主控台 GUI 設定 (較簡單):**
    1.  前往 **Cloud Run** > **Jobs (作業)** 分頁。
    2.  點擊 `gaptrading-daily-job`。
    3.  點擊上方的 **TRIGGERS (觸發條件)** 分頁 > **Add Scheduler Trigger (新增排程器觸發條件)**。
    4.  名稱 (Name): `daily-trading-start`
    5.  頻率 (Frequency): `50 8 * * 1-5` (代表每週一到週五的 08:50)。
    6.  時區 (Timezone): 搜尋並選擇 `Taiwan Standard Time (CST)`。
    7.  點擊 **Create (建立)**。

## 步驟 5: 驗證測試

1.  **手動測試**:
    您可以手動觸發一次作業，確認程式能正常執行。
    ```bash
    gcloud run jobs execute gaptrading-daily-job --location asia-east1
    ```
2.  **查看日誌 (Logs)**:
    前往 **Cloud Run** > **Jobs** > `gaptrading-daily-job` > **Logs (記錄)**，您應該能看到 `headless_monitor.py` 輸出的執行紀錄。

## 更新流程
當您修改了程式碼 (例如 `strategy.py` 或 `headless_monitor.py`)：
1.  重新建置映像檔 (`docker build ...`)。
2.  重新推送映像檔 (`docker push ...`)。
3.  更新 Job 使用新的映像檔：
    ```bash
    gcloud run jobs update gaptrading-daily-job --image asia-east1-docker.pkg.dev/[您的專案ID]/gaptrading-repo/monitor:v1
    ```

