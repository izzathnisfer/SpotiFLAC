"""
Radio Service - Utilities
"""

import re

def clean_search_query(artist: str, title: str) -> str:
    """
    Clean up track title and artist for better search results on SoundCloud/YouTube.
    Removes:
    - Text in brackets () []
    - Separators like | -
    - "Feat." "Ft."
    """
    # Simply sanitize the title first
    # Remove text in brackets
    safe_title = re.sub(r'\([^)]*\)', '', title)
    safe_title = re.sub(r'\[[^\]]*\]', '', safe_title)
    
    # Remove separators like | (often used for " | Official Video" etc)
    if '|' in safe_title:
        safe_title = safe_title.split('|')[0]
    
    # Remove "ft.", "feat"
    safe_title = re.sub(r'(?i)\b(ft\.|feat\.|feat|featuring)\b.*', '', safe_title)
    
    # Remove "Official Video", "Lyric Video"
    safe_title = re.sub(r'(?i)\b(official|lyric|video|audio)\b', '', safe_title)
    
    safe_title = safe_title.strip()
    safe_artist = artist.split(',')[0].strip() # Take primary artist
    
    # Construct simplifed query
    return f"{safe_artist} - {safe_title}"
