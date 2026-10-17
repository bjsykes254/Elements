"""State plug-ins for the Elements tools.

Each jurisdiction gets one module here, named by its lowercase code (nc.py for NC).
A module describes where that state's statutes live and how to read its pages.
It must provide:

    JURISDICTION            "NC"
    WATCH_ARTICLES          list of {"id", "label", "url"} pages that list whole groups of sections
    section_key(url)        -> "14-52"                   short name of a section, used by the accept command
    section_file_name(url)  -> "GS_14-52"                 file name for the saved text in sources/<state>/
    section_text(html)      -> (text, history_note)      one section page
    article_headings(html)  -> [heading, ...]            one article page
    last_session_law(history_note) -> str
    is_repealed(text)       -> bool

and may provide:

    check_secondary(data, fetch, pause) -> (items, notes)
        extra sources worth watching, such as pattern jury instructions

To add a state, copy nc.py, change the URLs and the parsing, and add a test using a saved
copy of one of that state's section pages in tests/fixtures/.
"""
import importlib


def load(jurisdiction):
    try:
        return importlib.import_module("adapters." + jurisdiction.lower())
    except ImportError as ex:
        raise SystemExit("No adapter for jurisdiction %r (tools/adapters/%s.py): %s" % (jurisdiction, jurisdiction.lower(), ex))
