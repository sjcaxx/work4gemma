"""A product in the catalog or order."""


class Product:
    """A product in the catalog."""

    def __init__(self, name, price):
        self.name = name
        self.price = price

    def tax(self, rate=0.08):
        return self.price * rate


class LineItem:
    """A single line in a shopping cart."""

    def __init__(self, product, qty=1):
        self.product = product
        self.qty = qty

    def subtotal(self):
        return self.product.price * self.qty


def format_money(amount):
    """Return amount formatted as dollars."""
    return f"${amount:.2f}"