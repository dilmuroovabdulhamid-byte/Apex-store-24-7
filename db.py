"""Ma'lumotlar bazasi (SQLite). Login va parollar Fernet bilan shifrlanib saqlanadi."""
import sqlite3
import threading
from datetime import datetime

from cryptography.fernet import Fernet


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Store:
    def __init__(self, path: str, enc_key: str):
        self.fernet = Fernet(enc_key.encode())
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY, username TEXT, name TEXT,
                balance INTEGER NOT NULL DEFAULT 0, created TEXT);
            CREATE TABLE IF NOT EXISTS accounts(
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                price INTEGER NOT NULL, descr TEXT, login_enc TEXT NOT NULL,
                pass_enc TEXT NOT NULL, sold INTEGER NOT NULL DEFAULT 0,
                buyer_id INTEGER, sold_at TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS topups(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                created TEXT);
            """
        )

    # ---- yordamchilar
    def _one(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    def _all(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def _run(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).rowcount

    def enc(self, s: str) -> str:
        return self.fernet.encrypt(s.encode()).decode()

    def dec(self, s: str) -> str:
        return self.fernet.decrypt(s.encode()).decode()

    # ---- foydalanuvchilar
    def touch_user(self, uid, username, name):
        with self.lock:
            self.db.execute(
                "INSERT INTO users(id,username,name,created) VALUES(?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET username=excluded.username, name=excluded.name",
                (uid, (username or "").lower(), name, now()),
            )

    def get_user(self, uid):
        return self._one("SELECT * FROM users WHERE id=?", (uid,))

    def add_balance(self, uid, amount) -> bool:
        return self._run("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid)) > 0

    def admin_ids_by_username(self, usernames):
        if not usernames:
            return set()
        marks = ",".join("?" * len(usernames))
        rows = self._all(f"SELECT id FROM users WHERE username IN ({marks})", tuple(usernames))
        return {r["id"] for r in rows}

    # ---- akkauntlar
    def add_account(self, title, price, descr, login, password) -> int:
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO accounts(title,price,descr,login_enc,pass_enc,created) VALUES(?,?,?,?,?,?)",
                (title, price, descr, self.enc(login), self.enc(password), now()),
            )
            return cur.lastrowid

    def list_available(self, limit, offset):
        return self._all(
            "SELECT id,title,price FROM accounts WHERE sold=0 ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def get_account(self, acc_id):
        return self._one("SELECT id,title,price,descr,sold FROM accounts WHERE id=?", (acc_id,))

    def set_price(self, acc_id, price) -> bool:
        return self._run("UPDATE accounts SET price=? WHERE id=? AND sold=0", (price, acc_id)) > 0

    def delete_account(self, acc_id) -> bool:
        return self._run("DELETE FROM accounts WHERE id=? AND sold=0", (acc_id,)) > 0

    def purchase(self, uid, acc_id):
        """Atomik xarid. Qaytaradi: ('ok'|'gone'|'money', account_dict)."""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                acc = self.db.execute(
                    "SELECT * FROM accounts WHERE id=? AND sold=0", (acc_id,)
                ).fetchone()
                if not acc:
                    self.db.execute("ROLLBACK")
                    return "gone", None
                r = self.db.execute(
                    "UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",
                    (acc["price"], uid, acc["price"]),
                )
                if r.rowcount == 0:
                    self.db.execute("ROLLBACK")
                    return "money", dict(acc)
                self.db.execute(
                    "UPDATE accounts SET sold=1,buyer_id=?,sold_at=? WHERE id=?",
                    (uid, now(), acc_id),
                )
                self.db.execute("COMMIT")
            except Exception:
                try:
                    self.db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        data = dict(acc)
        data["login"] = self.dec(acc["login_enc"])
        data["password"] = self.dec(acc["pass_enc"])
        return "ok", data

    def user_orders(self, uid):
        rows = self._all(
            "SELECT title,price,login_enc,pass_enc,sold_at FROM accounts WHERE buyer_id=? ORDER BY sold_at DESC",
            (uid,),
        )
        out = []
        for r in rows:
            d = dict(r)
            d["login"], d["password"] = self.dec(r["login_enc"]), self.dec(r["pass_enc"])
            out.append(d)
        return out

    # ---- balans to'ldirish
    def add_topup(self, uid, amount) -> int:
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO topups(user_id,amount,created) VALUES(?,?,?)", (uid, amount, now())
            )
            return cur.lastrowid

    def resolve_topup(self, topup_id, approve: bool):
        """Faqat 'pending' holatdagini hal qiladi. Muvaffaqiyatli bo'lsa topup qatorini qaytaradi."""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                t = self.db.execute(
                    "SELECT * FROM topups WHERE id=? AND status='pending'", (topup_id,)
                ).fetchone()
                if not t:
                    self.db.execute("ROLLBACK")
                    return None
                self.db.execute(
                    "UPDATE topups SET status=? WHERE id=?", ("ok" if approve else "no", topup_id)
                )
                if approve:
                    self.db.execute(
                        "UPDATE users SET balance=balance+? WHERE id=?", (t["amount"], t["user_id"])
                    )
                self.db.execute("COMMIT")
                return dict(t)
            except Exception:
                try:
                    self.db.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    # ---- statistika
    def stats(self):
        g = lambda sql: self._one(sql)[0] or 0
        return {
            "users": g("SELECT COUNT(*) FROM users"),
            "available": g("SELECT COUNT(*) FROM accounts WHERE sold=0"),
            "sold": g("SELECT COUNT(*) FROM accounts WHERE sold=1"),
            "revenue": g("SELECT SUM(price) FROM accounts WHERE sold=1"),
            "pending": g("SELECT COUNT(*) FROM topups WHERE status='pending'"),
        }
