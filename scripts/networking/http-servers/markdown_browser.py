#!/usr/bin/env python3

# Browse a directory of markdown documentation.
# Markdown files are rendered to HTML by default. Append '?raw' to get the source.
# Directory listings show a README/index markdown file underneath the file table.
# Other files are served as-is by the regular file sharing handler.

import os, sys, time
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

# Script Content

TITLE_CSS = 'css'
TITLE_ESCAPE_HTML = 'escape-html'
TITLE_TREE_CACHE = 'tree-cache-seconds'
TITLE_TREE_MAX_DIRECTORIES = 'tree-max-directories'
TITLE_TREE_SKIP = 'tree-skip'

MARKDOWN_EXTENSIONS = ['.md', '.markdown']
MARKDOWN_PLUGINS = ['fenced_code', 'tables', 'toc', 'sane_lists']
INDEX_NAMES = ['readme.md', 'index.md', 'readme.markdown', 'index.markdown']

# File tree sidebar
DEFAULT_TREE_CACHE = 10
DEFAULT_TREE_MAX_DIRECTORIES = 5000
DEFAULT_TREE_SKIP = 'node_modules,__pycache__'

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
      .layout { display: flex; gap: 40px; align-items: flex-start; }
      .doc { flex: 1; min-width: 0; max-width: 900px; }
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
      .readme { margin-top: 30px; border: 1px solid var(--border); border-radius: 6px; padding: 0 25px 10px; }
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
      @media (max-width: 900px) {
        .nav-panel { position: fixed; top: 0; right: 0; bottom: 0; z-index: 10; width: min(85vw, 320px); max-height: none; padding: 65px 15px 15px; background: var(--bg, #ffffff); box-shadow: -4px 0 16px rgba(0,0,0,.25); }
      }
"""

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

PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>%(title)s</title>
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
    </div>%(nav_script)s
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
    if self[TITLE_TREE_MAX_DIRECTORIES] < 1:
        errors.append(
            'Tree directory limit must be at least 1. Given: %s'
            % common.colour_text(self[TITLE_TREE_MAX_DIRECTORIES])
        )
    return errors


args.add_validator(validate_tree)


class MarkdownBrowserRequestHandler(SimpleHTTPVerboseReqeustHandler):

    server_version = "CoreHttpServer (Markdown Browser)"

    def get_css(self):
        return getattr(self.server, 'data', None) or DEFAULT_CSS

    def is_markdown(self, path):
        return os.path.splitext(path)[1].lower() in MARKDOWN_EXTENSIONS

    def guess_type(self, path):
        # Show raw markdown in the browser instead of prompting a download.
        if self.is_markdown(path):
            return 'text/plain; charset=utf-8'
        return super().guess_type(path)

    def is_raw_requested(self):
        values = self.get.get('raw')
        if values is None:
            # parse_qs() drops blank values, so look for a bare '?raw' in the request line.
            query = (getattr(self, common.ATTR_REQUEST_LINE, '').split(' ') + ['', ''])[
                1
            ].partition('?')[2]
            return 'raw' in query.split('&')
        return values[-1].lower() not in ('0', 'false', 'no')

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
            content += (
                '\n    <div class="readme doc"><div class="readme-name">%s</div>%s</div>'
                % (escape(os.path.basename(index_path)), body)
            )

        return self.serve_page(
            'Directory listing for %s' % displaypath, displaypath, content
        )

    def render_markdown(self, path):
        """Render a markdown file. Returns a tuple of (body HTML, TOC HTML or None)."""
        with open(path, encoding='utf-8', errors='replace') as f:
            source = f.read()

        if not markdown:
            return '<pre>%s</pre>' % escape(source), None

        md = markdown.Markdown(extensions=MARKDOWN_PLUGINS)
        if args[TITLE_ESCAPE_HTML]:
            md.preprocessors.deregister('html_block')
            md.inlinePatterns.deregister('html')
        body = md.convert(source)

        toc = None
        tokens = getattr(md, 'toc_tokens', [])
        if len(tokens) > 1 or (tokens and tokens[0].get('children')):
            toc = md.toc
        return body, toc

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
        try:
            body, toc = self.render_markdown(path)
        except IOError:
            return self.send_error(404, 'Not Found')

        content = '<div class="layout">\n      <div class="doc">%s</div>' % body
        if toc:
            content += '\n      <nav class="toc-panel">%s</nav>' % toc
        content += '\n    </div>'

        displaypath = escape(unquote(getattr(self, common.ATTR_PATH, "/")))
        raw_link = ' <a class="raw" href="%s?raw">View raw</a>' % quote(
            os.path.basename(path)
        )
        return self.serve_page(displaypath, displaypath, content, raw_link)

    def get_markdown_tree(self):
        # Walking a large tree on every request would be slow, so keep the result for a short while.
        cached = getattr(self.server, 'markdown_tree', None)
        now = time.time()
        if cached and now - cached[0] < args[TITLE_TREE_CACHE]:
            return cached[1]

        visited = set()
        tree = self.build_markdown_tree(self.base_directory, '/', visited)
        self.server.markdown_tree = (now, tree)
        return tree

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

    def serve_page(self, title, displaypath, content, raw_link=''):
        tree = self.get_markdown_tree()
        if tree:
            tree_content = self.render_markdown_tree(
                tree, getattr(self, common.ATTR_PATH, '/')
            )
        else:
            tree_content = '<p class="nav-empty">No markdown files found.</p>'

        values = {
            'title': '%s (%s)' % (title, escape(self.base_directory)),
            'css': self.get_css(),
            'nav_css': NAV_CSS,
            'nav_icon': NAV_TOGGLE_ICON,
            'nav_script': NAV_SCRIPT,
            # render_breadcrumbs() escapes and quotes for itself, so pass the raw path.
            'crumbs': self.render_breadcrumbs(getattr(self, common.ATTR_PATH, '/')),
            'raw_link': raw_link,
            'content': content,
            'tree': tree_content,
        }
        return self.serve_content(PAGE_TEMPLATE % values)


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

    if args[TITLE_ESCAPE_HTML]:
        print_notice('Raw HTML in markdown documents will be escaped.')

    css = None
    if args[TITLE_CSS]:
        with open(args[TITLE_CSS], encoding='utf-8') as f:
            css = f.read()
        print_notice(
            'Using stylesheet: %s'
            % common.colour_text(args[TITLE_CSS], common.COLOUR_GREEN)
        )

    common.serve(MarkdownBrowserRequestHandler, True, data=css)
