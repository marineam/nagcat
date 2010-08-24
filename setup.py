from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
from twisted.python.dist import getPackages

setup(
    name = "nagcat",
    author = "Michael Marineau",
    author_email = "mmarineau@itasoftware.com",
    license = "Apache 2.0",
    packages = getPackages("python/nagcat") +
               getPackages("python/snapy") +
               getPackages("python/twirrdy"),
    package_dir = {'': "python"},
    ext_modules = [Extension("nagcat._object_parser_c",
                     ["python/nagcat/_object_parser_c.pyx"])],
    cmdclass = {'build_ext': build_ext},
)
