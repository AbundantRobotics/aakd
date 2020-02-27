
import re
import telnetlib
import time
import math
import atexit
import struct
import socket


def nice_name(name, ip):
    return name + " (ip: " + ip + ")"


def akd_parse_internal(s):
    if s[0] == 70:  # Note that elements of a byte string are ints, 70 is 'F'
        factor = int(s[1:2])  # Slice to get a string
        return int(s[2:], 16) * pow(10, -factor)
    return int(s, 16)


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

    Trying to set the window size to a big enough size so that we can get big messages back without line breaks.
    see https://stackoverflow.com/questions/38288887/python-telnetlib-read-until-returns-cut-off-string
    """
    from telnetlib import DO, DONT, IAC, WILL, WONT, NAWS, SB, SE
    MAX_WINDOW_WIDTH = 20000  # Max Value: 65535
    MAX_WINDOW_HEIGHT = 65535

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

    def __init__(self, ip, port=23, trace=False):
        self.ip = ip
        self.port = port
        self.trace = trace
        self.connect()
        self.name = self.commandS("drv.name")
        atexit.register(AKD.disconnect, self)

    def nice_name(self):
        return nice_name(self.name, self.ip)

    def connect(self):
        try:
            t = telnetlib.Telnet(self.ip, port=self.port, timeout=1)
        except socket.timeout:
            t = None
        if not t:
            raise Exception("Could not connect to " + self.ip +
                            ", verify that nothing is already connected to it.")
        self.t = t
        self.t.set_option_negotiation_callback(set_max_window_size)
        self.t.read_very_eager()  # safety for random garbage

    def disconnect(self):
        if 't' in self.__dict__:
            if self.t:
                self.t.close()

    def __enter__(self):
        return self

    def __del__(self):
        self.disconnect()

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
        return False

    def remove_comment(self, cmd):
        m = re.match("(.*?)\s*#.*", cmd)
        if m:
            cmd = m.group(1)
        return cmd

    def command(self, cmd, timeout=5):
        cmd = self.remove_comment(cmd)
        if not cmd:
            return b""
        sending = cmd.encode('ascii') + b'\r\n'
        if self.trace:
            print(time.time(), repr(sending), flush=True)
        self.t.write(sending)

        answer = b""
        while True:
            answer += self.t.read_until(b"-->", timeout)
            if not answer:
                if self.trace:
                    print(time.time(), repr(answer), flush=True)
                raise Exception("AKD {} (cmd: {}) doesn't respond".format(self.name, repr(cmd)))
            g = re.match(b"Error:(.*)", answer, re.MULTILINE | re.DOTALL)
            if g:
                if self.trace:
                    print(time.time(), repr(answer), flush=True)
                raise Exception("AKD {} (cmd: {}) Error: {}".format(self.name, repr(cmd), g.group(1)))
            r = re.match(b"(.*)\r\n-->", answer, re.MULTILINE | re.DOTALL)
            if not r:
                continue
            if self.trace:
                print(time.time(), repr(answer), flush=True)
            return r.group(1)

    def commandI(self, cmd, unit=False):
        """ Execute command and return the result as am int.
            If unit is given also return the unit.
        """
        r = self.command(cmd)
        g = re.match(b"\s*([^ ]+)( \[(.*)\])?", r)
        if g:
            if unit and g.group(2):
                return (int(g.group(1)), g.group(3).decode('latin-1'))
            else:
                return int(g.group(1))
        else:
            raise Exception("Expecting an int, got {}".format(r))

    def commandF(self, cmd, unit=False):
        """ Execute command and return the result as a float.
            If unit is given also return the unit.
        """
        r = self.command(cmd)
        g = re.match(b"\s*([^ ]+)( \[(.*)\])?", r)
        if g:
            if unit and g.group(2):
                return (float(g.group(1)), g.group(3).decode('latin-1'))
            else:
                return float(g.group(1))
        else:
            raise Exception("Expecting a float, got {}".format(r))

    def commandS(self, cmd):
        """ Execute command and return the result as a string. """
        s = self.command(cmd).decode('latin-1').replace('\r\n', '\n')
        return s

    def cset(self, var, value):
        """ Set a variable. """
        if isinstance(value, float):  # floats are rejected when they have more than 3 digits
            return self.command("{} {:.3f}".format(var, value))
        else:
            return self.command(var + ' ' + str(value))

    def drv_infos(self):
        s = "# DRV.INFO\n#   "
        s += "\n#   ".join(self.commandS("drv.info").splitlines())

        info_vars = ["IP.MODE",
                     "IL.KPDRATIO",
                     "MOTOR.BRAKE",
                     "MOTOR.CTF0",
                     "MOTOR.ICONT",
                     "MOTOR.INERTIA",
                     "MOTOR.IPEAK",
                     "MOTOR.KE",
                     "MOTOR.KT",
                     "MOTOR.LDLL",
                     "MOTOR.LISAT",
                     "MOTOR.LQLL",
                     "MOTOR.NAME",
                     "MOTOR.POLES",
                     "MOTOR.R",
                     "MOTOR.RSOURCE",
                     "MOTOR.RTYPE",
                     "MOTOR.TBRAKEAPP",
                     "MOTOR.TBRAKERLS",
                     "MOTOR.TEMPFAULT",
                     "MOTOR.TYPE",
                     "MOTOR.VMAX",
                     "MOTOR.VOLTMAX",
                     "FB1.IDENTIFIED"]
        for v in info_vars:
            try:
                s += "\n# {} {}".format(v, self.commandS(v))
            except Exception:
                # silently fail since those params might not be part of the drive params (eg AKDC)
                pass

        s += "\n#\n# DRV.NVCHECK {}".format(self.commandS("drv.nvcheck"))
        return s


    def save_params(self, filename, diffonly=True):
        with open(filename, 'w') as f:
            if diffonly:
                dd = self.diff_params()
                for d in dd:
                    print("{} {}   # ({})".format(d[0], d[1], d[2]), file=f)
            else:
                s = self.commandS("drv.nvlist")
                f.write(s)

            print("\n### Infos\n", file=f)
            print(self.drv_infos(), file=f)


    def load_params(self, filename, flash_afterward=True, factory_reset=False, trust_drv_nvcheck=True):
        with open(filename) as f:
            needs_update = True

            if trust_drv_nvcheck:
                for line in f:
                    g = re.match("^# DRV.NVCHECK ([^ ]+)\n$", line)
                    if g:
                        if g.group(1) == self.commandS("DRV.NVCHECK"):
                            needs_update = False
                            print("{}\tMatching nvcheck found, no need to restore".format(self.nice_name()))

            if needs_update:
                print("{}\tRestoring parameters from {}".format(self.nice_name(), filename))
                if factory_reset:
                    self.factory_params()
                f.seek(0)
                for l in f:
                    if l[0] != '#':
                        self.command(l.rstrip('\r\n'))
                if flash_afterward:
                    self.flash_params()


    def diff_params(self):
        """ Return a list of (parameter, value, defaultvalue) for non default parameters in the drive """
        delta = []
        s = self.commandS("drv.difvar")
        for l in s.splitlines():
            g = re.match("(.*?) (.*?) \((.*)\)", l)
            if not g:
                raise Exception("Unexpected difvar output:", l)
            delta.append((g.group(1), g.group(2), g.group(3)))
        return delta

    def factory_params(self):
        return self.command("drv.rstvar", 20)  # long to do that

    def flash_params(self):
        r = self.command("drv.nvsave", 10)
        time.sleep(1)  # After saving, the falsh is written a bit after (background job)
        return r

    def rec_columns(self):
        """ Returns the list of the fields setup to be recorded. """
        return self.commandS("rec.retrievehdr").splitlines()[2].split(',')

    def rec_setup(self, frequency, to_record, numpoints=10000):
        """ Frequency [hz] parameter
        Note that recording one channel, we can go up to gap 5 (less than 4khz)
        three channels we go to gap 6 (3khz) etc.
        With normal format, instead of the internal,
        that is even worse, degrade by 2x almost
        """
        if (len(to_record) > 6):
            raise Exception("Cannot record more than 6 channels")

        gap = math.ceil(16000.0 / frequency)
        frequency = 16000 / gap

        self.command("rec.off")
        self.cset("rec.gap", gap)
        self.cset("rec.numpoints", min(int(numpoints), 10000))  # max buffer size for recording
        self.cset("rec.stoptype", 1)  # 0 for one shot, 1 for continuous
        self.cset("rec.trigtype", 0)
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

    def rec_setup_bitmask_trigger(self, trig_parameter, trig_bitmask, trig_value, trig_percent=90):
        self.cset("rec.stoptype", 0)
        self.cset("rec.trigtype", 5)
        self.cset("rec.trigparam", trig_parameter)
        self.cset("rec.trigmask", trig_bitmask)
        self.cset("rec.trigval", trig_value)
        self.cset("rec.trigpos", trig_percent)

    def rec_start(self):
        self.command("rec.trig")
        self.rec_time = 0
        self.rec_time_incr = 1 / self.frequency

    def rec_get(self, data, index=None):
        if index is None:
            lines = self.command("rec.retrievedata").splitlines()
        else:
            lines = self.cset("rec.retrievedata", index).splitlines()
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

    def faults(self, warnings=False):
        faults = []

        fault_string = self.commandS("drv.faults")
        if (fault_string and fault_string != "No faults active"):
            faults = [ 'F' + f for f in fault_string.splitlines()]

        if warnings:
            fault_string = self.commandS("drv.warnings")
            if (fault_string and fault_string != "No warnings active"):
                faults.extend([ 'W' + f for f in fault_string.splitlines()])

        return faults

    def faults_short(self, warnings=False):
        fault_string = ""
        for i in range(1, 11):
            f = self.commandI("drv.fault" + str(i))
            if f:
                fault_string += (',' if fault_string else '') + 'F' + str(f)
            else:
                break
        if warnings:
            for i in range(1, 11):
                f = self.commandI("drv.warning" + str(i))
                if f:
                    fault_string += (',' if fault_string else '') + 'W' + str(f)
                else:
                    break
        return fault_string

    def disable_sources(self):
        drv_dissources_table = [
            "Software disable",
            "Fault exists",
            "Hardware disable",
            "In-rush disable (no high power)",
            "Initialization disable (the drive did not finish the initialization)",
            "Controlled stop disable from a digital input",
            "Field Bus requested disable (SynqNet and EtherNet / IP only)",
            "AKD-C requested disable (AKD-N only)",
            "AKD pre-charge disable (AKD-C only)",
            "Unknown",
            "AKD-C in download mode"
        ]
        dissources = []
        drvdisss = self.commandI("drv.dissources")
        for source in drv_dissources_table:
            if drvdisss & 1:
                dissources.append(source)
            drvdisss = drvdisss >> 1
        return dissources


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

