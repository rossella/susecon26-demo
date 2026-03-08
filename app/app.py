"""
I-love-geekos Marketplace – Flask application.

Currently uses FileStorage (Phase 1): cart data is written to JSON files on
a PersistentVolume.  Run the helper script to watch the disk fill up:
  python simulate_load.py

The /storage-status page shows live disk usage.

To fix the problem (Phase 2), implement RedisStorage in storage.py and update
create_storage() to return it when STORAGE_BACKEND=redis is set.
"""

import logging
import os
import uuid

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from storage import create_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "geeko-secret-change-in-prod")

# One storage instance for the whole application lifetime
storage = create_storage()

# ── Product catalogue ─────────────────────────────────────────────────────────

PRODUCTS = [
    {
        "id": 1,
        "name": "Geeko Plush Toy",
        "price": 19.99,
        "description": "The cutest Geeko plush in the universe. Perfect desk companion for any open-source enthusiast.",
        "emoji": "🦎",
        "category": "Collectibles",
    },
    {
        "id": 2,
        "name": "Geeko T-Shirt",
        "price": 24.99,
        "description": "100 % organic cotton tee featuring the legendary Geeko mascot. Available in all sizes.",
        "emoji": "👕",
        "category": "Apparel",
    },
    {
        "id": 3,
        "name": "SUSE Linux Handbook",
        "price": 39.99,
        "description": "The definitive guide to SUSE Linux Enterprise. From installation to enterprise configuration.",
        "emoji": "📗",
        "category": "Books",
    },
    {
        "id": 4,
        "name": "Geeko Sticker Pack",
        "price": 4.99,
        "description": "15 high-quality vinyl stickers featuring Geeko in various poses. Water-resistant.",
        "emoji": "🎨",
        "category": "Collectibles",
    },
    {
        "id": 5,
        "name": "SUSE Green Hat",
        "price": 14.99,
        "description": "Classic green embroidered cap. Show your SUSE pride wherever you go.",
        "emoji": "🧢",
        "category": "Apparel",
    },
    {
        "id": 6,
        "name": "Kubernetes Notebook",
        "price": 9.99,
        "description": "A5 hard-cover notebook with Kubernetes logo. 192 pages of dot-grid paper.",
        "emoji": "📓",
        "category": "Stationery",
    },
    {
        "id": 7,
        "name": "Geeko Enamel Pin",
        "price": 7.99,
        "description": "Hard enamel pin with Geeko design. Gold plating, butterfly clasp.",
        "emoji": "📌",
        "category": "Collectibles",
    },
    {
        "id": 8,
        "name": "Open-Source Hoodie",
        "price": 49.99,
        "description": "Warm zip-up hoodie with \"Open Source All The Things\" embroidered on the back.",
        "emoji": "🧥",
        "category": "Apparel",
    },
    {
        "id": 9,
        "name": "Container Ship Model",
        "price": 29.99,
        "description": "Die-cast model ship labelled with famous container names (docker, podman, containerd …).",
        "emoji": "🚢",
        "category": "Collectibles",
    },
    {
        "id": 10,
        "name": "Tux & Geeko Mug",
        "price": 12.99,
        "description": "Ceramic 350 ml mug featuring Tux and Geeko having coffee together.",
        "emoji": "☕",
        "category": "Kitchen",
    },
    {
        "id": 11,
        "name": "SUSE Socks",
        "price": 8.99,
        "description": "Comfy cotton socks with Geeko pattern. One size fits most.",
        "emoji": "🧦",
        "category": "Apparel",
    },
    {
        "id": 12,
        "name": "Linux Penguin Figurine",
        "price": 22.99,
        "description": "Hand-painted resin figurine of Tux wearing a SUSE-green scarf.",
        "emoji": "🐧",
        "category": "Collectibles",
    },
]

PRODUCTS_BY_ID = {p["id"]: p for p in PRODUCTS}

# ── Helpers ───────────────────────────────────────────────────────────────────


def _session_id() -> str:
    """Return (and persist) a stable session identifier."""
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return session["sid"]


def _cart_total(cart: list) -> float:
    return round(sum(item["price"] * item["qty"] for item in cart), 2)


# ── Routes ────────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    visits = storage.increment_visits()
    backend = os.environ.get("STORAGE_BACKEND", "file")
    return render_template(
        "index.html",
        products=PRODUCTS,
        visits=visits,
        backend=backend,
    )


@app.route("/product/<int:product_id>")
def product(product_id: int):
    p = PRODUCTS_BY_ID.get(product_id)
    if p is None:
        abort(404)
    backend = os.environ.get("STORAGE_BACKEND", "file")
    return render_template("product.html", product=p, backend=backend)


@app.route("/cart")
def cart():
    sid = _session_id()
    cart_items = storage.get_cart(sid)
    total = _cart_total(cart_items)
    backend = os.environ.get("STORAGE_BACKEND", "file")
    return render_template(
        "cart.html", cart=cart_items, total=total, backend=backend
    )


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id: int):
    p = PRODUCTS_BY_ID.get(product_id)
    if p is None:
        abort(404)

    sid = _session_id()
    cart_items = storage.get_cart(sid)

    # Update quantity if already in cart
    for item in cart_items:
        if item["id"] == product_id:
            item["qty"] += 1
            storage.save_cart(sid, cart_items)
            return redirect(url_for("cart"))

    cart_items.append(
        {"id": p["id"], "name": p["name"], "price": p["price"], "emoji": p["emoji"], "qty": 1}
    )
    storage.save_cart(sid, cart_items)
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id: int):
    sid = _session_id()
    cart_items = storage.get_cart(sid)
    cart_items = [item for item in cart_items if item["id"] != product_id]
    storage.save_cart(sid, cart_items)
    return redirect(url_for("cart"))


@app.route("/cart/checkout", methods=["POST"])
def checkout():
    sid = _session_id()
    cart_items = storage.get_cart(sid)
    total = _cart_total(cart_items)
    storage.clear_cart(sid)
    backend = os.environ.get("STORAGE_BACKEND", "file")
    return render_template(
        "checkout.html", cart=cart_items, total=total, backend=backend
    )


@app.route("/storage-status")
def storage_status():
    """Admin page that shows the current storage usage – key for the demo."""
    info = storage.storage_info()
    backend = os.environ.get("STORAGE_BACKEND", "file")
    return render_template("storage_status.html", info=info, backend=backend)


@app.errorhandler(404)
def not_found(e):
    backend = os.environ.get("STORAGE_BACKEND", "file")
    return render_template("404.html", backend=backend), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
