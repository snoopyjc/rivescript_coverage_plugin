"""
Tests for `rivescript_coverage_plugin` module.
"""
#from rivescript_coverage_plugin import rivescript_coverage_plugin

import rive
import pytest
from rivescript import RiveScript
import os

USER='localuser'

@pytest.fixture(scope="session", autouse=True)
def initialize():
    rive.rs_init()

def say(message):
    return rive.reply(USER, message)

def test_basic():
    assert say('hi') == 'hey'
    resp = say('hi')
    assert resp in ('hey again!', 'I already said "hey"')
    assert say('yo') == 'hey yo'
    resp = say('hi there')
    assert resp in ('You said hi there', 'Hi there back!')
    assert say('bye') == 'Good bye!'
    assert say('hey') == 'hey'
    resp = say('hey')
    assert resp in ('hey again!', 'I already said "hey"')
    assert say('formal') == 'Localuser'
    assert say('green') == 'No, purple is the best color!'
    assert say('purple') == 'Correct, purple is the best color!'
    assert say('topic') == 'entered topic'
    assert say('hi') == "You're in topic, type q to quit"
    assert say('q') == 'Exiting topic'
    assert say('object') == 'result from object'

def test_star():
    resp = say('star')
    assert resp in ("I don't know what you mean", "Sorry, I don't know that")
    assert say('xyzzy') == '[ERR: No Reply Matched]'

def test_bugs():        # Test bugs found in the code
    # v0.2.0: Issue #3: Plugin crashes if rive file is deleted by test
    with open('brain/issue_3.rive', 'w') as d:
        print('+ dynamic', file=d)
        print('- dynomite!', file=d)

    rive.rs.load_file('brain/issue_3.rive')
    rive.rs.sort_replies()
    assert say('dynamic') == 'dynomite!'

    os.remove('brain/issue_3.rive')



