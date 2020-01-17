"""RiveScript Coverage Plugin"""

__author__ = 'Joe Cool'
__email__ = 'snoopyjc@gmail.com'
__version__ = '0.1.0'

from .plugin import RiveScriptPlugin
from .plugin import RiveScriptPluginException       # noqa

def coverage_init(reg, options):
    reg.add_file_tracer(RiveScriptPlugin(options))
