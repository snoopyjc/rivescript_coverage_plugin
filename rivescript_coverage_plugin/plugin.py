"""The RiveScript coverage plugin."""
# Written by @snoopyjc 2020-01-16
# Based on Coverage RiveScript Plugin by nedbat with changes by PamelaM
# v0.2.0

# It's not pretty in places but it works!!

import datetime
import os.path
import re
import sys
import inspect
import importlib
import shutil

#import six

import coverage.plugin
from rivescript import RiveScript
from rivescript.inheritance import get_topic_tree
from rivescript.python import PyRiveObjects

class RiveScriptPluginException(Exception):
    """Used for any errors from the plugin itself."""
    pass


# For debugging the plugin itself.
SHOW_PARSING = False
SHOW_TRACING = False
SHOW_STARTUP = False
CLEAN_RS_OBJECTS = True
LOG_FILE_PATH = None
RS_DIR = "_rs_objects_"     # Where we keep files that represent rivescript python object blocks
RS_PREFIX = "rs_obj_"

class RiveScriptOptionsCapture:
    def __init__(self):
        """Capture the RiveScript options and directory locally by monkeypatching the code"""
        RiveScript._old_init = RiveScript.__init__
        RiveScript._old_load_directory = RiveScript.load_directory
        RiveScript._old_load_file = RiveScript.load_file
        RiveScript._old_say = RiveScript._say
        self.rs_initialized = False
        self.debug_callback = None
        self._debug = False
        def _new_rs_init(rs_self, *args, **kwargs):
            for k in kwargs:
                setattr(self, k, kwargs[k])
            rs_self._old_init(*args, **kwargs)
            self._debug = rs_self._debug
            rs_self._debug = True
            self.rs = rs_self
        def _new_load_directory(rs_self, directory, ext=None):
            self.directory = directory
            if not ext:
                ext = ('.rive', '.rs')
            if type(ext) == str:
                ext = [ext]
            self.ext = ext
            self.rs_initialized = True
            rs_self._old_load_directory(directory, ext)

        def _new_load_file(rs_self, filename):
            fr = FileReporter(filename)
            fr.lines()      # Compute the set of executable lines, which in turn sets trigger_source for the file
            rs_self._old_load_file(filename)

        def _new_say(rs_self, message):
            if self.debug_callback:
                if self._debug:
                    rs_self._old_say(message)
                self.debug_callback(message)
            elif self._debug:
                rs_self._old_say(message)

        def _new_load(py_obj_self, name, code):
            """Replace the PyRiveObjects.load function to instead create a temp file
            of the code, so we can trace it.  Later we grab the trace data and remap it
            back to the '> object'
            """
            os.makedirs(RS_DIR, exist_ok=True)
            with open(os.path.join(RS_DIR, '__init__.py'), 'w') as f:
                pass
            module = f'{RS_PREFIX}{name}'
            filename = os.path.join(RS_DIR, module + '.py')
            with open(filename, 'w', encoding="utf-8") as f:
                print(f'def {module}(rs, args):', file=f)
                # Use our code instead of their code because they delete blank lines,
                # making it hard to match up the executed line numbers!
                if name in object_source:
                    fn, lno = object_source[name]
                    if fn in rs_lexed:
                        lexer = rs_lexed[fn]
                        tokens = lexer.tokenize()
                        if lno in lexer.lineno_to_token_index:
                            ndx = lexer.lineno_to_token_index[lno]
                            token = tokens[ndx]
                            code = token.extra['code']
                for line in code:
                    print(f'\t{line.rstrip()}', file=f)
            try:
                importlib.invalidate_caches()
                mod = importlib.import_module(f'{RS_DIR}.{module}')
                py_obj_self._objects[name] = getattr(mod, module)   # func
            except Exception as e:
                print("Failed to load code from object", name)
                print("The error given was: ", e)

        RiveScript.__init__ = _new_rs_init
        RiveScript.load_directory = _new_load_directory
        RiveScript.load_file = _new_load_file
        RiveScript._say = _new_say

        PyRiveObjects.load = _new_load

rs_options = RiveScriptOptionsCapture()     # Do the monkeypatch right away

trigger_source = {}     # map from [topic:]trigger to (filename, lineno) or a list of them with a regexp of prev match
object_source = {}      # map from object name to (filename, lineno)
rs_lexed = {}           # map from filename to Lexer
rs_line_data = {}       # { filename: { lineno: None, ... }, ...}
coverage_object = None

def get_trigger_source(rs, user, trigger, last_topic, last_reply):
    """Get the filename and line number of the trigger that last matched.  This is harder than is seems!"""
    #print(f'get_trigger_source(rs, {user}, {trigger}, {last_topic}, {last_reply})')

    if last_topic == 'random':
        all_topics = [last_topic]
    else:
        all_topics = get_topic_tree(rs, last_topic)     # Handle topic inheritance and includes

    last_reply_formatted = False
    for topic in all_topics:
        tr = trigger
        if topic and topic != 'random':
            tr = f'{topic}:{trigger}'

        if tr in trigger_source:
            value = trigger_source[tr]
            if not isinstance(value, list):
                value = [value]

            if last_reply:
                # First look for triggers with a "% prev" that matches ours
                for i in range(len(value)):
                    flp = value[i]
                    #print(f'flp = {flp}')
                    if len(flp) == 3:
                        if not last_reply_formatted:        # Only do this once and if we need it
                            last_reply = rs._brain.format_message(last_reply, botreply=True)
                            #print(f'last_reply formatted = "{last_reply}"')
                            last_reply_formatted = True
                        f, l, p = flp
                        #print(f'checking {flp}')
                        if isinstance(p, str):
                            if '<get ' in p or '<bot ' in p:        # If we refer to user or bot vars, then we can't save the regexp
                                p = rs._brain.reply_regexp(user, p)
                            else:
                                p = rs._brain.reply_regexp(user, p)
                                value[i] = [f, l, p]
                        #print(p)
                        match = re.match(p, last_reply)
                        if match:
                            #print(f'matched: returning ({f}, {l})')
                            return (f, l)
            # Then handle the normal case
            for fl in value:
                if len(fl) == 2:
                    #print(f'returning {fl}')
                    return fl

    #print(f'returning None')
    return None


def print_log(*args, **kwargs):
    """ Print logging message, either appending to the LOG_FILE_PATH or to stdout."""
    log_file = None
    try:
        if LOG_FILE_PATH:
            log_file = open(LOG_FILE_PATH, "a")
        kwargs['file'] = log_file if log_file else sys.stdout
        print(*args, **kwargs)
    finally:
        if log_file:
            log_file.close()


def get_debug_option_value(curr_value, options, option_name):
    """Common handling of debug options.
    - If the current value is truthy, then ignore the option value  All
    current values should default to falsy, so they will only be truthy
    when someone is debugging the plugin code
    - If the requested option name isn't in the options, then use the default
    (aka current) value.
    :param  curr_value  Initial value of option
    :param  options     Dictionary of options passed in from coverage.py
    :param  option_name Key name of option in 'options' dict
    :returns option value
    """
    #if curr_value:
        #if option_name:
            #print_log(
                #"Ignoring options '%s', already set to %s" % (option_name, curr_value)
            #)
        #return curr_value

    value = options.get(option_name, curr_value)
    # Be permissive wrt boolean configuration values
    if isinstance(value, str):
        v = value.lower()
        if v in ("f", "false", "no", "n", 0):
            value = False
        elif v in ("t", "true", "yes", "y", 1):
            value = True
    return value


def handle_debugging_options(options):
    """Set global debugging flags based on configuration options"""
    global LOG_FILE_PATH, SHOW_PARSING, SHOW_TRACING, SHOW_STARTUP, CLEAN_RS_OBJECTS
    #print("handle_debugging_options: %r" % options)
    LOG_FILE_PATH = get_debug_option_value(LOG_FILE_PATH, options, 'log_file_path')
    SHOW_PARSING = get_debug_option_value(SHOW_PARSING, options, 'show_parsing')
    SHOW_TRACING = get_debug_option_value(SHOW_TRACING, options, 'show_tracing')
    SHOW_STARTUP = get_debug_option_value(SHOW_STARTUP, options, 'show_startup')
    CLEAN_RS_OBJECTS = get_debug_option_value(CLEAN_RS_OBJECTS, options, 'clean_rs_objects')
    if SHOW_STARTUP:
        print_log("--- RiveScript_coverage_plugin started at %s ---" % datetime.datetime.now())
        print_log("Python Version: %s" % (sys.version,))
        print_log("RiveScript Version: %s" % (RiveScript.VERSION(),))
        print_log("command args  : %s" % (sys.argv,))


def get_brain_dir():
    """Get the Brain Directory that the RiveScript object is using.
    It can take a fair amount of time before the RiveScript settings are fully
    configured, so get_brain_dir() is called by file_tracer() until it
    returns something.
    Returns the path to the brain, None otherwise
    """

    if rs_options.rs_initialized:
        #if not rs_options._debug:
            #raise RiveScriptPluginException("RiveScript debug option must be enabled!")
        return rs_options.directory

    return None


def filename_for_frame(frame):
    try:
        return frame.f_globals.get('__file__')
    except (KeyError, AttributeError):
        return None

def position_for_node(node):    # Not used
    try:
        return node.token.position
    except AttributeError:
        return None

def position_for_token(token):  # Not used
    return token.position

def read_template_source(filename):
    """Read the source of a RiveScript template, returning the Unicode text."""

    try:                    # v0.2.0: Issue #3
        with open(filename, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception:       # v0.2.0: Issue #3
        text = ''           # v0.2.0: Issue #3

    return text


class RE:       # Borrowed from rivescript/regexp.py
    equals      = re.compile('\s*=\s*')
    ws          = re.compile('\s+')
    space       = re.compile('\\\\s')
    objend      = re.compile('^\s*<\s*object')
    crlf        = re.compile('<crlf>')
    get_reply_to_user = re.compile(r"Get reply to \[([^]]*)\] .*$")
    try_to_match = re.compile(r"^Try to match '[^']*' against '([^']+)'.*$")
    now_try_to_match = re.compile(r"^Now try to match .* to (.+)$")
    reply       = re.compile(r'^Reply: (.*)$')
    checking_topic = re.compile(r"^Checking topic (.+) for any %Previous's\.$")
    conditional = re.compile(r"^Left: ([^;]*); eq: ([^;]*); right: (.*) => (.*)$")
    #call = re.compile(r"<call>([^\s<]+)")

class RiveScriptPlugin(
    coverage.plugin.CoveragePlugin,
    coverage.plugin.FileTracer,
):

    def __init__(self, options):
        # This is actually called twice, once at the start of collection, and once at the end.  Use that fact to write out the results
        global coverage_object
        handle_debugging_options(options)
        if coverage_object is None:
            try:
                from coverage import Coverage
                stack = inspect.stack()
                for frame in stack:
                    if 'self' in frame.frame.f_locals and isinstance(frame.frame.f_locals['self'], Coverage):
                        coverage_object = frame.frame.f_locals['self']
                        if SHOW_STARTUP:
                            print_log("RiveScriptPlugin: found Coverage object")
                        break
            finally:
                del stack
        if coverage_object:
            config = coverage_object.config
            omit_rs = f'{RS_DIR}/*'
            if config.report_omit:
                config.report_omit.append(omit_rs)
            else:
                config.report_omit = [omit_rs]

        if rs_line_data:
            cd = coverage_object.get_data()
            self.move_executed_rs_objects_to_rive(cd)
            if CLEAN_RS_OBJECTS:
                self.clean_rs_objects(cd)
            file_tracers = {}
            for fn in rs_line_data:
                file_tracers[fn] = 'rivescript_coverage_plugin.RiveScriptPlugin'
            cd.add_lines(rs_line_data)
            cd.add_file_tracers(file_tracers)
        if SHOW_STARTUP:
            print_log("RiveScriptPlugin.__init__")
        #self.debug_checked = False

        self.rs_brain_dir = None
        self.rs_brain_abspath = None

        self.source_map = {}
        self.topic = 'random'
        self.last_reply = '<undef>'

    # --- CoveragePlugin methods

    def sys_info(self):
        return [
            ("rs_brain_dir", self.rs_brain_dir),
        ]

    def move_executed_rs_objects_to_rive(self, cd):
        """In order to figure out what lines of '> object' blocks were executed, we created files
        out of them so the tracer could find them.  Here we move the coverage info back into
        the .rive files where the objects are actually defined."""
        global object_source, rs_line_data
        for name in object_source:
            fn, lno = object_source[name]
            filename = os.path.abspath(os.path.join(RS_DIR, f'{RS_PREFIX}{name}.py'))
            lines = cd.lines(filename)
            if lines is None:
                continue
            rive_file = os.path.abspath(fn)
            for line in lines:
                if line == 1:       # v0.2.0: Issue 4: ignore hit on 'def NAME():' line
                    continue        # v0.2.0: Issue 4
                nl = lno + line - 1
                if rive_file in rs_line_data:
                    rs_line_data[rive_file][nl] = None
                else:
                    rs_line_data[rive_file] = {nl: None}

    def clean_rs_objects(self, cd):
        """Clean up source files we created in the _rs_objects_ folders now that we are done with them"""
        try:
            shutil.rmtree(RS_DIR)
            # We really need to delete them from the sqldata, but there is no API to do that!
            #for f in cd.measured_files():
                #if RS_DIR in f:
                    #del cd._file_map[f]
        except Exception as e:
            print(f"Cannot clean up {RS_DIR}: {e}")

    def debug_callback(self, message):
        """Handle the RiveScript debug message by figuring out which source line(s) were executed and marking same"""
        global object_source
        if SHOW_TRACING:
            if message.startswith(' ') or message.startswith('\t') or message.startswith('Line:') or message.startswith('Loading file') or \
               message.startswith('Parsing ') or message.startswith('Command:') or message.startswith('Sorting ') or message.startswith('Analyzing '):
                pass        # Skip stuff we ignore anyway
            else:
                print_log(f'debug_callback({message})')
        if message == 'Found a match!':
            fn_lno = get_trigger_source(rs_options.rs, self.user, self.last_trigger, self.last_topic, self.last_reply)
            if SHOW_TRACING:
                print_log(f'debug_callback: found {self.last_trigger} on {fn_lno}')
            if fn_lno:
                fn, lineno = fn_lno
                self.filename = os.path.abspath(fn)
                self.last_trigger_lineno = lineno
                if self.filename in rs_line_data:
                    rs_line_data[self.filename][lineno] = None
                else:
                    rs_line_data[self.filename] = {lineno: None}
                # This is smart enough to just do it once:
                lexer = Lexer(None, self.filename)
                tokens = lexer.tokenize()
                if lineno in lexer.lineno_to_token_index:
                    ndx = lexer.lineno_to_token_index[lineno] + 1
                    while ndx < len(tokens):        # If the trigger is continued or has a %Prev, mark them as executed too
                        token = tokens[ndx]
                        if token.token_type in (TOKEN_CONTINUE, TOKEN_PREVIOUS):
                            rs_line_data[self.filename][token.lineno] = None
                        else:
                            break
                        ndx += 1
        elif message.startswith('Get reply to ['):
            mo = re.match(RE.get_reply_to_user, message)
            if mo:
                self.user = mo.group(1)
        elif message.startswith('Try to match'):            # Normal trigger match
            mo = re.match(RE.try_to_match, message)
            if mo:
                self.last_trigger = mo.group(1)
                self.prev_match = False
                self.conditional = None
        elif message.startswith('Now try to match'):        # Trigger match with %Previous already matched
            mo = re.match(RE.now_try_to_match, message)
            if mo:
                self.last_trigger = mo.group(1)
                self.conditional = None
        elif message.startswith('lastReply: '):
            self.last_reply = message[len('lastReply: '):]
        elif message.startswith('Reply:'):
            mo = re.match(RE.reply, message)
            if mo:
                reply = mo.group(1)
                lexer = Lexer(None, self.filename)
                tokens = lexer.tokenize()
                if self.last_trigger_lineno in lexer.lineno_to_token_index:
                    ndx = lexer.lineno_to_token_index[self.last_trigger_lineno] + 1
                    found = False
                    while ndx < len(tokens):
                        token = tokens[ndx]
                        if found: 
                            if token.token_type == TOKEN_CONTINUE:
                                rs_line_data[self.filename][token.lineno] = None
                            else:
                                break
                        elif token.token_type == TOKEN_CONDITION and token.extra == self.conditional:
                            rs_line_data[self.filename][token.lineno] = None
                            found = True
                        elif token.token_type == TOKEN_REPLY and token.extra == reply:
                            rs_line_data[self.filename][token.lineno] = None
                            found = True
                        elif token.token_type in (TOKEN_TRIGGER, TOKEN_OBJECT, TOKEN_LABEL, TOKEN_DEF): # Didn't find it
                            if SHOW_TRACING:
                                print_log(f"Didn't find reply '{reply}' for {self.last_trigger} near {self.filename}:{self.last_trigger_lineno}")
                            break
                        ndx += 1
                elif SHOW_TRACING:
                    print_log(f"Didn't find line {self.last_trigger_lineno} of {self.filename} in lineno_to_token_index")
            # We don't have to do this any more now that we have real coverage in objects
            #mo = re.search(RE.call, reply)  # If this is an object call, mark the object declaration as executed
            #if mo:
                #obj = mo.group(1)
                #if obj in object_source:
                    #fn, lno = object_source[obj]
                    #rs_line_data[os.path.abspath(fn)][lno] = None

            if SHOW_TRACING:
                print_log(f"Lines marked as executable in {self.filename} are now {rs_line_data[self.filename]}")
            self.last_reply = reply
        elif message.startswith('Checking topic '):
            mo = re.match(RE.checking_topic, message)
            if mo:
                self.last_topic = mo.group(1)
                self.prev_match = False
                self.conditional = None
        elif message == 'Bot side matched!':    # last_reply matched the %previous
            self.prev_match = True
        elif message.startswith("Redirecting us to "):
            lexer = Lexer(None, self.filename)
            tokens = lexer.tokenize()
            if self.last_trigger_lineno in lexer.lineno_to_token_index:
                ndx = lexer.lineno_to_token_index[self.last_trigger_lineno] + 1
                while ndx < len(tokens):
                    token = tokens[ndx]
                    if token.token_type == TOKEN_REDIRECT:
                        rs_line_data[self.filename][token.lineno] = None    # Mark it as executed
                    elif token.token_type in (TOKEN_TRIGGER, TOKEN_OBJECT, TOKEN_LABEL, TOKEN_DEF): # Didn't find it
                        break
                    ndx += 1
                if SHOW_TRACING:
                    print_log(f"Lines marked as executable in {self.filename} are now {rs_line_data[self.filename]}")
            elif SHOW_TRACING:
                print_log(f"Didn't find line {self.last_trigger_lineno} of {self.filename} in lineno_to_token_index")

        elif message.startswith("Left: "):
            mo = re.match(RE.conditional, message)
            if mo:
                self.conditional = f'{mo.group(1)} {mo.group(2)} {mo.group(3)} => {mo.group(4)}'

    def file_tracer(self, filename):
        if SHOW_STARTUP and not filename.endswith(".py"):
            print_log("file_tracer: %s" % filename)
        if self.rs_brain_dir is None:
            # Keep calling get_brain_dir until it returns the path to the brain, which it
            # will only do after settings have been configured
            self.rs_brain_dir = get_brain_dir()
            if self.rs_brain_dir:
                self.rs_brain_abspath = os.path.abspath(self.rs_brain_dir)
        if not rs_options.debug_callback:
            rs_options.debug_callback = lambda message: self.debug_callback(message)
        # Doesn't seem to let us trace the generated RSOBJ function, so we replace the 'load' function
        # above instead.
        #if filename.endswith(os.path.join('rivescript', 'python.py')):
            #if SHOW_STARTUP:
                #print_log(f'file_tracer: {filename}')
            #return self
        #print(f'self.rs_brain_abspath = {self.rs_brain_abspath}, filename = {filename}')
        if self.rs_brain_abspath is not None and filename.startswith(self.rs_brain_abspath):
            return self
        return None

    def file_reporter(self, filename):
        if SHOW_STARTUP or SHOW_TRACING:
            print_log(f'file_reporter({filename})')
        if filename.endswith('.py'):
            return 'python'
        return FileReporter(filename)

    def find_executable_files(self, src_dir):
        if SHOW_STARTUP or SHOW_TRACING:
            print(f'find_executable_files: checking {src_dir}')
        for (dirpath, dirnames, filenames) in os.walk(src_dir):
            for filename in filenames:
                # We're only interested in files that look like reasonable RiveScript
                # files: Must end with .rs or .rive, and must not have certain
                # funny characters that probably mean they are editor junk.
                if not hasattr(rs_options, 'ext'):
                    rs_options.ext = ('.rive', '.rs')
                #print(f'find_executable_files: checking {filename}')
                for e in rs_options.ext:
                    if re.match(r"^[^.#~!$@%^&*()+=,]+" + re.escape(e) + r"$", filename):
                        if SHOW_STARTUP or SHOW_TRACING:
                            print_log(f'find_executable_files found {os.path.join(dirpath, filename)}')
                        yield os.path.join(dirpath, filename)

    # --- FileTracer methods

    def has_dynamic_source_filename(self):
        return False

    def dynamic_source_filename(self, filename, frame): # Not used
        if SHOW_TRACING:
            print(f'dynamic_source_filename({filename}, {frame}): {frame.f_code.co_name}')
        return None

    def line_number_range(self, frame):             # Not used
        #assert frame.f_code.co_name == 'render'
        if SHOW_TRACING:
            dump_frame(frame, label="line_number_range")

        render_self = frame.f_locals['self']
        #if isinstance(render_self, (NodeList, Template)):
            #return -1, -1

        position = position_for_node(render_self)
        if position is None:
            return -1, -1

        return -1, -1

    # --- FileTracer helpers

    def get_line_map(self, filename):
        """The line map for `filename`.
        A line map is a list of character offsets, indicating where each line
        in the text begins.  For example, a line map like this::
            [13, 19, 30]
        means that line 2 starts at character 13, line 3 starts at 19, etc.
        Line 1 always starts at character 0.
        """
        if filename not in self.source_map:
            template_source = read_template_source(filename)
            if SHOW_TRACING:   # change to see the template text
                for i in range(0, len(template_source), 10):
                    print_log("%3d: %r" % (i, template_source[i:i+10]))
            self.source_map[filename] = make_line_map(template_source)
        return self.source_map[filename]


class Token:
    def __init__(self, token_type, lineno, contents, extra=None):
        self.token_type = token_type
        self.lineno = lineno
        self.contents = contents
        self.extra = extra

# Values for token_type
TOKEN_OBJECT, TOKEN_COMMENT, TOKEN_DEF, TOKEN_LABEL, TOKEN_LABEL_END, TOKEN_TRIGGER, TOKEN_REPLY, TOKEN_PREVIOUS, TOKEN_CONTINUE, TOKEN_REDIRECT, TOKEN_CONDITION = range(11)

# Names for token_type
TOKEN_MAPPING = ['object', 'comment', '! def', '> label', '< label', '+ trigger', '- reply', '% previous', '^ continue', '@ redirect', '* condition']

# v0.2.0: Issue #4: EXECUTIBLE_TOKENS = {TOKEN_OBJECT, TOKEN_TRIGGER, TOKEN_REPLY, TOKEN_PREVIOUS, TOKEN_CONTINUE, TOKEN_REDIRECT, TOKEN_CONDITION}
# v0.2.0: Issue #4: NON_EXECUTIBLE_TOKENS = {TOKEN_COMMENT, TOKEN_DEF, TOKEN_LABEL, TOKEN_LABEL_END}
EXECUTIBLE_TOKENS = {TOKEN_TRIGGER, TOKEN_REPLY, TOKEN_PREVIOUS, TOKEN_CONTINUE, TOKEN_REDIRECT, TOKEN_CONDITION}   # v0.2.0: Issue #4
NON_EXECUTIBLE_TOKENS = {TOKEN_OBJECT, TOKEN_COMMENT, TOKEN_DEF, TOKEN_LABEL, TOKEN_LABEL_END}                      # v0.2.0: Issue #4

class Lexer:
    """Lexer for RiveScript"""

    # Concatenation mode characters.
    concat_modes = dict(
        none="",
        space=" ",
        newline="\n",
    )

    def __init__(self, source, filename):
        global rs_lexed
        self.source = source
        self.filename = filename
        if filename in rs_lexed:            # If we lexed this file already, then just grab that
            self.tokens = rs_lexed[filename].tokens
            self.lineno_to_token_index = rs_lexed[filename].lineno_to_token_index
            self.source = rs_lexed[filename].source
        else:
            self.tokens = None
            self.lineno_to_token_index = None
            if self.source is None:
                self.source = read_template_source(filename)

    def _add_token(self, token):
        if self.tokens is None:
            self.tokens = []
        self.tokens.append(token)
        if self.lineno_to_token_index is None:
            self.lineno_to_token_index = {}
        self.lineno_to_token_index[token.lineno] = len(self.tokens) - 1

    def tokenize(self):     # Borrowed from rivescript/parser.py
        global trigger_source, object_source, rs_lexed
        if self.tokens is not None:
            return self.tokens
        code = self.source.splitlines()

        # Track temporary variables.
        topic   = 'random'  # Default topic=random
        lineno  = 0         # Line numbers for syntax tracking
        comment = False     # In a multi-line comment
        inobj   = False     # In an object
        objname = ''        # The name of the object we're in
        objlang = ''        # The programming language of the object
        objbuf  = []        # Object contents buffer
        objlineno = 0       # Line number of object start
        curtrig = None      # Pointer to the current trigger in ast.topics
        isThat  = None      # Is a %Previous trigger

        # Local (file scoped) parser options.
        local_options = dict(
            concat="none",  # Concat mode for ^Continue command
        )

        # Read each line.

        for lp, line in enumerate(code):
            lineno += 1

            #self.say("Line: " + line + " (topic: " + topic + ") incomment: " + str(inobj))
            #if len(line.strip()) == 0:  # Skip blank lines
                #continue

            # In an object?
            if inobj:
                if re.match(RE.objend, line):
                    # End the object.
                    if len(objname):
                        #ast["objects"].append({
                        self._add_token(Token(TOKEN_OBJECT, objlineno, "object", extra={
                            "name": objname,
                            "language": objlang,
                            "code": objbuf,
                            "end_lineno": lineno,     # v0.2.0: Issue #4
                        }))
                        object_source[objname] = (self.filename, objlineno)
                    objname = ''
                    objlang = ''
                    objbuf  = []
                    objlineno = 0
                    inobj   = False
                else:
                    objbuf.append(line)
                continue

            line = line.strip()  # Trim excess space. We do it down here so we
                                 # don't mess up python objects!
            if len(line) == 0:      # Skip blank lines
                continue
            line = RE.ws.sub(" ", line)  # Replace the multiple whitespaces by single whitespace

            # Look for comments.
            if line[:2] == '//':  # A single-line comment.
                self._add_token(Token(TOKEN_COMMENT, lineno, "comment"))
                continue
            elif line[0] == '#':
                self._add_token(Token(TOKEN_COMMENT, lineno, "comment"))
                continue # self.warn("Using the # symbol for comments is deprecated", filename, lineno)
            elif line[:2] == '/*':  # Start of a multi-line comment.
                if '*/' not in line:  # Cancel if the end is here too.
                    comment = True
                self._add_token(Token(TOKEN_COMMENT, lineno, "comment"))
                continue
            elif '*/' in line:
                comment = False
                self._add_token(Token(TOKEN_COMMENT, lineno, "comment"))
                continue
            if comment:
                self._add_token(Token(TOKEN_COMMENT, lineno, "comment"))
                continue

            # Separate the command from the data.
            if len(line) < 2:
                #self.warn("Weird single-character line '" + line + "' found.", filename, lineno)
                continue
            cmd = line[0]
            line = line[1:].strip()

            # Ignore inline comments if there's a space before the // symbols.
            if " //" in line:
                line = line.split(" //")[0].strip()

            # Reset the %Previous state if this is a new +Trigger.
            if cmd == '+':
                isThat = None

            # Do a lookahead for ^Continue and %Previous commands.
            for i in range(lp + 1, len(code)):
                lookahead = code[i].strip()
                if len(lookahead) < 2:
                    continue
                lookCmd = lookahead[0]
                lookahead = lookahead[1:].strip()
                lookahead = re.sub(RE.space, ' ', lookahead)  # Replace the `\s` in the message

                # Only continue if the lookahead line has any data.
                if len(lookahead) != 0:
                    # The lookahead command has to be either a % or a ^.
                    if lookCmd != '^' and lookCmd != '%':
                        break

                    # If the current command is a +, see if the following is
                    # a %.
                    if cmd == '+':
                        if lookCmd == '%':
                            isThat = lookahead
                            break
                        else:
                            isThat = None

                    # If the current command is a ! and the next command(s) are
                    # ^, we'll tack each extension on as a line break (which is
                    # useful information for arrays).
                    if cmd == '!':
                        if lookCmd == '^':
                            line += "<crlf>" + lookahead
                        continue

                    # If the current command is not a ^ and the line after is
                    # not a %, but the line after IS a ^, then tack it on to the
                    # end of the current line.
                    if cmd != '^' and lookCmd != '%':
                        if lookCmd == '^':
                            line += self.concat_modes.get(
                                local_options["concat"], ""
                            ) + lookahead
                        else:
                            break

            #self.say("Command: " + cmd + "; line: " + line)

            # Handle the types of RiveScript commands.
            if cmd == '!':
                # ! DEFINE
                halves = re.split(RE.equals, line, 2)
                left = re.split(RE.ws, halves[0].strip(), 2)
                value, type, var = '', '', ''
                if len(halves) == 2:
                    value = halves[1].strip()
                if len(left) >= 1:
                    type = left[0].strip()
                    if len(left) >= 2:
                        var = ' '.join(left[1:]).strip()

                # Remove 'fake' line breaks unless this is an array.
                if type != 'array':
                    value = re.sub(RE.crlf, '', value)

                # Handle version numbers.
                if type == 'version':
                    self._add_token(Token(TOKEN_DEF, lineno, 'version'))
                    continue

                # Handle the rest of the types.
                if type == 'local':
                    # Local file-scoped parser options.
                    #self.say("\tSet parser option " + var + " = " + value)
                    local_options[var] = value
                    self._add_token(Token(TOKEN_DEF, lineno, 'local', extra={'var': var, 'value': value}))
                elif type == 'global':
                    # 'Global' variables
                    #self.say("\tSet global " + var + " = " + value)

                    if value == '<undef>':
                        self._add_token(Token(TOKEN_DEF, lineno, 'global', extra={'var': var, 'value': None}))
                    else:
                        # Handle flipping debug and depth vars.
                        if var == 'debug':
                            if value.lower() == 'true':
                                value = True
                            else:
                                value = False
                        elif var == 'depth':
                            try:
                                value = int(value)
                            except:
                                pass
                                #self.warn("Failed to set 'depth' because the value isn't a number!", filename, lineno)
                        elif var == 'strict':
                            if value.lower() == 'true':
                                value = True
                            else:
                                value = False
                        self._add_token(Token(TOKEN_DEF, lineno, 'global', extra={'var': var, 'value': value}))
                elif type == 'var':
                    # Bot variables
                    #self.say("\tSet bot variable " + var + " = " + value)

                    if value == '<undef>':
                        self._add_token(Token(TOKEN_DEF, lineno, 'var', extra={'var': var, 'value': None}))
                    else:
                        self._add_token(Token(TOKEN_DEF, lineno, 'var', extra={'var': var, 'value': value}))
                elif type == 'array':
                    # Arrays
                    #self.say("\tArray " + var + " = " + value)

                    if value == '<undef>':
                        self._add_token(Token(TOKEN_DEF, lineno, 'array', extra={'var': var, 'value': None}))
                        continue

                    # Did this have multiple parts?
                    parts = value.split("<crlf>")

                    # Process each line of array data.
                    fields = []
                    for val in parts:
                        if '|' in val:
                            fields.extend(val.split('|'))
                        else:
                            fields.extend(re.split(RE.ws, val))

                    # Convert any remaining '\s' escape codes into spaces.
                    for f in fields:
                        f = f.replace('\s', ' ')

                    self._add_token(Token(TOKEN_DEF, lineno, 'array', extra={'var': var, 'value': fields}))
                elif type == 'sub':
                    # Substitutions
                    #self.say("\tSubstitution " + var + " => " + value)

                    if value == '<undef>':
                        self._add_token(Token(TOKEN_DEF, lineno, 'sub', extra={'var': var, 'value': None}))
                    else:
                        self._add_token(Token(TOKEN_DEF, lineno, 'sub', extra={'var': var, 'value': value}))
                elif type == 'person':
                    # Person Substitutions
                    #self.say("\tPerson Substitution " + var + " => " + value)

                    if value == '<undef>':
                        self._add_token(Token(TOKEN_DEF, lineno, 'person', extra={'var': var, 'value': None}))
                    else:
                        self._add_token(Token(TOKEN_DEF, lineno, 'person', extra={'var': var, 'value': value}))
                else:
                    pass # self.warn("Unknown definition type '" + type + "'", filename, lineno)
            elif cmd == '>':
                # > LABEL
                temp = re.split(RE.ws, line)
                typ   = temp[0]
                name   = ''
                fields = []
                if len(temp) >= 2:
                    name = temp[1]
                if len(temp) >= 3:
                    fields = temp[2:]

                # Handle the label types.
                if typ == 'begin':
                    # The BEGIN block.
                    #self.say("\tFound the BEGIN block.")
                    typ = 'topic'
                    name = '__begin__'
                if typ == 'topic':
                    # Starting a new topic.
                    #self.say("\tSet topic to " + name)
                    curtrig = None
                    topic  = name

                    # Initialize the topic tree.
                    #self._init_topic(ast["topics"], topic)

                    # Does this topic include or inherit another one?
                    mode = ''  # or 'inherits' or 'includes'
                    if len(fields) >= 2:
                        for field in fields:
                            if field == 'includes':
                                mode = 'includes'
                            elif field == 'inherits':
                                mode = 'inherits'
                            elif mode != '':
                                # This topic is either inherited or included.
                                pass
                                #if mode == 'includes':
                                    #ast["topics"][name]["includes"][field] = 1
                                #else:
                                    #ast["topics"][name]["inherits"][field] = 1
                    self._add_token(Token(TOKEN_LABEL, lineno, 'topic', extra={'topic': name, 'mode': mode}))
                elif typ == 'object':
                    # If a field was provided, it should be the programming
                    # language.
                    lang = None
                    if len(fields) > 0:
                        lang = fields[0].lower()

                    # Only try to parse a language we support.
                    curtrig = None
                    if lang is None:
                        #self.warn("Trying to parse unknown programming language", filename, lineno)
                        lang = 'python'  # Assume it's Python.

                    # We have a handler, so start loading the code.
                    objname = name
                    objlang = lang
                    objbuf  = []
                    objlineno = lineno
                    inobj   = True
                else:
                    pass # self.warn("Unknown label type '" + typ + "'", filename, lineno)
            elif cmd == '<':
                # < LABEL
                typ = line

                if typ == 'begin' or typ == 'topic':
                    #self.say("\tEnd topic label.")
                    self._add_token(Token(TOKEN_LABEL_END, lineno, 'topic', extra={'topic': topic}))
                    topic = 'random'
                elif typ == 'object':
                    #self.say("\tEnd object label.")
                    inobj = False
            elif cmd == '+':
                # + TRIGGER
                #self.say("\tTrigger pattern: " + line)

                # Initialize the topic tree.
                #self._init_topic(ast["topics"], topic)
                curtrig = {
                    "trigger": line,
                    "reply": [],
                    "condition": [],
                    "redirect": None,
                    "previous": isThat,
                }
                #ast["topics"][topic]["triggers"].append(curtrig)
                self._add_token(Token(TOKEN_TRIGGER, lineno, '+', extra=curtrig))

                ts_topic = '' if topic == 'random' else f'{topic}:'
                trigger = f'{ts_topic}{line}'
                if isThat:
                    new_one = [self.filename, lineno, isThat]
                else:
                    new_one = (self.filename, lineno)
                if trigger in trigger_source:
                    if isinstance(trigger_source[trigger], list):
                        trigger_source[trigger].append(new_one)
                    else:
                        trigger_source[trigger] = [trigger_source[trigger], new_one]
                elif isinstance(new_one, list):
                    trigger_source[trigger] = [new_one]
                else:
                    trigger_source[trigger] = new_one

            elif cmd == '-':
                # - REPLY
                if curtrig is None:
                    #self.warn("Response found before trigger", filename, lineno)
                    continue

                #self.say("\tResponse: " + line)
                curtrig["reply"].append(line.strip())
                self._add_token(Token(TOKEN_REPLY, lineno, '-', extra=line.strip()))
            elif cmd == '%':
                # % PREVIOUS
                pass  # This was handled above.
                self._add_token(Token(TOKEN_PREVIOUS, lineno, '%', extra=line.strip()))
            elif cmd == '^':
                # ^ CONTINUE
                pass  # This was handled above.
                self._add_token(Token(TOKEN_CONTINUE, lineno, '^', extra=line.strip()))
            elif cmd == '@':
                # @ REDIRECT
                if curtrig is None:
                    #self.warn("Redirect found before trigger", filename, lineno)
                    continue

                #self.say("\tRedirect: " + line)
                curtrig["redirect"] = line.strip()
                self._add_token(Token(TOKEN_REDIRECT, lineno, '@', extra=line.strip()))
            elif cmd == '*':
                # * CONDITION
                if curtrig is None:
                    #self.warn("Condition found before trigger", filename, lineno)
                    continue

                #self.say("\tAdding condition: " + line)
                curtrig["condition"].append(line.strip())
                self._add_token(Token(TOKEN_CONDITION, lineno, '*', extra=line.strip()))
            else:
                #self.warn("Unrecognized command \"" + cmd + "\"", filename, lineno)
                continue

        # print(f'trigger_source = {trigger_source}')     # DEBUG
        if self.tokens is None: # v0.2.0: Issue #2
            self.tokens = []    # v0.2.0: Issue #2
        rs_lexed[self.filename] = self
        return self.tokens

class FileReporter(coverage.plugin.FileReporter):
    def __init__(self, filename):
        super(FileReporter, self).__init__(filename)

        self._source = None
        self._tokens = None
        self._lines_shown = False
        self._excluded_lines_shown = False

    def source(self):
        if self._source is None:
            self._source = read_template_source(self.filename)
        return self._source

    def lines(self):
        """Return the set of executible lines of the file"""
        source_lines = set()
        show_parsing = SHOW_PARSING if not self._lines_shown else False

        if not self._tokens:
            lexer = Lexer(self.source(), self.filename)
            self._tokens = lexer.tokenize()

        tokens = self._tokens

        if show_parsing:
            print_log("-------------- {}".format(self.filename))
            self._lines_shown = True

        for token in tokens:
            if show_parsing:
                print_log(
                    "%10s %2d: %r (%r)" % (
                        TOKEN_MAPPING[token.token_type],
                        token.lineno,
                        token.contents,
                        token.extra,
                    )
                )
            if token.token_type in EXECUTIBLE_TOKENS:
                source_lines.add(token.lineno)
            elif token.token_type == TOKEN_OBJECT:      # v0.2.0: Issue #4: The code is executable, not the OBJECT
                for i, code in enumerate(token.extra['code'], start=1):
                    line = code.strip()
                    if len(line) and line[0] != '#':
                        source_lines.add(token.lineno+i)

            if show_parsing:
                print_log("\t\t\tNow source_lines is: {!r}".format(source_lines))

        return source_lines

    def excluded_lines(self):
        """Return the set of non-executible lines of the file"""
        non_source_lines = set()

        show_parsing = SHOW_PARSING if not self._excluded_lines_shown else False

        if not self._tokens:
            lexer = Lexer(self.source(), self.filename)
            self._tokens = lexer.tokenize()

        tokens = self._tokens

        if show_parsing:
            print_log("-------------- {}".format(self.filename))
            self._excluded_lines_shown = True

        for token in tokens:
            if token.token_type not in EXECUTIBLE_TOKENS:
                non_source_lines.add(token.lineno)
                if token.token_type == TOKEN_OBJECT:        # v0.2.0: Issue #4
                    for i, code in enumerate(token.extra['code'], start=1):
                        line = code.strip()
                        if not len(line) or line[0] == '#':
                            non_source_lines.add(token.lineno+i)
                    non_source_lines.add(token.extra['end_lineno']) # v0.2.0: Issue #4

        if show_parsing:
            print_log("\t\t\tNon source_lines is: {!r}".format(non_source_lines))

        return non_source_lines


def running_sum(seq):
    total = 0
    for num in seq:
        total += num
        yield total


def make_line_map(text):
    line_lengths = [len(l) for l in text.splitlines(True)]
    line_map = list(running_sum(line_lengths))
    return line_map


def get_line_number(line_map, offset):
    """Find a line number, given a line map and a character offset."""
    for lineno, line_offset in enumerate(line_map, start=1):
        if line_offset > offset:
            return lineno
    return -1


def dump_frame(frame, label=""):
    """
    Dump interesting information about this frame.
    ** ONLY USED WHEN DEBUGGING **
    """
    locals = dict(frame.f_locals)
    self = locals.get('self', None)
    context = locals.get('context', None)
    if "__builtins__" in locals:
        del locals["__builtins__"]

    if label:
        label = " ( %s ) " % label
    print_log("-- frame --%s---------------------" % label)
    print_log("{}:{}:{}".format(
        os.path.basename(frame.f_code.co_filename),
        frame.f_lineno,
        type(self),
        ))
    print_log(locals)
    if self:
        print_log("self:", self.__dict__)
    if context:
        print_log("context:", context.__dict__)
    print_log("\\--")
