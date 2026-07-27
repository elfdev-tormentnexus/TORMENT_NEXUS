"""
Incremental filter for streamed model output.

Two problems this solves that don't exist when you get the whole reply
at once:

1. Tags arrive split. "<think>" can turn up as "<thi" in one chunk and
   "nk>" in the next, so you cannot just check each chunk for the tag.
   Text that might be the start of a tag is held back until we know.

2. You have to decide what to show BEFORE you have seen the end. Once
   a hallucinated turn marker appears there is no point generating any
   further, so the caller is told to hang up.
"""

# Reasoning blocks to hide. Qwen3 emits these unless the chat template
# disables them.
_OPEN = "<think>"
_CLOSE = "</think>"

# The model writing one of these means it has started inventing the
# rest of the conversation.
_TURN_MARKERS = [
    "\nUser:",
    "\nAssistant:",
    "\nYou:",
    "\nAI:",
]

# Longest thing we might need to hold back while waiting for more text.
_TAGS = [_OPEN, _CLOSE] + _TURN_MARKERS


def _holdback_len(buf):
    """
    How many characters at the end of buf could be the start of a tag
    we care about. Those get held until the next chunk resolves them.
    """
    best = 0

    for tag in _TAGS:
        limit = min(len(tag) - 1, len(buf))

        for k in range(1, limit + 1):
            if buf.endswith(tag[:k]):
                if k > best:
                    best = k

    return best


class StreamFilter:
    def __init__(self):
        self.raw = ""          # everything the model sent
        self.visible = ""      # what the user should actually see
        self.stopped = False   # caller should close the connection

        self._buf = ""
        self._in_think = False

    def feed(self, piece):
        """
        Push a chunk in, get back only the newly displayable text.
        Returns "" when everything so far is held back or hidden.
        """
        if not piece or self.stopped:
            return ""

        self.raw += piece
        self._buf += piece

        out = []

        while True:
            if self._in_think:
                idx = self._buf.find(_CLOSE)

                if idx == -1:
                    # Still inside a reasoning block. Keep only what
                    # might be a partial closing tag.
                    hold = _holdback_len(self._buf)
                    self._buf = self._buf[len(self._buf) - hold:] if hold else ""
                    break

                self._buf = self._buf[idx + len(_CLOSE):]
                self._in_think = False
                continue

            idx = self._buf.find(_OPEN)

            if idx != -1:
                out.append(self._buf[:idx])
                self._buf = self._buf[idx + len(_OPEN):]
                self._in_think = True
                continue

            hold = _holdback_len(self._buf)

            if hold:
                out.append(self._buf[:len(self._buf) - hold])
                self._buf = self._buf[len(self._buf) - hold:]
            else:
                out.append(self._buf)
                self._buf = ""

            break

        new_text = "".join(out)

        if not new_text:
            return ""

        candidate = self.visible + new_text

        # Did a hallucinated turn appear? Cut there and tell the caller
        # to stop pulling tokens.
        cut = -1

        for marker in _TURN_MARKERS:
            found = candidate.find(marker)

            if found != -1 and (cut == -1 or found < cut):
                cut = found

        if cut != -1:
            candidate = candidate[:cut]
            self.stopped = True

        emitted = candidate[len(self.visible):]
        self.visible = candidate

        return emitted

    def finish(self):
        """
        Flush anything still held back. Called once the stream ends, in
        case the reply ended mid-holdback.
        """
        if self._in_think or self.stopped:
            self._buf = ""
            return ""

        tail = self._buf
        self._buf = ""

        if not tail:
            return ""

        # The stream is over, so a suffix that merely *resembles the
        # start of a tag can no longer become one. Emit it directly.
        # Feeding it through feed() again would hold it back a second
        # time and also duplicate it in raw.
        self.visible += tail
        return tail
