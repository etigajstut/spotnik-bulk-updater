import os
import asyncio
import httpx
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")

if not MONDAY_API_KEY:
    raise RuntimeError("MONDAY_API_KEY is not set in .env file.")

HEADERS = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json",
    "API-Version": "2024-01"
}


async def run_query(query: str, variables: dict = None) -> dict:
    """Run a GraphQL query. Auto-retries on rate limit errors."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(MONDAY_API_URL, json=payload, headers=HEADERS, timeout=30)
            res.raise_for_status()
            data = res.json()

        if "errors" in data:
            msg = data["errors"][0]["message"]
            # Rate limit hit — sleep and retry
            if "Complexity budget exhausted" in msg:
                reset_in = data["errors"][0].get("extensions", {}).get("reset_in_x_seconds", 60)
                print(f"Rate limit hit. Retrying in {reset_in}s...")
                await asyncio.sleep(reset_in + 1)
                return await run_query(query, variables)
            raise Exception(f"GraphQL error: {msg}")

        return data

    except httpx.TimeoutException:
        raise Exception("monday.com API timed out.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get("Retry-After", 60))
            print(f"HTTP 429 rate limit. Retrying in {retry_after}s...")
            await asyncio.sleep(retry_after + 1)
            return await run_query(query, variables)
        raise Exception(f"HTTP error: {e.response.status_code}")


async def get_boards() -> list:
    """Fetch all boards for the board selector."""
    query = "query { boards(limit: 50, order_by: created_at) { id name } }"
    data = await run_query(query)
    return data["data"]["boards"]


async def get_columns(board_id: int) -> list:
    """Fetch all columns for a board including label settings."""
    query = """
    query($board_id: ID!) {
        boards(ids: [$board_id]) {
            columns { id title type settings_str }
        }
    }
    """
    data = await run_query(query, {"board_id": board_id})
    return data["data"]["boards"][0]["columns"]


async def get_items_page(board_id: int, cursor: Optional[str] = None, filter: Optional[dict] = None) -> dict:
    """
    Fetch one page of items (max 500) using cursor pagination.
    Filtering is done server-side for efficiency — only matching items are returned.
    """
    # Subsequent pages use the cursor from the previous response
    if cursor:
        query = """
        query($cursor: String!) {
            next_items_page(limit: 500, cursor: $cursor) {
                cursor
                items { id }
            }
        }
        """
        data = await run_query(query, {"cursor": cursor})
        return data["data"]["next_items_page"]

    # First page with server-side filter
    if filter:
        compare_values = "[" + ",".join(filter["values"]) + "]"
        query = f"""
        query {{
            boards(ids: [{board_id}]) {{
                items_page(limit: 500, query_params: {{
                    rules: [{{
                        column_id: "{filter["column_id"]}",
                        compare_value: {compare_values},
                        operator: any_of
                    }}]
                }}) {{
                    cursor
                    items {{ id }}
                }}
            }}
        }}
        """
        data = await run_query(query)

    # First page with no filter — fetch all items
    else:
        query = """
        query($board_id: ID!) {
            boards(ids: [$board_id]) {
                items_page(limit: 500) {
                    cursor
                    items { id }
                }
            }
        }
        """
        data = await run_query(query, {"board_id": board_id})

    return data["data"]["boards"][0]["items_page"]


async def update_items_batch(board_id: int, item_ids: List[str], column_id: str, value: str) -> dict:
    """
    Update a batch of items in a single GraphQL mutation using aliases.
    Batching reduces API calls dramatically vs updating one item at a time.
    """
    aliases = "\n".join([
        f'u{i}: change_simple_column_value(board_id: {board_id}, item_id: {item_id}, column_id: "{column_id}", value: "{value}") {{ id }}'
        for i, item_id in enumerate(item_ids)
    ])
    mutation = f"mutation {{ complexity {{ before after }} {aliases} }}"
    return await run_query(mutation)
