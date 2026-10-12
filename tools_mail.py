"""Print the HTML body of the daily 素材包 email (run after the cards commit exists).
usage: python3 tools_mail.py <DATE> <CARDS_COMMIT_SHA>"""
import glob, html, json, os, sys
date, sha = sys.argv[1], sys.argv[2]
root = os.path.dirname(os.path.abspath(__file__))
c = json.load(open(os.path.join(root, "content", f"{date}.json"), encoding="utf-8"))
auto = json.load(open(os.path.join(root, "config.json"))).get("auto_post", True)
imgs = sorted(glob.glob(os.path.join(root, "output", date, "[0-9][0-9].jpg")))
raw = f"https://raw.githubusercontent.com/ochenme/newsdaily-autopost/{sha}/output/{date}"
pre = 'style="white-space:pre-wrap;font-family:inherit;font-size:15px;background:#f4f4f4;color:#111;padding:12px;border-radius:8px"'
h = [f"<h2>📦 知日報今日素材包｜{date}</h2>",
     f"<p>自動發文：<b>{'開啟（11:30 已排程自動發出）' if auto else '關閉（請手動發文）'}</b></p>",
     "<h3>① Threads 主文</h3>", f"<pre {pre}>{html.escape(c.get('threads_text', ''))}</pre>",
     "<h3>② Threads 第一則留言／IG 內文</h3>", f"<pre {pre}>{html.escape(c['caption'])}</pre>",
     f"<h3>③ 圖片（共 {len(imgs)} 張，依序發佈；點圖開原圖後長按儲存）</h3>"]
for i, p in enumerate(imgs, 1):
    u = f"{raw}/{os.path.basename(p)}"
    h.append(f'<p>第 {i} 張：<a href="{u}">開啟原圖</a><br><a href="{u}"><img src="{u}" width="270" alt="card {i}"></a></p>')
print("\n".join(h))
