"""In-memory storage for Items (swap for a database later)."""

from app.models import Item, ItemIn


class Store:
    def __init__(self) -> None:
        self._items: dict[int, Item] = {}
        self._next = 1

    def create(self, data: ItemIn) -> Item:
        item = Item(id=self._next, **data.model_dump())
        self._items[item.id] = item
        self._next += 1
        return item

    def list(self) -> list[Item]:
        return list(self._items.values())

    def get(self, item_id: int) -> Item | None:
        return self._items.get(item_id)

    def update(self, item_id: int, data: ItemIn) -> Item | None:
        if item_id not in self._items:
            return None
        self._items[item_id] = Item(id=item_id, **data.model_dump())
        return self._items[item_id]

    def delete(self, item_id: int) -> bool:
        return self._items.pop(item_id, None) is not None
