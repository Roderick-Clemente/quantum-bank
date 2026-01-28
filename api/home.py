from flask import render_template, request, session
from split_config import get_split_client
import os

def is_demo_mode(user_key=None, entry_path=None):
    """Check if demo mode is enabled (instant switching with iframes)
    
    Priority order:
    1. URL path (/demo) - forces demo mode ON
    2. Split.io flag 'demo_mode' with user attributes (entry_path)
    3. DEMO_MODE env var (default: 'off')
    
    Handles Split.io SDK initialization timing gracefully.
    """
    # Priority 1: Check if user came from /demo path
    if entry_path == '/demo':
        print(f"[Demo Mode] 🎯 Entry path '/demo' detected -> Demo mode FORCED ON")
        return True
    
    # Priority 2: Try Split.io flag with user attributes
    split_client = get_split_client()
    if split_client and user_key:
        try:
            # Build user attributes for Split.io targeting
            attributes = {}
            if entry_path:
                attributes['entry_path'] = entry_path
            
            treatment = split_client.get_treatment(user_key, 'demo_mode', attributes=attributes if attributes else None)
            print(f"[Demo Mode] Split.io flag 'demo_mode' = {treatment} (user: {user_key}, entry_path: {entry_path})")
            
            # Explicit treatments
            if treatment in ('on', 'true', '1', 'yes'):
                print(f"[Demo Mode] ✅ Split.io flag = ON -> Demo mode ENABLED")
                return True
            elif treatment in ('off', 'false', '0', 'no'):
                print(f"[Demo Mode] ❌ Split.io flag = OFF -> Demo mode DISABLED")
                return False
            # If treatment is 'control' or unknown, Split.io isn't configured or SDK not ready
            # Fall through to env var as safe default
            elif treatment == 'control':
                print(f"[Demo Mode] Split.io returned 'control' - flag may not be configured, using env var")
            else:
                print(f"[Demo Mode] Split.io returned unknown treatment '{treatment}' - using env var")
        except Exception as e:
            print(f"[Demo Mode] Error getting Split.io treatment: {e} - using env var")
    
    # Priority 3: Fallback to environment variable (safe default: 'off' for AI testing)
    demo_mode = os.environ.get('DEMO_MODE', 'off').lower()
    result = demo_mode in ('true', '1', 'yes', 'on')
    print(f"[Demo Mode] Using env var DEMO_MODE = {demo_mode} (default: 'off') -> {result}")
    return result

def handle_home():
    """Handle home page - renders wrapper or single variant based on demo mode"""
    
    user_key = request.remote_addr or 'anonymous'
    # Check session for entry path (set by /demo route), or use current path
    entry_path = session.get('entry_path', request.path)
    demo_mode_enabled = is_demo_mode(user_key, entry_path)
    print(f"[Home] DEMO_MODE check -> {demo_mode_enabled}")
    
    if demo_mode_enabled:
        # Demo mode: Pre-load all variants as iframes for instant switching
        print(f"[Home] Rendering wrapper template (DEMO MODE ON)")
        return render_template('home_wrapper.html', demo_mode=True)
    else:
        # Traditional mode: Server-side rendering of single variant
        # Better for AI testing tools that need isolated variants
        print(f"[Home] Rendering single template (DEMO MODE OFF - no badge)")
        split_client = get_split_client()
        template = 'home.html'  # Default
        
        if split_client:
            user_key = request.remote_addr or 'anonymous'
            treatment = split_client.get_treatment(user_key, 'home_page_variant')
            
            if treatment == 'old_home':
                template = 'old_home.html'
            elif treatment == 'dev_home':
                template = 'home_v3.html'
            else:
                template = 'home.html'  # new_home or control
            
            print(f"[Home] Traditional mode - User {user_key} received treatment: {treatment} -> {template}")
        else:
            print("[Home] Traditional mode - Split.io unavailable, using default template")
        
        # Explicitly pass demo_mode=False to ensure badge doesn't show
        return render_template(template, demo_mode=False)