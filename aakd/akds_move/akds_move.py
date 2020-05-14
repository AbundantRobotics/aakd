import time
import enum


class MotionStat(enum.Flag):
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

    _ignore_ = ["motionstat_descriptions"]
    motionstat_descriptions = [
        "Motion task is active (high active)",
        "Home position found /reference point set (high active)",
        "Home routine finished (high active)."
            " Bits 1 and 2 both must be set to confirm that the homing process is complete.",
        "Homing active (high active)",
        "Homing error condition has occurred (high active)*",
        "Slave in electronic gearing mode synchronized (high active)."
            " Synchronization can be controlled using GEAR.SYNCWND",
        "Electronic gearing is active (high active)",
        "Emergency stop procedure in progress (high active)",
        "Emergency stop procedure has an error (high active)",
        "Service motion active (high active)",
        "A motion task could not be activated /invalid MT (high active)**",
        "Bit 11 will be set after the motion task has finished it’s “trajectory” and the actual"
            " position is within the motion task target position window (MT.TPOSWND).",
        "Motion task target velocity has been reached. See also (high active).",
        "Motion task encountered an exception."
            " A motion task exception can happen during a static motion task activation,"
            " or during activation of motion task on the fly (when velocity is not zero)."
            " The status bit will be reset automatically on successful activation of any motion,"
            " or by a command DRV.CLRFAULT.",
        "The target position of a motion task has been crossed."
            " This situation occurs for motion tasks with a change on the fly when triggering"
            " the DRV.STOP command just before the reaching the target velocity of the current"
            " active motion task. The ramp-down procedure with the motion task deceleration ramp"
            " causes the target position to be crossed (high active).",
        "Bit 15 will be set if the actual position is within the motion task"
            " target position window (MT.TPOSWND).",
        "AKD BASIC trajectory generator is executing a move.",
        "AKD BASIC trajectory generator has completed a move.",
        "Reserved",
        "Reserved",
        "Reserved",
        "Drive actual position is within the homing target position window HOME.TPOSWND.",
        "Cogging compensation teach move is active (high active).",
    ]

    def __str__(self):
        s = ""
        for x in range(0, len(motionstat_descriptions)):
            xms = MotionStat(2**x)
            if self & xms:
                s += f"{xms.name} (bit {x}): {motionstat_descriptions[x]}"
        return s






execute_next_task = 16  # [0b10000] see mt.cntl  # Execute next move
execute_next_task_with_dwell = 48  # [0b110000] see mt.cntl  # Execute next move with dwell
do_not_execute_next_task = 0  # [0b00000] see mt.cntl  # Do not execute next move
dwell_time_between_tasks = 100  # [ms]
dwell_time_first_task = 500  # [ms]
last_move_pos_incr = 1  # [deg]
last_task_dict = {}  # Dictionary of last task for each akd



def akd_mt_cfg_low_level(akd, task_num, pos, vel, acc, dec, next_task_flag, dwell_time):
    a = akd['aakd_obj']
    a.cset("mt.num", task_num)
    a.cset("mt.p", pos)
    a.cset("mt.v", vel)
    a.cset("mt.acc", acc)
    a.cset("mt.dec", dec)
    if next_task_flag == 1:
        a.cset("mt.cntl", execute_next_task_with_dwell)
        a.cset("mt.tnext", dwell_time)
        a.cset("mt.mtnext", task_num + 1)
    elif next_task_flag == 0:
        a.cset("mt.cntl", do_not_execute_next_task)
    a.command("mt.set")  # Write the parameters to the Motion Task


def akd_mt_cfg_high_level(akd, position, mov_type):
    vel = akd['vel']
    acc = akd['accdec']
    dec = acc
    dwell_time = dwell_time_between_tasks
    global last_move_pos_incr
    a = akd['aakd_obj']

    start_pos = a.commandF("pl.fb")  # Extract current position
    akd['start_pos'] = start_pos

    task_num = 0
    pos = akd['start_pos']
    next_task_flag = 1
    akd_mt_cfg_low_level(akd, task_num, pos, vel, acc, dec, next_task_flag, dwell_time_first_task)

    task_num = 1
    if mov_type == 'absolute':
        pos = position - last_move_pos_incr
    elif mov_type == 'relative':
        pos = akd['start_pos'] + position - last_move_pos_incr
    next_task_flag = 1
    akd_mt_cfg_low_level(akd, task_num, pos, vel, acc, dec, next_task_flag, dwell_time)

    task_num = 2
    if mov_type == 'absolute':
        pos = position
    elif mov_type == 'relative':
        pos = akd['start_pos'] + position
    next_task_flag = 0
    akd_mt_cfg_low_level(akd, task_num, pos, vel, acc, dec, next_task_flag, dwell_time)

    akd['last_task'] = task_num
    global last_task_dict
    last_task_dict.update([(akd['name'], task_num)])


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


# Setting up motion tasks on all akdns
def akd_mt_setup(all_akdns, pos_list, mov_type):
    print("Setting up motion task(s)")
    for idx, akd in enumerate(all_akdns):
        a = akd['aakd_obj']
        target_pos = pos_list[idx]
        akd_mt_cfg_high_level(akd, target_pos, mov_type)


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


def akd_enable(all_akdns):
    # Enabling all akdns in the group
    print('Enable all akdns')
    start = time.time()
    for akd in all_akdns:
        a = akd['aakd_obj']
        print('Enabling drive: ' + akd['name'])
        a.command("drv.en")  # Enable if not already
        while (not a.commandI("drv.active")):
            print("Waiting on drive to enable...")
            end = time.time()
        # Wait to make sure they have enabled
    time.sleep(1)


# Start motions for the given group
def akd_disable(all_akdns):
    print('Attempting to disable the drives in the group')
    for akd in all_akdns:
        a = akd['aakd_obj']
        a.command("drv.dis")  # Disable if not already
        print('Disabling drive for: ' + a.name)


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


def akds_move(akdn_list_user, pos_list, mov_type):
    # From this list above, retrieve the matching dictionary in the cfg file
    akdn_list = []
    akdc_list = []
    for akdn_name_user in akdn_list_user:
        akdn_dict, akdc_name = retrieve_akdn_dict(akdn_name_user)
        akdn_list.append(akdn_dict)
        akdc_dict = retrieve_akdc_dict(akdc_name)
        if akdc_dict not in akdc_list:
            akdc_list.append(akdc_dict)

    akds_move_main(akdn_list, akdc_list, pos_list, mov_type)


if __name__ == '__main__':
    akdn_list_user = ['akdn_plung', 'akdn_vert']
    pos_list = [200, 200]
    mov_type = 'absolute'
    akds_move(akdn_list_user, pos_list, mov_type)

