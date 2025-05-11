# Database Fix Notes

## Issue Description

The system was encountering three main issues when trying to create an admin user:

1. **Missing PostgreSQL Extension**: The error `function gen_salt(unknown) does not exist` indicated that the `pgcrypto` extension was not installed or enabled in the PostgreSQL database. This extension provides cryptographic functions including `gen_salt()` which is used for password hashing.

2. **UUID Generation Issue**: The error `null value in column "id" of relation "users" violates not-null constraint` showed that when inserting a user, the UUID was not being automatically generated.

3. **UUID Serialization Issue**: After fixing the above issues, there was a serialization error when returning user objects in API responses. The UUID objects needed to be explicitly converted to strings.

## Solution Applied

The following fixes were implemented:

1. **Added pgcrypto Extension**:

   - Created a new migration file to add the pgcrypto extension
   - Also updated the fix_database.sh script to directly install the extension using SQL

2. **Fixed UUID Generation**:

   - Updated the users table migration to include the server_default for UUID generation
   - Modified the create_admin.sh script to generate UUIDs directly in the SQL statement

3. **Improved Admin User Creation**:

   - Updated the create_admin.sh script to handle password hashing and UUID generation in a single SQL statement
   - This ensures that both the UUID and password hash are properly generated

4. **Fixed UUID Serialization**:

   - Modified the API endpoints to explicitly convert UUID objects to strings in the response
   - Updated the user endpoints to manually construct the response objects with string UUIDs
   - This ensures proper JSON serialization of UUID values in API responses

## How to Use

If you encounter database issues:

1. Run the fix_database.sh script:

   ```bash
   ./fix_database.sh
   ```

2. If you need to create an admin user manually:
   ```bash
   ./create_admin.sh -f
   ```

## Technical Details

### PostgreSQL Extensions

The system requires the `pgcrypto` extension for:

- Password hashing with `crypt()` and `gen_salt()`
- UUID generation with `gen_random_uuid()`

### Database Migrations

The migration sequence is:

1. `initial_migration.py` - Creates the basic tables
2. `add_users_table.py` - Adds the users table with proper UUID generation
3. `add_pgcrypto_367e4604.py` - Ensures the pgcrypto extension is installed

### User Authentication

The system uses bcrypt password hashing via the pgcrypto extension. Passwords are hashed using:

```sql
crypt('password', gen_salt('bf'))
```

This provides secure password storage with proper salting and hashing.
