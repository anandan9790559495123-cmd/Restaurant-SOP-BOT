import database

# Staff credentials - Manager has full admin control, Staff have scoped access
# Passwords and roles are verified here, display names and designations are stored dynamically in DB
# Staff credentials - Manager has full admin control, Staff have scoped access
# Passwords, roles, display names and designations are stored dynamically in SQLite DB

def authenticate(username, password):
    profile = database.get_user_profile(username)

    if profile and profile.get("password") == password:
        return {
            "username": username,
            "role": profile["role"],
            "display_name": profile["display_name"] if profile["display_name"] else username,
            "designation": profile["designation"] if profile["designation"] else "Staff"
        }

    return None