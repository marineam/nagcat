#!/usr/bin/env python

import os
import stat
from glob import glob
from distutils import log
from distutils.core import setup
from distutils.extension import Extension
from distutils.command.build_py import build_py as du_build_py
from twisted.python.dist import getPackages

# distutils doesn't provide a way to make some package data executable
# but nagcat requires a test script for unit testing, so hack time.
package_scripts = ["python/nagcat/unittests/queries/simple_subprocess"]

class build_py(du_build_py):

    def copy_file(self, infile, outfile, **kwargs):
        du_build_py.copy_file(self, infile, outfile, **kwargs)

        # Ripped out of install_scripts, might as well be consistent.
        if os.name == 'posix' and infile in package_scripts:
            if self.dry_run:
                log.info("changing mode of %s", outfile)
            else:
                mode = ((os.stat(outfile)[stat.ST_MODE]) | 0555) & 07777
                log.info("changing mode of %s to %o", outfile, mode)
                os.chmod(outfile, mode)

setup_args = dict(
    name = "nagcat",
    author = "Michael Marineau",
    author_email = "mmarineau@itasoftware.com",
    url = "http://code.google.com/p/nagcat/",
    license = "Apache 2.0",
    packages = getPackages("python/nagcat") +
               getPackages("python/snapy") +
               getPackages("python/twirrdy"),
    package_data = {'nagcat': ["plugins/dropin.cache",
                               "unittests/trend_data*",
                               "unittests/queries/oracle_package.sql",
                               "unittests/queries/simple_subprocess"],
                    'snapy': ["netsnmp/unittests/snmpd.conf"]},
    package_dir = {'': "python"},
    scripts = glob("bin/*"),
    data_files = [('share/doc/nagcat', ["README", "LICENSE"]),
                  ('share/doc/nagcat/docs', glob("docs/*.*"))],
    cmdclass = {'build_py': build_py},
)

# Nagcat works without Cython so make it optional
try:
    from Cython.Distutils import build_ext
    setup_args['ext_modules'] = [Extension("nagcat._object_parser_c",
                                 ["python/nagcat/_object_parser_c.pyx"])]
    setup_args['cmdclass']['build_ext'] = build_ext
except ImportError:
    pass

setup(**setup_args)
