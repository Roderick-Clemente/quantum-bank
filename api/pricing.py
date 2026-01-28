from flask import render_template, request
from split_config import get_split_client
import os

def is_demo_mode():
    """Check if demo mode is enabled (instant switching with iframes)"""
    # Default to True for demo/showcase purposes
    demo_mode = os.environ.get('DEMO_MODE', 'true').lower()
    return demo_mode in ('true', '1', 'yes', 'on')

def handle_pricing():
    """Handle pricing page - renders wrapper or single variant based on demo mode"""
    
    if is_demo_mode():
        # Demo mode: Pre-load all variants as iframes for instant switching
        return render_template('pricing_wrapper.html')
    else:
        # Traditional mode: Server-side rendering of single variant
        # Better for AI testing tools that need isolated variants
        split_client = get_split_client()
        template = 'pricing_v2.html'  # Default
        
        if split_client:
            user_key = request.remote_addr or 'anonymous'
            treatment = split_client.get_treatment(user_key, 'home_page_variant')
            
            if treatment == 'old_home':
                template = 'pricing_old.html'
            elif treatment == 'dev_home':
                template = 'pricing_v3.html'
            else:
                template = 'pricing_v2.html'  # new_home or control
            
            print(f"[Pricing] Traditional mode - User {user_key} received treatment: {treatment} -> {template}")
        else:
            print("[Pricing] Traditional mode - Split.io unavailable, using default template")
        
        return render_template(template)
