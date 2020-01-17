from rivescript import RiveScript

DEBUG_RIVESCRIPT=False
BRAIN='brain'

rs = None

def rs_init():
    global rs
    print("Loading rs brain")
    rs = RiveScript(DEBUG_RIVESCRIPT, utf8=True)
    rs.load_directory(BRAIN)
    rs.sort_replies()
    print("rs brain loaded")

def reply(user, msg):
    global rs
    return rs.reply(user, msg)
