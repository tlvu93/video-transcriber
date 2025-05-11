# Database Fix Instructions

## Issue Description

The initialization script (`init.sh`) failed because the database schema is missing the `users` table, which is required for authentication. The error occurs because:

1. The `videos` table already exists in the database
2. The `users` table does not exist, but is referenced in the admin user creation script

## Solution

We've created a fix that:

1. Adds a `User` model to the application
2. Creates a new migration to add the `users` table to the database
3. Adds authentication functionality to the API
4. Provides a script to apply the fix

## How to Fix

Run the following command to fix the database schema:

```bash
./fix_database.sh
```

This script will:

1. Run the new migration to add the `users` table
2. Create an admin user with default credentials (username: admin, password: admin)

## What Changed

The following files were added or modified:

1. `src/models.py` - Added User model
2. `migrations/versions/add_users_table.py` - New migration to add users table
3. `src/auth.py` - Authentication functionality
4. `src/api.py` - Updated to include authentication endpoints
5. `requirements.txt` - Added authentication packages
6. `fix_database.sh` - Script to apply the fix

## After the Fix

After running the fix, you should be able to:

1. Access the API at http://localhost:8000
2. Log in with the default admin credentials:
   - Username: admin
   - Password: admin

## API Authentication

The API now requires authentication for all endpoints. To authenticate:

1. Get a token by sending a POST request to `/api/auth/token` with your username and password
2. Include the token in the Authorization header of subsequent requests:
   ```
   Authorization: Bearer <your_token>
   ```

## Creating Additional Users

Only admin users can create new users. To create a new user:

1. Authenticate as an admin
2. Send a POST request to `/api/users` with the new user details:
   ```json
   {
     "username": "new_user",
     "password": "password",
     "role": "user"
   }
   ```
