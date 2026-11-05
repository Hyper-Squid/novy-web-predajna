
import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "zmen-tento-kluc")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DB = os.environ.get("DB_PATH", "shop.db")


def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT
    )
    """)

    count = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if count == 0:
        products = [
            ("Jablká", "Ovocie", 1.50, "Čerstvé jablká"),
            ("Banány", "Ovocie", 1.80, "Sladké banány"),
            ("Jahody", "Ovocie", 3.90, "Čerstvé jahody"),
            ("Hrušky", "Ovocie", 2.00, "Šťavnaté hrušky"),
            ("Mrkva", "Zelenina", 1.20, "Čerstvá mrkva"),
            ("Zemiaky", "Zelenina", 0.90, "Kvalitné zemiaky"),
            ("Paradajky", "Zelenina", 2.50, "Čerstvé paradajky"),
        ]

        conn.executemany("""
        INSERT INTO products
        (name, category, price, description)
        VALUES (?, ?, ?, ?)
        """, products)

    conn.commit()
    conn.close()


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    sort = request.args.get("sort", "name")
    category = request.args.get("category", "Všetko")

    sorting = {
        "name": "name ASC",
        "price_low": "price ASC",
        "price_high": "price DESC"
    }

    order = sorting.get(sort, "name ASC")

    conn = connect()

    sql = "SELECT * FROM products"
    params = []

    if category in ["Ovocie", "Zelenina"]:
        sql += " WHERE category = ?"
        params.append(category)

    # TRIEDENIE PREBIEHA NA BACKENDE
    sql += " ORDER BY " + order

    products = conn.execute(sql, params).fetchall()
    conn.close()

    return render_template(
        "index.html",
        products=products,
        sort=sort,
        category=category,
        cart_count=sum(session.get("cart", {}).values())
    )


@app.route("/add-cart/<int:product_id>", methods=["POST"])
def add_cart(product_id):
    conn = connect()
    product = conn.execute(
        "SELECT id FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()
    conn.close()

    if product:
        cart = session.get("cart", {})
        key = str(product_id)
        cart[key] = cart.get(key, 0) + 1
        session["cart"] = cart

    return redirect(url_for("index"))


@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})
    products = []
    total = 0

    conn = connect()

    for product_id, quantity in cart_data.items():
        product = conn.execute(
            "SELECT * FROM products WHERE id = ?",
            (int(product_id),)
        ).fetchone()

        if product:
            subtotal = product["price"] * quantity
            total += subtotal

            products.append({
                "id": product["id"],
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "subtotal": subtotal
            })

    conn.close()

    return render_template(
        "cart.html",
        products=products,
        total=total
    )


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 1

    cart = session.get("cart", {})
    key = str(product_id)

    if quantity <= 0:
        cart.pop(key, None)
    elif quantity <= 99:
        cart[key] = quantity

    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_cart(product_id):
    cart = session.get("cart", {})
    cart.pop(str(product_id), None)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))

        flash("Nesprávne heslo!")

    return render_template("login.html")


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin():
    conn = connect()
    products = conn.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()
    conn.close()

    return render_template("admin.html", products=products)


@app.route("/admin/add", methods=["POST"])
@admin_required
def add_product():
    name = request.form.get("name", "").strip()
    category = request.form.get("category")
    description = request.form.get("description", "").strip()

    try:
        price = float(request.form.get("price", ""))
    except ValueError:
        price = -1

    if (not name or len(name) > 80
        or category not in ["Ovocie", "Zelenina"]
        or not 0 <= price <= 100000):
        flash("Skontroluj údaje produktu.")
        return redirect(url_for("admin"))

    conn = connect()
    conn.execute("""
    INSERT INTO products (name, category, price, description)
    VALUES (?, ?, ?, ?)
    """, (name, category, price, description[:250]))

    conn.commit()
    conn.close()

    flash("Produkt bol pridaný!")
    return redirect(url_for("admin"))


@app.route("/admin/delete/<int:product_id>", methods=["POST"])
@admin_required
def delete_product(product_id):
    conn = connect()
    conn.execute(
        "DELETE FROM products WHERE id = ?",
        (product_id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("admin"))


init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
