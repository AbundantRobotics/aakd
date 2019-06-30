
import re
import telnetlib
import time
import math
import atexit
import struct
import socket
import collections
import threading


def akd_parse_internal(s):
    if s[0] == 70:  # Note that elements of a byte string are ints, 70 is 'F'
        factor = int(s[1:2])  # Slice to get a string
        return int(s[2:], 16) * pow(10, -factor)
    return int(s, 16)


"""
Trying to set the window size to a big enough size so that we can get big messages back without line breaks.
see https://stackoverflow.com/questions/38288887/python-telnetlib-read-until-returns-cut-off-string
"""
from telnetlib import DO, DONT, IAC, WILL, WONT, NAWS, SB, SE
MAX_WINDOW_WIDTH = 20000  # Max Value: 65535
MAX_WINDOW_HEIGHT = 65535
def set_max_window_size(tsocket, command, option):
    """
    Set Window size to resolve line width issue
    Set Windows size command: IAC SB NAWS <16-bit value> <16-bit value> IAC SE
    --> inform the Telnet server of the window width and height.
    Refer to https://www.ietf.org/rfc/rfc1073.txt
    :param tsocket: telnet socket object
    :param command: telnet Command
    :param option: telnet option
    :return: None
    """
    if option == NAWS:
        width = struct.pack('H', MAX_WINDOW_WIDTH)
        height = struct.pack('H', MAX_WINDOW_HEIGHT)
        tsocket.send(IAC + WILL + NAWS)
        tsocket.send(IAC + SB + NAWS + width + height + IAC + SE)
    # -- below code taken from telnetlib source
    elif command in (DO, DONT):
        tsocket.send(IAC + WONT + option)
    elif command in (WILL, WONT):
        tsocket.send(IAC + DONT + option)


class AKD:
    """
    Can be used simply as an object
    (in which case it will release the telnet port only when program exits)
    or can be used in a contextmanager (`with`)
    """

    def __init__(self, ip, trace=False):
        try:
            t = telnetlib.Telnet(ip, port=2222, timeout=1)
        except socket.timeout:
            t = None
        if not t:
            raise Exception("Could not connect to " + ip +
                            ", verify that nothing is already connected to it.")
        self.t = t
        self.t.set_option_negotiation_callback(set_max_window_size)
        self.ip = ip
        self.trace = trace
        self.t.read_very_eager()  # safety for random garbage
        self.name = self.commandS("drv.name")
        atexit.register(AKD.__del__, self)

    def __del__(self):
        if 't' in self.__dict__:
            self.t.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.t:
            self.t.close()
        return False

    def command(self, cmd, timeout=5):
        sending = cmd.encode('ascii') + b'\r\n'
        if self.trace:
            print(repr(sending))
        self.t.write(sending)

        answer = b""
        while True:
            answer += self.t.read_until(b"-->", timeout)
            if not answer:
                raise Exception("AKD {} (cmd: {}) doesn't respond".format(self.name, repr(cmd)))
            g = re.match(b"Error:(.*)", answer, re.MULTILINE | re.DOTALL)
            if g:
                raise Exception("AKD {} (cmd: {}) Error: {}".format(self.name, repr(cmd), g.group(1)))
            r = re.match(b"(.*)\r\n-->", answer, re.MULTILINE | re.DOTALL)
            if not r:
                continue
            if self.trace:
                print(repr(answer))
            return r.group(1)

    def commandI(self, cmd):
        return int(self.command(cmd))

    def commandF(self, cmd, unit=False):
        """ Execute command and return the result as a float.
            If unit is given also return the unit.
        """
        r = self.command(cmd)
        g = re.match(b"(.*?)( \[(.*?)\])", r)
        if g:
            if unit and g.group(2):
                return (float(g.group(1)), g.group(3).decode())
            else:
                return float(g.group(1))
        else:
            raise Exception("Expecting a float, got {}", r)

    def commandS(self, cmd):
        """ Execute command and return the result as a string. """
        s = self.command(cmd).decode().replace('\r\n', '\n')
        return s

    def cset(self, var, value):
        """ Set a variable. """
        if isinstance(value, float):  # floats are rejected when they have more than 3 digits
            self.command("{} {:.3f}".format(var, value))
        else:
            self.command(var + ' ' + str(value))

    def save_params(self, filename):
        with open(filename, 'w') as f:
            s = self.commandS("drv.nvlist")
            f.write(s)

    def load_params(self, filename):
        with open(filename) as f:
            for l in f:
                if l[0] != '#':
                    self.command(l.rstrip('\r\n'))

    def factory_params(self):
        return self.command("drv.rstvar", 20)  # long to do that

    def flash_params(self):
        return self.command("drv.nvsave")

    def rec_columns(self):
        """ Returns the list of the fields setup to be recorded. """
        return self.commandS("rec.retrievehdr").splitlines()[2].split(',')

    def rec_setup(self, frequency, to_record):
        """ Frequency [hz] parameter
        Note that recording one channel, we can go up to gap 5 (less than 4khz)
        three channels we go to gap 6 (3khz) etc.
        With normal format, instead of the internal,
        that is even worse, degrade by 2x almost
        """
        if (len(to_record) > 5):
            raise Exception("Cannot record more than 5 channels")

        gap = math.ceil(16000.0 / frequency)
        frequency = 16000 / gap

        self.command("rec.off")
        self.cset("rec.gap", gap)
        self.cset("rec.numpoints", 10000)  # max buffer size for recording
        self.cset("rec.stoptype", 1)  # 0 for one shot, 1 for continuous
        self.cset("rec.retrievefrmt", 1)  # 0 for readable, 1 for internal
        self.cset("rec.retrievesize", 4800)

        j = 1
        for c in to_record:
            self.cset("rec.ch" + str(j), c)
            j += 1
        while j <= 6:
            self.cset("rec.ch" + str(j), "clear")
            j += 1
        self.frequency = frequency
        return frequency

    def rec_start(self):
        self.command("rec.trig")
        self.rec_time = 0
        self.rec_time_incr = 1 / self.frequency

    def rec_get(self, data):
        lines = self.command("rec.retrievedata").splitlines()
        gotdata = False
        for l in lines[1:]:
            data.append([
                self.rec_time,
                *(akd_parse_internal(v) for v in l.split(b','))
            ])
            self.rec_time = self.rec_time + self.rec_time_incr
            gotdata = True
        return gotdata

    def rec_stop(self, data):
        self.command("rec.off")
        while self.rec_get(data):
            pass

    def rec_header(self):
        return "time [s]," + ",".join(self.rec_columns())

    def set_std_units(self):
        self.cset("unit.protary", 2)  # deg
        self.cset("unit.vrotary", 1)  # rev/s
        self.cset("unit.accrotary", 1)  # rev/s/s
        self.cset("unit.pin", 1048576)
        self.cset("unit.pout", 1)

    def temperature(self):
        return self.commandI("motor.tempc")

    def faults(self):
        fault_string = self.commandS("drv.faults")
        if (fault_string and fault_string != "No faults active"):
            return fault_string.splitlines()
        else:
            return []

    def clear_faults(self):
        self.command("drv.clrfaults")

    def enable(self):
        self.clear_faults()
        self.command("drv.en")
        while not self.commandI("drv.active"):
            time.sleep(0.1)
            f = self.faults()
            if f:
                raise Exception("Drive Faults: " + f)
            self.command("drv.en")
        print("Drive enabled")

    def disable(self):
        while self.commandI("drv.active"):
            self.command("drv.dis")
            time.sleep(0.1)
        print("Drive disabled")


def record(akds, files, frequency, to_records, internal_trigger_akd_index=-1,
           interact_callback=lambda akd: False):
    buffers = [collections.deque() for a in akds]

    for a, t in zip(akds, to_records):
        a.rec_setup(frequency, t)

    def worker(a, b, c):
        try:
            a.rec_start()
            b.append([a.rec_header()])
            while not c(a):
                a.rec_get(b)
        finally:
            try:
                a.rec_stop(b)
            except:
                print("possible bad file")

    stop = False
    cnt = 0

    def internal_trigger_callback(a):
        if cnt < 2:
            a.cset("DOUT1.STATEU", 0)
        elif cnt < 3:
            a.cset("DOUT1.STATEU", 1)
        elif cnt < 4:
            a.cset("DOUT1.STATEU", 0)
        cnt = cnt + 1
        return stop or interact_callback(a)

    def regular_callback(a):
        return stop or interact_callback(a)

    threads = []
    for i, (a, b) in enumerate(zip(akds, buffers)):
        if i == internal_trigger_akd_index:
            threads.append(threading.Thread(target=worker, args=(a, b, internal_trigger_callback)))
        else:
            threads.append(threading.Thread(target=worker, args=(a, b, regular_callback)))

    for t in threads:
        t.start()

    def empty_buffers():
        for b, f in zip(buffers, files):
            topop = len(b)
            for _ in range(topop):
                print(','.join(str(v) for v in b.popleft()), file=f)
            f.flush()

    while not stop:
        try:
            empty_buffers()
            for t in threads:
                stop = stop or not t.is_alive()
            time.sleep(0.01)
        except KeyboardInterrupt:
            print("Stopping the recording")
            stop = True
            for t in threads:
                t.join()
            empty_buffers()
        except:
            stop = True
            print("possible bad file")
            raise


def current_profile(a, prog_start_time, ctt):
    """ Apply the current time table `ctt` to the drive `a`.
    The table is supposed to be tuples (start_time, end_time, current)
    Like: [(0, 1, 5), (1, 2, -5)] to apply 5 Arms for 1 sec then -5 for another
    """
    t = time.monotonic() - prog_start_time
    for (start_time, end_time, current) in ctt:
        if (start_time < t <= end_time):
            a.cset("il.cmdu", current)
            return False
    return True


def record_current_profile(a, ctt, file, frequency=500,
                           to_record=["IL.FB", "IL.CMD", "VL.FB"]):
    a.disable()
    a.cset("drv.cmdsource", 0)  # service mode
    a.cset("drv.opmode", 0)  # torque mode
    a.enable()

    start_time = time.monotonic()

    def callback(a):
        return current_profile(a, start_time, ctt)

    with open(file, mode='w') as f:
        record([a], [f], frequency, [to_record], interact_callback=callback)


def velocity_profile(a, prog_start_time, vtt, repeat=False):
    t = time.monotonic() - prog_start_time
    if repeat:
        t = t % vtt[-1][1]
    for (end_time, velocity) in vtt:
        if t < end_time:
            a.cset("vl.cmdu", velocity)
            return False
    return True


def record_velocity_profile(a, vtt, file, frequency=500,
                            to_record=["IL.FB", "VL.CMD", "VL.FB"], repeat=False):
    a.disable()
    a.cset("drv.cmdsource", 0)  # service mode
    a.cset("drv.opmode", 1)  # velocity mode
    a.enable()

    start_time = time.monotonic()

    def callback(a):
        return velocity_profile(a, start_time, vtt, repeat=repeat)

    with open(file, mode='w') as f:
        record([a], [f], frequency, [to_record], interact_callback=callback)
