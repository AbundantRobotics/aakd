import time
import enum


class MotionStat(enum.Flag):
    """DRV.MOTIONSTAT flags definitions"""

    MotionActive = 2**0
    HomeFound = 2**1
    HomeFinished = 2**2
    HomingActive = 2**3
    HomingError = 2**4
    SlaveElectronicGearing = 2**5
    ElectronicGearing = 2**6
    EStop = 2**7
    EstopError = 2**8
    ServiceMotionActive = 2**9
    MTInvalid = 2**10
    MTCompleted = 2**11
    MTVelocityReached = 2**12
    MTFault = 2**13
    MTPositionCrossed = 2**14
    MTPositionReached = 2**15
    AKDBasicMoveInProgress = 2**16
    AKDBasicMoveCompleted = 2**17
    Reserved1 = 2**18
    Reserved2 = 2**19
    Reserved3 = 2**20
    DriveNearHome = 2**21
    CoggingTeachMove = 2**22

    @classmethod
    def descriptions(cls):
        descriptions_dict = {
            MotionStat.MotionActive          : "Motion task is active (high active)",
            MotionStat.HomeFound             : "Home position found /reference point set (high active)",
            MotionStat.HomeFinished          : "Home routine finished (high active). Bits 1 and 2 both must be set to confirm that the homing process is complete.",
            MotionStat.HomingActive          : "Homing active (high active)",
            MotionStat.HomingError           : "Homing error condition has occurred (high active)*",
            MotionStat.SlaveElectronicGearing: "Slave in electronic gearing mode synchronized (high active). Synchronization can be controlled using GEAR.SYNCWND",
            MotionStat.ElectronicGearing     : "Electronic gearing is active (high active)",
            MotionStat.EStop                 : "Emergency stop procedure in progress (high active)",
            MotionStat.EstopError            : "Emergency stop procedure has an error (high active)",
            MotionStat.ServiceMotionActive   : "Service motion active (high active)",
            MotionStat.MTInvalid             : "A motion task could not be activated /invalid MT (high active)**",
            MotionStat.MTCompleted           : "Bit 11 will be set after the motion task has finished it’s “trajectory” and the actual position is within the motion task target position window (MT.TPOSWND).",
            MotionStat.MTVelocityReached     : "Motion task target velocity has been reached. See also (high active).",
            MotionStat.MTFault               : "Motion task encountered an exception. A motion task exception can happen during a static motion task activation, or during activation of motion task on the fly (when velocity is not zero). The status bit will be reset automatically on successful activation of any motion, or by a command DRV.CLRFAULT.",
            MotionStat.MTPositionCrossed     : "The target position of a motion task has been crossed. This situation occurs for motion  tasks with a change on the fly when triggering the DRV.STOP command just before the reaching the target velocity of the current active motion task. The ramp-down procedure with the motion task deceleration ramp causes the target position to be crossed (high active).",
            MotionStat.MTPositionReached     : "Bit 15 will be set if the actual position is within the motion task target position window (MT.TPOSWND).",
            MotionStat.AKDBasicMoveInProgress: "AKD BASIC trajectory generator is executing a move.",
            MotionStat.AKDBasicMoveCompleted : "AKD BASIC trajectory generator has completed a move.",
            MotionStat.Reserved1             : "Reserved",
            MotionStat.Reserved2             : "Reserved",
            MotionStat.Reserved3             : "Reserved",
            MotionStat.DriveNearHome         : "Drive actual position is within the homing target position window HOME.TPOSWND.",
            MotionStat.CoggingTeachMove      : "Cogging compensation teach move is active (high active).",
        }
        return description_dict

    def __str__(self):
        sl = []
        for flag in MTCntl:
            if self & flag:
                sl.append(f"{flag.name}: {descriptions()[flag]}")
        return '\n'.join(sl)


class MTCntl(enum.Flag):
    """MT.CNTL flags definitions"""

    MTTypeAbsolute = 0b0000
    MTTypeReserved = 0b1000
    MTTypeRelative = 0b0001
    MTTypeRelativePrev = 0b0011
    MTTypeRelativeExternal = 0b0101
    MTTypeRelativeFeedback = 0b0111
    MTExecuteNext = 0x00010
    MTNextDefault = 0b00000 << 5
    MTNextDwell = 0b00001 << 5
    MTNextExternal = 0b00010 << 5
    MTNextDwellExternal = 0b00011 << 5
    MTNextDwellOrExternal = 0b00111 << 5
    MTNextMergeSpeed = 0b10000 << 5
    MTNextMergeAccel = 0b11000 << 5
    MTAccelTrapezoidal = 0b00 << 10
    MTAccelOneOneProfile = 0b01 << 10
    MTAccelProfile = 0b11 << 10
    MTReserved1 = 0x01000
    MTExclusive = 0x02000
    MTInterrupt = 0x04000
    MTReserved2 = 0x08000
    MTVelExternal = 0x10000

    @classmethod
    def descriptions(cls):
        return {
            MTCntl.MTTypeAbsolute: "Absolute. The target position is defined by the MT.P value.",
            MTCntl.MTTypeReserved: "Reserved.",
            MTCntl.MTTypeRelative: "Relative to Command Position. The target position is defined as: Target position = PL.CMD + MT.P",
            MTCntl.MTTypeRelativePrev: "Relative to Previous Target Position. The target position is defined as: Target position = Target position of the last motion task + MT.P",
            MTCntl.MTTypeRelativeExternal: "Relative to External Start Position. The target position is defined as: Target position = External start position + MT.P",
            MTCntl.MTTypeRelativeFeedback: "Relative to Feedback Position. The target position is defined as: Target position = PL.FB + MT.P",
            MTCntl.MTExecuteNext: "If set the next MT is executed.",
            MTCntl.MTNextDefault: "Switches over to next MT after stopping. After an MT ends, the next MT starts immediately.",
            MTCntl.MTNextDwell: "Switches over to next MT after stopping and delay. After an MT ends, the MT following time (MT.TNEXT) elapse in order to start the next MT.",
            MTCntl.MTNextExternal: "Switches over to next MT after stopping and external event. After an MT ends, an external event (such as a high digital input) must occur in order to start the next MT.",
            MTCntl.MTNextDwellExternal: "Switches over to next MT after stopping, delay, and external event. After an MT ends, the MT.TNEXT must elapse and an external event (such as a high digital input) must occur in order to start the next MT.",
            MTCntl.MTNextDwellOrExternal: "Switches over to next MT after stopping, then delay or external event. After an MT ends, the MT.TNEXT must elapse or an external event (such as a high digital input) must occur in order to start the next MT.",
            MTCntl.MTNextMergeSpeed: "Switches over to the next MT at present MT speed (change on the fly). After reaching the target position of an MT, the next MT starts. The drive then accelerates with the adjusted acceleration ramp of this next MT to the target velocity of this next MT. The MT.TNEXT setting is ignored.",
            MTCntl.MTNextMergeAccel: "Switches over to the next MT at next MT speed (change on the fly). When the target position of an MT is reached, the drive has already accelerated with the acceleration ramp of the next MT to the target velocity of the next MT. Thus, the drive begins the next MT at the next MT target velocity. The MT.TNEXT setting is ignored if adjusted.",
            MTCntl.MTAccelTrapezoidal: "Trapezoidal acceleration and deceleration.",
            MTCntl.MTAccelOneOneProfile: "1:1 motion profile table motion task. The drive follows the customer motion profile table without inserting a constant velocity phase between the acceleration and deceleration process. This setting allows the usage of nonsymmetric velocity profiles. The MT.TNUM parameter defines which table to use for the 1:1 profile handling.",
            MTCntl.MTAccelProfile: "Standard motion profile table motion task. The drive accelerates according to the shape of the motion profile table by stepping through the first half of the customer table. Then the drive inserts a constant velocity phase until the brake point is reached. Finally, the drive decelerates by stepping through the second half of the customer profile table. The MT.TNUM parameter defines which table to use for the 1:1 profile handling. This mode allows also a change on the fly between motion tasks (see Table 3 above). See \"AKD Customer Profile Application Note\" on the Kollmorgen web site (www.kollmorgen.com) for additional details.",
            MTCntl.MTReserved1: "Deprecated as of firmware version 01-11-02-000. In previous versions of firmware this bit enabled the feedrate for homing (see HOME.FEEDRATE).",
            MTCntl.MTExclusive: "If set, an attempt to trigger any new motion task will be denied while this motion task is currently running.",
            MTCntl.MTInterrupt: "If this bit is set, the motion task that is supposed to be started cannot be started from velocity 0. The motion can be started if a motion task already running will be interrupted.",
            MTCntl.MTReserved2: "Reserved.",
            MTCntl.MTVelExternal: "The motion task target velocity will be taken from an external source such as an analog input signal (see AIN.MODE for further details)."
        }

    def __str__(self):
        sl = []
        for flag in MTCntl:
            if self & flag:
                sl.append(f"{flag.name}: {descriptions()[flag]}")
        return '\n'.join(sl)


def setup_motiontask(akd, mt_num, pos, vel, acc, dec, absolute=True, next_task=None, dwell_time=0):
    akd.cset("mt.num", mt_num)
    akd.cset("mt.")
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


#TODO setup_servicemode run_motiontask wait_motiontask motionstat_check (and fault, combine in a status check and use in aakd.enable())

# Setting up parameters on all akdns (and storing current parameters)
def akd_drv_setup(all_akdns):
    print("Setting up drive parameter")
    opmode_list = []
    cmdsource_list = []
    for akd in all_akdns:
        a = akd['aakd_obj']
        opmode = a.commandI("drv.opmode")
        cmdsource = a.commandI("drv.cmdsource")
        opmode_list.append(opmode)
        cmdsource_list.append(cmdsource)
        a.cset("drv.opmode", 2)  # Set drive to Position mode
        a.cset("drv.cmdsource", 0)  # Set drive to Service mode
    return opmode_list, cmdsource_list


# Resetting parameters on all akdns
def akd_drv_desetup(all_akdns, opmode_list, cmdsource_list):
    print("Resetting drive parameters")
    for idx, akd in enumerate(all_akdns):
        a = akd['aakd_obj']
        a.cset("drv.opmode", opmode_list[idx])
        a.cset("drv.cmdsource", cmdsource_list[idx])


# Clear Motion Task
def akd_clear_mt(all_akdns):
    print("Clear all existing motion tasks")
    for akd in all_akdns:
        a = akd['aakd_obj']
        a.cset("mt.clear", -1)  # Clear all existing motion tasks


def stop_fct(a):
    last_task_check_val = last_task_dict[a.name]
    current_task_str = a.commandS("mt.params")
    # print('Current task: ' + str(a.name) + ' = ' + current_task_str[0])
    if int(current_task_str[0]) == last_task_check_val:
        motion_active = 0
        print('Stop moving for: ' + a.name)
    else:
        motion_active = 1
    return motion_active


# Start motions for the given group
def akd_start_motion(all_akdns, pos_list, mov_type):
    for idx, akd in enumerate(all_akdns):
        a = akd['aakd_obj']
        start_pos = a.commandF("pl.fb")  # Extract current position
        print('Start moving: ' + str(a.name))
        a.cset("mt.move", 0)
        while stop_fct(a):
            if mov_type == 'absolute':
                target_pos = pos_list[idx]
            elif mov_type == 'relative':
                target_pos = start_pos + pos_list[idx]
            print('Motion still ongoing... Current position: ' + str(a.commandF("pl.fb")) + ' Target: ' + str(target_pos))



# Provide list of akdns that one wishes to move, find which akdc correspond to each AKDN
def akds_move_main(all_akdns, all_akdcs, pos_list, mov_type):
    # Then setup drives and motions task
    akd_create_aakd_obj(all_akdns, all_akdcs)
    akd_check_swls(all_akdns)
    akd_disable(all_akdns)
    akd_clear_mt(all_akdns)
    akd_clear_faults(all_akdns, all_akdcs)
    opmode_list, cmdsource_list = akd_drv_setup(all_akdns)
    akd_mt_setup(all_akdns, pos_list, mov_type)
    # Enable AKD(s) and start motion(s)
    akd_enable(all_akdns)
    akd_start_motion(all_akdns, pos_list, mov_type)
    akd_disable(all_akdns)
    akd_clear_mt(all_akdns)
    akd_drv_desetup(all_akdns, opmode_list, cmdsource_list)


    print('All drives disabled, test over')
