# newsdaily-autopost

每天 09:00（台北）自動把「每日簡報」濃縮成 5～8 張 4:5 新聞卡片，發到 Instagram 與 Threads（@newsdaily.tw）。

## 流程
1. **Claude 排程（08:45）**：讀 Gmail 最新「每日簡報」→ 依 `SPEC.md` 寫 `content/<date>.json` → push。
2. **GitHub Actions `build-and-post`**（push 觸發）：
   - Pexels 抓背景 → `src/render.py` 用固定模板畫卡 → 存到 `output/<date>/`
   - `publish: true` 時等到 09:00 → 發 IG 輪播 + Threads 輪播 → 記錄在 `output/<date>/posted.json`（重跑不會重複發文）
3. **`refresh-tokens`**：每週一自動續期 IG / Threads 權杖並寫回 Secrets。
4. **`check-setup`**：手動執行，檢查所有 Secrets 是否有效（不會發文）。

## Secrets
| 名稱 | 用途 |
|---|---|
| `PEXELS_API_KEY` | 背景照片 |
| `IG_ACCESS_TOKEN` | Instagram API（Instagram 登入）長效權杖 |
| `THREADS_ACCESS_TOKEN` | Threads API 長效權杖 |
| `GH_PAT` | 讓 refresh-tokens 能寫回 Secrets（Fine-grained，只限本 repo，Secrets: Read and write） |

## 手動操作
- 只產圖不發文：Actions → build-and-post → Run workflow → mode = build
- 立即發文：mode = post
- 失敗時 GitHub 會寄信通知。

背景照片來自 [Pexels](https://www.pexels.com)，來源記錄於 `output/<date>/credits.json`。
