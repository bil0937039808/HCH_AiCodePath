# login-service/app.py

import json
import math
import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    render_template_string,
    request,
    session,
    url_for,
)
from flask_dance.contrib.google import google, make_google_blueprint
from werkzeug.security import check_password_hash, generate_password_hash

# --- 1. 環境變數設定 ---
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    print("FATAL ERROR: 'SECRET_KEY' is not set.", file=sys.stderr)
    sys.exit(1)

# --- 2. Flask 應用程式初始化 ---
app = Flask(__name__)
app.secret_key = SECRET_KEY


# --- 3. 資料庫連線管理 ---
def get_db():
    if "db" not in g:
        try:
            g.db = psycopg2.connect(
                dbname=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                host=os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT", "5432"),
            )

        except psycopg2.OperationalError as e:
            print(f"FATAL ERROR: Database connection failed: {e}", file=sys.stderr)

            raise e
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# --- 4. Google OAuth 藍圖 (Blueprint) 設定 ---
google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
    redirect_to="google_login_logic",
)
# 告訴 Flask 應用程式要註冊並使用這個 Google 登入藍圖
app.register_blueprint(google_bp, url_prefix="/login")


# --- 5. 登入狀態管理與路由 ---


def login_user(user):
    session.clear()
    session["user_id"] = user["member_id"]
    session["username"] = user["username"]


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(request.host_url)
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(request.host_url)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        error = None
        db = get_db()
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM members WHERE username = %s", (username,))
            user = cur.fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "帳號或密碼錯誤！"

        if error is None:
            login_user(user)
            return redirect(request.host_url)

        flash(error, "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect("/")
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        error = None
        db = get_db()
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if not all([username, email, password]):
                error = "所有欄位均為必填。"

            if error is None:
                cur.execute(
                    "SELECT member_id FROM members WHERE username = %s OR email = %s",
                    (username, email),
                )
                if cur.fetchone() is not None:
                    error = "該帳號或電子郵件已被註冊。"

            if error is None:
                password_hash = generate_password_hash(password)
                cur.execute(
                    "INSERT INTO members (username, email, password_hash) VALUES (%s, %s, %s)",
                    (username, email, password_hash),
                )
                db.commit()
                flash("註冊成功，請登入！", "success")
                return redirect(url_for("login"))

        flash(error, "danger")
    return render_template("register.html")


@app.route("/api/status")
def get_status():
    if "user_id" in session and "username" in session:
        return {
            "logged_in": True,
            "username": session["username"],
            "member_id": session["user_id"],  # <--- 新增這一行
        }
    else:
        return {"logged_in": False}


@app.route("/history")
def history():
    if "user_id" not in session:
        flash("請先登入！", "warning")
        return redirect(url_for("login"))

    page = request.args.get("page", 1, type=int)
    PER_PAGE = 5

    member_id = session["user_id"]
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            "SELECT COUNT(*) FROM chat_history WHERE member_id = %s", (member_id,)
        )
        total_records = cur.fetchone()[0]
        total_pages = math.ceil(total_records / PER_PAGE)
        offset = (page - 1) * PER_PAGE

        cur.execute(
            "SELECT history_id, conversation, created_at FROM chat_history WHERE member_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (member_id, PER_PAGE, offset),
        )
        chat_histories = [dict(row) for row in cur.fetchall()]

    for record in chat_histories:
        try:
            convo_data = record["conversation"]
            user_message = next(
                (msg["content"] for msg in convo_data if msg.get("role") == "user"),
                "無標題",
            )
            record["summary"] = (
                user_message[:30] + "..." if len(user_message) > 30 else user_message
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            record["summary"] = "對話紀錄格式錯誤"

    return render_template(
        "history.html",
        username=session.get("username"),
        histories=chat_histories,
        current_page=page,
        total_pages=total_pages,
    )


@app.route("/history/load/<int:history_id>")
def load_history_to_chat(history_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            "SELECT conversation FROM chat_history WHERE history_id = %s AND member_id = %s",
            (history_id, session["user_id"]),
        )
        history_record = cur.fetchone()

    if not history_record:
        flash("找不到該筆歷史紀錄。", "danger")
        return redirect(url_for("history"))

    # 渲染一個帶有 JavaScript 的中介頁面
    # 這個頁面會將對話紀錄存到 sessionStorage，然後跳轉到 chatbot.html
    conversation_json = json.dumps(history_record["conversation"])
    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head><title>載入中...</title></head>
        <body>
            <p>正在載入您的對話紀錄...</p>
            <script>
                try {
                    sessionStorage.setItem('chat_to_load', {{ conversation_json | tojson }});
                    window.location.href = '/chatbot.html';
                } catch (e) {
                    console.error('無法儲存歷史紀錄到 sessionStorage', e);
                    // 如果失敗，導回主頁
                    window.location.href = '/';
                }
            </script>
        </body>
        </html>
    """,
        conversation_json=conversation_json,
    )


# 為了讓 Flask 能產生 chatbot.html 的 URL，我們需要一個虛設的端點
@app.route("/chatbot-redirect")
def chatbot_page():
    return redirect("/chatbot.html")  # 直接導向前端的靜態 HTML


@app.route("/google-login-logic")
def google_login_logic():
    # ... (Google 登入邏輯維持不變，僅修改最後的重新導向) ...
    if not google.authorized:
        return redirect("/")
    try:
        resp = google.get("/oauth2/v2/userinfo")
        resp.raise_for_status()
    except Exception:
        flash("從 Google 獲取使用者資訊失敗", "danger")
        return redirect(url_for("login"))

    user_info = resp.json()
    email = user_info["email"]
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM members WHERE email = %s", (email,))
        user = cur.fetchone()
        if not user:
            username = email.split("@")[0]
            cur.execute("SELECT * FROM members WHERE username = %s", (username,))
            if cur.fetchone():
                username = f"{username}_{user_info.get('id', '')[-4:]}"
            password_hash = generate_password_hash(f"google-oauth-{user_info['id']}")
            cur.execute(
                "INSERT INTO members (username, email, password_hash) VALUES (%s, %s, %s) RETURNING *",
                (username, email, password_hash),
            )
            user = cur.fetchone()
            db.commit()
    login_user(user)
    return redirect(request.host_url)


@app.route("/logout")
def logout():
    session.clear()
    flash("您已成功登出！", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
