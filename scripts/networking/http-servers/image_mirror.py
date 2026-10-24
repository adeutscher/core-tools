#!/usr/bin/env python

# "Scudder" Image Sharing
# This is a more independent version of a Django application that I kludged together for quickly browsing images from another machine.

from __future__ import print_function
import getopt, os, socket, sys, tempfile, urllib
import CoreHttpServer as common

common.local_files.append(os.path.realpath(__file__))

# Used specifically by the image mirror
import getpass, json, posixpath, re
from random import randint

if sys.version_info[0] == 2:
    from urlparse import unquote
else:
    from urllib.parse import unquote


# Remove unused arguments
common.args.add_validator(common.validate_common_directory)  # Validate directory.
common.add_link_arguments()

# Common fields

image_extensions = ('.png', '.jpg', '.jpeg', '.gif')

DEFAULT_AUTO_MODE_DELAY = 5
TITLE_AUTO_MODE_DELAY = "auto-mode-default-delay"

common.args.add_opt(
    common.OPT_TYPE_LONG,
    TITLE_AUTO_MODE_DELAY,
    TITLE_AUTO_MODE_DELAY,
    "Default number of seconds between image changes in auto mode (minimum: 1).",
    converter=float,
    default=DEFAULT_AUTO_MODE_DELAY,
    default_announce=True,
)


def validate_auto_mode_delay(self):
    errors = []
    delay = self[TITLE_AUTO_MODE_DELAY]
    # Phrased to also reject NaN.
    if not 1 <= delay < float("inf"):
        errors.append(
            "Auto mode delay must be a number of seconds that is at least 1. Given: %s"
            % common.colour_text(delay)
        )
    return errors


common.args.add_validator(validate_auto_mode_delay)

TITLE_PRELOAD = "preload"
common.args.add_opt(
    common.OPT_TYPE_LONG_FLAG,
    TITLE_PRELOAD,
    TITLE_PRELOAD,
    "Have browsers preload the previous and next images to speed up navigation.",
)


def format_seconds(seconds):
    # Display seconds without needless trailing zeroes (e.g. "5" or "2.5").
    return ("%f" % seconds).rstrip("0").rstrip(".")


# Functions and Classes


# Browser
class BrowseController:

    def __init__(self, basePath, path):
        self.path = path
        if not path:
            self.path = ''
        self.realPath = "%s/%s" % tuple([basePath, self.path])

    def getContents(self):
        l = []  # List of sub-directories.
        c = 0  # Count of images.
        try:
            for currentFile in sorted(
                os.listdir(self.realPath), key=lambda s: s.lower()
            ):
                candidate = [
                    "%s/%s" % tuple([self.realPath, currentFile]),
                    re.sub(r'^\/*', '', "%s/%s" % tuple([self.path, currentFile])),
                    currentFile,
                ]
                if os.path.islink(candidate[0]) and not common.link_allowed(
                    candidate[0]
                ):
                    continue
                if os.path.isdir(candidate[0]):
                    l.append(candidate)
                elif os.path.isfile(candidate[0]) and candidate[0].lower().endswith(
                    image_extensions
                ):
                    c = c + 1
        except Exception as e:
            pass
        return l, c


# Viewer
class ViewController:

    def __get_directory(self):
        return os.path.join(
            self.baseDirectory, re.sub(r'^\/+', '', self.relativeDirectory or '')
        )

    def __get_directoryId(self):
        # If a directory exists, make the path file-name-friendly by replacing and '/' in the path with a '-'
        if not os.path.isdir(self.directory):
            return None
        return "id-" + re.sub(r'/', '-', self.relativeDirectory)

    def __get_indexDir(self):
        return os.path.join(self.tempDir, 'tallies')

    def __get_indexFile(self):
        return os.path.join(self.indexDir, self.directoryId)

    def __get_tallyDir(self):
        return os.path.join(self.tempDir, 'indices')

    def __get_tallyFile(self):
        return os.path.join(self.tallyDir, self.directoryId)

    def __init__(
        self,
        baseDirectory,
        relativeDirectory,
        tempDir,
        forceRefresh=False,
        testState=False,
    ):

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

    def getFilePath(self, targetIndex):
        # Get the file path stored at the 'targetIndex'-th line of the file (very first line is '1')
        line = ''

        # The benefit of having a tally is that we don't need to read all the way through a file to know if we're requesting a valid index.
        if targetIndex < 1 or targetIndex > self.getTally():
            return line

        # confirm initialized values
        previousDirIndex = 0  # Index of first indexed image in previous directory
        currentDir = ""
        currentDirIndex = 0  # Index of first indexed image in current directory
        # Reminder: An INDEX includes a zero value, but a PAGE does not

        # TODO: There has to be a build-in method for getting an arbitrary line from a text file without this cycling.
        # TODO: Directory cycling is still not working quite right. Need to take another look at how this is done at the beginning/end of each file.
        with open(self.indexFile, 'r') as fin:
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
                    currentDir = lineDir
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
        directories = [(dir_path, 0)]
        # Track visited directories
        # We will be following symbolic links,
        #   but we do not want to revisit the same directory twice or more.
        # This also avoids loops.
        visited_directories = []

        # list of values to be returned
        images = []

        for root, depth in directories:
            real_root = os.path.realpath(root)
            if real_root in visited_directories:
                # Skip visited directory
                continue
            visited_directories.append(real_root)
            try:
                for current_file in sorted(os.listdir(root), key=lambda d: d.lower()):
                    candidate = "%s/%s" % (root, current_file)
                    if os.path.islink(candidate) and not common.link_allowed(candidate):
                        continue
                    if os.path.isdir(candidate):
                        directories.append((candidate, depth + 1))
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

        return randint(1, tally)

    def getTally(self):
        # Get our tally count right from the file.

        # Use the stored tally if available.
        if self.tally is not None:
            return self.tally

        try:
            with open(self.tallyFile, 'r') as fin:
                tally = int(fin.readline())
                fin.close()
            self.tally = tally
            return tally
        except:
            # If there's any sort of error, just return '0' for now.
            return 0

    def isImage(self, fileName):
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
        if (
            not self.forceRefresh
            and os.path.isfile(self.tallyFile)
            and os.path.isfile(self.indexFile)
        ):
            return True

        # At this point, we know we have to make an index because a refresh has been requested, or one of the necessary files is missing.

        tally = 0
        with open(self.indexFile, 'w') as fout:
            print(self.indexFile)
            for image in self.getImages(self.directory):
                # Store the path relative to the base directory, always with a single leading '/'.
                # Line example: /comics/dc/wallpaper-123.png
                line = "/%s\n" % os.path.relpath(image, self.baseDirectory)
                fout.write(line)
                tally = tally + 1
        # Place our count of images in a convenient place.
        with open(self.tallyFile, 'w') as fout:
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
            # Paths with denied symbolic links will pretend to be 404 errors.
            if not common.path_allowed(target_path):
                return self.send_error(404, "File not found")
            return self.serve_file(target_path)
        elif mode == "api":
            # For API requests, the rest of the URL path names the endpoint rather than a directory.
            if relativePath == "image":
                # JSON description of the Nth (or a random) image in a directory.
                if 'path' not in self.get:
                    return self.serve_json({"error": "No path specified."}, code=400)
                if not self.view_path_allowed():
                    return self.serve_json({"error": "Directory not found."}, code=404)
                return self.handle_api_image(common.get_target())
            return self.serve_json({"error": "Unknown API endpoint."}, code=404)

        elif mode == "random":
            # If nothing is specified, boot them back to root browsing...
            if 'path' not in self.get:
                return self.send_redirect("/browse/")
            if not self.view_path_allowed():
                return self.send_error(404, "File not found")
            return self.handle_random(realPath)

        elif mode == "view":
            # We are in view mode, now where do we want to view?

            # If nothing is specified, boot them back to root browsing...
            if 'path' not in self.get:
                return self.send_redirect("/browse/")
            if not self.view_path_allowed():
                return self.send_error(404, "File not found")

            return self.handle_view(realPath)

        elif mode == "browse" or not relativePath:
            if os.path.isdir(realPath) and common.path_allowed(realPath):
                if not getattr(self, common.ATTR_PATH, "").endswith("/"):
                    return self.send_redirect(getattr(self, common.ATTR_PATH, ""))
                else:
                    return self.handle_path(relativePath, realPath)
            else:
                return self.serve_content(
                    "Directory not found: %s" % realPath, code=404
                )

    def get_navigation_javascript(self, state, random_mode):
        # Escape '</' so that an odd file name cannot close the script tag early.
        initial = json.dumps({"state": state, "random": random_mode}).replace(
            "</", "<\\/"
        )
        auto_delay = json.dumps(common.args[TITLE_AUTO_MODE_DELAY])
        return """
        <script>
        // Currently displayed image, as described by the API, and whether clicking the image picks a random one.
        var current = %s;

        function query(params){
            // Leave '/' readable in directory paths.
            return new URLSearchParams(params).toString().replace(/%%2F/gi, "/");
        }

        function pageHref(page){
            // Regular HTTP equivalent of a navigation target.
            if(page === "random"){
                return "/random?" + query({path: current.state.path, origin: current.state.page});
            }
            return "/view?" + query({path: current.state.path, page: page});
        }

        function viewHref(){
            var params = {path: current.state.path, page: current.state.page};
            if(current.random){
                params.source = "random";
            }
            return "/view?" + query(params);
        }

        function setLink(link, page){
            if(page === null){
                link.removeAttribute("href");
                delete link.dataset.page;
                return;
            }
            link.href = pageHref(page);
            link.dataset.page = page;
        }

        function render(){
            var state = current.state;
            document.title = state.title;

            // Navigation links are at both the top and bottom.
            var navBars = document.getElementsByClassName("navBar");
            for(var i = 0; i < navBars.length; i++){
                var bar = navBars[i];
                bar.textContent = "";
                state.nav.forEach(function(item){
                    var link = document.createElement("a");
                    link.className = item["class"];
                    link.textContent = item.label;
                    setLink(link, item.page);
                    bar.appendChild(link);
                });
                var count = document.createElement("strong");
                count.className = "navCount";
                count.textContent = "(" + state.page + " / " + state.total + ")";
                bar.appendChild(count);
            }

            // Clicking the image moves on to another random image if we arrived randomly, or otherwise to the next page.
            var imagePage = null;
            if(current.random){
                imagePage = "random";
            } else if(state.page < state.total){
                imagePage = state.page + 1;
            }
            setLink(document.getElementById("largeImageLink"), imagePage);
            document.getElementById("largeImage").src = state.image;

            document.getElementById("viewingFile").textContent = "." + state.file;
            document.getElementById("viewingPath").textContent = state.real_path;
            var dirs = document.getElementById("imageDirs");
            dirs.textContent = "";
            state.image_dirs.forEach(function(item){
                dirs.appendChild(document.createTextNode(" / "));
                var link = document.createElement("a");
                link.href = item[0];
                link.textContent = item[1];
                dirs.appendChild(link);
            });
        }

        function showToast(message){
            var toast = document.getElementById("toast");
            if(!toast){
                toast = document.createElement("div");
                toast.id = "toast";
                toast.setAttribute("role", "alert");
                // Tap to dismiss early.
                toast.addEventListener("click", function(){
                    toast.classList.remove("visible");
                });
                document.body.appendChild(toast);
            }
            toast.textContent = message;
            toast.classList.add("visible");
            clearTimeout(toast.timer);
            toast.timer = setTimeout(function(){
                toast.classList.remove("visible");
            }, 5000);
        }

        function goTo(page, random, history_mode, scroll){
            // history_mode: "push" for a new history entry, "replace" to update the current one, or null to leave history alone.
            fetch("/api/image?" + query({path: current.state.path, page: page}))
                .then(function(response){
                    if(!response.ok){
                        throw new Error("Server responded with HTTP " + response.status + ".");
                    }
                    return response.json();
                })
                .then(function(state){
                    current = {state: state, random: random};
                    render();
                    if(history_mode === "push"){
                        history.pushState({page: state.page, random: random}, "", viewHref());
                    } else if(history_mode === "replace"){
                        history.replaceState({page: state.page, random: random}, "", viewHref());
                    }
                    if(scroll){
                        window.scrollTo(0, 0);
                    }
                    whenImageLoaded(scheduleAuto);
                    whenImageLoaded(preloadNeighbours);
                })
                .catch(function(error){
                    // Stay on the current image rather than navigating to a page that may not load (e.g. the server is down).
                    console.error(error);
                    var message = "Unable to load image: " + error.message;
                    if(error instanceof TypeError){
                        // fetch() rejects with a TypeError when the server cannot be reached at all.
                        message = "Unable to reach the server.";
                    }
                    if(autoMode.enabled){
                        setAutoMode(false);
                        message += " Auto mode disabled.";
                    }
                    showToast(message);
                });
        }

        document.addEventListener("click", function(event){
            // Leave middle-clicks and modified clicks (e.g. open in new tab) to the browser.
            if(event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey){
                return;
            }
            var link = event.target.closest("a[data-page]");
            if(!link){
                return;
            }
            event.preventDefault();
            var page = link.dataset.page;
            goTo(page, page === "random", "push", true);
        });

        window.addEventListener("popstate", function(event){
            if(event.state){
                goTo(event.state.page, event.state.random, null, true);
            }
        });

        history.replaceState({page: current.state.page, random: current.random}, "", location.href);

        // Neighbouring images loaded ahead of time (only listed by the server if preloading is enabled).
        // Holding references to them keeps them available for reuse in this page.
        var preloaded = [];

        function preloadNeighbours(){
            preloaded = current.state.preload.map(function(src){
                var image = new Image();
                image.src = src;
                return image;
            });
        }

        document.addEventListener("DOMContentLoaded", function(){
            whenImageLoaded(preloadNeighbours);
        });

        // Auto mode: periodically move on to whatever clicking the image would show.
        var autoMode = {enabled: false, delay: %s, timer: null};

        function whenImageLoaded(callback){
            var image = document.getElementById("largeImage");
            if(image.complete){
                callback();
                return;
            }
            var done = function(){
                image.removeEventListener("load", done);
                image.removeEventListener("error", done);
                callback();
            };
            image.addEventListener("load", done);
            image.addEventListener("error", done);
        }

        function scheduleAuto(){
            clearTimeout(autoMode.timer);
            autoMode.timer = null;
            if(autoMode.enabled){
                autoMode.timer = setTimeout(autoAdvance, autoMode.delay * 1000);
            }
        }

        function autoAdvance(){
            var link = document.getElementById("largeImageLink");
            var page = link.dataset.page;
            if(!page){
                // Reached the last image.
                setAutoMode(false);
                return;
            }
            // Update the current history entry rather than adding one for every change,
            //   and leave the scroll position alone.
            goTo(page, page === "random", "replace", false);
        }

        function setAutoMode(enabled){
            autoMode.enabled = enabled;
            var button = document.getElementById("autoToggle");
            button.textContent = enabled ? "AUTO: ON" : "AUTO: OFF";
            button.setAttribute("aria-pressed", enabled ? "true" : "false");
            scheduleAuto();
            updateWakeLock();
        }

        // Keep the screen awake (no screensaver or lock screen) while auto mode is on.
        // The Screen Wake Lock API is only available in secure contexts (HTTPS, or localhost).
        var wakeLock = {lock: null, pending: false};

        function updateWakeLock(){
            if(!("wakeLock" in navigator)){
                // Auto mode still works, but the screen may sleep.
                if(autoMode.enabled){
                    console.debug("Screen wake lock unavailable (requires HTTPS).");
                }
                return;
            }
            if(autoMode.enabled && !wakeLock.lock && !wakeLock.pending && document.visibilityState === "visible"){
                wakeLock.pending = true;
                navigator.wakeLock.request("screen")
                    .then(function(lock){
                        wakeLock.pending = false;
                        if(!autoMode.enabled){
                            // Auto mode was disabled while the request was pending.
                            lock.release();
                            return;
                        }
                        wakeLock.lock = lock;
                        // The browser releases the lock by itself when the page is hidden.
                        lock.addEventListener("release", function(){
                            if(wakeLock.lock === lock){
                                wakeLock.lock = null;
                            }
                        });
                    })
                    .catch(function(error){
                        wakeLock.pending = false;
                        // Auto mode still works, but the screen may sleep.
                        console.debug("Unable to keep the screen awake for auto mode: " + error.message);
                    });
            } else if(!autoMode.enabled && wakeLock.lock){
                wakeLock.lock.release();
                wakeLock.lock = null;
            }
        }

        // Re-acquire the lock when returning to the page.
        document.addEventListener("visibilitychange", updateWakeLock);

        document.addEventListener("click", function(event){
            if(event.target.closest("#autoToggle")){
                setAutoMode(!autoMode.enabled);
            }
        });

        document.addEventListener("change", function(event){
            if(event.target.id !== "autoDelay"){
                return;
            }
            var delay = parseFloat(event.target.value);
            if(delay >= 1 && isFinite(delay)){
                autoMode.delay = delay;
                scheduleAuto();
            } else {
                // Restore the last valid delay.
                event.target.value = autoMode.delay;
            }
        });

        document.addEventListener("keypress",function(event){
            if(event.target.closest && event.target.closest("input, textarea, select")){
                // Do not hijack typing.
                return;
            }
            var destElement = null;
            var destSearch = null
            if(event.charCode == 97){
                // Auto mode (a)
                setAutoMode(!autoMode.enabled);
            } else if(event.charCode == 110){
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
                destSearch[0].click();
            }
        });
        </script>
        """ % (initial, auto_delay)

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

        contents = "<p class='title'>%s (%d direct images)</p>" % (
            relativePath,
            imageCount,
        )
        contents += "<ul>\n%s\n          </ul>" % "\n".join(
            [
                "            <li><a href='/browse/%s/'>%s</a> (<a href='/view?path=%s/'>View</a>)"
                % (entry[1], entry[2], entry[1])
                for entry in sub_directories
            ]
        )
        title = relativePath
        if not title:
            title = "."
        return self.serve_content(
            self.render_page(
                "Image Directory: %s"
                % os.path.realpath(common.get_target() + "/" + relativePath),
                self.render_breadcrumbs(relativePath),
                contents,
            )
        )

    def view_path_allowed(self):
        # Apply symbolic link rules to the directory named by the 'path' parameter.
        path = self.get["path"][0]
        return common.path_allowed(os.path.join(common.get_target(), path.lstrip('/')))

    def handle_api_image(self, realPath):

        # Time-saver shorthand
        path = self.get["path"][0]

        vc = self.get_view_controller(realPath, path)
        page = self.get_requested_page(vc)
        if not 1 <= page <= vc.getTally():
            return self.serve_json({"error": "Image not found."}, code=404)

        return self.serve_json(self.get_view_state(vc, path, page))

    def handle_random(self, realPath):

        # Time-saver shorthand
        path = self.get["path"][0]

        vc = self.get_view_controller(realPath, path)
        return self.send_redirect(
            "/view?path=%s&page=%d&source=random" % (path, vc.getRandomIndex())
        )

    def handle_view(self, realPath):

        # Time-saver shorthand
        path = self.get["path"][0]

        # Confirm our index
        vc = self.get_view_controller(realPath, path)
        state = self.get_view_state(vc, path, self.get_requested_page(vc))
        page = state["page"]
        tally = state["total"]
        random_mode = next(iter(self.get.get('source', [])), None) == "random"

        # Navigation links will be at both the top and bottom, so build them in Python.
        # The JavaScript in get_navigation_javascript() re-renders them in the same way when switching images.
        nav_html = "<div class='navBar'>\n"
        for item in state["nav"]:
            nav_html += "\t\t<a class='%s' href='%s' data-page='%s'>%s</a>\n" % (
                item["class"],
                self.get_page_href(path, page, item["page"]),
                item["page"],
                item["label"],
            )
        nav_html += "<strong class='navCount'>(%d / %d)</strong></div>\n" % (
            page,
            tally,
        )

        # Clicking the image moves on to another random image if we arrived randomly, or otherwise to the next page.
        image_page = None
        if random_mode:
            image_page = "random"
        elif page < tally:
            image_page = page + 1

        image_link = ""
        if image_page is not None:
            image_link = " href='%s' data-page='%s'" % (
                self.get_page_href(path, page, image_page),
                image_page,
            )
        image_html = (
            "<div class='largeImageWrapper'><a id='largeImageLink'%s><img id='largeImage' class='largeImage' src='%s'/></a></div>\n"
            % (image_link, state["image"])
        )

        auto_html = (
            "<div class='autoBar'><button type='button' id='autoToggle' aria-pressed='false'>AUTO: OFF</button><label class='autoDelay'>Every <input type='number' id='autoDelay' min='1' step='any' inputmode='decimal' value='%s'> seconds</label></div>\n"
            % format_seconds(common.args[TITLE_AUTO_MODE_DELAY])
        )

        path_html = (
            "<p>Viewing: <strong id='viewingFile'>.%s</strong></p><p>Path: <strong id='viewingPath'>%s</strong></p><p>Image Dirs:<span id='imageDirs'>%s</span></p>"
            % (
                state["file"],
                state["real_path"],
                self.render_breadcrumbs(os.path.dirname(state["file"]), False),
            )
        )
        # Reminder of the keyboard shortcuts handled in get_navigation_javascript().
        shortcuts_html = "<p class='shortcuts'>Shortcuts: %s</p>" % ", ".join(
            [
                "<kbd>%s</kbd> %s" % item
                for item in [
                    ("p", "previous"),
                    ("n", "next"),
                    ("i", "last dir"),
                    ("b", "next dir"),
                    ("m", "random"),
                    ("a", "auto mode toggle"),
                ]
            ]
        )

        return self.serve_content(
            self.render_page(
                state["title"],
                self.render_breadcrumbs(path),
                nav_html
                + image_html
                + nav_html
                + auto_html
                + path_html
                + shortcuts_html,
                self.get_navigation_javascript(state, random_mode),
            )
        )

    def get_page_href(self, path, origin, page):
        # Regular HTTP equivalent of a navigation target.
        if page == "random":
            return "/random?path=%s&origin=%d" % (path, origin)
        return "/view?path=%s&page=%d" % (path, page)

    def get_requested_page(self, vc):
        value = next(iter(self.get.get('page', [])), None)
        if value == "random":
            return vc.getRandomIndex()
        try:
            return max(int(value), 1)
        except (TypeError, ValueError):
            # Default to page 1 if no page was provided (None) or it was not a parseable string (e.g. "DOOM")
            return 1

    def get_view_controller(self, realPath, path):
        return ViewController(
            realPath,
            path,
            self.server.data,
            forceRefresh=(next(iter(self.get.get('action', [])), None) == "refresh"),
        )

    def get_view_state(self, vc, path, page):
        # Describe the image at the given page. This is served as-is by the API.

        # Get the path to our image from the index.
        # This must be done first, as it also notes where the neighbouring directories start.
        page_path = vc.getFilePath(page)

        # Get a tally of how many pages have been indexed in total.
        tally = vc.getTally()

        nav = []
        if page > 1:
            nav.append({"class": "prev_link", "page": page - 1, "label": "PREVIOUS"})
        if vc.previousDirIndex > 0:
            nav.append(
                {"class": "prev_dir", "page": vc.previousDirIndex, "label": "LAST DIR"}
            )
        nav.append({"class": "random_link", "page": "random", "label": "RANDOM"})
        if vc.nextDirIndex > 0:
            nav.append(
                {"class": "next_dir", "page": vc.nextDirIndex, "label": "NEXT DIR"}
            )
        if page < tally:
            nav.append({"class": "next_link", "page": page + 1, "label": "NEXT"})

        # Neighbouring images for the browser to load ahead of time, next image first.
        # This must come after building the navigation, as getFilePath() also resets the neighbouring directory indices.
        preload = []
        if common.args[TITLE_PRELOAD]:
            preload = [
                "/image%s" % vc.getFilePath(p)
                for p in (page + 1, page - 1)
                if 1 <= p <= tally
            ]

        return {
            "path": path,
            "page": page,
            "total": tally,
            "image": "/image%s" % page_path,
            "file": page_path,
            "real_path": os.path.realpath(common.get_target() + page_path),
            "title": "Image: %s (%s)"
            % (
                os.path.basename(page_path),
                os.path.realpath(os.path.dirname(common.get_target() + page_path)),
            ),
            "image_dirs": self.get_breadcrumb_items(os.path.dirname(page_path)),
            "nav": nav,
            "preload": preload,
        }

    def get_breadcrumb_items(self, path):
        current = "/browse/"
        items = [[current, "Root"]]

        for item in path.split("/"):
            if not item:
                continue

            current += item + "/"
            items.append([current, item])

        return items

    def render_breadcrumbs(self, path, trailer=True):
        items = self.get_breadcrumb_items(path)

        content = ""
        for item in items:
            content += " / <a href='%s'>%s</a>" % (item[0], item[1])

        if trailer:
            content += " (<a href='/view?path=%s'>View</a>)" % re.sub(
                r'^/browse/', '/', items[len(items) - 1][0]
            )
            content += " (<a href='/view?path=%s&action=refresh'>Refresh</a>)" % re.sub(
                r'^/browse/', '/', items[len(items) - 1][0]
            )

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

    /* Navigation */

    .navBar {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: center;
      gap: 12px;
      margin: 30px 0px;
    }

    .navBar a {
      display: inline-block;
      min-width: 90px;
      min-height: 48px;
      line-height: 48px;
      padding: 0px 20px;
      font-size: 1.2em;
      font-weight: bold;
      text-align: center;
      text-decoration: none;
      color: #fff;
      background-color: #2a5db0;
      border-radius: 8px;
      box-sizing: border-box;
    }

    .navBar a:hover, .navBar a:focus {
      background-color: #1d4280;
    }

    .shortcuts {
      color: #666;
    }

    .shortcuts kbd {
      padding: 1px 6px;
      border: 1px solid #999;
      border-radius: 4px;
    }

    .navCount {
      font-size: 1.2em;
      padding: 0px 10px;
    }

    .autoBar {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: center;
      gap: 12px;
      margin: 0px 0px 30px;
    }

    #autoToggle {
      min-width: 140px;
      min-height: 48px;
      padding: 0px 20px;
      font-family: inherit;
      font-size: 1.2em;
      font-weight: bold;
      color: #fff;
      background-color: #666;
      border: none;
      border-radius: 8px;
      cursor: pointer;
    }

    #autoToggle[aria-pressed='true'] {
      background-color: #2a8a3e;
    }

    .autoDelay {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 1.2em;
    }

    .autoDelay input {
      width: 5em;
      min-height: 48px;
      padding: 0px 8px;
      font-family: inherit;
      font-size: 1em;
      box-sizing: border-box;
      border: 2px solid #2a5db0;
      border-radius: 8px;
    }

    .autoDelay input:invalid {
      border-color: #c0392b;
    }

    #toast {
      position: fixed;
      left: 0px;
      right: 0px;
      bottom: 20px;
      margin: 0px auto;
      width: fit-content;
      max-width: calc(100%% - 32px);
      box-sizing: border-box;
      padding: 14px 20px;
      font-size: 1.1em;
      color: #fff;
      background-color: #c0392b;
      border-radius: 8px;
      box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.3);
      cursor: pointer;
      opacity: 0;
      visibility: hidden;
      transition: opacity 0.3s, visibility 0.3s;
    }

    #toast.visible {
      opacity: 1;
      visibility: visible;
    }

    @media (max-width: 1024px) {
      body {
        width: auto;
        margin: 10px;
      }

      #largeWrapper {
        width: auto;
        padding: 8px;
      }

      .navBar a {
        flex: 1 1 40%%;
        min-height: 56px;
        line-height: 56px;
      }
    }
    </style>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
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

    def serve_json(self, data, code=200):
        return self.serve_content(
            json.dumps(data), code=code, mimetype="application/json"
        )

    def translate_path(self, path):
        """
        Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)
        """

        # abandon query parameters
        path = path.split('?')[0]
        path = path.split('#', 1)[0]
        path = posixpath.normpath(unquote(path))
        words = path.split('/')
        words = [_f for _f in words if _f]
        path = common.get_target()

        for word in words[1:]:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (common.get_target(), os.pardir):
                continue
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
    common.announce_link_arguments()
    if common.args[TITLE_PRELOAD]:
        common.print_notice("Browsers shall preload the previous and next images.")

    with tempfile.TemporaryDirectory(
        prefix='image-mirror-%d-' % os.getpid()
    ) as tempFilePath:
        os.chmod(tempFilePath, 0o700)
        common.serve(ImageMirrorRequestHandler, data=tempFilePath)


if __name__ == '__main__':
    run(sys.argv)
