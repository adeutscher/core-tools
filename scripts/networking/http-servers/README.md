
# HTTP Server Scripts

Extensions of BaseHttpServer to serve HTTP content.

# Making More HTTP Scripts

When making a new HTTP script using the common codebase, it's recommended
  to copy an existing script that is somewhat close to what you need.

If the new script is not in this directory, you can add this the directory to
  your path.

Example:

    import os, sys
    tools_dir = os.environ.get("toolsDir")
    if tools_dir:
        sys.path.append(tools_dir + "/scripts/networking/http-servers")
    import CoreHttpServer as common

# History

I originally had two HTTP scripts scripts which were entirely standalone.
  However, after I needed to make a third script in another module,
  I decided to break my standalone script policy and store things in a
  common file. While I would prefer to have scripts in this directory stand
  on their own for easy extraction, three scripts pushed things over the
  limit (and the two were large enough to be outstaying their welcome to begin with...)
