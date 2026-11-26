#!/usr/bin/env python3

# Browse a directory of markdown documentation.
# Markdown files are rendered to HTML by default. Append '?raw' to get the source.
# Directory listings show a README/index markdown file underneath the file table.
# Other files are served as-is by the regular file sharing handler.
# Open pages refresh themselves when their document or the file tree changes.
#   On Linux, changes are noticed with inotify. Elsewhere, they are checked for on a timer.
# Fenced code blocks work inside lists and blockquotes, and are highlighted when Pygments is installed.
# Lists nest at CommonMark's indentation (to the item's text) as well as in steps of 4.

import ctypes, ctypes.util, errno, hashlib, os, re, select, struct, sys, time
import CoreHttpServer as common
from CoreHttpServer import args, print_notice, print_warning

common.local_files.append(os.path.realpath(__file__))

# Reuse listing, Range handling, and symbolic link rules from the file sharer.
# Note: Importing this also registers the symbolic link arguments, but not the upload arguments.
from verbose_share import SimpleHTTPVerboseReqeustHandler

from html import escape
from urllib.parse import quote, unquote

try:
    import markdown
except ImportError:
    markdown = None

try:
    from pygments.formatters import HtmlFormatter
    from pygments.util import ClassNotFound
except ImportError:
    HtmlFormatter = None

# Script Content

TITLE_CSS = 'css'
TITLE_ESCAPE_HTML = 'escape-html'
TITLE_LIVE_RELOAD_INTERVAL = 'live-reload-interval'
TITLE_LIVE_RELOAD_OFF = 'no-live-reload'
TITLE_LIVE_RELOAD_POLL = 'live-reload-poll'
TITLE_TREE_CACHE = 'tree-cache-seconds'
TITLE_TREE_MAX_DIRECTORIES = 'tree-max-directories'
TITLE_TREE_SKIP = 'tree-skip'

MARKDOWN_EXTENSIONS = ['.md', '.markdown']
MARKDOWN_PLUGINS = ['fenced_code', 'codehilite', 'tables', 'toc', 'sane_lists']
MARKDOWN_PLUGIN_CONFIGS = {
    # Leave unlabelled blocks plain instead of guessing at a language.
    'codehilite': {'guess_lang': False},
}
INDEX_NAMES = ['readme.md', 'index.md', 'readme.markdown', 'index.markdown']

# File tree sidebar
DEFAULT_TREE_CACHE = 10
DEFAULT_TREE_MAX_DIRECTORIES = 5000
DEFAULT_TREE_SKIP = 'node_modules,__pycache__'

# Live reload
DEFAULT_LIVE_RELOAD_INTERVAL = 0.5
LIVE_DEBOUNCE = 0.15  # Seconds to let the rest of a save land before telling the page.
LIVE_HEARTBEAT = 5  # Seconds between keep-alive comments. A failed write is how a closed tab is noticed.
LIVE_RETRY = (
    3000  # Milliseconds for the browser to wait before reconnecting to a lost stream.
)
LIVE_WAIT_LIMIT = 1.0  # Longest single wait, so that shutdown and changes inotify cannot see are still noticed.
LIVE_META = 'markdown-browser-events'

DEFAULT_CSS = """
      :root { --fg: #24292f; --bg: #ffffff; --muted: #57606a; --border: #d0d7de; --code-bg: #f6f8fa; --link: #0969da; --hover: rgba(0,0,0,.075); }
      @media (prefers-color-scheme: dark) {
        :root { --fg: #e6edf3; --bg: #0d1117; --muted: #8d96a0; --border: #30363d; --code-bg: #161b22; --link: #4493f8; --hover: rgba(255,255,255,.06); }
      }
      body { font-family: "Poppins", "Roboto", Sans-serif; color: var(--fg); background: var(--bg); margin: 0; padding: 25px; line-height: 1.5; }
      a { color: var(--link); text-decoration: none; }
      a:hover { text-decoration: underline; }
      .crumbs { color: var(--muted); margin-bottom: 20px; padding-right: 50px; word-break: break-all; }
      .crumbs .raw { float: right; }
      .layout { display: flex; gap: 40px; align-items: flex-start; justify-content: center; max-width: 1400px; margin: 0 auto; }
      .doc { flex: 1; min-width: 0; max-width: 1100px; }
      .toc-panel { position: sticky; top: 65px; flex: 0 0 250px; max-height: calc(100vh - 90px); overflow-y: auto; font-size: 14px; border-left: 1px solid var(--border); padding-left: 15px; }
      .toc-panel ul { list-style: none; padding-left: 12px; margin: 0; }
      .toc-panel > .toc > ul { padding-left: 0; }
      @media (max-width: 900px) { .layout { display: block; } .toc-panel { display: none; } }
      h1, h2 { border-bottom: 1px solid var(--border); padding-bottom: .3em; }
      code { background: var(--code-bg); padding: .15em .35em; border-radius: 4px; font-size: 90%; }
      pre { background: var(--code-bg); padding: 12px 16px; border-radius: 6px; overflow-x: auto; }
      pre code { background: none; padding: 0; font-size: 90%; }
      blockquote { margin: 0; padding: 0 1em; color: var(--muted); border-left: 4px solid var(--border); }
      .doc table { border-collapse: collapse; margin: 1em 0; display: block; overflow-x: auto; }
      .doc th, .doc td { border: 1px solid var(--border); padding: 6px 13px; }
      .doc img { max-width: 100%; }
      .listing table { border-collapse: collapse; }
      .listing th { text-align: left; }
      .listing tr.hover-row:hover { background-color: var(--hover); }
      .listing td { vertical-align: text-top; padding: 5px 0px; margin: 0px; }
      .listing tr td { border-top: 1px solid var(--border); }
      .c_name { min-width: 300px; padding-left: 25px; }
      .c_mod { padding: 5px 20px; min-width: 175px; }
      .c_size { padding: 5px 10px 5px 20px; min-width: 125px; }
      .c_info { min-width: 175px; }
      .s_dead { color: #821e00; }
      .path { font-weight: bold; }
      .readme { border: 1px solid var(--border); border-radius: 6px; padding: 0 25px 10px; }
      .listing + .layout { margin-top: 30px; }
      .readme-name { color: var(--muted); font-size: 14px; padding: 10px 0; border-bottom: 1px solid var(--border); margin-bottom: 10px; }
"""

# Sidebar layout, always included so that the sidebar still works with a custom stylesheet.
NAV_CSS = """
      .page { display: flex; gap: 30px; align-items: flex-start; }
      .page > main { flex: 1; min-width: 0; }
      .nav-toggle { position: fixed; top: 15px; right: 15px; z-index: 20; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; padding: 0; cursor: pointer; color: var(--fg, #24292f); background: var(--bg, #ffffff); border: 1px solid var(--border, #d0d7de); border-radius: 6px; }
      .nav-toggle:hover { background: var(--hover, rgba(0,0,0,.075)); }
      .nav-panel { display: none; position: sticky; top: 65px; flex: 0 0 260px; max-height: calc(100vh - 90px); overflow-y: auto; font-size: 14px; border-left: 1px solid var(--border, #d0d7de); padding-left: 15px; }
      body.nav-open .nav-panel { display: block; }
      .nav-title { color: var(--muted, #57606a); font-weight: 600; margin-bottom: 8px; }
      .nav-panel ul { list-style: none; margin: 0; padding-left: 14px; }
      .nav-panel > ul { padding-left: 0; }
      .nav-panel li { margin: 2px 0; }
      .nav-panel summary { cursor: pointer; }
      .nav-panel li.current > a { font-weight: 700; }
      .nav-empty { color: var(--muted, #57606a); }
      .live-notice { margin: 0 0 20px; padding: 8px 12px; color: var(--muted, #57606a); border: 1px solid var(--border, #d0d7de); border-radius: 6px; }
      @media (max-width: 900px) {
        .nav-panel { position: fixed; top: 0; right: 0; bottom: 0; z-index: 10; width: min(85vw, 320px); max-height: none; padding: 65px 15px 15px; background: var(--bg, #ffffff); box-shadow: -4px 0 16px rgba(0,0,0,.25); }
      }
"""

# Pygments styles for highlighted code, picked to match the default light and dark colours.
HIGHLIGHT_STYLES_LIGHT = ['default']
HIGHLIGHT_STYLES_DARK = ['github-dark', 'monokai']


def highlight_rules(styles):
    """Token colour rules for the first available Pygments style in a list."""
    for style in styles:
        try:
            defs = HtmlFormatter(style=style).get_style_defs('.codehilite')
        except ClassNotFound:
            continue
        # Keep only token rules. The block background comes from the page's own pre style.
        return '\n'.join(
            '        ' + line
            for line in defs.splitlines()
            if line.startswith('.codehilite .')
        )
    return ''


def highlight_css():
    if not HtmlFormatter:
        return ''
    return (
        '\n      @media (prefers-color-scheme: light) {\n%s\n      }'
        '\n      @media (prefers-color-scheme: dark) {\n%s\n      }\n'
        % (
            highlight_rules(HIGHLIGHT_STYLES_LIGHT),
            highlight_rules(HIGHLIGHT_STYLES_DARK),
        )
    )


# Only added to the built-in style. A custom stylesheet may not suit these colours.
HIGHLIGHT_CSS = highlight_css()

NAV_TOGGLE_ICON = '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 4h14M2 9h14M2 14h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'

NAV_SCRIPT = """
    <script>
    (function() {
      var key = "markdown-browser-nav-open";
      var button = document.getElementById("nav-toggle");
      var panel = document.getElementById("nav-panel");

      function setOpen(open, remember) {
        document.body.classList.toggle("nav-open", open);
        button.setAttribute("aria-expanded", open ? "true" : "false");
        if (remember) {
          try { localStorage.setItem(key, open ? "1" : "0"); } catch (e) {}
        }
        if (open) {
          // Bring the current page into view within the sidebar, without scrolling the page itself.
          var current = panel.querySelector("li.current");
          if (current) {
            panel.scrollTop = current.offsetTop - panel.offsetTop - panel.clientHeight / 2;
          }
        }
      }

      var stored = null;
      try { stored = localStorage.getItem(key); } catch (e) {}
      setOpen(stored === "1", false);

      button.addEventListener("click", function() {
        setOpen(!document.body.classList.contains("nav-open"), true);
      });
      document.addEventListener("keydown", function(event) {
        if (event.key === "Escape" && document.body.classList.contains("nav-open") && window.matchMedia("(max-width: 900px)").matches) {
          setOpen(false, true);
        }
      });
    })();
    </script>"""

LIVE_SCRIPT = """
    <script>
    (function() {
      // Live reload: the server holds an event stream open, and sends "change" once this page
      //   or the file tree no longer matches what was served. The page then fetches itself again
      //   and swaps in the new content, keeping the scroll position and the sidebar state.
      if (!window.EventSource || !window.fetch || !window.DOMParser) { return; }

      var metaSelector = 'meta[name="%s"]';
      var source = null;
      var refreshing = false;
      var url = eventsUrl(document);

      function eventsUrl(doc) {
        var meta = doc.querySelector(metaSelector);
        return meta ? meta.getAttribute("content") : null;
      }

      function connect() {
        if (source || refreshing || !url || document.hidden) { return; }
        source = new EventSource(url);
        source.addEventListener("change", function(event) {
          disconnect();
          refreshing = true;
          // The event carries the tokens for what the server sees now, for use if the page cannot be fetched.
          refresh(event.data, 0);
        });
      }

      function disconnect() {
        if (source) {
          source.close();
          source = null;
        }
      }

      function resume(next) {
        url = next;
        refreshing = false;
        connect();
      }

      function refresh(fallback, attempt) {
        fetch(location.pathname + location.search, { cache: "no-store", credentials: "same-origin" })
          .then(function(response) {
            if (!response.ok) { throw new Error("HTTP " + response.status); }
            return response.text();
          })
          .then(function(text) {
            var next = new DOMParser().parseFromString(text, "text/html");
            swap(next);
            resume(eventsUrl(next) || fallback);
          })
          .catch(function(error) {
            if (attempt < 1) {
              // An editor that saves by renaming a new file into place can leave a brief gap.
              setTimeout(function() { refresh(fallback, attempt + 1); }, 500);
              return;
            }
            notice("Unable to reload this page (" + error.message + "). Waiting for it to change again.");
            resume(fallback);
          });
      }

      function swap(next) {
        var main = document.querySelector("main");
        var nextMain = next.querySelector("main");
        if (!main || !nextMain) { throw new Error("unexpected page layout"); }
        var x = window.scrollX, y = window.scrollY;
        main.innerHTML = nextMain.innerHTML;

        var panel = document.getElementById("nav-panel");
        var nextPanel = next.getElementById("nav-panel");
        if (panel && nextPanel) {
          // Keep folders that the reader opened or closed by hand.
          var open = {};
          panel.querySelectorAll("details").forEach(function(details) {
            var link = details.querySelector("summary > a");
            if (link) { open[link.getAttribute("href")] = details.open; }
          });
          var panelScroll = panel.scrollTop;
          panel.innerHTML = nextPanel.innerHTML;
          panel.querySelectorAll("details").forEach(function(details) {
            var link = details.querySelector("summary > a");
            if (link && Object.prototype.hasOwnProperty.call(open, link.getAttribute("href"))) {
              details.open = open[link.getAttribute("href")];
            }
          });
          panel.scrollTop = panelScroll;
        }

        // Keep the tokens in the head current too, for anyone inspecting the page.
        var meta = document.querySelector(metaSelector);
        var nextUrl = eventsUrl(next);
        if (meta && nextUrl) { meta.setAttribute("content", nextUrl); }

        document.title = next.title;
        window.scrollTo(x, y);
      }

      function notice(text) {
        var main = document.querySelector("main");
        if (!main) { return; }
        var element = main.querySelector(".live-notice");
        if (!element) {
          element = document.createElement("p");
          element.className = "live-notice";
          main.insertBefore(element, main.firstChild);
        }
        element.textContent = text;
      }

      document.addEventListener("visibilitychange", function() {
        // Browsers allow only a few connections to one server, so hidden tabs let go of theirs.
        if (document.hidden) {
          disconnect();
        } else {
          connect();
        }
      });
      connect();
    })();
    </script>""" % LIVE_META

PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>%(title)s</title>%(live_meta)s
    <style>%(css)s%(nav_css)s
    </style>
  </head>
  <body>
    <script>try { if (localStorage.getItem("markdown-browser-nav-open") === "1") { document.body.classList.add("nav-open"); } } catch (e) {}</script>
    <button type="button" class="nav-toggle" id="nav-toggle" aria-controls="nav-panel" aria-expanded="false" title="Toggle file tree">%(nav_icon)s</button>
    <div class="page">
      <main>
        <div class="crumbs">%(crumbs)s%(raw_link)s</div>
        %(content)s
      </main>
      <aside class="nav-panel" id="nav-panel" aria-label="Markdown files">
        <div class="nav-title">Documents</div>
        %(tree)s
      </aside>
    </div>%(nav_script)s%(live_script)s
  </body>
</html>
"""

# Define arguments

args.add_opt(
    common.OPT_TYPE_LONG,
    TITLE_CSS,
    TITLE_CSS,
    'Stylesheet file to use instead of the built-in style.',
)
args.add_opt(
    common.OPT_TYPE_LONG_FLAG,
    TITLE_ESCAPE_HTML,
    TITLE_ESCAPE_HTML,
    'Escape raw HTML inside markdown documents instead of passing it through.',
)


def name_list(value):
    # Comma-separated list of names, blank entries ignored.
    return [n.strip() for n in value.split(',') if n.strip()]


args.add_opt(
    common.OPT_TYPE_LONG,
    TITLE_TREE_CACHE,
    TITLE_TREE_CACHE,
    'Seconds to reuse the file tree sidebar before scanning again (0 to scan on every page).',
    converter=float,
    default=DEFAULT_TREE_CACHE,
    default_announce=True,
    environment='MARKDOWN_BROWSER_TREE_CACHE',
)
args.add_opt(
    common.OPT_TYPE_LONG,
    TITLE_TREE_MAX_DIRECTORIES,
    TITLE_TREE_MAX_DIRECTORIES,
    'Maximum number of directories to scan for the file tree sidebar.',
    converter=int,
    default=DEFAULT_TREE_MAX_DIRECTORIES,
    default_announce=True,
    environment='MARKDOWN_BROWSER_TREE_MAX_DIRECTORIES',
)
args.add_opt(
    common.OPT_TYPE_LONG,
    TITLE_TREE_SKIP,
    TITLE_TREE_SKIP,
    'Comma-separated directory names to leave out of the file tree sidebar. Hidden directories are always left out.',
    converter=name_list,
    default=DEFAULT_TREE_SKIP,
    default_announce=True,
    environment='MARKDOWN_BROWSER_TREE_SKIP',
)


args.add_opt(
    common.OPT_TYPE_LONG_FLAG,
    TITLE_LIVE_RELOAD_OFF,
    TITLE_LIVE_RELOAD_OFF,
    'Do not refresh open pages when their document or the file tree changes.',
)
args.add_opt(
    common.OPT_TYPE_LONG_FLAG,
    TITLE_LIVE_RELOAD_POLL,
    TITLE_LIVE_RELOAD_POLL,
    'Check open pages for changes on a timer instead of with inotify. Always the case outside of Linux.',
)
args.add_opt(
    common.OPT_TYPE_LONG,
    TITLE_LIVE_RELOAD_INTERVAL,
    TITLE_LIVE_RELOAD_INTERVAL,
    'Seconds between checks for changes when checking on a timer.',
    converter=float,
    default=DEFAULT_LIVE_RELOAD_INTERVAL,
    default_announce=True,
    environment='MARKDOWN_BROWSER_LIVE_RELOAD_INTERVAL',
)


def validate_css(self):
    path = self[TITLE_CSS]
    if path and not os.path.isfile(path):
        return 'Stylesheet not found: %s' % common.colour_text(
            path, common.COLOUR_GREEN
        )


args.add_validator(validate_css)


def validate_tree(self):
    errors = []
    # Phrased to also reject NaN.
    if not 0 <= self[TITLE_TREE_CACHE] < float("inf"):
        errors.append(
            'Tree cache must be a number of seconds that is at least 0. Given: %s'
            % common.colour_text(self[TITLE_TREE_CACHE])
        )
    if not 0 < self[TITLE_LIVE_RELOAD_INTERVAL] < float("inf"):
        errors.append(
            'Live reload interval must be a number of seconds above 0. Given: %s'
            % common.colour_text(self[TITLE_LIVE_RELOAD_INTERVAL])
        )
    if self[TITLE_TREE_MAX_DIRECTORIES] < 1:
        errors.append(
            'Tree directory limit must be at least 1. Given: %s'
            % common.colour_text(self[TITLE_TREE_MAX_DIRECTORIES])
        )
    return errors


args.add_validator(validate_tree)


# inotify(7) constants, from <sys/inotify.h>.
IN_MODIFY = 0x00000002
IN_ATTRIB = 0x00000004
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_IGNORED = 0x00008000
IN_ONLYDIR = 0x01000000
IN_WATCH_MASK = (
    IN_MODIFY
    | IN_ATTRIB
    | IN_CLOSE_WRITE
    | IN_MOVED_FROM
    | IN_MOVED_TO
    | IN_CREATE
    | IN_DELETE
    | IN_DELETE_SELF
    | IN_MOVE_SELF
)
# struct inotify_event: wd, mask, cookie and name length, followed by the name itself.
INOTIFY_EVENT = struct.Struct('iIII')


def load_inotify():
    """Return a libc handle set up for the inotify functions, or None where inotify is not available."""
    if not sys.platform.startswith('linux'):
        return None
    try:
        libc = ctypes.CDLL(ctypes.util.find_library('c') or 'libc.so.6', use_errno=True)
        init = libc.inotify_init1
        add_watch = libc.inotify_add_watch
    except (OSError, AttributeError):
        return None
    init.argtypes = [ctypes.c_int]
    init.restype = ctypes.c_int
    add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    add_watch.restype = ctypes.c_int
    return libc


INOTIFY = load_inotify()


class InotifyWatcher(object):
    """Wakes up when something changes in a set of directories.
    Directories are watched instead of files, so that a save that renames a new file into place is still seen.
    Waking up only means that something may have changed. The caller compares file signatures to be sure.
    """

    def __init__(self, libc):
        self.libc = libc
        # IN_NONBLOCK and IN_CLOEXEC share their values with O_NONBLOCK and O_CLOEXEC.
        fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if fd < 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
        self.fd = fd
        self.watches = {}  # Watch descriptor -> directory
        # poll() rather than select(), which cannot handle descriptors above FD_SETSIZE.
        self.poller = select.poll()
        self.poller.register(fd, select.POLLIN)

    def watch(self, directories):
        watched = set(self.watches.values())
        for directory in directories:
            if directory in watched:
                continue
            wd = self.libc.inotify_add_watch(
                self.fd, os.fsencode(directory), IN_WATCH_MASK | IN_ONLYDIR
            )
            # A directory that cannot be watched yet (missing or unreadable) is tried again on the next pass.
            if wd >= 0:
                self.watches[wd] = directory

    def wait(self, timeout):
        if self.poller.poll(int(max(0, timeout) * 1000)):
            self.drain()

    def drain(self):
        while True:
            try:
                data = os.read(self.fd, 64 * 1024)
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    return
                raise
            if not data:
                return
            offset = 0
            while offset + INOTIFY_EVENT.size <= len(data):
                wd, mask, cookie, length = INOTIFY_EVENT.unpack_from(data, offset)
                if mask & IN_IGNORED:
                    # The kernel dropped this watch (directory removed or moved away), so let watch() add it again.
                    self.watches.pop(wd, None)
                offset += INOTIFY_EVENT.size + length

    def close(self):
        os.close(self.fd)


class PollWatcher(object):
    """Stand-in for InotifyWatcher where inotify is not available or not wanted. Wakes up on a timer."""

    def __init__(self, interval):
        self.interval = interval

    def watch(self, directories):
        pass

    def wait(self, timeout):
        time.sleep(max(0, min(timeout, self.interval)))

    def drain(self):
        pass

    def close(self):
        pass


def digest(value):
    """Short token for a value made of tuples, lists, dictionaries, strings and numbers."""
    # repr() escapes the surrogates that surrogateescape leaves in undecodable file names.
    return hashlib.sha1(repr(value).encode('utf-8')).hexdigest()[:16]


def stat_signature(path, follow=True):
    """Identity and version of a file or directory as of now, or None if it is missing."""
    try:
        st = os.stat(path) if follow else os.lstat(path)
    except OSError:
        return None
    return (st.st_ino, st.st_size, st.st_mtime_ns)


# Nested code fences
#
# The stock fenced_code extension only finds fences at the start of a line, so a fence
#   inside a list item or a blockquote comes out as a run of inline code.
# This preprocessor finds those fences too, strips their container prefix, hands each one
#   to fenced_code (so highlighting and attributes are handled in one place), and leaves
#   the stored block's placeholder behind with the same prefix so the container stays whole.

# Opening fence: blockquote markers, then indentation, then the fence and its info string.
FENCE_OPEN_RE = re.compile(
    r'^(?P<quote>(?:[ ]{0,3}>[ ]?)*)(?P<indent>[ ]*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$'
)
FENCE_QUOTE_RE = re.compile(r'[ ]{0,3}>[ ]?')
FENCE_QUOTES_RE = re.compile(r'^(?:[ ]{0,3}>[ ]?)*')
# Info strings that fenced_code already understands.
FENCE_INFO_RE = re.compile(
    r'^(?:\{.*\}|\.?[\w#.+-]*[ ]*(?:hl_lines=(["\']).*?\1[ ]*)?)$'
)
LIST_ITEM_RE = re.compile(r'^(?:[*+-]|\d+[.)])(?:[ ]|$)')

# List indentation
#
# CommonMark (and GitHub) nest a block in a list item when it is indented to the
#   item's text: 3 spaces under "1. ", 2 under "* ". Python-Markdown wants steps of 4,
#   so a nested list under "1. " ran into the item's paragraph, "*" and all.
# This preprocessor moves each item's content from the column CommonMark reads to
#   the column Python-Markdown reads, keeping any further indentation, so indented
#   code blocks and fences inside items move with it. Lines outside lists are left alone.

# A list marker: indentation, the marker, and the spaces before the item's text.
LIST_MARKER_RE = re.compile(r'^(?P<indent>[ ]*)(?P<marker>[*+-]|\d{1,9}[.)])(?P<gap>[ ]+|$)')
# A fence, after its line's indentation is removed.
LIST_FENCE_RE = re.compile(r'^(`{3,}|~{3,})')


def list_content_column(match):
    """The column an item's text starts at, as CommonMark counts it."""
    start = len(match.group('indent')) + len(match.group('marker'))
    gap = len(match.group('gap'))
    # No text, or 5 or more spaces (an indented code block), means one space.
    return start + (gap if 1 <= gap <= 4 else 1)


def fence_info(info):
    """Rewrite an info string such as 'py title="a.py"' into the '{ .py title="a.py" }' form fenced_code reads."""
    info = info.strip()
    if FENCE_INFO_RE.match(info):
        return info
    words = info.split(None, 1)
    lang, rest = words[0], (words[1] if len(words) > 1 else '')
    if '=' in lang or lang.startswith('{'):
        return '{ %s }' % info
    rest = rest.strip()
    if rest.startswith('{') and rest.endswith('}'):
        # Pandoc style: ```python {.numberLines}
        rest = rest[1:-1]
    return '{ .%s %s }' % (lang.lstrip('.'), rest)


def in_list(lines, index):
    """Guess whether the line at index continues a list item, by finding the last unindented line before it."""
    for line in reversed(lines[:index]):
        line = FENCE_QUOTES_RE.sub('', line, count=1)
        if not line.strip() or line.startswith(' '):
            continue
        return bool(LIST_ITEM_RE.match(line))
    return False


if markdown:

    class NestedFencePreprocessor(markdown.preprocessors.Preprocessor):
        def run(self, lines):
            out = []
            index = 0
            while index < len(lines):
                consumed = self.convert(lines, index, out)
                if not consumed:
                    out.append(lines[index])
                    consumed = 1
                index += consumed
            return out

        def convert(self, lines, index, out):
            """Convert the fence opening at index, if there is one. Returns the number of lines used, or 0."""
            match = FENCE_OPEN_RE.match(lines[index])
            if not match:
                return 0
            quote, fence = match.group('quote'), match.group('fence')
            depth = quote.count('>')
            indent = len(match.group('indent'))
            if fence[0] == '`' and '`' in match.group('info'):
                return 0  # Inline code such as ```x```, not a fence.

            listed = in_list(lines, index)
            if indent > 3 and not listed:
                return 0  # Indented code block that happens to show a fence.
            close_re = re.compile(
                r'^[ ]{0,3}%s{%d,}[ ]*$' % (re.escape(fence[0]), len(fence))
            )

            body = []
            for end in range(index + 1, len(lines)):
                line = self.strip_prefix(lines[end], depth, indent)
                if line is None:
                    return 0  # The blockquote ended before the fence closed.
                if close_re.match(line):
                    break
                body.append(line)
            else:
                return 0  # Never closed. Leave it as the stock extension would.

            # fenced_code needs the closing fence to match the opening one exactly.
            block = [fence + fence_info(match.group('info'))] + body + [fence]
            stash = self.md.htmlStash
            count = len(stash.rawHtmlBlocks)
            result = '\n'.join(self.md.preprocessors['fenced_code_block'].run(block))
            if len(stash.rawHtmlBlocks) == count:
                return 0  # fenced_code did not accept it either.

            # Python-Markdown wants list item content after a blank line indented in steps of 4.
            lead = quote + (' ' * (-(-indent // 4) * 4) if listed else '')
            # The placeholder must be a paragraph of its own to be swapped for the block.
            # Separate it from neighbouring text, but do not leave an empty line at the
            #   edge of a blockquote, which would join the placeholder's paragraph.
            blank = quote.rstrip()
            if out and self.has_text(out[-1]):
                out.append(blank)
            out.append(lead + result.strip())
            if end + 1 < len(lines) and self.has_text(lines[end + 1]):
                out.append(blank)
            return end - index + 1

        def has_text(self, line):
            return bool(FENCE_QUOTES_RE.sub('', line, count=1).strip())

        def strip_prefix(self, line, depth, indent):
            """Remove a fence's container prefix from one of its lines. Returns None if the line is outside the container."""
            for _ in range(depth):
                match = FENCE_QUOTE_RE.match(line)
                if not match:
                    return None
                line = line[match.end() :]
            spaces = len(line) - len(line.lstrip(' '))
            return line[min(spaces, indent) :]

    class ListIndentPreprocessor(markdown.preprocessors.Preprocessor):
        def run(self, lines):
            out = []
            # Open items, innermost last: (CommonMark content column, Python-Markdown content column).
            items = []
            fence = None  # (fence characters, column shift) while inside a fence.
            after_blank = True
            # Whether the lines since the last blank one began as an item's indented
            #   content. Python-Markdown splits on blank lines first and gives such a
            #   block whole to the item above, so a marker in it needs a blank line first.
            continuation = False
            for line in lines:
                spaces = len(line) - len(line.lstrip(' '))
                if fence:
                    out.append(self.shift(line, spaces, fence[1]))
                    stripped = line.strip()
                    if stripped.startswith(fence[0]) and not stripped.strip(fence[0][0]):
                        fence = None
                    continue
                if not line.strip():
                    out.append(line)
                    after_blank = True
                    continue

                marker = LIST_MARKER_RE.match(line)
                if marker and not self.is_rule(line):
                    while items and spaces < items[-1][0]:
                        items.pop()
                    if items:
                        # Any extra indentation past the parent's text is kept.
                        column = items[-1][1] + spaces - items[-1][0]
                    else:
                        column = spaces
                    items.append((list_content_column(marker), (column // 4 + 1) * 4))
                    if continuation and not after_blank:
                        out.append('')
                    out.append(' ' * column + line[spaces:])
                    after_blank = continuation = False
                    continue

                if after_blank:
                    continuation = bool(items) and spaces >= items[-1][0]

                if items and spaces < items[-1][0] and not after_blank:
                    # A lazy continuation of the paragraph above: leave it be.
                    out.append(line)
                    continue
                while items and spaces < items[-1][0]:
                    items.pop()
                shift = items[-1][1] - items[-1][0] if items else 0
                out.append(self.shift(line, spaces, shift))
                opening = LIST_FENCE_RE.match(line[spaces:])
                if opening:
                    fence = (opening.group(1), shift)
                after_blank = False
            return out

        def shift(self, line, spaces, by):
            return ' ' * max(0, spaces + by) + line[spaces:]

        def is_rule(self, line):
            """A thematic break such as '* * *' looks like a list marker."""
            return bool(re.match(r'^[ ]{0,3}([*_-])(?:[ ]*\1){2,}[ ]*$', line))

    class NestedFenceExtension(markdown.Extension):
        def extendMarkdown(self, md):
            # After whitespace normalization (30), before fenced_code (25). List
            #   indentation first, so fences inside items sit where nested_fence looks.
            md.preprocessors.register(ListIndentPreprocessor(md), 'list_indent', 29)
            md.preprocessors.register(NestedFencePreprocessor(md), 'nested_fence', 28)


class MarkdownBrowserRequestHandler(SimpleHTTPVerboseReqeustHandler):

    server_version = "CoreHttpServer (Markdown Browser)"

    def get_css(self):
        return getattr(self.server, 'data', None) or DEFAULT_CSS + HIGHLIGHT_CSS

    def is_markdown(self, path):
        return os.path.splitext(path)[1].lower() in MARKDOWN_EXTENSIONS

    def guess_type(self, path):
        # Show raw markdown in the browser instead of prompting a download.
        if self.is_markdown(path):
            return 'text/plain; charset=utf-8'
        return super().guess_type(path)

    def query_flag(self, name):
        values = self.get.get(name)
        if values is None:
            # parse_qs() drops blank values, so look for a bare '?name' in the request line.
            query = (getattr(self, common.ATTR_REQUEST_LINE, '').split(' ') + ['', ''])[
                1
            ].partition('?')[2]
            return name in query.split('&')
        return values[-1].lower() not in ('0', 'false', 'no')

    def query_value(self, name):
        values = self.get.get(name)
        return values[-1] if values else ''

    def is_raw_requested(self):
        return self.query_flag('raw')

    def do_GET(self):
        if self.live_reload_enabled() and self.query_flag('events'):
            return self.serve_events(self.file_path)
        return super().do_GET()

    def find_index(self, path):
        try:
            names = {
                n.lower(): n
                for n in os.listdir(path)
                if os.path.isfile(os.path.join(path, n))
            }
        except os.error:
            return None
        for candidate in INDEX_NAMES:
            if candidate in names:
                index_path = os.path.join(path, names[candidate])
                # Apply the same symbolic link rules as a direct request would.
                if common.path_allowed(index_path):
                    return index_path
        return None

    def list_directory(self, path):
        live_token = self.live_state(path)[0]
        table_content = self.render_file_table(path)
        if not table_content:
            # Intentionally keeping the reason for this vague.
            self.send_error(404, "Unable to list directory")
            return None

        displaypath = escape(unquote(getattr(self, common.ATTR_PATH, "/")))
        content = '<div class="listing">%s</div>' % table_content

        index_path = self.find_index(path)
        if index_path:
            body, toc = self.render_markdown(index_path)
            body = '<div class="readme-name">%s</div>%s' % (
                escape(os.path.basename(index_path)),
                body,
            )
            content += '\n    ' + self.render_layout(body, toc, 'readme doc')

        return self.serve_page(
            'Directory listing for %s (%s)'
            % (displaypath, escape(self.base_directory)),
            displaypath,
            content,
            live_token=live_token,
        )

    def render_markdown(self, path):
        """Render a markdown file. Returns a tuple of (body HTML, TOC HTML or None)."""
        with open(path, encoding='utf-8', errors='replace') as f:
            source = f.read()

        if not markdown:
            # Wrap long lines, since this is prose rather than code.
            return (
                '<pre style="white-space: pre-wrap; overflow-wrap: anywhere;">%s</pre>'
                % escape(source),
                None,
            )

        md = markdown.Markdown(
            extensions=MARKDOWN_PLUGINS + [NestedFenceExtension()],
            extension_configs=MARKDOWN_PLUGIN_CONFIGS,
        )
        if args[TITLE_ESCAPE_HTML]:
            md.preprocessors.deregister('html_block')
            md.inlinePatterns.deregister('html')
        body = md.convert(source)

        toc = None
        tokens = getattr(md, 'toc_tokens', [])
        if len(tokens) > 1 or (tokens and tokens[0].get('children')):
            toc = md.toc
        return body, toc

    def render_layout(self, body, toc, doc_class='doc'):
        """Wrap rendered markdown in the centred document layout, with an optional TOC panel."""
        content = '<div class="layout">\n      <div class="%s">%s</div>' % (doc_class, body)
        if toc:
            content += '\n      <nav class="toc-panel">%s</nav>' % toc
        content += '\n    </div>'
        return content

    def serve_file(self, path):
        # Reached after the parent handler's symbolic link checks.
        if (
            os.path.isfile(path)
            and self.is_markdown(path)
            and not self.is_raw_requested()
        ):
            return self.serve_markdown(path)
        return super().serve_file(path)

    def serve_markdown(self, path):
        live_token = self.live_state(path)[0]
        try:
            body, toc = self.render_markdown(path)
        except IOError:
            return self.send_error(404, 'Not Found')

        content = self.render_layout(body, toc)

        displaypath = escape(unquote(getattr(self, common.ATTR_PATH, "/")))
        raw_link = ' <a class="raw" href="%s?raw">View raw</a>' % quote(
            os.path.basename(path)
        )
        title = '%s (%s)' % (escape(os.path.basename(path)), displaypath)
        return self.serve_page(
            title, displaypath, content, raw_link, live_token=live_token
        )

    def get_markdown_tree(self):
        """Returns a tuple of (tree, token). The token changes when the tree does."""
        # Walking a large tree on every request would be slow, so keep the result for a short while.
        cached = getattr(self.server, 'markdown_tree', None)
        now = time.time()
        if cached and now - cached[0] < args[TITLE_TREE_CACHE]:
            return cached[1], cached[2]

        visited = set()
        tree = self.build_markdown_tree(self.base_directory, '/', visited)
        token = digest(tree)
        self.server.markdown_tree = (now, tree, token)
        return tree, token

    def expire_markdown_tree(self, changed_at):
        """Drop the cached tree if it was scanned before changed_at."""
        # Comparing times means that several open pages noticing the same change rescan only once.
        cached = getattr(self.server, 'markdown_tree', None)
        if cached and cached[0] < changed_at:
            self.server.markdown_tree = None

    def build_markdown_tree(self, path, url, visited):
        """Collect directories under path that contain markdown files, directly or further down.
        Returns a dictionary describing the directory, or None if it holds no markdown files.
        """
        real_path = os.path.realpath(path)
        if real_path in visited or len(visited) >= args[TITLE_TREE_MAX_DIRECTORIES]:
            return None
        visited.add(real_path)

        try:
            names = sorted(os.listdir(path), key=lambda n: n.lower())
        except os.error:
            return None

        skip_names = args[TITLE_TREE_SKIP]
        if isinstance(skip_names, str):
            # Defaults are not run through the converter, so the default is still a string.
            skip_names = name_list(skip_names)
        directories = []
        files = []
        for name in names:
            if name.startswith('.') or name in skip_names:
                continue
            full_path = os.path.join(path, name)
            if os.path.islink(full_path) and not common.link_allowed(full_path):
                continue
            if os.path.isdir(full_path):
                child = self.build_markdown_tree(
                    full_path, '%s%s/' % (url, name), visited
                )
                if child:
                    directories.append(child)
            elif os.path.isfile(full_path) and self.is_markdown(full_path):
                files.append((name, url + name))

        if not (directories or files):
            return None
        return {
            'name': os.path.basename(path),
            'url': url,
            'directories': directories,
            'files': files,
        }

    def render_markdown_tree(self, node, current):
        items = []
        for directory in node['directories']:
            # Expand directories leading to the current page.
            expanded = ' open' if current.startswith(directory['url']) else ''
            items.append(
                '<li><details%s><summary><a href="%s">%s/</a></summary>%s</details></li>'
                % (
                    expanded,
                    quote(directory['url']),
                    escape(directory['name']),
                    self.render_markdown_tree(directory, current),
                )
            )
        for name, url in node['files']:
            css_class = ' class="current"' if url == current else ''
            items.append(
                '<li%s><a href="%s">%s</a></li>' % (css_class, quote(url), escape(name))
            )
        return '<ul>%s</ul>' % ''.join(items)

    def serve_page(self, title, displaypath, content, raw_link='', live_token=None):
        tree, tree_token = self.get_markdown_tree()
        if tree:
            tree_content = self.render_markdown_tree(
                tree, getattr(self, common.ATTR_PATH, '/')
            )
        else:
            tree_content = '<p class="nav-empty">No markdown files found.</p>'

        live_meta = live_script = ''
        if live_token and self.live_reload_enabled():
            live_meta = '\n    <meta name="%s" content="?events&amp;v=%s&amp;t=%s">' % (
                LIVE_META,
                live_token,
                tree_token,
            )
            live_script = LIVE_SCRIPT

        values = {
            'title': title,
            'css': self.get_css(),
            'nav_css': NAV_CSS,
            'nav_icon': NAV_TOGGLE_ICON,
            'nav_script': NAV_SCRIPT,
            'live_meta': live_meta,
            'live_script': live_script,
            # render_breadcrumbs() escapes and quotes for itself, so pass the raw path.
            'crumbs': self.render_breadcrumbs(getattr(self, common.ATTR_PATH, '/')),
            'raw_link': raw_link,
            'content': content,
            'tree': tree_content,
        }
        return self.serve_content(PAGE_TEMPLATE % values)

    def live_reload_enabled(self):
        return not args[TITLE_LIVE_RELOAD_OFF]

    def live_state(self, path):
        """Describe what the page for path shows from the file system, for noticing changes.
        Returns a tuple of (page token, signature of the containing directory, directories to watch).
        """
        path = os.path.normpath(path)
        if os.path.isdir(path):
            # Listings change when entries are added, removed or renamed, or when the README changes.
            directory = path
            index = self.find_index(path)
            parts = (stat_signature(path), index)
            watch = {path}
            if index:
                parts += (stat_signature(index), stat_signature(index, False))
                watch.add(os.path.dirname(os.path.realpath(index)))
        else:
            # Both signatures, so that repointing a symbolic link counts as a change.
            directory = os.path.dirname(path)
            parts = (stat_signature(path), stat_signature(path, False))
            watch = {directory, os.path.dirname(os.path.realpath(path))}
        return digest(parts), stat_signature(directory), watch

    def open_watcher(self):
        if INOTIFY and not args[TITLE_LIVE_RELOAD_POLL]:
            try:
                return InotifyWatcher(INOTIFY)
            except OSError as e:
                # Usually the per-user limit on inotify instances (fs.inotify.max_user_instances).
                if not getattr(self.server, 'inotify_warned', False):
                    self.server.inotify_warned = True
                    print_warning(
                        'Unable to start inotify (%s), checking for changes on a timer instead.'
                        % e.strerror
                    )
        return PollWatcher(args[TITLE_LIVE_RELOAD_INTERVAL])

    def write_event(self, text):
        self.wfile.write(text.encode('utf-8'))
        self.wfile.flush()

    def serve_events(self, path):
        """Hold a server-sent event stream open until the page at path or the file tree
        no longer matches the tokens that the page was served with, then send 'change'.
        """
        if os.path.exists(path) and not common.path_allowed(path):
            return self.send_error(404, 'File not found')
        # A missing markdown file is still watched, so that a page whose document was removed refreshes once it returns.
        if not (os.path.isdir(path) or self.is_markdown(path)):
            return self.send_error(404, 'File not found')

        page_token = self.query_value('v')
        tree_token = self.query_value('t')

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        # Ask buffering reverse proxies (such as nginx) to pass events through as they are written.
        self.send_header('X-Accel-Buffering', 'no')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = 1
        if self.command == 'HEAD':
            return None

        watcher = self.open_watcher()
        try:
            self.write_event('retry: %d\n\n' % LIVE_RETRY)

            # Changes to other directories are only seen by rescanning the tree, so follow the tree cache.
            tree_interval = max(args[TITLE_TREE_CACHE], LIVE_WAIT_LIMIT)
            now = time.time()
            heartbeat_at = now + LIVE_HEARTBEAT
            tree_at = now
            last_directory = None

            while self.alive and self.server.alive:
                token, directory, directories = self.live_state(path)
                watcher.watch(directories)
                now = time.time()

                if last_directory is None:
                    last_directory = directory
                elif directory != last_directory:
                    # Something was added, removed or renamed beside the page, which may change the tree.
                    #   Rescan now instead of waiting for the cache to expire.
                    last_directory = directory
                    self.expire_markdown_tree(directory[2] / 1e9 if directory else now)
                    tree_at = now

                changed = token != page_token
                if not changed and now >= tree_at:
                    changed = self.get_markdown_tree()[1] != tree_token
                    tree_at = now + tree_interval

                if changed:
                    # Let the rest of a save land, so that the page does not fetch a half-written file.
                    time.sleep(LIVE_DEBOUNCE)
                    watcher.drain()
                    self.write_event(
                        'event: change\ndata: ?events&v=%s&t=%s\n\n'
                        % (self.live_state(path)[0], self.get_markdown_tree()[1])
                    )
                    # The page closes its stream on 'change' and opens a new one after refreshing.
                    return None

                if now >= heartbeat_at:
                    self.write_event(': ping\n\n')
                    heartbeat_at = now + LIVE_HEARTBEAT

                watcher.wait(min(heartbeat_at, tree_at, now + LIVE_WAIT_LIMIT) - now)
        except OSError:
            # The tab was closed or went to another page.
            pass
        finally:
            watcher.close()
        return None


if __name__ == '__main__':
    args.process(sys.argv)

    common.announce_common_arguments("Serving documentation")
    common.announce_link_arguments()

    if not markdown:
        print_warning(
            'Python %s module not found, markdown will be shown as plain text. Install with: %s'
            % (
                common.colour_text('markdown'),
                common.colour_text('pip install markdown'),
            )
        )
    elif not HtmlFormatter:
        print_notice(
            'Python %s module not found, code blocks will not be highlighted. Install with: %s'
            % (
                common.colour_text('pygments'),
                common.colour_text('pip install pygments'),
            )
        )

    if args[TITLE_ESCAPE_HTML]:
        print_notice('Raw HTML in markdown documents will be escaped.')

    if args[TITLE_LIVE_RELOAD_OFF]:
        print_notice('Live reload is off.')
    elif INOTIFY and not args[TITLE_LIVE_RELOAD_POLL]:
        print_notice(
            'Live reload: watching for changes with %s.' % common.colour_text('inotify')
        )
    else:
        print_notice(
            'Live reload: checking for changes every %s seconds.'
            % common.colour_text(args[TITLE_LIVE_RELOAD_INTERVAL])
        )

    css = None
    if args[TITLE_CSS]:
        with open(args[TITLE_CSS], encoding='utf-8') as f:
            css = f.read()
        print_notice(
            'Using stylesheet: %s'
            % common.colour_text(args[TITLE_CSS], common.COLOUR_GREEN)
        )

    common.serve(MarkdownBrowserRequestHandler, True, data=css)
