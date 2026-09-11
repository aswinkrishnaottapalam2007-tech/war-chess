import asyncio
import sys

sys.path.append('/app/backend')

from database import db, client


async def main():
    docs = await db.users.find(
        {'email': {'$regex': r'^test_extra_'}},
        {'_id': 0, 'email': 1},
    ).to_list(500)
    for row in sorted({d['email'] for d in docs}):
        print(row)
    client.close()


if __name__ == '__main__':
    asyncio.run(main())
