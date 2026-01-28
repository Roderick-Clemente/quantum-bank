from flask import render_template, request
from split_config import get_split_client
import os

def is_demo_mode(user_key=None):
    """Check if demo mode is enabled (instant switching with iframes)
    
    Checks Split.io flag 'demo_mode' first, then falls back to DEMO_MODE env var.
    """
    from split_config import get_split_client
    
    # First, try Split.io flag
    split_client = get_split_client()
    if split_client and user_key:
        treatment = split_client.get_treatment(user_key, 'demo_mode')
        print(f"[Demo Mode] Split.io flag 'demo_mode' = {treatment}")
        if treatment in ('on', 'true', '1', 'yes'):
            return True
        elif treatment in ('off', 'false', '0', 'no'):
            return False
        # If treatment is 'control' or unknown, fall through to env var
    
    # Fallback to environment variable
    demo_mode = os.environ.get('DEMO_MODE', 'on').lower()
    print(f"[Demo Mode] Using env var DEMO_MODE = {demo_mode}")
    return demo_mode in ('true', '1', 'yes', 'on')

def handle_pricing():
    """Handle pricing page - renders wrapper or single variant based on demo mode"""
    
    user_key = request.remote_addr or 'anonymous'
    demo_mode_enabled = is_demo_mode(user_key)
    print(f"[Pricing] DEMO_MODE check -> {demo_mode_enabled}")
    
    if demo_mode_enabled:
        # Demo mode: Pre-load all variants as iframes for instant switching
        print(f"[Pricing] Rendering wrapper template (DEMO MODE ON)")
        return render_template('pricing_wrapper.html', demo_mode=True)
    else:
        # Traditional mode: Server-side rendering of single variant
        # Better for AI testing tools that need isolated variants
        print(f"[Pricing] Rendering single template (DEMO MODE OFF - no badge)")
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
        
        # Explicitly pass demo_mode=False to ensure badge doesn't show
        return render_template(template, demo_mode=False)
