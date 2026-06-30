# Couple Finance Plugin — 伴侶記帳

專為伴侶共同記帳設計的 Hermes Agent 插件。純 SQLite 儲存，無外部依賴。

## 簡介

Couple Finance（記帳）是一個 Hermes Agent 插件，讓伴侶可以透過自然語言共同記帳。只要告訴 agent「晚餐 850 我付的」，就會自動記錄一筆結構化的支出。查詢「這個月花了多少」，就會回傳附帶拆帳計算的統計報表。

## 功能

- **6 個 Hermes 工具**：`expense_add`（新增）、`expense_list`（查詢）、`expense_report`（報表）、`expense_delete`（刪除）、`expense_search`（搜尋）、`expense_config`（設定）
- **自然語言輸入**：LLM 自動從對話中解析金額、類別、付款人
- **彈性分攤方式**：50/50、60/40、各付各，或自訂比例
- **拆帳計算**：自動算出誰該給誰多少錢
- **全文搜尋**：支援 FTS5 全文檢索（備援為 LIKE 查詢）
- **軟刪除**：資料保留在資料庫中，但查詢時自動排除
- **可自訂付款人名稱**：例如將付款人改為「小明」與「小華」
- **無外部依賴**：僅使用 Python 標準函式庫
- **測試覆蓋**：94+ 項測試，使用隔離的臨時資料庫

## 需求

- Python 3.10+
- Hermes Agent（執行環境）
- `pytest` 9.0.3（執行測試用）

## 安裝

```bash
# 1. 下載專案
git clone <repo-url>
cd couple_finance_plugin

# 2. 將插件連結到 Hermes 插件目錄
mkdir -p ~/.hermes/plugins
ln -sfn $(pwd)/plugins/couple-finance ~/.hermes/plugins/couple-finance

# 3. 在 ~/.hermes/config.yaml 中啟用插件與工具集
#    plugins:
#      enabled:
#        - couple-finance
#    toolsets:
#      - couple-finance
```

## 使用方式

插件在 `couple-finance` 工具集下註冊了 6 個工具：

| 工具 | 說明 |
|------|------|
| `expense_add` | 記錄一筆支出（金額、類別①、付款人、分攤方式、備註） |
| `expense_list` | 查詢支出（可依日期範圍、類別、付款人篩選，支援分頁） |
| `expense_report` | 統計報表（依類別、依付款人、摘要、拆帳計算） |
| `expense_delete` | 軟刪除指定支出 |
| `expense_search` | 全文搜尋備註與類別 |
| `expense_config` | 查詢或修改設定（付款人名稱等） |

① 類別：餐飲、交通、購物、娛樂、住房、水電、醫療、教育、其他

**與 agent 對話範例：**

> 使用者：「晚餐 850 我付的」  
> Agent 呼叫 `expense_add(amount=850, category="餐飲", payer="Brian", split_method="50/50", note="晚餐")`

> 使用者：「這個月花了多少」  
> Agent 呼叫 `expense_report()` → 回傳各類別統計、各付款人統計、以及拆帳結果

## 執行測試

```bash
# 完整測試套件
python3 -m pytest plugins/couple-finance/tests/ -v

# 單一測試檔案
python3 -m pytest plugins/couple-finance/tests/test_db.py -v
```

所有測試均使用隔離的臨時資料庫，不會影響正式資料。

## 專案結構

```
plugins/couple-finance/
  plugin.yaml          # 插件中繼資料
  __init__.py          # 進入點：register() + 6 個工具處理函式
  db.py                # SQLite 結構、連線、CRUD（12 個公開函式）
  conftest.py          # 解決 pytest 對連字號目錄的收集問題
  tests/
    conftest.py        # 測試用 fixture
    test_db.py         # db.py 單元測試
    test_init.py       # 處理函式與註冊測試
    test_integration.py # 端到端流程測試
```

## 資料庫

- **引擎**：SQLite（WAL 模式，啟用外部鍵）
- **資料表**：`expenses`（軟刪除透過 `is_deleted` 標記）、`config`（鍵值設定）
- **全文搜尋**：支援 FTS5；若環境不支援則自動降級為 `LIKE` 查詢
- **路徑**：首次使用時自動建立於 `~/.hermes/couple-finance.db`（程式碼中可透過 `base_dir` 參數覆蓋）

## 架構備註

- 所有處理函式成功時回傳 `json.dumps({"ok": True, ...})`，失敗時回傳 `json.dumps({"error": str(e)})`
- 處理函式和 db 函式中的 `base_dir` 參數僅供測試使用，不會出現在工具 schema 中
- 目錄名稱含連字號（`couple-finance/`）導致 pytest 匯入問題，解決方式請參閱 `conftest.py` 及 `__init__.py` 中的雙重匯入模式
- `expense_edit` 是規劃中的第 7 個工具（詳見 `.sisyphus/plans/expense-edit.md`）

## 授權條款

MIT
