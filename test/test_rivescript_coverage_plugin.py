"""
Tests for `rivescript_coverage_plugin` module.
"""
#from rivescript_coverage_plugin import rivescript_coverage_plugin

import rive
import pytest
from rivescript import RiveScript
import os

USER='user'         # v1.0.0: Issue 14
USER2='user2'       # v1.0.0: Issue 14

@pytest.fixture(scope="session", autouse=True)
def initialize():
    rive.rs_init()

def say(message):
    return rive.reply(USER, message)

def say_u(user, message):                      # v1.0.0: Issue 14
    return rive.reply(user, message)           # v1.0.0: Issue 14

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
    assert say('formal') == 'User'
    assert say('green') == 'No, purple is the best color!'
    assert say('purple') == 'Correct, purple is the best color!'
    assert say('topic') == 'entered topic'
    assert say('hi') == "You're in topic, type q to quit"
    assert say('try in topic') == 'response in topic'
    assert say('conditional in topic') == 'conditional in topic response'
    assert say('q') == 'Exiting topic'
    assert say('object') == 'result from object'

def test_star():
    # v1.0.0: Issue 12   resp = say('star')
    # v1.0.0: Issue 12   assert resp in ("I don't know what you mean", "Sorry, I don't know that")

    # v1.0.0: Issue 12: Test both replies for 'star' as the one with weight wasn't being marked as executed
    star_replies = ("I don't know what you mean", "Sorry, I don't know that")
    star_replies_found = set()
    while True:
        resp = say('star')
        star_replies_found.add(resp)
        if len(star_replies_found) == len(star_replies):
            break

    assert say('xyzzy') == '[ERR: No Reply Matched]'

def test_bugs():        
    """Test bugs found in the code"""
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

    # v1.0.0: Issue #9: local concat
    assert say('issue 9 default') == 'Issue 9default response without space'
    assert say('issue 9 newline') == 'Issue 9\nresponse with newline'
    assert say('issue 9 space') == 'Issue 9 response with space'
    assert say('issue 9 none') == 'Issue 9response without space'

    # v1.0.0: Issue 10: line numbers off due to whitespace at end of object
    assert say('issue 10') == 'Issue 10 response'

    # v1.0.0: Issue 11: 'else', 'nonlocal' marked as not executed in object
    assert say('issue 11') == \
            'Issue 11 response'

    # v1.0.0: Issue 12: Responses with weights were not being marked as executed
    issue_12_replies = (
      'issue 12 response 1',
      'issue 12 response 2',
      'issue 12 response 3',
      'issue 12 response 4',
      'issue 12 response 5',
      'issue 12 response 6',
      'issue 12 response 7',
      'issue 12 response 8 - unweighted',
                        )
    issue_12_replies_found = set()
    while True:
        resp = say('issue 12')
        assert resp in issue_12_replies
        issue_12_replies_found.add(resp)
        if len(issue_12_replies_found) == len(issue_12_replies):
            break

    # v1.0.0: Issue 13: Responses didn't match if the question contained a single quote

    assert say("issue 13 single quote doesn't work") == "issue 13 single quote response"
    assert say('issue 13 double quote "how about it?"') == "issue 13 double quote response"
    assert say('issue 13 both quotes "don\'t break!"') == "issue 13 both quotes response"

    # v1.0.0: Issue 14: Need separate topic for each user

    for i in range(1, 11):
        for u in (USER, USER2):
            assert say_u(u, f"issue 14 {u} q{i}") == f"issue 14 {u} r{i}"

