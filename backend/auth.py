import database

# Staff credentials - Manager has full admin control, Staff have scoped access
# Passwords and roles are verified here, display names and designations are stored dynamically in DB
USERS = {
    # Manager
    "admin": {
        "password": "admin123",
        "role": "manager"
    },
    # Kitchen Staff
    "head_chef": {
        "password": "staff123",
        "role": "kitchen"
    },
    "sous_chef": {
        "password": "staff123",
        "role": "kitchen"
    },
    # Service Staff
    "senior_waiter": {
        "password": "staff123",
        "role": "server"
    },
    "waitress": {
        "password": "staff123",
        "role": "server"
    },
    "bartender": {
        "password": "staff123",
        "role": "server"
    }
}


def authenticate(username, password):
    user = USERS.get(username)

    if user and user["password"] == password:
        # Load dynamic profile fields (display_name, designation) from database
        profile = database.get_user_profile(username)
        return {
            "username": username,
            "role": user["role"],
            "display_name": profile["display_name"] if profile else username,
            "designation": profile["designation"] if profile else "Staff"
        }

    return None