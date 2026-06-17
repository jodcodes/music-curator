"""
affective_playlists - Unified music analysis and organization package.

Combines three core subsystems:
1. 4tempers - AI-based playlist temperament analysis
2. metad_enr - Metadata filling and enrichment
3. plsort - Playlist organization and classification

All modules in this package should be imported using absolute imports:
    from src.logger import setup_logger
    from src.config import load_centralized_whitelist
    from src.metadata_fill import MetadataFiller

Do NOT use sys.path.insert() or relative path manipulation.
See openspec/changes/packaging-hardening/design.md for import strategy.
"""

__version__ = "1.0.0"
__author__ = "Joel Debeljak"
