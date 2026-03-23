"""
utils/payment_processor.py
===========================
Paddle payment integration helpers (stdlib only).
Paddle handles EU VAT automatically — recommended for indie devs.

Usage:
    from utils.payment_processor import open_checkout_url, PADDLE_PRODUCTS
    open_checkout_url('pro_monthly')
"""
import webbrowser

# ── Product config (replace with your real Paddle product links) ──────────────
PADDLE_PRODUCTS = {
    "pro_monthly":  {
        "name":     "Valo Optimise Pro — Monthly",
        "price":    "£4.99/mo",
        "url":      "https://your-paddle-checkout-url.com/pro-monthly",
    },
    "pro_lifetime": {
        "name":     "Valo Optimise Pro — Lifetime",
        "price":    "£69.99",
        "url":      "https://your-paddle-checkout-url.com/pro-lifetime",
    },
}


def open_checkout_url(product_key: str) -> tuple[bool, str]:
    """
    Open the Paddle checkout page for the given product in the user's browser.
    Returns (ok, message).
    """
    product = PADDLE_PRODUCTS.get(product_key)
    if not product:
        return False, f"Unknown product: {product_key}"
    try:
        webbrowser.open(product["url"])
        return True, f"Opening checkout for {product['name']} ({product['price']})"
    except Exception as e:
        return False, f"Could not open browser: {e}"


def get_product_info(product_key: str) -> dict:
    """Return display info for a product without opening the browser."""
    return PADDLE_PRODUCTS.get(product_key, {})
