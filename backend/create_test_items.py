import asyncio
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")

HEADERS = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json",
    "API-Version": "2024-01"
}

BOARD_ID = 5094938432  # your board ID
GROUP_ID = "topics"    # default group, we'll fetch it

async def get_group_id():
    query = f"""
    query {{
        boards(ids: [{BOARD_ID}]) {{
            groups {{
                id
                title
            }}
        }}
    }}
    """
    async with httpx.AsyncClient() as client:
        res = await client.post(MONDAY_API_URL, json={"query": query}, headers=HEADERS)
        data = res.json()
        groups = data["data"]["boards"][0]["groups"]
        print("Available groups:", groups)
        return groups[0]["id"]

async def create_item(client, group_id: str, index: int):
    mutation = f"""
    mutation {{
        create_item(
            board_id: {BOARD_ID},
            group_id: "{group_id}",
            item_name: "Test item {index}"
        ) {{
            id
        }}
    }}
    """
    res = await client.post(MONDAY_API_URL, json={"query": mutation}, headers=HEADERS)
    data = res.json()
    if "errors" in data:
        print(f"Error creating item {index}: {data['errors']}")
    else:
        print(f"Created item {index}: {data['data']['create_item']['id']}")

async def main():
    group_id = await get_group_id()
    print(f"Using group: {group_id}")

    async with httpx.AsyncClient() as client:
        # Create 10 at a time to avoid rate limits
        for batch_start in range(0, 200, 10):
            tasks = [
                create_item(client, group_id, i)
                for i in range(batch_start, batch_start + 10)
            ]
            await asyncio.gather(*tasks)
            print(f"Created items {batch_start} to {batch_start + 10}")
            await asyncio.sleep(1)  # small pause between batches

    print("Done! 200 test items created.")

asyncio.run(main())