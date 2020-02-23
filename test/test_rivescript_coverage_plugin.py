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
    assert say('try in topic') == 'response in topic'
    assert say('conditional in topic') == 'conditional in topic response'
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

    # v0.2.2: Issue #6: Topic with inherits or includes don't show any coverage

    assert say('issue 6') == 'Entering topic issue_6'
    assert say('issue') == 'Check coverage!'
    assert say('bye') == 'Good bye!'

    assert say('issue 6a') == 'Entering topic issue_6a'
    assert say('sixa') == 'Check sixa!'
    assert say('exit') == 'Exiting topic'

    # v0.2.3: Issue #7: Conditional with alternate response not covered
    assert say('issue 7').startswith('issue_7 response')

    # v0.2.3: Issue #8: Topic changed in object
    assert say('issue_8') == 'result from issue_8_object'
    assert say('hi') == "You're in issue_8, type q to quit"
    assert say('try in issue_8') == 'response in issue_8'
    assert say('prev in issue_8') == 'prev response in issue_8'
    assert say('conditional in issue_8') == 'conditional response in issue_8'
    assert say('q') == 'Exiting issue_8'
