from .models import Product


class Inventory:
    """In-memory product database."""

    def __init__(self):
        self._items = {}

    def add(self, product):
        self._items[product.name] = product

    def get(self, name):
        return self._items.get(name)

    def total_value(self):
        sum_ = 0.0
        for p in self._items.values():
            sum_ += p.price
        return sum_


def load_default_inventory():
    inv = Inventory()
    inv.add(Product("apple", 0.50))
    inv.add(Product("banana", 0.30))
    return inv
