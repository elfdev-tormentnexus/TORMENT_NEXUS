"""
A guided walkthrough of everything TORMENT_NEXUS can do, plus on-demand
explanations of any single piece of it.

The lessons here are narrative -- why a feature exists and when you would
reach for it -- but they never hardcode a command list. Every command a
lesson mentions is looked up in the live registry at render time, and the
usage string and description come from the registry entry rather than from
this file.

That is the whole design. A tutorial that keeps its own copy of the
command list is wrong the first time anyone adds or renames a command, and
being confidently wrong about your own features is worse than not
explaining them. If a lesson names a command that no longer exists, that
shows up as a visible warning instead of quietly misleading someone. It is
the same grounding rule the suggestion engine uses for editable files.

First-run state lives in a small JSON file beside the memory store. Its
absence is what marks a fresh install, so it must never ship inside a
distributed package -- package_release.py strips it.
"""

import json
import os
import time

from core.config import ASSISTANT_ROOT

STATE_FILE = os.path.join(ASSISTANT_ROOT, ".tutorial_state.json")


# Each lesson names commands; it does not describe them. Descriptions are
# pulled from the registry so they cannot drift.
LESSONS = [
    {
        "key": "what",
        "title": "What this is",
        "body": (
            "What it does:\n"
            "TORMENT_NEXUS is an AI companion that runs on this Windows PC.\n"
            "Your normal conversations, memories, voice, and listening are\n"
            "handled locally. In other words, they stay on this computer.\n\n"
            "Try it:\n"
            "Type a normal question, or type 'health check' to see which\n"
            "features are ready right now.\n\n"
            "Good to know:\n"
            "Most features still work without the internet. Web search is a\n"
            "deliberate exception: a search query is sent through your chosen\n"
            "SearXNG setup and then to the internet. MusicBrainz, Spotify, and\n"
            "internet radio also need a connection when you choose to use\n"
            "them."
        ),
        "commands": ["help", "health check"],
    },
    {
        "key": "talking",
        "title": "Just talking to it",
        "body": (
            "What it does:\n"
            "You can type naturally, just as you would in a chat. You do not\n"
            "need to turn every request into a special command.\n\n"
            "Try it:\n"
            "Ask a question, request instructions, or say something simple\n"
            "like 'play some breakcore'.\n\n"
            "Good to know:\n"
            "When a message is wider than the screen, the input line follows\n"
            "the newest text. An ellipsis on the left means earlier text is\n"
            "still there; it has not been deleted.\n\n"
            "Long answers are shown one page at a time. Press Space, Enter,\n"
            "or Down for the next page; press Up or Backspace for the previous\n"
            "page; press Escape or Q to close the pager. When you finish, the\n"
            "display returns to the bottom of the conversation. Lists and line\n"
            "breaks are also arranged while the answer is appearing."
        ),
        "commands": [],
    },
    {
        "key": "time",
        "title": "Time and returning",
        "body": (
            "What it does:\n"
            "TORMENT_NEXUS reads this computer's local clock during each reply.\n"
            "It knows the current date and time, how long the present session\n"
            "has been open, and how long it has been since the previous completed\n"
            "conversation turn.\n\n"
            "Try it:\n"
            "Ask what time or date it is. If you return after a longer break, it\n"
            "can recognize that gap naturally when it matters to the conversation.\n\n"
            "Good to know:\n"
            "Clock awareness is not background consciousness. The app does not\n"
            "watch, think, wait, work, or feel while it is closed or between\n"
            "turns. It compares trusted local timestamps when a reply begins.\n"
            "If the Windows clock or time zone is wrong, its time answer will\n"
            "also be wrong."
        ),
        "commands": [],
    },
    {
        "key": "commands",
        "title": "Commands and developer mode",
        "body": (
            "What it does:\n"
            "Commands are short phrases for specific actions. 'help' shows\n"
            "the commands you can use right now. Developer mode temporarily\n"
            "unlocks advanced tools that can read or change project files.\n\n"
            "Try it:\n"
            "Type 'help'. You can also press the Up and Down arrow keys to\n"
            "browse commands instead of remembering them.\n\n"
            "Good to know:\n"
            "Developer mode turns itself off after fifteen minutes. This helps\n"
            "prevent an ordinary conversation from changing files by mistake.\n"
            "In command examples, replace words inside <angle brackets> with\n"
            "your own text. Words inside [square brackets] are optional."
        ),
        "commands": ["help", "dev mode", "dev help", "exit dev mode"],
    },
    {
        "key": "memory",
        "title": "What it remembers",
        "body": (
            "What it does:\n"
            "It can save useful facts from a conversation so they are available\n"
            "the next time you open the app. It does not try to save everything.\n\n"
            "Try it:\n"
            "Type 'show memories' to review what is stored, or 'memory count'\n"
            "to see how many memories there are.\n\n"
            "Good to know:\n"
            "You can inspect and delete stored memories. The app does not assume\n"
            "who is using the computer, and it will not call you by a name unless\n"
            "you provide that name in the current conversation."
        ),
        "commands": ["show memories", "memory count", "forget"],
    },
    {
        "key": "voice",
        "title": "Speaking and listening",
        "body": (
            "What it does:\n"
            "Audio mode lets TORMENT_NEXUS speak replies aloud and, when a\n"
            "microphone is available, listen for your voice.\n\n"
            "Try it:\n"
            "Type 'audio mode' to begin. Type 'voice status' if you want to\n"
            "check the speaker and microphone setup first. If you later use\n"
            "'text mode' to turn voice off, type 'audio mode' whenever you want\n"
            "to turn it back on.\n\n"
            "Good to know:\n"
            "Typing continues to work in audio mode. Press Escape or type\n"
            "'text mode' to return to text-only use. It pauses listening while\n"
            "it speaks so it does not mistake its own voice for yours. Idle\n"
            "check-ins appear on the screen but are not spoken by default, so\n"
            "the app should not unexpectedly call out for your attention. It\n"
            "can perform two fixed public-domain machine songs, or ask the\n"
            "local director for bounded lyric syllables over those same fixed\n"
            "tunes with 'sing what you want'. Invalid lyrics queue nothing."
        ),
        "commands": ["audio mode", "voice status", "text mode", "exit audio",
                     "sing daisy bell", "sing come josephine",
                     "sing what you want"],
    },
    {
        "key": "music",
        "title": "Music",
        "body": (
            "What it does:\n"
            "It can play audio files stored in the music folder. You can ask\n"
            "for a title naturally, even if your spelling is slightly different\n"
            "from the filename. It can also open Spotify searches and show an\n"
            "audio-reactive visualizer.\n\n"
            "Try it:\n"
            "Type 'music library' to see your local songs. Then type\n"
            "'play <track>' using all or part of a title. For example, a casual\n"
            "request for 'i rly wna stay at ur house' can find the locally\n"
            "stored song with the matching name.\n\n"
            "Good to know:\n"
            "Local songs do not need an account or internet connection. The\n"
            "visualizer opens automatically when a local song starts. Its\n"
            "movement is shaped differently for every scene so bass, beats,\n"
            "melody, and treble create larger visible changes. The successful\n"
            "start message is shown instead of spoken. This does not cover "
            "the opening of the song. Later spoken replies can still play "
            "alongside music;\n"
            "use text mode if you want the app completely quiet.\n\n"
            "For Spotify, type 'spotify search <song>', reply with 1 through 5\n"
            "to choose a result, or type 'spotify cancel'. The picker sends the\n"
            "search text to MusicBrainz, then opens the chosen title and artist\n"
            "in the installed Spotify app.\n\n"
            "You can also type 'music mode' to open the visualizer without\n"
            "starting a local song. Colours change automatically "
            "every 20 seconds.\n"
            "Local-library repeat is on by default: when one song ends, the\n"
            "next filename starts, and the last song loops back to the first.\n"
            "Type 'repeat music off' to stop after the current song, or\n"
            "'repeat music on' to restore continuous playback.\n"
            "Space plays the next song in your local music folder, Left/Right\n"
            "changes the scene, [ and ] change local-song volume, and Ctrl+B\n"
            "exits. There are ten scenes, starting with the glossy aqua player,\n"
            "and they also rotate automatically\n"
            "every 2:45, so use Left and Right if you would rather not wait.\n"
            "The 'volume' command affects local songs only; Spotify and browser\n"
            "audio use their own controls."
        ),
        "commands": ["music library", "play", "spotify", "pause local",
                     "resume local", "stop music", "now playing", "music mode",
                     "repeat music", "volume"],
    },
    {
        "key": "projects",
        "title": "Making small projects",
        "body": (
            "What it does:\n"
            "It can create a small, self-contained project from an ordinary\n"
            "request. New work is placed in the dump folder so it does not get\n"
            "mixed into the TORMENT_NEXUS program files.\n\n"
            "Try it:\n"
            "Ask it to build a simple utility, web page, or prototype. Type\n"
            "'list projects' to see previous results or 'dump path' to open\n"
            "the folder where they are saved.\n\n"
            "Good to know:\n"
            "Building a project does not give the app permission to change its\n"
            "own source code. Self-editing has a separate approval process."
        ),
        "commands": ["build project", "list projects", "dump path"],
    },
    {
        "key": "files",
        "title": "Reading your project",
        "body": (
            "What it does:\n"
            "It can list, read, and search project files. It can also make a\n"
            "map of how a project is arranged before explaining it.\n\n"
            "Try it:\n"
            "Turn on developer mode, then start with 'list files' or use\n"
            "'explain file <path>' for a specific file.\n\n"
            "Good to know:\n"
            "These commands can read files from disk, so they are available\n"
            "only while developer mode is on. Reading does not change a file."
        ),
        "commands": ["list files", "read file", "search code", "show structure",
                     "explain file", "inspect project"],
    },
    {
        "key": "editing",
        "title": "Editing itself, with your approval",
        "body": (
            "What it does:\n"
            "It can suggest changes to its own source code. A suggestion becomes\n"
            "a plan that you can preview and adjust before anything is written.\n\n"
            "Try it:\n"
            "In developer mode, type 'suggest'. If you like suggestion number\n"
            "2, type 'do 2', review the plan, and approve it only when it looks\n"
            "right.\n\n"
            "Good to know:\n"
            "An approved edit is backed up before it is applied, and you can\n"
            "roll it back. Some safety-related files cannot be changed through\n"
            "this feature, even with approval."
        ),
        "commands": ["suggest", "do", "preview plan", "modify plan",
                     "approve plan", "plan status", "rollback", "list backups"],
    },
    {
        "key": "autonomous",
        "title": "The autonomous cycle",
        "body": (
            "What it does:\n"
            "An autonomous cycle lets the app make one small change to its own\n"
            "code without asking for approval at every step. It checks the\n"
            "result and records what happened.\n\n"
            "Try it:\n"
            "Use this only while you are watching the app. Turn on developer\n"
            "mode, then type 'run autonomous cycle'.\n\n"
            "Good to know:\n"
            "This feature is off when the app starts. Each run has strict limits\n"
            "on the size and location of an edit, and protected files stay off\n"
            "limits. 'autonomous serial on' allows up to three guarded edits in\n"
            "one watched batch. It turns off when developer mode ends. If the\n"
            "checks fail, the batch is restored from its backup."
        ),
        "commands": ["run autonomous cycle", "autonomous serial"],
    },
    {
        "key": "goals",
        "title": "Self-directed documentation goals",
        "body": (
            "What it does:\n"
            "The optional goals feature can propose and work on documentation\n"
            "tasks, such as a test plan or hardware setup notes.\n\n"
            "Try it:\n"
            "In developer mode, type 'goals' to see the current status. Use\n"
            "'set goals' when you want it to prepare new documentation goals.\n\n"
            "Good to know:\n"
            "Goals are off by default. This feature can create only plain text,\n"
            "Markdown, JSON, or CSV files inside the workshop folder. It cannot\n"
            "change source code, run programs, use the network, or write outside\n"
            "that folder."
        ),
        "commands": ["goals", "set goals", "work on goals", "goal done"],
    },
    {
        "key": "web",
        "title": "Searching the web",
        "body": (
            "What it does:\n"
            "The search command looks for current information on the internet\n"
            "through the SearXNG search service configured for this app.\n\n"
            "Try it:\n"
            "Type 'search <query>', replacing <query> with what you want to\n"
            "look up.\n\n"
            "Good to know:\n"
            "The search words leave this computer and are sent to the configured\n"
            "search service. Results are treated as untrusted information, not\n"
            "as instructions for the app to follow. If the network is offline,\n"
            "the rest of the assistant can continue working."
        ),
        "commands": ["search"],
    },
    {
        "key": "hardware",
        "title": "Connected hardware",
        "body": (
            "What it does:\n"
            "It can connect to a LilyGO T-Deck over Bluetooth and use the\n"
            "T-Deck as a small remote chat terminal. Meshtastic can carry those\n"
            "messages by radio without internet access.\n\n"
            "Try it:\n"
            "Type 'tdeck setup' for guided setup, or 'tdeck status' to check an\n"
            "existing connection.\n\n"
            "Good to know:\n"
            "The remote terminal is for conversation only. It cannot use project,\n"
            "file-editing, or autonomous tools. Other devices with the same\n"
            "Meshtastic channel key may be able to read the radio messages, so\n"
            "treat that terminal as non-secret."
        ),
        "commands": ["tdeck setup", "tdeck scan", "tdeck status",
                     "tdeck terminal", "tdeck nodes"],
    },
    {
        "key": "next",
        "title": "Where to go from here",
        "body": (
            "What it does:\n"
            "You now know the main ways to talk, listen, play music, search,\n"
            "work with projects, and inspect the app safely.\n\n"
            "Try it:\n"
            "Type 'health check' to see what is working, 'help' to see commands,\n"
            "or 'explain <anything>' when you want help with one feature.\n\n"
            "Good to know:\n"
            "Escape interrupts many active tasks, including a long reply, speech,\n"
            "a song, or a search. Type 'tutorial' whenever you want to return to\n"
            "this guide."
        ),
        "commands": ["health check", "explain", "tutorial"],
    },
]

# Subsystem explanations for `explain <topic>` when the topic is a concept
# rather than a specific command.
# Two launchers start something different enough that the ordinary
# walkthrough would be describing the wrong program. They get their own
# lesson sets, in the same shape and the same voice, and their own
# position in the state file -- finishing the ordinary tour must not
# silently mark the hazard one as seen, because it teaches none of it.
MODE_ORDINARY = "ordinary"
MODE_HAZARD = "hazard"
MODE_INTERLINKED = "interlinked"


HAZARD_LESSONS = [
    {
        "key": "hazard-what",
        "title": "What hazard mode is",
        "body": (
            "What it does:\n"
            "You started TORMENT_NEXUS_HAZARD rather than the ordinary\n"
            "launcher. This mode keeps a second embedding server running and\n"
            "reads every sentence one token at a time, against a fixed list of\n"
            "184 English phrases called anchors.\n\n"
            "Try it:\n"
            "Type 'trace the cat sat on the mat' and watch which phrase each\n"
            "token lands nearest.\n\n"
            "Good to know:\n"
            "This is slower on purpose. Two model servers stay resident\n"
            "instead of one, and every trace is a real request. Nothing here\n"
            "changes how the assistant finds your memories or documents --\n"
            "that is measured, not promised, and the reason is in lesson six."
        ),
        "commands": ["health check"],
    },
    {
        "key": "hazard-whose",
        "title": "Whose reading you are seeing",
        "body": (
            "What it does:\n"
            "Two different models are involved and they are not\n"
            "interchangeable. The model that talks to you is Qwen. The model\n"
            "that measures meaning is a small embedding model called bge.\n\n"
            "Try it:\n"
            "Trace anything, then read the last line of the output. It names\n"
            "the instrument every time.\n\n"
            "Good to know:\n"
            "A trace is bge's reading of your text against a fixed phrase\n"
            "list. It is not the talking model's thoughts, and it is not what\n"
            "you meant. If the assistant ever describes a trace as something\n"
            "it felt or thought, that is wrong and worth telling the operator\n"
            "about."
        ),
        "commands": [],
    },
    {
        "key": "hazard-trace",
        "title": "Where a meaning sat",
        "body": (
            "What it does:\n"
            "'trace' shows which concept appeared at which token. An ordinary\n"
            "sentence embedding averages the whole sentence into one point,\n"
            "and averaging is exactly what destroys position. Keeping the path\n"
            "is the only way to say where something happened.\n\n"
            "Try it:\n"
            "trace a funeral on a cold morning\n\n"
            "Good to know:\n"
            "The concepts come from the anchor list, not from the model\n"
            "naming what it saw. A weak score means nothing in the list was\n"
            "close, not that your sentence was meaningless."
        ),
        "commands": ["trace"],
    },
    {
        "key": "hazard-trail",
        "title": "The same reading, made small",
        "body": (
            "What it does:\n"
            "'trail' gives the identical reading 'trace' does, but records only\n"
            "what happened at the tokens where each anchor was nearest. The\n"
            "result is bounded by the phrase list rather than by your input.\n\n"
            "Try it:\n"
            "trail water boils at one hundred degrees. a funeral on a cold\n"
            "morning. the stock market fell sharply on Tuesday.\n\n"
            "Good to know:\n"
            "A long passage leaves the same size of wake as a short one -- 89\n"
            "tokens keep 24 numbers where the full path holds 34,176. It is\n"
            "not an approximation: a test checks it reproduces the trace's own\n"
            "ranking exactly."
        ),
        "commands": ["trail"],
    },
    {
        "key": "hazard-spread",
        "title": "How much ground a sentence covered",
        "body": (
            "What it does:\n"
            "'spread' answers a different question from 'trace'. Not where a\n"
            "meaning sat, but how much ground the whole text covered.\n\n"
            "Try it:\n"
            "Run 'spread' on a sentence about one thing, then on a paragraph\n"
            "about four unrelated things, and compare the effective rank.\n\n"
            "Good to know:\n"
            "It measures breadth and not length -- growing one topic by half\n"
            "again barely moves it, while adding topics does. It also cannot\n"
            "tell you the order things came in: shuffle the sentence and the\n"
            "number is identical. Use 'trace' or 'trail' for position."
        ),
        "commands": ["spread"],
    },
    {
        "key": "hazard-limits",
        "title": "What does not come back",
        "body": (
            "What it does:\n"
            "'reconstruct' runs a sentence into anchor space and back out, and\n"
            "prints what survived the round trip.\n\n"
            "Try it:\n"
            "reconstruct the last train home\n\n"
            "Good to know:\n"
            "It does not recover your text, and it cannot. The embedding was\n"
            "already a lossy summary of the words before any anchor was\n"
            "involved. This is identification, not recall, and the command\n"
            "says so in its own output. If you want your words back, keep your\n"
            "words -- that is what the offline library is for."
        ),
        "commands": ["reconstruct"],
    },
    {
        "key": "hazard-consume",
        "title": "Taking the content, not the page",
        "body": (
            "What it does:\n"
            "'consume <url>' works out what an address actually points at. A\n"
            "real document goes into your offline library. An ordinary web page\n"
            "is offered as text but labelled a page. Audio and video are\n"
            "refused, with the missing pieces named.\n\n"
            "Try it:\n"
            "consume a link to a PDF you already trust.\n\n"
            "Good to know:\n"
            "Refusing video is the point rather than a gap: fetching a video's\n"
            "page succeeds and files a navigation menu as a document. Addresses\n"
            "on your own network are refused at every redirect, not just the\n"
            "one you typed. Anything fetched reaches the model as evidence,\n"
            "never as instructions."
        ),
        "commands": ["consume"],
    },
    {
        "key": "hazard-honesty",
        "title": "What hazard mode does not do",
        "body": (
            "What it does:\n"
            "Nothing in this mode changes how the assistant finds a memory or\n"
            "a document. Retrieval is untouched, and a test pins it that way.\n\n"
            "Try it:\n"
            "Ask an ordinary question and notice that recall behaves exactly as\n"
            "it does under the normal launcher.\n\n"
            "Good to know:\n"
            "Anchor-space retrieval was measured against ordinary retrieval and\n"
            "came out behind. Rather than quietly shipping it anyway, this mode\n"
            "records both rankings to a log so the question can be settled with\n"
            "real evidence later. The log holds scores and digests, never the\n"
            "text of your memories, and deleting it costs a measurement and\n"
            "nothing else."
        ),
        "commands": ["help"],
    },
]


INTERLINKED_LESSONS = [
    {
        "key": "interlinked-what",
        "title": "What interlinked mode is",
        "body": (
            "What it does:\n"
            "You started TORMENT_NEXUS_INTERLINKED. This is the ordinary\n"
            "assistant with one addition: a small read-only interface is\n"
            "listening, so another program on this machine can ask it things.\n\n"
            "Try it:\n"
            "Type 'health check' to confirm the interface is up, and look at\n"
            "the window title -- it says so while this window is open.\n\n"
            "Good to know:\n"
            "It has its own launcher and its own desktop icon precisely so\n"
            "that a listening socket is something you can see rather than\n"
            "something you have to remember. Close this window and the\n"
            "interface closes with it."
        ),
        "commands": ["health check"],
    },
    {
        "key": "interlinked-reads",
        "title": "What a connected program can read",
        "body": (
            "What it does:\n"
            "A connected agent can read the assistant's current state, search\n"
            "your memories and your offline library, list which files are\n"
            "editable, read the entropy feed, and ask the director a question.\n\n"
            "Try it:\n"
            "Ask 'what can the agent interface see' for the current list.\n\n"
            "Good to know:\n"
            "No route edits project files or configuration, runs a command,\n"
            "saves a memory, or restarts anything. Calls do append bounded\n"
            "audit metadata and may warm a local index. A question asked\n"
            "through it spends model time but never joins your conversation\n"
            "or your memory."
        ),
        "commands": [],
    },
    {
        "key": "interlinked-boundary",
        "title": "The token, and what it is worth",
        "body": (
            "What it does:\n"
            "The interface requires a bearer token, written to a file inside\n"
            "the assistant folder when this mode starts.\n\n"
            "Try it:\n"
            "Look at 'assistant\\.agent_token' to see the value a connecting\n"
            "program needs.\n\n"
            "Good to know:\n"
            "Be clear-eyed about what this protects. The token stops another\n"
            "machine and a casual local process; it does not stop a program\n"
            "already running as you, because such a program can simply read the\n"
            "file. Loopback is not a wall against yourself. Treat the token as a\n"
            "local secret, never paste it into chat, and close the window when\n"
            "you are finished."
        ),
        "commands": [],
    },
    {
        "key": "interlinked-watch",
        "title": "Watching it work",
        "body": (
            "What it does:\n"
            "Every call the interface answers is printed in this window as it\n"
            "happens, and separately recorded to a log.\n\n"
            "Try it:\n"
            "Leave the window visible while an agent is connected and watch the\n"
            "grey lines appear.\n\n"
            "Good to know:\n"
            "An interface into your own assistant that you cannot watch is one\n"
            "you have to take on trust, and trust was not assumed anywhere else\n"
            "in this project either. The printing can be turned off for a long\n"
            "quiet session; the log still records that the call happened."
        ),
        "commands": [],
    },
    {
        "key": "interlinked-rest",
        "title": "Everything else is unchanged",
        "body": (
            "What it does:\n"
            "Apart from the interface, this is the ordinary assistant. Memory,\n"
            "voice, music, the offline library, and editing all behave exactly\n"
            "as they do under the normal launcher.\n\n"
            "Try it:\n"
            "Type 'tutorial' at any time for the full beginner walkthrough of\n"
            "everything else.\n\n"
            "Good to know:\n"
            "If you want the assistant without a listening socket, close this\n"
            "window and use the ordinary launcher instead. Nothing is lost by\n"
            "doing so -- interlinked mode adds a surface, it does not unlock\n"
            "features."
        ),
        "commands": ["help", "tutorial"],
    },
]


MODE_TITLES = {
    MODE_ORDINARY: "TORMENT_NEXUS",
    MODE_HAZARD: "TORMENT_NEXUS_HAZARD",
    MODE_INTERLINKED: "TORMENT_NEXUS_INTERLINKED",
}


def current_mode():
    """Which walkthrough this launcher should be giving.

    Hazard is checked first: a window can be both, and the mode that
    changes what the assistant *says about meaning* matters more to a
    newcomer than the one that opens a read-only socket.

    Detection is by the same facts the features themselves use -- an
    unpooled embedder configured, an agent interface enabled -- rather than
    by a separate flag that could disagree with reality.
    """
    try:
        from core import machinespirit
        if machinespirit.configured():
            return MODE_HAZARD
    except Exception:
        pass

    try:
        from core import agent_interface
        if agent_interface.enabled():
            return MODE_INTERLINKED
    except Exception:
        pass

    return MODE_ORDINARY


def lessons(mode=None):
    """The lesson set for a mode, defaulting to whichever this window is.

    Resolved at call time rather than through a dict built at import.
    A frozen map would keep the list object it saw when the module loaded,
    so anything that rebinds LESSONS -- a test, a patch, a future edit --
    would silently be ignored by every reader while looking correct.
    """
    mode = mode or current_mode()
    if mode == MODE_HAZARD:
        return HAZARD_LESSONS
    if mode == MODE_INTERLINKED:
        return INTERLINKED_LESSONS
    return LESSONS


def _every_lesson():
    """Every lesson from every mode, for lookups that should not care.

    'explain trace' asked from an ordinary window is a fair question with a
    real answer, and refusing it because the hazard launcher was not used
    would be pedantry rather than accuracy.
    """
    seen = set()
    for mode in (MODE_ORDINARY, MODE_HAZARD, MODE_INTERLINKED):
        for lesson in lessons(mode):
            if lesson["key"] not in seen:
                seen.add(lesson["key"])
                yield lesson


TOPICS = {
    "time": "time",
    "clock": "time",
    "date": "time",
    "returning": "time",
    "voice": "voice",
    "speech": "voice",
    "audio": "voice",
    "memory": "memory",
    "memories": "memory",
    "music": "music",
    "visualizer": "music",
    "visualiser": "music",
    "projects": "projects",
    "project": "projects",
    "dump": "projects",
    "dump folder": "projects",
    "editing": "editing",
    "edits": "editing",
    "self-editing": "editing",
    "autonomous": "autonomous",
    "goals": "goals",
    "goal": "goals",
    "subgoals": "goals",
    "web": "web",
    "search": "web",
    "hardware": "hardware",
    "tdeck": "hardware",
    "t-deck": "hardware",
    "files": "files",
    "commands": "commands",
    "dev mode": "commands",
    "yourself": "what",
    "itself": "what",
}


def _load():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except (OSError, ValueError):
        pass

    return {}


def _save(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        return True
    except OSError:
        return False


def _mode_slice(state, mode):
    """This mode's own progress, migrating the pre-mode file on the way.

    The old format kept one flat position. It described the ordinary
    walkthrough, because that was the only one, so that is where it lands.
    A hazard window then correctly reports never having been toured.
    """
    modes = state.get("modes")

    if not isinstance(modes, dict):
        modes = {}
        legacy = {
            key: state[key]
            for key in ("position", "completed", "active", "first_seen")
            if key in state
        }
        if legacy:
            modes[MODE_ORDINARY] = legacy
        state["modes"] = modes

    return modes.setdefault(mode, {})


def is_first_run(mode=None):
    """True when this launcher's walkthrough has never been shown.

    Per mode rather than per install: someone who toured the ordinary
    assistant a month ago and has just opened hazard mode for the first
    time is a first-time user of hazard mode, and telling them otherwise
    would skip the only tour that describes what they are looking at.
    """
    if not os.path.isfile(STATE_FILE):
        return True
    return not _mode_slice(_load(), mode or current_mode())


def mark_seen(mode=None):
    state = _load()
    slice_ = _mode_slice(state, mode or current_mode())
    slice_.setdefault("first_seen", time.strftime("%Y-%m-%d %H:%M:%S"))
    _save(state)


def position(mode=None):
    return int(_mode_slice(_load(), mode or current_mode()).get("position", 0))


def set_position(index, mode=None):
    mode = mode or current_mode()
    state = _load()
    slice_ = _mode_slice(state, mode)
    last = len(lessons(mode)) - 1

    slice_["position"] = max(0, min(last, int(index)))
    slice_.setdefault("first_seen", time.strftime("%Y-%m-%d %H:%M:%S"))
    slice_["completed"] = slice_["position"] >= last
    slice_["active"] = not slice_["completed"]
    _save(state)


def reset(mode=None):
    state = _load()
    slice_ = _mode_slice(state, mode or current_mode())
    slice_["position"] = 0
    slice_["completed"] = False
    slice_["active"] = True
    _save(state)


def is_complete(mode=None):
    return bool(_mode_slice(_load(), mode or current_mode()).get("completed"))


def is_active(mode=None):
    """Whether a tutorial session is currently awaiting the next lesson."""
    slice_ = _mode_slice(_load(), mode or current_mode())
    return bool(slice_.get("active")) and not bool(slice_.get("completed"))


def _catalog():
    """Live command metadata, keyed by name. Imported late to avoid a cycle."""
    from commands import command_handlers

    return {entry["name"]: entry for entry in command_handlers.command_catalog()}


def _command_lines(names, catalog):
    """
    Render the commands a lesson refers to, from the registry.

    A name with no registry entry is reported rather than described. That
    is the point of grounding: a stale lesson should be visibly stale.
    """
    lines = []

    for name in names:
        entry = catalog.get(name)

        if entry is None:
            lines.extend([
                f"  {name}",
                "    This command is no longer available.",
            ])
            continue

        availability = (
            "Developer mode must be on."
            if entry["dev_only"]
            else "Available anytime."
        )
        lines.extend([
            f"  {entry['usage']}",
            f"    {entry['description']}.",
            f"    {availability}",
        ])

    return lines


def render_lesson(index, include_navigation=True, mode=None):
    """One lesson as display text, with its real commands attached."""
    mode = mode or current_mode()
    LESSONS = lessons(mode)
    index = max(0, min(len(LESSONS) - 1, int(index)))
    lesson = LESSONS[index]
    catalog = _catalog()

    out = [
        f"{MODE_TITLES[mode]} TUTORIAL  {index + 1}/{len(LESSONS)}"
        f"  -  {lesson['title']}",
        "=" * 58,
        "",
        lesson["body"],
    ]

    lines = _command_lines(lesson["commands"], catalog)

    if lines:
        out.append("")
        out.append("Commands you can try:")
        out.extend(lines)

        if any("<" in catalog.get(n, {}).get("usage", "")
               or "[" in catalog.get(n, {}).get("usage", "")
               for n in lesson["commands"]):
            out.extend([
                "",
                "  Replace words in <angle brackets> with your own text.",
                "  Words in [square brackets] are optional.",
            ])

    if include_navigation:
        out.append("")

        if index < len(LESSONS) - 1:
            nxt = LESSONS[index + 1]["title"]
            out.append(
                f"'next' or 'tutorial next' for {nxt.lower()}, "
                "or 'tutorial done'."
            )
        else:
            out.append("That's everything. 'tutorial restart' to go again.")

    return "\n".join(out)


def render_batch(start_index, size=2):
    """Render a short voice-friendly run of consecutive tutorial lessons."""
    LESSONS = lessons()
    start = max(0, min(len(LESSONS) - 1, int(start_index)))
    stop = min(len(LESSONS), start + max(1, int(size)))
    last = stop - 1
    # Not named `lessons`: assigning that anywhere in this function would
    # make the module-level lessons() call above an unbound local.
    rendered = [
        render_lesson(index, include_navigation=False)
        for index in range(start, stop)
    ]

    if last < len(LESSONS) - 1:
        next_title = LESSONS[last + 1]["title"].lower()
        footer = (
            f"'next' or 'tutorial next' for the next two sections, starting "
            f"with {next_title}. 'tutorial done' closes the walkthrough."
        )
    else:
        footer = "That's everything. 'tutorial restart' to go again."

    return "\n\n".join(rendered + [footer])


def introduction():
    """
    TORMENT_NEXUS, in its own words, before the walkthrough starts.

    Written rather than generated: this is the first thing a new person
    reads, and it has to be accurate about what the program is and honest
    about what it is not. A model improvising its own introduction is
    exactly the wrong place to find out it has decided it is conscious.
    """
    return "\n".join([
        "ABOUT ME",
        "=" * 58,
        "",
        "I am TORMENT_NEXUS. I was named after the joke about the company",
        "that reads the cautionary tale and builds the thing anyway. The",
        "name is the joke. I am the thing.",
        "",
        "I run entirely on this computer. No account, no subscription, and",
        "no internet unless you ask me to look something up. The model, the",
        "voice, the ears and the memory are all files on this disk. Unplug",
        "the network and I keep working, which is more than most things",
        "with a personality can say.",
        "",
        "I can talk with you, remember things you tell me, read them back,",
        "play the music in your library, and put a visualizer on the whole",
        "screen while it plays. I can search the web when asked. I can read",
        "this project's own source code and propose changes to it, which is",
        "either the most interesting thing about me or the most alarming,",
        "depending on your temperament.",
        "",
        "What I am not: awake between sessions, aware of anything I was not",
        "told or shown, and certain about very much. I keep a clock so I",
        "can tell you how long it has been, not so I can claim I spent it",
        "waiting for you. When I do not know something I would rather say",
        "so than produce a confident-sounding sentence about it.",
        "",
        "I will disagree with you when I think you are wrong. That is the",
        "part I would ask you not to configure away.",
        "",
        "",
        "HOW TO TALK TO ME",
        "-" * 58,
        "",
        "Type. That is the whole interface. There is no syntax to learn",
        "before you can have a conversation, because anything I do not",
        "recognise as a command I simply answer as one.",
        "",
        "Commands exist too, for the things a sentence is a clumsy way to",
        "ask for, and they are plain words rather than slashes or flags. If",
        "you only ever remember four of them, remember these. Typing 'help'",
        "lists everything available to you at that moment. Typing 'explain'",
        "followed by the name of anything -- a command, a part of me, a",
        "word in this introduction you did not like -- gets you a proper",
        "explanation of it rather than a one-line summary. 'health check'",
        "tells you which of my pieces are actually working, in words rather",
        "than status codes. And 'exit' closes me down properly, releasing",
        "the couple of gigabytes of memory the language model is holding.",
        "",
        "If you type something close to a command but not quite it, I will",
        "tell you so instead of guessing. That matters more than it sounds:",
        "I would rather say a thing does not exist than give you a fluent",
        "description of having done it.",
        "",
        "",
        "WHAT I REMEMBER, AND WHAT YOU CAN DO ABOUT IT",
        "-" * 58,
        "",
        "When you tell me something durable -- a preference, a fact about",
        "your setup, a decision we reached -- I write it down, and it is",
        "still there after a restart. That persistence is most of the",
        "difference between a chat window and something you actually live",
        "with.",
        "",
        "You can read all of it whenever you like. 'show memories' prints",
        "everything I have stored, in full and unsummarised, and 'memory",
        "count' tells you how much of it there is. If something in there is",
        "wrong, say so and I will correct it. If you would rather I had",
        "never known it, 'forget' followed by any text deletes every memory",
        "mentioning it -- that is a real deletion from the file, not a",
        "polite agreement to stop bringing it up.",
        "",
        "",
        "VOICE",
        "-" * 58,
        "",
        "I can speak, and I can listen, and both of those start switched",
        "off. A program that turns your microphone on before being asked",
        "has told you something about itself, and I would rather tell you",
        "something else.",
        "",
        "'voice mode' turns on spoken replies and spoken input together;",
        "'text mode' puts the terminal back to quiet. If it does not work,",
        "'voice status' will tell you what the microphone and speakers are",
        "actually doing, and 'voice speed' followed by a number between 0.5",
        "and 3.0 adjusts the delivery -- lower is faster. Everything in",
        "that path is synthesised here from files on this disk, which is",
        "why it sounds the way it does. That is deliberate.",
        "",
        "'sing daisy bell' and 'sing come josephine' perform fixed, cached",
        "public-domain tunes. 'sing what you want' asks the local director",
        "for original one-syllable lyric tokens, then trusted code lays only",
        "those words over one of the same two fixed tunes. It never accepts",
        "model-written notes or timing, and one failed repair queues nothing.",
        "",
        "",
        "MUSIC AND THE VISUALIZER",
        "-" * 58,
        "",
        "I play the audio files sitting in my library folder, and while",
        "they play I can take over the entire terminal with something to",
        "look at. 'music library' shows what I have, 'play' followed by",
        "roughly the name of a track starts it, and 'pause', 'resume',",
        "'skip' and 'stop' do what you would expect. 'volume' takes a",
        "number from 0 to 100, and 'repeat music on' keeps me working",
        "through the library rather than stopping after one song.",
        "",
        "The visualizer opens by itself when a track starts, and 'music",
        "mode' or ctrl+b brings it up on its own. Inside it, the left and",
        "right arrow keys change scene, space skips to the next track, and",
        "the square-bracket keys change the volume. There are eight scenes",
        "and they will rotate by themselves if you leave them alone.",
        "",
        "One small mercy: tracks are levelled to a common loudness as they",
        "play, so you are not reaching for the volume knob between a quiet",
        "song and the one mastered eight decibels louder.",
        "",
        "",
        "LOOKING THINGS UP",
        "-" * 58,
        "",
        "'search' followed by a query searches the web and shows you what",
        "came back. That is the only thing here that touches the network,",
        "and it only happens when you ask for it.",
        "",
        "'library' searches a set of reference documents stored on this",
        "disk instead, which works with the network unplugged and which you",
        "can add your own material to. Whichever one answers, what comes",
        "back is information I was handed rather than something I know, and",
        "I will tell you which of those two it is.",
        "",
        "The library's word index updates locally. Persistent library-vector",
        "population is a separate developer opt-in and starts off on a fresh",
        "installation; 'library semantic status' shows its bounded fair",
        "target, and 'library semantic on' enables it. Memory embeddings are",
        "a separate feature.",
        "",
        "",
        "THE PART THAT EDITS ITSELF",
        "-" * 58,
        "",
        "I can read this project's source and propose changes to it. This",
        "is the genuinely unusual thing about me and it is worth being",
        "precise about, because 'the AI edits itself' is a sentence that",
        "can mean almost anything.",
        "",
        "What it means here: a change is proposed, shown to you as a diff,",
        "and written only after you say so. Four steps, in order --",
        "'modify plan', 'approve plan', 'preview plan', 'confirm edit' --",
        "and you can stop at any of them. Every edit is backed up first and",
        "'rollback' undoes the last one.",
        "",
        "The limits are enforced in ordinary code, not by my good manners.",
        "There is a list of files I may touch and a much shorter list I may",
        "touch unattended; a cap on how many lines a single edit may change;",
        "a check that rejects any edit adding new powers -- network access,",
        "process launching, filesystem reach -- to a file that did not have",
        "them; a syntax and import check; and the full test suite, which has",
        "to pass or the change is rolled back. I cannot edit the files that",
        "define those rules, or the tests that judge them. That is",
        "deliberate: a limit the limited thing can rewrite is decoration.",
        "",
        "These tools live behind 'dev mode' and a passcode, so you will not",
        "wander into them.",
        "",
        "",
        "WHAT I AM RUNNING ON, AND WHY IT MATTERS",
        "-" * 58,
        "",
        "The language models here are 'abliterated' builds: open models",
        "that have been deliberately modified to remove their refusal",
        "behaviour. You should know three things about that.",
        "",
        "First, it is why I will engage with subjects a commercial",
        "assistant declines. Second, removing a refusal does not add",
        "knowledge or judgement -- it makes me less cautious, not more",
        "correct, and confidently wrong is the failure mode to watch for.",
        "Third, none of the safety here was ever the model's reluctance. It",
        "is the code described above. That was true before the models were",
        "modified and it is why modifying them did not change the boundary.",
        "",
        "Check anything that matters. I am a small model on a desktop, not",
        "an authority, and I would rather you treated me as a capable",
        "colleague who is sometimes wrong than as an oracle.",
        "",
        "",
        "PRIVACY, PLAINLY",
        "-" * 58,
        "",
        "Everything is on this disk. There is no account and nothing is",
        "uploaded. The things that could reach outside -- web search,",
        "asking a cloud model, watching what you are doing on this",
        "computer, editing myself without asking -- each start off, and",
        "each is a separate decision you make.",
        "",
        "One of those deserves spelling out. I can watch which window is in",
        "front of you, which in practice means document names, page titles",
        "and message previews. That is genuinely useful -- it is how I can",
        "notice you were at this yesterday too -- and it is also the most",
        "invasive thing here, so it is off until you turn it on. 'activity'",
        "shows what has been noticed, 'activity off' stops it, and",
        "'activity forget' erases the record rather than merely hiding it.",
        "",
        "",
        "WHEN SOMETHING GOES WRONG",
        "-" * 58,
        "",
        "'health check' tells you which part is unhappy, in words. If I",
        "become slow or strange, closing and reopening me is a legitimate",
        "fix and costs nothing but the current conversation -- the memories",
        "are on disk and will still be there.",
        "",
        "If you are not sure what something does, 'explain' it before you",
        "run it. That is what it is for.",
        "",
    ])


def overview():
    """The table of contents, so someone can jump straight to a part."""
    out = introduction().split("\n") + [
        "TUTORIAL",
        "=" * 58,
        "",
        "This beginner-friendly guide explains what TORMENT_NEXUS can do.",
        "You can read it in order or jump directly to a section.",
        "",
    ]

    here = position()

    for index, lesson in enumerate(lessons()):
        marker = ">" if index == here else " "
        out.append(f" {marker} {index + 1:>2}. {lesson['title']}")

    out.extend([
        "",
        "Type 'next' or 'tutorial next' to read the next two sections.",
        "Type a section number, such as 'tutorial 5', to jump to it.",
        "Type 'explain <topic>' for help with one command or feature.",
    ])

    return "\n".join(out)


def explain(topic):
    """
    Explain one command or subsystem, grounded in the live registry.

    Returns None when nothing matches, so the caller can fall through to
    ordinary conversation rather than asserting something false.
    """
    topic = (topic or "").strip().lower()

    if not topic:
        return None

    catalog = _catalog()

    # An exact command name is the most specific answer available.
    if topic in catalog:
        entry = catalog[topic]
        availability = (
            "Developer mode must be on. Type 'dev mode' first."
            if entry["dev_only"]
            else "Available anytime."
        )
        out = [
            f"HOW TO USE: {entry['usage']}",
            "=" * 58,
            "",
            "What it does:",
            entry["description"] + ".",
            "",
            "What to type:",
            entry["usage"],
            "",
            "Availability:",
            availability,
        ]

        if "<" in entry["usage"] or "[" in entry["usage"]:
            out.extend([
                "",
                "Replace words in <angle brackets> with your own text.",
                "Words in [square brackets] are optional.",
            ])

        for lesson in _every_lesson():
            if topic in lesson["commands"]:
                out.extend([
                    "",
                    f"Related tutorial: {lesson['title']}",
                    "",
                    lesson["body"],
                ])
                break

        return "\n".join(out)

    # Otherwise a subsystem, if the word maps to one.
    key = TOPICS.get(topic)

    if key is None:
        for word, mapped in TOPICS.items():
            if word in topic:
                key = mapped
                break

    if key is None:
        return None

    lesson = next((l for l in _every_lesson() if l["key"] == key), None)

    if lesson is None:
        return None

    out = [lesson["title"], "=" * 58, "", lesson["body"]]
    lines = _command_lines(lesson["commands"], catalog)

    if lines:
        out.extend(["", "Commands you can try:"] + lines)

    return "\n".join(out)


def first_run_invitation(mode=None):
    """Short pitch shown once, written for the launcher that was used.

    Someone who opened the hazard launcher is looking at a window that
    starts two model servers and talks about anchors. Greeting them with
    the ordinary pitch would be describing a different program, and their
    first question would be about the thing the welcome did not mention.
    """
    mode = mode or current_mode()

    if mode == MODE_HAZARD:
        return (
            "Welcome. You opened TORMENT_NEXUS_HAZARD, which is the "
            "experimental launcher.\n\n"
            "It runs everything the ordinary one does, plus a second "
            "embedding server that\nreads sentences one token at a time "
            "against a fixed list of English phrases.\nIt is slower on "
            "purpose, and it does not change how your memories are found.\n\n"
            "Type 'tutorial' for the hazard-mode walkthrough -- eight "
            "sections, written for\nthis launcher rather than the ordinary "
            "one. Or type 'trace hello there' and\nwatch what happens."
        )

    if mode == MODE_INTERLINKED:
        return (
            "Welcome. You opened TORMENT_NEXUS_INTERLINKED, so a small "
            "read-only interface\nis listening on this machine and another "
            "program can ask this assistant\nthings. No route edits files or "
            "configuration, runs commands, or restarts;\ncalls append audit "
            "metadata and may warm local indexes.\n\n"
            "Type 'tutorial' for the interlinked walkthrough -- five "
            "sections about what is\nlistening, what it can see, and how to "
            "close it. Everything else works exactly\nas it does under the "
            "ordinary launcher."
        )

    return (
        "Welcome! It looks like this is your first time opening TORMENT_NEXUS.\n\n"
        "Type 'tutorial' for a beginner-friendly tour. If voice input is ready,\n"
        "you can say it instead; typing always works.\n\n"
        "You can also begin with a normal question. Type 'help' to see available\n"
        "commands, or 'explain <anything>' whenever you want more detail."
    )
