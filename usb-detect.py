import json
import os
import re
import sys
import usb.core
import usb.util
import subprocess
from ppk2_api.ppk2_api import PPK2_API
import argparse

parser = argparse.ArgumentParser(prog='usb-detect.py',
                                 description='detect esp and ppk usb devices')

parser.add_argument('--debug', action='store_true')

args=parser.parse_args()

device = usb.core.find(find_all=True, idVendor=0x1915, idProduct=0xc00a)

devs = {
    "ppk": [],
    "esp": {}
}

for d in device:
    bus = "%03i" % d.bus
    address = "%03i" % d.address
    dev = subprocess.check_output(('udevadm', 'info', '-q', 'path', '-n', f'/dev/bus/usb/{bus}/{address}'))
    dev = dev.strip().decode()
    devs['ppk'].append(dev)

if args.debug:
    print("ppklist", devs['ppk'],file=sys.stderr)

serial_devices_to_probe = []
ppks = []
for d in os.listdir('/dev/serial/by-path'):
    dev = subprocess.check_output(('udevadm', 'info', '-q', 'path', '-n', f'/dev/serial/by-path/{d}'))
    dev = dev.strip().decode()

    try:
        for ppk in devs['ppk']:
            if dev.startswith(ppk):
                if args.debug:
                    print(f"{dev} is a ppk {ppk}",file=sys.stderr)
                raise StopIteration
    except StopIteration:
        ppks.append('/dev/serial/by-path/' + d)
        continue

    serial_devices_to_probe.append('/dev/serial/by-path/' + d)

if args.debug:
    print(f"serial devices to probe: {serial_devices_to_probe}",file=sys.stderr)

for ppk_port in ppks:
    ppk = PPK2_API(port=ppk_port)
    ppk.use_ampere_meter()
    ppk.set_source_voltage(3300)
    ppk.toggle_DUT_power("ON")
    if args.debug:
        print(f"ppk {ppk} has vdd {ppk.current_vdd}",file=sys.stderr)

for dev in serial_devices_to_probe:
    chip = None
    mac = None
    description = None
    completed = subprocess.run(('python3', '-m', 'esptool', '-p', dev, 'chip_id'),
                               capture_output=True)
    if completed.returncode == 0:
        if args.debug:
            print(f"probe of {dev} successful",file=sys.stderr)
        lines = completed.stdout.decode().split("\n")
        for line in lines:
            if line.startswith('Detecting chip type... ESP'):
                match = re.match("Detecting chip type...\\s+(.*)", line)
                if match is not None:
                    chip = match.groups()[0]
            if line.startswith("MAC:") and mac is None:
                match = re.match("MAC:\\s+(.*)", line)
                if match is not None:
                    mac = match.groups()[0]
            if line.startswith("BASE MAC:"):
                match = re.match("BASE MAC:\\s+(.*)", line)
                if match is not None:
                    mac = match.groups()[0]
            if line.startswith("Chip is"):
                match = re.match("Chip is\\s+(.*)", line)
                if match is not None:
                    description = match.groups()[0]

        if args.debug:
            print(f"port {dev} has {chip} {mac} {description}", file=sys.stderr)

        devs['esp'][dev]={"chip": chip, "mac": mac, "description":description}

print(json.dumps(devs))

