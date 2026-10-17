import asyncio
import json
import re
import time
import urllib.error
import urllib.request


WEBHOOK_URL = "https://discord.com/api/webhooks/1560829918642708490/EqFP2EeHzu2ygAACdhcHV1bPetR7GKJg5ltLSPkavrM5nPpw-omXanhaT7YgLMSvpLi2"    # paste your Discord webhook URL between the quotes; empty = only print
EXCLUDE_ME = False  # True = don't count yourself (the account running the game)
MIN_SECONDS_BETWEEN_POSTS = 20

JOIN_CODE = (144, 2)          # "a player joined" (4 of these when the room grew by 4)
JOIN_LOG_FILE = "join_packets.log"
MAX_JOIN_LOGS = 60

NAME_PATTERN = re.compile(rb"[A-Za-z0-9_+]{2,}#[0-9]{4}")


def read_short(buf, pos):
    # reads a 2-byte number from the packet bytes
    if len(buf) < pos + 2:
        return None
    return (buf[pos] << 8) | buf[pos + 1]


def send_to_discord(text):
    data = json.dumps({"content": text}).encode("utf-8")
    request = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "tfm-room-counter/1.0",
        },
    )
    urllib.request.urlopen(request, timeout=10).read()


class Plugin:
    name = "counter"

    def __init__(self):
        self.room = None
        self.count = None            # live count (includes you)
        self.known_names = set()     # names seen in the room's player list
        self.printed_count = None
        self.posted_count = None
        self.last_post_time = 0
        self.flush_task = None
        self.tested = False
        self.join_logs = 0

    async def tear_down(self):
        pass

    def shown_count(self):
        if self.count is None:
            return None
        if EXCLUDE_ME:
            return max(self.count - 1, 0)
        return self.count

    async def post(self, text):
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, send_to_discord, text)
            return True
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode("utf-8", "replace")
            print("Discord post failed: HTTP {} {}".format(e.code, body))
        except Exception as e:
            print("Discord post failed:", repr(e))
        return False

    async def webhook_check(self):
        self.tested = True

        if not WEBHOOK_URL:
            print("Discord: WEBHOOK_URL is empty in this file, so nothing will be posted.")
            return

        valid = ("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")
        if not WEBHOOK_URL.startswith(valid):
            print("Discord: the link does not look like a webhook URL "
                  "(it should start with https://discord.com/api/webhooks/).")

        if await self.post("Counter plugin started."):
            print("Discord: test message sent. Check your channel.")

    async def send_count(self):
        shown = self.shown_count()
        if shown is None or not WEBHOOK_URL or shown == self.posted_count:
            return

        self.last_post_time = time.time()
        text = "**{}**: {} players".format(self.room or "unknown room", shown)
        if await self.post(text):
            self.posted_count = shown

    async def flush_later(self, wait):
        await asyncio.sleep(wait)
        await self.send_count()

    async def changed(self):
        shown = self.shown_count()
        if shown is None:
            return

        if shown != self.printed_count:
            self.printed_count = shown
            print("[{}] {}: {} players".format(
                time.strftime("%H:%M:%S"), self.room or "unknown room", shown))

        if not WEBHOOK_URL or shown == self.posted_count:
            return

        wait = MIN_SECONDS_BETWEEN_POSTS - (time.time() - self.last_post_time)
        if wait > 0:
            # too soon: post the latest number once the wait is over
            if self.flush_task is None or self.flush_task.done():
                self.flush_task = asyncio.ensure_future(self.flush_later(wait))
            return

        await self.send_count()

    def log_join(self, now, tag, names, buf):
        if self.join_logs >= MAX_JOIN_LOGS:
            return
        self.join_logs += 1
        shown_names = ",".join(n.decode("utf-8", "replace") for n in names) or "-"
        with open(JOIN_LOG_FILE, "a") as f:
            f.write("{} {} names={} size={} {}\n".format(
                now, tag, shown_names, len(buf), buf[:48].hex()))

    async def packet_received(self, client, conn, packet):
        if not self.tested:
            await self.webhook_check()

        if conn.name != "bulle":
            return

        try:
            buf = bytes(packet.buffer)
            if len(buf) < 2:
                return

            code = (buf[0], buf[1])
            now = time.strftime("%H:%M:%S")

            if code == (5, 21):
                # room name: 1 byte flag, 2 byte length, then the text
                size = read_short(buf, 3)
                self.room = buf[5:5 + size].decode("utf-8", "replace")
                self.count = None
                self.known_names = set()
                self.printed_count = None
                self.posted_count = None

            elif code == (144, 1):
                # player list, when you join a room
                self.known_names = set(NAME_PATTERN.findall(buf))
                self.count = read_short(buf, 2)
                await self.changed()

            elif code == (5, 2):
                # new map: the game's own count, used to correct the live one
                actual = read_short(buf, 6)
                if actual is not None:
                    print("[{}] round check: live count was {} | game says {}".format(
                        now, self.count, actual))
                    self.count = actual
                    await self.changed()

            elif code == JOIN_CODE:
                names = set(NAME_PATTERN.findall(buf))
                is_new = (not names) or bool(names - self.known_names)
                self.log_join(now, "NEW" if is_new else "KNOWN", names, buf)

                if is_new and self.count is not None:
                    self.count += 1
                    self.known_names |= names
                    await self.changed()

        except Exception as e:
            print("counter plugin error:", repr(e))

    async def packet_sent(self, client, conn, fingerprint, packet):
        pass


plugin = Plugin()
