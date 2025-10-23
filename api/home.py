from flask import render_template, request
from split_config import get_split_client

def handle_home():
    """Handle home page with Split.io feature flag"""

    # Get Split.io client
    split_client = get_split_client()

    # Default to new home page
    template = 'home.html'

    if split_client:
        # Get user key (using IP address or session ID as identifier)
        # In production, you'd use actual user ID
        user_key = request.remote_addr or 'anonymous'

        # Get treatment for home_page_variant feature flag
        treatment = split_client.get_treatment(user_key, 'home_page_variant')

        # Select template based on treatment
        if treatment == 'old_home':
            template = 'old_home.html'
        elif treatment == 'new_home':
            template = 'home.html'
        else:
            # Default treatment (control)
            template = 'home.html'

        print(f"[Split.io] User {user_key} received treatment: {treatment} -> {template}")
    else:
        print("[Split.io] Client not available, using default template")

    return render_template(template)