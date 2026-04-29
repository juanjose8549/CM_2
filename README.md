# User Account Update Service

This is a FastAPI service for updating user accounts using PostgreSQL and MongoDB.

## Setup

1. Install dependencies:
   pip install -r requirements.txt

2. Set up databases:
   - PostgreSQL: Create a database and update DATABASE_URL in .env
   - MongoDB: Ensure MongoDB is running, update MONGO_URL if needed

3. Run the service:
   uvicorn main:app --reload

## API

PATCH /users/{user_id}

Headers:
- X-User-ID: ID of the authenticated user performing the update

Body (JSON, partial update):
- name: string (optional)
- surname: string (optional)
- password: string (optional)
- is_active: boolean (optional)

Response:
- 200: {"message": "User updated successfully"}
- 400: Invalid data
- 404: User not found