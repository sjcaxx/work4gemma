from .models import Product


def apply_discount(product, percent):
    """Return a discounted copy of the product."""
    disc = product.price * (1 - percent / 100.0)
    return Product(product.name, disc)


def bulk_price(items):
    """Compute total given a list of products, with volume discount."""
    total = 0.0
    for p in items:
        total += p.price
    if len(items) >= 5:
        total *= 0.9
    return total
