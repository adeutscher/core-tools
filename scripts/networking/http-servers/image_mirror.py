#!/usr/bin/env python

# "Scudder" Image Sharing
# This is a more independent version of a Django application that I kludged together for quickly browsing images from another machine.

from __future__ import print_function
import getopt, os, socket, sys, tempfile, urllib
import CoreHttpServer as common
common.local_files.append(os.path.realpath(__file__))

# Used specifically by the image mirror
import getpass, posixpath, re
from random import randint

if sys.version_info[0] == 2:
    from urlparse import unquote
else:
    from urllib.parse import unquote


# Remove unused arguments
common.args.add_validator(common.validate_common_directory) # Validate directory.

# Common fields

image_extensions = ('.png','.jpg', '.jpeg', '.gif')

# Functions and Classes

# Browser
class BrowseController:

    def __init__(self,basePath,path):
        self.path = path
        if not path:
            self.path = ''
        self.realPath = "%s/%s" % tuple([basePath,self.path])

    def getContents(self):
        l = [] # List of sub-directories.
        c = 0 # Count of images.
        try:
            for currentFile in sorted(os.listdir(self.realPath), key=lambda s: s.lower()):
                candidate = [ "%s/%s" % tuple([self.realPath,currentFile]), re.sub(r'^\/*','',"%s/%s" % tuple([self.path,currentFile])),currentFile ]
                if os.path.isdir(candidate[0]):
                    l.append(candidate)
                elif os.path.isfile(candidate[0]) and candidate[0].lower().endswith(image_extensions):
                    c = c + 1
        except Exception as e:
            pass
        return l, c

# Viewer
class ViewController:

    def __get_directory(self):
        return os.path.join(self.baseDirectory, re.sub('^\/+', '', self.relativeDirectory or ''))

    def __get_directoryId(self):
        # If a directory exists, make the path file-name-friendly by replacing and '/' in the path with a '-'
        if not os.path.isdir(self.directory):
            return None
        return "id-" + re.sub(r'/','-',self.relativeDirectory)

    def __get_indexDir(self):
        return os.path.join(self.tempDir, 'tallies')

    def __get_indexFile(self):
        return os.path.join(self.indexDir, self.directoryId)

    def __get_tallyDir(self):
        return os.path.join(self.tempDir, 'indices')

    def __get_tallyFile(self):
        return os.path.join(self.tallyDir, self.directoryId)

    def __init__(self, baseDirectory, relativeDirectory, tempDir, forceRefresh = False, testState = False):

        self.baseDirectory = baseDirectory
        self.relativeDirectory = relativeDirectory
        self.forceRefresh = forceRefresh
        self.tempDir = tempDir

        self.tally = None
        self.makeStructure()

        self.testState = testState

        self.previousDirIndex = 0
        self.nextDirIndex = 0

        try:
            self.makeIndex()
            self.valid = True
        except Exception as e:
            self.valid = False

    directory = property(__get_directory)
    directoryId = property(__get_directoryId)
    indexDir = property(__get_indexDir)
    indexFile = property(__get_indexFile)
    tallyDir = property(__get_tallyDir)
    tallyFile = property(__get_tallyFile)

    def getFilePath(self,targetIndex):
        # Get the file path stored at the 'targetIndex'-th line of the file (very first line is '1')
        line = ''

        # The benefit of having a tally is that we don't need to read all the way through a file to know if we're requesting a valid index.
        if targetIndex < 1 or targetIndex > self.getTally():
            return line

        # confirm initialized values
        previousDirIndex = 0 # Index of first indexed image in previous directory
        currentDir = ""
        currentDirIndex = 0 # Index of first indexed image in current directory
        # Reminder: An INDEX includes a zero value, but a PAGE does not

        # TODO: There has to be a build-in method for getting an arbitrary line from a text file without this cycling.
        # TODO: Directory cycling is still not working quite right. Need to take another look at how this is done at the beginning/end of each file.
        with open(self.indexFile,'r') as fin:
            currentIndex = 0
            lastDir = ""
            while currentIndex < targetIndex:
                line = fin.readline()
                currentIndex = currentIndex + 1

                # Get directory
                lineDir = os.path.dirname(line)

                # If our current line's directory is different than
                #   the previous directory, then throw out the
                #   old previous and mark the current as the new previous.
                if currentDir != lastDir:
                    self.previousDirIndex = currentDirIndex
                    # Note the index of the current directory.
                    currentDir=lineDir
                    currentDirIndex = currentIndex

                lastDir = lineDir
                continue

            targetDir = lineDir

            # We are also noting directories, so
            #     continue until we reach a different directory or the last index
            while currentIndex < self.getTally():
                lineDir = os.path.dirname(fin.readline())
                if lineDir != targetDir:
                    self.nextDirIndex = currentIndex + 1
                    break
                currentIndex = currentIndex + 1
                lastDir = lineDir
            fin.close()
            return line.strip()

    def getImages(self, dir_path):
        directories = [(dir_path,0)]
        # Track visited directories
        # We will be following symbolic links,
        #   but we do not want to revisit the same directory twice or more.
        # This also avoids loops.
        visited_directories = []

        # list of values to be returned
        images = []

        for root, depth in directories:
            if root in visited_directories:
                # Skip visited directory
                continue
            visited_directories.append(os.path.realpath(root))
            try:
                for current_file in sorted(os.listdir(root), key= lambda d: d.lower()):
                    candidate = "%s/%s" % (root, current_file)
                    if os.path.isdir(candidate):
                        directories.append((candidate,depth+1))
                    elif self.isImage(candidate):
                        images.append(candidate)
            except OSError as e:
                # Ignore OS Errors for the moment.
                common.print_exception(e)
                pass
        return images

    def getRandomIndex(self):
        tally = self.getTally()

        # Dodge a ValueError by checking to see the tally did not return 0.
        if tally < 1:
            return 0

        return randint(1,tally)

    def getTally(self):
        # Get our tally count right from the file.

        # Use the stored tally if available.
        if self.tally is not None:
            return self.tally

        try:
            with open(self.tallyFile,'r') as fin:
                tally = int(fin.readline())
                fin.close()
            self.tally = tally
            return tally
        except:
            # If there's any sort of error, just return '0' for now.
            return 0

    def isImage(self,fileName):
        # Crude check to see if the given file name is an image (or some other type that can be immediately rendered in a browser).
        if fileName.lower().endswith(image_extensions):
            return True
        return False

    def makeIndex(self):
        if not self.directoryId:
            return False

        # At this point, directory is confirmed to exist, so it is valid for indexing.

        # Do not generate an index unless there is an explicit need to do so,
        #     as this gets to be more than a bit time-consuming with deeper image directories.
        # This is the reason that we have the index in the first place, and why we store it in tmpfs: To try and make the monster move as quickly as possible.
        if not self.forceRefresh and os.path.isfile(self.tallyFile) and os.path.isfile(self.indexFile):
            return True

        # At this point, we know we have to make an index because a refresh has been requested, or one of the necessary files is missing.

        tally = 0
        with open(self.indexFile,'w') as fout:
            print(self.indexFile)
            for image in self.getImages(self.directory):
                # Strip out double-/, add a newline to the end, and strip away the base directory from the beginning.
                # Line example: /comics/dc/wallpaper-123.png
                line = re.sub(r'/{2,}', "/", "%s\n" % re.sub(r"^"+self.baseDirectory, "", image))
                fout.write(line)
                tally = tally + 1
        # Place our count of images in a convenient place.
        with open(self.tallyFile,'w') as fout:
            # Newline is only for the benefit of debugging.
            fout.write(str(tally) + "\n")
            self.tally = tally

        return True

    def makeStructure(self):
        # Make sure that we have the proper directory structure.
        for d in [i for i in [self.tallyDir, self.indexDir] if not os.path.isdir(i)]:
            os.makedirs(d)

class ImageMirrorRequestHandler(common.CoreHttpServer):

    server_version = "CoreHttpServer (Image Serving)"

    def do_GET(self):
        """Code for GET commands.
        This sends the response code and MIME headers.
        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.
        """

        path = getattr(self, common.ATTR_PATH, "/")
        if path.lower() == "/favicon.ico":
            return self.send_error(404, "File not found.")

        # Get the full path, getting rid of any symbolic links.
        # Reminder: translate_path omits the first "word" in the URL, assuming it to be a keyword such as "browse" or view
        mode, realPath, relativePath = self.translate_path(path)

        if mode == "image":
            target_path = "%s/%s" % (common.get_target(), relativePath)
            return self.serve_file(target_path)
        elif mode == "random":
            # If nothing is specified, boot them back to root browsing...
            if 'path' not in self.get:
                return self.send_redirect("/browse/")
            return self.handle_random(realPath)

        elif mode == "view":
            # We are in view mode, now where do we want to view?

            # If nothing is specified, boot them back to root browsing...
            if 'path' not in self.get:
                return self.send_redirect("/browse/")

            return self.handle_view(realPath)

        elif mode == "browse" or not relativePath:
            if os.path.isdir(realPath):
                if not getattr(self, common.ATTR_PATH, "").endswith("/"):
                    return self.send_redirect(getattr(self, common.ATTR_PATH, ""))
                else:
                    return self.handle_path(relativePath, realPath)
            else:
                return self.serve_content("Directory not found: %s" % realPath, code = 404)

    def get_navigation_javascript(self):
        return """
        <script>
        document.addEventListener("keypress",function(event){
            var destElement = null;
            var destSearch = null
            if(event.charCode == 110){
                // Next page (n)
                console.debug("Looking for next link.")
                destSearch = document.getElementsByClassName("next_link");
            } else if(event.charCode == 112){
                // Previous Page (p)
                console.debug("Looking for previous link.")
                destSearch = document.getElementsByClassName("prev_link");
            } else if(event.charCode == 98){
                // Next Directory (b)
                console.debug("Looking for next directory.")
                destSearch = document.getElementsByClassName("next_dir");
            } else if(event.charCode == 105){
                // Previous Page (p)
                console.debug("Looking for previous directory.")
                destSearch = document.getElementsByClassName("prev_dir");
            } else if(event.charCode == 109){
                // Random (m)
                console.debug("Looking for random link.")
                destSearch = document.getElementsByClassName("random_link");
            } else {
                // Print out character to console if not recognized.
                // Useful for development if I want to add more features in the future.
                console.log("Unknown character code: " + event.charCode);
            }
            console.log(destSearch);
            if(destSearch && destSearch.length > 0){
                console.debug(destSearch[0].href);
                window.location = destSearch[0].href;
            }
        });
        </script>
        """

    def handle_path(self, relativePath, fullPath):
        """Helper to produce a directory listing (absent index.html).
        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for do_GET().
        """
        try:
            bc = BrowseController(common.get_target(), relativePath)
            sub_directories, imageCount = bc.getContents()
        except os.error:
            self.send_error(404, "No permission to list directory")
            return None

        contents = "<p class='title'>%s (%d direct images)</p>" % (relativePath, imageCount)
        contents += "<ul>\n%s\n          </ul>" % "\n".join(["            <li><a href='/browse/%s/'>%s</a> (<a href='/view?path=%s/'>View</a>)" % (entry[1], entry[2], entry[1]) for entry in sub_directories])
        title = relativePath
        if not title:
            title = "."
        return self.serve_content(self.render_page("Image Directory: %s" % os.path.realpath(common.get_target()+"/"+relativePath), self.render_breadcrumbs(relativePath), contents))

    def handle_random(self, realPath):

        # Time-saver shorthand
        path = self.get["path"][0]

        vc = ViewController(realPath, path, self.server.data, forceRefresh=(next(iter(self.get.get('action', [])), None) == "refresh"))
        return self.send_redirect("/view?path=%s&page=%d&source=random" % (path, vc.getRandomIndex()))

    def handle_view(self, realPath):

        # Time-saver shorthand
        path = self.get["path"][0]

        # Get path information
        bc = BrowseController(realPath, path)

        # Confirm our index
        vc = ViewController(realPath, path, self.server.data, forceRefresh=(next(iter(self.get.get('action', [])), None) == "refresh"))
        try:
            page = max(int(self.get["page"][0]), 1)
            # If an exception is thrown, then default our page to 1
        except TypeError:
            # If TypeError, fallback in case the value was not a string or number (e.g. None)
            page = 1
        except ValueError:
            # If ValueError, fallback in case the value was not a parseable string (e.g. "DOOM")
            page = 1
        except KeyError:
            # If KeyError, then page was not provided.
            page = 1

        # Get the path to our image from the index.
        page_path = vc.getFilePath(page)

        # Get a tally of how many pages have been indexed in total.
        tally = vc.getTally()

        # Get the path to our image from the index.
        page_path = vc.getFilePath(page)

        # Navigation links will be at both the top and bottom, so build them in Python.
        nav_links = []
        if page > 1:
            nav_links.append(('prev_link', '/view?path=%s&page=%d' % (path, page - 1), "PREVIOUS"))
        if vc.previousDirIndex > 0:
            nav_links.append(('prev_dir', '/view?path=%s&page=%d' % (path, vc.previousDirIndex), "LAST DIR"))
        nav_links.append(('random_link', '/random?path=%s&origin=%d' % (path, page), "RANDOM"))
        if vc.nextDirIndex > 0:
            nav_links.append(('next_dir', '/view?path=%s&page=%d' % (path, vc.nextDirIndex), "NEXT DIR"))
        if page < tally:
            nav_links.append(('next_link', '/view?path=%s&page=%d' % (path, page + 1), "NEXT"))

        nav_html = "<div>\n"
        for link in nav_links:
            nav_html += "\t\t<a class='%s' href='%s'>%s</a>\n" % link
        nav_html += "<strong>(%d / %d)</strong></div>\n" % (page, tally)

        image_html = '<div class="largeImageWrapper">'
        if next(iter(self.get.get('source', [])), None) == "random":
            # From a random page
            image_html += """<a href="/random?path=%s&path&origin=%d">
                                <img class="largeImage" src="/image%s"/>
                            </a>\n""" % (path, page, page_path)
        elif page < tally:
            # More pages to go
            image_html += """<a href="/view?path=%s&page=%d">
                                <img class="largeImage" src="/image%s"/>
                            </a>\n""" % (path, page + 1, page_path)
        else:
            # No more pages to go, ergo no link.
            image_html += "<img class='largeImage' src='/image%s'/>\n" % (page_path)
        image_html += "</div>"

        path_html = "<p>Viewing: <strong>.%s</strong></p><p>Path: <strong>%s</strong></p><p>Image Dirs:%s</p>" % (page_path, os.path.realpath(common.get_target() + page_path), self.render_breadcrumbs(os.path.dirname(page_path), False))
        return self.serve_content(self.render_page("Image: %s (%s)" % (os.path.basename(page_path), os.path.realpath(os.path.dirname(common.get_target() + page_path))), self.render_breadcrumbs(path), nav_html + image_html + nav_html + path_html, self.get_navigation_javascript()))

    def render_breadcrumbs(self, path, trailer=True):
        current = "/browse/"
        items = [ [ current, "Root" ] ]

        for item in path.split("/"):
            if not item:
                continue

            current += item + "/"
            items.append([current, item])

        i = 0
        content = ""
        for item in items:
            content += " / <a href='%s'>%s</a>" % (item[0], item[1])

        if trailer:
            content += " (<a href='/view?path=%s'>View</a>)" % re.sub(r'^/browse/', '/', items[len(items) - 1][0])
            content += " (<a href='/view?path=%s&action=refresh'>Refresh</a>)" % re.sub(r'^/browse/', '/', items[len(items) - 1][0])

        return content

    def render_page(self, title, breadcrumb_content, entry_content, extra_headers=""):
        return """<!doctype html>
<html>
  <head>
    <title>%s</title>
    <style>
    /* Structure and Wrappers */

    body {
      margin: 25px auto 25px;
      width: 1024px;
    }

    #primaryWrapper {
      border: 2px dashed blue;
    }

    #largeWrapper {
      padding: 15px;
      vertical-align: top;
      width: 975px;
      margin: auto;
    }

    /* Images */

    .largeImage {
      max-width: 100%%;
      margin: auto;
    }

    .largeImageWrapper {
      width: 100%%;
      padding: 0px;
      padding-right: 0px;
      margin: auto;
      text-align: center;
      float: center;
    }
    </style>
    <meta charset='UTF-8'>
    %s
  </head>
  <body id='body'>
    <div id='primaryWrapper'>
      <div id='largeWrapper'>
        <div id='mainWindow'>
          <ul class='breadcrumbList'>
          %s
          </ul>
          %s
        </div>
      </div>
    </div>
  </body>
</html>""" % (title, extra_headers, breadcrumb_content, entry_content)

    def translate_path(self, path):
        """
        Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)
        """

        # abandon query parameters
        path = path.split('?')[0]
        path = path.split('#',1)[0]
        path = posixpath.normpath(unquote(path))
        words = path.split('/')
        words = [_f for _f in words if _f]
        path = common.get_target()

        for word in words[1:]:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (common.get_target(), os.pardir): continue
            path = os.path.join(path, word)
        try:
            dir_path = "/".join(words[1:])
            word = words[0]
        except IndexError:
            dir_path = "/"
            word = "browse"
        return word, path, dir_path

def run(args):
    common.args.process(args)

    common.announce_common_arguments("Sharing images")

    with tempfile.TemporaryDirectory(prefix='image-mirror-%d-' % os.getpid()) as tempFilePath:
        os.chmod(tempFilePath, 0o700)
        common.serve(ImageMirrorRequestHandler, data=tempFilePath)

if __name__ == '__main__':
    run(sys.argv)
