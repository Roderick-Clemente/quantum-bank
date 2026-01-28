from flask import render_template, request
from split_config import get_split_client

def handle_pricing():
    """Handle pricing page - renders variant based on Split.io feature flag"""
    
    # Get Split.io client
    split_client = get_split_client()
    
    # Default to v2 pricing (new/modern theme)
    template = 'pricing_v2.html'
    
    if split_client:
        # Get user key (using IP address or session ID as identifier)
        user_key = request.remote_addr or 'anonymous'
        
        # Get treatment for home_page_variant feature flag
        # (using same flag as home page to keep variants consistent)
        treatment = split_client.get_treatment(user_key, 'home_page_variant')
        
        # Select template based on treatment
        if treatment == 'old_home':
            # Old variant - use old/simple theme
            template = 'pricing_old.html'
        elif treatment == 'dev_home':
            # Dev variant - use v3 (dev theme)
            template = 'pricing_v3.html'
        else:
            # Default treatment (new_home or control) - use v2
            template = 'pricing_v2.html'
        
        print(f"[Pricing] User {user_key} received treatment: {treatment} -> {template}")
    else:
        print("[Pricing] Split.io client not available, using default template (v2)")
    
    return render_template(template)
