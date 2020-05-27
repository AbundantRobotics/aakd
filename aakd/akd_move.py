import time
from .akd_flags import MTCntl, MotionStat


def motiontask_setup(akd, mt_num, pos, vel, acc, dec, absolute=True, next_task=None, dwell_time=0):
    """ This function sets up a motion task """
    akd.cset("mt.num", mt_num)
    akd.cset("mt.p", pos)
    # We currently handle only trapezoidal motion tasks
    mtcntl = MTCntl.MTAccelTrapezoidal
    akd.cset("mt.v", vel)
    akd.cset("mt.acc", acc)
    akd.cset("mt.dec", dec)

    mtcntl |= MTCntl.MTTypeAbsolute if absolute else MTCntl.MTTypeRelative

    if next_task is not None:
        akd.cset("mt.mtnext", next_task)
        mtcntl |= MTCntl.MTExecuteNext
        if dwell_time:
            akd.cset("mt.tnext", dwell_time)
            mtcntl |= MTCntl.MTNextDwell
        else:
            mtcntl |= MTCntl.MTNextDefault
    akd.cset("mt.cntl", mtcntl.value)
    akd.command("mt.set")


def motiontask_completed(akd):
    ms = akd.motion_status()
    done = (ms & MotionStat.MTCompleted) and not (ms & MotionStat.MotionActive)
    if not done:  # It seems that tiny motion task updates will set MTFault but complete fine.
        mserr = ms.is_error()
        if mserr:
            raise Exception(f"Motion Task Failed: {mserr}")
    return done


def motiontask_run(akd, mt_num):
    """ Run the motion task mt_num until completion or error.
    Note, the drive will be enabled and put in position service mode.
    """
    akd.service_mode()
    akd.enable()
    akd.cset("mt.move", mt_num)
    start_time = time.time()
    while not motiontask_completed(akd):
        f = akd.faults(warnings=True)
        if f:
            raise Exception("Drive Faults: " + f)
        if time.time() - start_time > 2:
            print("Position:", akd.commandS("pl.fb"))
            start_time = time.time()
        time.sleep(0.01)
    print("Position:", akd.commandS("pl.fb"))
