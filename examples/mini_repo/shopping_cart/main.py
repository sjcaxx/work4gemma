from .models import Product, format_money
from .pricing import bulk_price, apply_discount
from .repository import load_default_inventory


def checkout(item_names):
    """Given names of items, build products and compute a total bill."""
    inv = load_default_inventory()
    products = []
    for name in item_names:
        p = inv.get(name)
        if p is None:
            continue
        products.append(p)
    total = bulk_price(products)
    return format_money(total)


def price_item(name):
    inv = load_default_inventory()
    p = inv.get(name)
    if p is None:
        return "unknown"
    discounted = apply_discount(p, 10)
    return format_money(discounted.price)
