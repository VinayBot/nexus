"""CRUD API for Items."""

from fastapi import FastAPI, HTTPException

from app.models import Item, ItemIn
from app.store import Store

app = FastAPI(title="Items API")
store = Store()


@app.post("/items", response_model=Item, status_code=201)
def create_item(data: ItemIn) -> Item:
    return store.create(data)


@app.get("/items", response_model=list[Item])
def list_items() -> list[Item]:
    return store.list()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int) -> Item:
    item = store.get(item_id)
    if item is None:
        raise HTTPException(404, "not found")
    return item


@app.put("/items/{item_id}", response_model=Item)
def update_item(item_id: int, data: ItemIn) -> Item:
    item = store.update(item_id, data)
    if item is None:
        raise HTTPException(404, "not found")
    return item


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int) -> None:
    if not store.delete(item_id):
        raise HTTPException(404, "not found")
