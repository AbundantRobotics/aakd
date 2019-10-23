
import collections
import threading
import time

from datetime import datetime


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
        nonlocal cnt
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


def record_on_fault(a, frequency, duration, to_record, polling_period=0.1, stop=lambda: False):
    """
    """
    numpoints = frequency * duration
    a.rec_setup(frequency, to_record, numpoints)
    a.rec_setup_bitmask_trigger("DS402.STATUSWORD", 8, 8)
    # wait for no faults to be active for 2 polling cycles
    clear = 0
    while clear < 2 and not stop():
        if a.faults():
            clear = 0
        else:
            clear = clear + 1
        time.sleep(polling_period)
    # start the trigger waiting for an active fault
    a.rec_start()
    # wait for the trigger to be done
    fault = ""
    while not fault and not stop():
        fault = a.faults_short()
    timestamp = datetime.now()
    while not a.commandI("rec.done"):
        if stop():
            a.command("rec.off")
            return (fault, timestamp, [])
    time.sleep(polling_period)
    # get the data
    data = []
    while a.rec_get(data):
        pass
    return (fault, timestamp, data)



def current_profile_callback(a, prog_start_time, ctt):
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
        return current_profile_callback(a, start_time, ctt)

    with open(file, mode='w') as f:
        record([a], [f], frequency, [to_record], interact_callback=callback)


def velocity_profile_callback(a, prog_start_time, vtt, repeat=False):
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
        return velocity_profile_callback(a, start_time, vtt, repeat=repeat)

    with open(file, mode='w') as f:
        record([a], [f], frequency, [to_record], interact_callback=callback)
