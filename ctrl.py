#! /usr/bin/python3

import argparse
import subprocess
import time
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# this is just to make the output look nice
formatter = logging.Formatter(fmt="%(asctime)s %(name)s.%(levelname)s: %(message)s", datefmt="%Y.%m.%d %H:%M:%S")

# this logs to stdout and I think it is flushed immediately
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)

class FileModifiedHandler(FileSystemEventHandler):
    def __init__(self, path, file_name, callback):
        self.file_name = file_name
        self.callback = callback

        # set observer to watch for changes in the directory
        self.observer = Observer()
        self.observer.schedule(self, path, recursive=False)
        self.observer.start()

    def on_modified(self, event):
        # only act on the change that we're looking for
        if not event.is_directory and event.src_path.endswith(self.file_name):
            self.callback()  # call callback


class BatteryStatus:
    isCharging = False
    level = 0

    def __init__(self, status, value):
        self.isCharging = status
        self.level = value


class Controller:
    config = None
    configPath = ""
    active = False
    section = ""

    def __init__(self, path, section):
        self.configPath = path
        self.section = section
        self.do_refresh()

    def do_refresh(self):
        with open(self.configPath, "r") as fp:
            self.config = json.load(fp)
        self.config = self.config[self.section]
        self.refresh()

    def refresh(self):
        pass

    def set_sleep(self):
        pass

    def do_control(self, force, batteryStatus):
        pass

    def get_config(self, key, defaultValue):
        value = self.config[key]
        if value == "":
            return defaultValue
        return value


class FrameworkManager(Controller):
    controllers = []
    sleep = False
    need_refresh = True
    batteryChargingStatusPath = ""
    batteryFullChargePath = ""
    batteryCurrentChargePath = ""
    batteryStatus = False
    batteryLevel = 0
    force = False

    def __init__(self, configPath):
        if configPath == "":
            logger.info("No config file")
            quit(1)

        Controller.__init__(self, configPath, "manager")
        self.controllers.append(FanController(configPath))
        self.controllers.append(LedController(configPath))
        self.controllers.append(BackLightController(configPath))

        self.refresh()

        FileModifiedHandler("/tmp/", ".fw-ctrl.tmp", self.live_update)

    def refresh(self):
        self.batteryChargingStatusPath = self.get_config(
            "batteryChargingStatusPath", "/sys/class/power_supply/BAT1/status")
        self.batteryFullChargePath = self.get_config(
            "batteryFullChargePath", "/sys/class/power_supply/BAT1/charge_full")
        self.batteryCurrentChargePath = self.get_config(
            "batteryCurrentChargePath", "/sys/class/power_supply/BAT1/charge_now")
        with open(self.batteryFullChargePath, "r") as fb:
            self.lastBatteryFullCharge = int(fb.readline().rstrip("\n"))

    def get_battery_charging_status(self):
        with open(self.batteryChargingStatusPath, "r") as fb:
            currentBatteryStatus = fb.readline().rstrip("\n")
            self.batteryStatus = currentBatteryStatus == "Charging"

        with open(self.batteryCurrentChargePath, "r") as fb:
            currentBatteryCharge = int(fb.readline().rstrip("\n"))
            self.batteryLevel = int(
                round((currentBatteryCharge / self.lastBatteryFullCharge) * 100, 0))

    def live_update(self):
        with open("/tmp/.fw-ctrl.tmp", "r+") as fp:
            value = fp.read()
            fp.seek(0)
            fp.truncate

            if value == "active":
                self.sleep = False
                self.force = True
            elif value == "sleep":
                self.sleep = True
            elif value == "refresh":
                self.need_refresh = True
                self.sleep = False
            else:
                fp.write("unknown command")

    def run(self):
        previousTs = 0
        while True:
            if self.need_refresh:
                logger.info("Refresh start")
                self.refresh()
                for c in self.controllers:
                    c.do_refresh()
                self.need_refresh = False
                self.force = True
                logger.info("Refresh end")

            ts = int(time.time())
            if (ts - previousTs) > 60 :
                logger.info("Force")
                self.force = True
            previousTs = ts

            if self.sleep:
                logger.info("Sleep")
                for c in self.controllers:
                    if c.active:
                        c.set_sleep()
            else:
                self.get_battery_charging_status()
                logger.info(
                    f"Control with battery : {self.batteryStatus} - {self.batteryLevel}")
                for c in self.controllers:
                    if c.active:
                        c.do_control(self.force, BatteryStatus(
                            self.batteryStatus, self.batteryLevel))
                    else:
                        c.set_sleep()
                self.force = False

            time.sleep(1)


class LedController(Controller):
    previousColor = 0
    isBlink = False
    lastBatteryFullCharge = 0
    lastBatteryLevel = 0
    lastBatteryStatus = ""
    batteryChargingColor = "white"
    defaultColor = "white"
    powerLevel1Battery = -1
    powerLevel1Color = ""
    powerLevel1Blink = False
    powerLevel2Battery = -1
    powerLevel2Color = ""
    powerLevel2Blink = False

    def __init__(self, configPath):
        Controller.__init__(self, configPath, "led")

    def refresh(self):
        self.active = self.config["active"]

        self.defaultColor = self.config["defaultColor"]
        self.batteryChargingColor = self.config["chargingColor"]

        self.powerLevel1Battery = self.config["powerLevel1"]["level"]
        self.powerLevel1Color = self.config["powerLevel1"]["color"]
        self.powerLevel1Blink = self.config["powerLevel1"]["blink"]

        self.powerLevel2Battery = self.config["powerLevel2"]["level"]
        self.powerLevel2Color = self.config["powerLevel2"]["color"]
        self.powerLevel2Blink = self.config["powerLevel2"]["blink"]

    def set_color(self, color, force = False):
        if self.previousColor != color or force:
            logger.info(f"Set led color to {color}")
            bashCommand = f"ectool led power {color}"
            r = subprocess.run(bashCommand, stdout=subprocess.PIPE, shell=True)
            if r.returncode != 0:
                quit(1)
            else:
                self.previousColor = color

    def set_sleep(self):
        color = "auto"
        self.set_color(color)

    def do_control(self, force, batteryStatus):
        self.isBlink = False
        color = self.defaultColor
        if batteryStatus.isCharging:
            color = self.batteryChargingColor
        elif batteryStatus.level <= self.powerLevel2Battery:
            color = self.powerLevel2Color
            self.isBlink = self.powerLevel2Blink
        elif batteryStatus.level <= self.powerLevel1Battery:
            color = self.powerLevel1Color
            self.isBlink = self.powerLevel1Blink

        if self.isBlink:
            ts = int(time.time())
            if (ts % 2) == 0:
                color = "off"

        self.set_color(color, force)


class FanController(Controller):
    speed = 0
    temps = [0] * 100
    tempIndex = 0
    switchableFanCurve = False
    lastBatteryStatus = False

    def __init__(self, configPath):
        Controller.__init__(self, configPath, "fan")

    def refresh(self):
        self.speed = 0
        self.temps = [0] * 100
        self.tempIndex = 0
        self.active = self.config["active"]

        strategyOnCharging = self.config["defaultStrategy"]
        self.strategyOnCharging = self.config["strategies"][strategyOnCharging]
        # if the user didnt specify a separate strategy for discharging, use the same strategy as for charging
        logger.info(f"Fan strategy on charging {strategyOnCharging}")
        strategyOnDischarging = self.config["strategyOnDischarging"]
        if strategyOnDischarging == "":
            self.switchableFanCurve = False
            self.strategyOnDischarging = self.strategyOnCharging
        else:
            self.strategyOnDischarging = self.config["strategies"][strategyOnDischarging]
            self.switchableFanCurve = True
            logger.info(f"Fan strategy on discharging {strategyOnDischarging}")
        self.set_strategy(self.strategyOnCharging)

    def set_strategy(self, strategy):
        self.speedCurve = strategy["speedCurve"]
        self.fanSpeedUpdateFrequency = strategy["fanSpeedUpdateFrequency"]
        self.movingAverageInterval = strategy["movingAverageInterval"]
        self.set_speed(self.speedCurve[0]["speed"])
        self.update_temperature()
        self.temps = [self.temps[self.tempIndex]] * 100

    def switch_strategy(self, batteryStatus):
        currentBatteryStatus = batteryStatus.isCharging
        if currentBatteryStatus == self.lastBatteryStatus:
            return   # battery charging status hasnt change - dont switch fan curve
        elif currentBatteryStatus != self.lastBatteryStatus:
            self.lastBatteryStatus = currentBatteryStatus
            if currentBatteryStatus:
                strategy = self.strategyOnCharging
            else:
                strategy = self.strategyOnDischarging
        # load fan curve according to strategy
        self.set_strategy(strategy)

    def set_sleep(self):
        if self.speed != 0:
            logger.info(f"Set auto fan")
            bashCommand = f"ectool autofanctrl"
            r = subprocess.run(bashCommand, stdout=subprocess.PIPE, shell=True)
            if r.returncode != 0:
                quit(1)
            else:
                self.speed = 0

    def set_speed(self, speed, force = False):
        if abs(self.speed - speed) >= 3 or force:
            logger.info(f"Set fan speed to {speed}")
            bashCommand = f"ectool fanduty {speed}"
            r = subprocess.run(bashCommand, stdout=subprocess.PIPE, shell=True)
            if r.returncode != 0:
                quit(1)
            else:
                self.speed = speed

    def adapt_speed(self, force = False):
        currentTemp = self.temps[self.tempIndex]
        currentTemp = min(currentTemp, self.get_moving_average_temperature(
            self.movingAverageInterval))
        minPoint = self.speedCurve[0]
        maxPoint = self.speedCurve[-1]
        for e in self.speedCurve:
            if currentTemp > e["temp"]:
                minPoint = e
            else:
                maxPoint = e
                break
        if minPoint == maxPoint:
            newSpeed = minPoint["speed"]
        else:
            slope = (maxPoint["speed"] - minPoint["speed"]) / \
                (maxPoint["temp"] - minPoint["temp"])
            newSpeed = int(minPoint["speed"] +
                           (currentTemp - minPoint["temp"]) * slope)
        self.set_speed(newSpeed, force)

    def update_temperature(self):
        sumCoreTemps = 0
        sensorsOutput = json.loads(
            subprocess.run(
                "sensors -j",
                stdout=subprocess.PIPE,
                shell=True,
                text=True,
                executable="/bin/bash",
            ).stdout
        )
        # sensors -j does not return the core temperatures at startup
        if "coretemp-isa-0000" not in sensorsOutput.keys():
            return
        cores = 0
        for k, v in sensorsOutput["coretemp-isa-0000"].items():
            if k.startswith("Core "):
                i = int(k.split(" ")[1])
                cores += 1
                sumCoreTemps += float(v[[key for key in v.keys()
                                      if key.endswith("_input")][0]])
        self.tempIndex = (self.tempIndex + 1) % len(self.temps)
        self.temps[self.tempIndex] = sumCoreTemps / cores

    # return mean temperature over a given time interval (in seconds)
    def get_moving_average_temperature(self, timeInterval):
        tempSum = 0
        for i in range(0, timeInterval):
            tempSum += self.temps[self.tempIndex - i]
        return tempSum / timeInterval

    def do_control(self, force, batteryStatus):
        if self.switchableFanCurve:
            self.switch_strategy(batteryStatus.isCharging)
        self.update_temperature()
        # update fan speed every "fanSpeedUpdateFrequency" seconds
        if self.tempIndex % self.fanSpeedUpdateFrequency == 0:
            self.adapt_speed(force)


class BackLightController(Controller):
    illuminanceSensorPath = ""
    currentIlluminance = 0
    backlightPath = ""
    currentBacklight = 0
    sensitivity = 0
    maxPercent = 0
    stepnumber = 0
    backlightMax = 0
    backlightMaxPath = ""
    min = 0
    max = 0
    brsensitivity = 0

    def __init__(self, configPath):
        Controller.__init__(self, configPath, "backlight")

    def refresh(self):
        self.active = self.config["active"]
        
        self.sensitivity = self.config["sensitivity"]
        self.maxPercent = self.config["maxPercent"]
        self.stepnumber = self.config["stepnumber"]
        self.illuminanceSensorPath = self.get_config(
            "sensor", "/sys/bus/iio/devices/iio:device0/in_illuminance_raw")
        self.backlightPath = self.get_config(
            "backlight",  "/sys/class/backlight/intel_backlight/brightness")
        self.backlightMaxPath = self.get_config(
            "backlightMax", "/sys/class/backlight/intel_backlight/max_brightness")

        with open(self.backlightMaxPath, "r") as fb:
            self.backlightMax = int(fb.readline().rstrip("\n"))

        self.min = self.backlightMax / self.sensitivity
        self.brsensitivity = (self.backlightMax - self.min) / self.sensitivity
        self.max = self.backlightMax * self.maxPercent / 100

    def get_illuminance(self):
        with open(self.illuminanceSensorPath, "r") as fb:
            self.currentIlluminance = int(fb.readline().rstrip("\n"))

        with open(self.backlightPath, "r") as fb:
            self.currentBacklight = int(fb.readline().rstrip("\n"))

    def set_brightness(self, brightness):
        logger.info(f"Set back light to {brightness}")
        with open(self.backlightPath, "w") as fp:
            fp.write(f"{int(brightness)}")

    def update_brightness(self):
        target = self.currentIlluminance
        if target > self.max:
            target = self.max
        if target < self.min:
            target = self.min
        step = (target - self.currentBacklight) / self.stepnumber
        up = self.currentBacklight
        if step != 0:
            for c in range(self.stepnumber):
                up = up + step
                self.set_brightness(up)
                time.sleep(1 / self.stepnumber)

    def do_control(self, force, batteryStatus):
        self.get_illuminance()
        if self.currentBacklight > self.currentIlluminance and (self.currentBacklight - self.currentIlluminance) > self.brsensitivity:
            self.update_brightness()
        elif self.currentBacklight < self.currentIlluminance and (self.currentBacklight - self.currentIlluminance) < self.brsensitivity:
            self.update_brightness()


def main():
    parser = argparse.ArgumentParser(
        description="Control Framework's laptop power led, fan and backlight",
    )
    parser.add_argument(
        "new_command",
        nargs="?",
        help="Switches mode of a currently running fw-ctrl instance, commands are sleep, active & refresh",
    )
    parser.add_argument("--config", type=str,
                        help="Path to config file", default="")
    args = parser.parse_args()

    if args.new_command:
        with open("/tmp/.fw-ctrl.tmp", "w") as fp:
            fp.write(args.new_command)
        time.sleep(0.1)
        with open("/tmp/.fw-ctrl.tmp", "r") as fp:
            if fp.read() == "unknown command":
                logger.info("Error: unknown command")
    else:
        manager = FrameworkManager(args.config)
        manager.run()


if __name__ == "__main__":
    main()
